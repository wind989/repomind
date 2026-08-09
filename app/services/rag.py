import re
from dataclasses import dataclass
from functools import lru_cache
from time import perf_counter
from typing import Protocol

import chromadb
from openai import OpenAI, OpenAIError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.document import Document
from app.models.document_chunk import DocumentChunk


class RagServiceError(Exception):
    pass


@dataclass(frozen=True)
class IndexableChunk:
    chunk_id: int
    document_id: int
    document_title: str
    chunk_index: int
    content: str


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_id: int
    document_id: int
    document_title: str
    chunk_index: int
    content: str
    distance: float


@dataclass(frozen=True)
class KeywordRetrievedChunk:
    chunk_id: int
    document_id: int
    document_title: str
    chunk_index: int
    content: str
    keyword_score: float


@dataclass(frozen=True)
class RankedRetrievedChunk:
    chunk_id: int
    document_id: int
    document_title: str
    chunk_index: int
    content: str
    keyword_rank: int | None
    keyword_score: float | None
    vector_rank: int | None
    vector_distance: float | None
    rrf_score: float
    rerank_score: float
    final_rank: int


@dataclass(frozen=True)
class HybridRetrievalResult:
    candidates: list[RankedRetrievedChunk]
    keyword_latency_ms: int
    vector_latency_ms: int
    fusion_latency_ms: int
    rerank_latency_ms: int


class VectorStore(Protocol):
    def replace_knowledge_base(self, knowledge_base_id: int, chunks: list[IndexableChunk]) -> int: ...

    def query(self, knowledge_base_id: int, question: str, top_k: int) -> list[RetrievedChunk]: ...


class AnswerGenerator(Protocol):
    def generate(self, question: str, evidence: list[RetrievedChunk]) -> str: ...


RRF_K = 60
CHINESE_SEQUENCE_PATTERN = re.compile(r"[\u4e00-\u9fff]+")
WORD_PATTERN = re.compile(r"[a-zA-Z0-9_]{2,}")


def extract_keyword_terms(question: str) -> set[str]:
    normalized_question = question.lower()
    terms = set(WORD_PATTERN.findall(normalized_question))
    for sequence in CHINESE_SEQUENCE_PATTERN.findall(normalized_question):
        if len(sequence) == 1:
            terms.add(sequence)
        else:
            terms.update(sequence[index : index + 2] for index in range(len(sequence) - 1))
    return terms


def keyword_retrieve(
    db: Session,
    knowledge_base_id: int,
    question: str,
    recall_k: int,
) -> list[KeywordRetrievedChunk]:
    terms = extract_keyword_terms(question)
    if not terms:
        return []
    rows = (
        db.query(DocumentChunk, Document)
        .join(Document, DocumentChunk.document_id == Document.id)
        .filter(Document.knowledge_base_id == knowledge_base_id)
        .order_by(Document.id.asc(), DocumentChunk.chunk_index.asc())
        .all()
    )
    matches: list[KeywordRetrievedChunk] = []
    for chunk, document in rows:
        searchable_text = f"{document.title}\n{chunk.content}".lower()
        matched_count = sum(term in searchable_text for term in terms)
        if matched_count:
            matches.append(
                KeywordRetrievedChunk(
                    chunk_id=chunk.id,
                    document_id=document.id,
                    document_title=document.title,
                    chunk_index=chunk.chunk_index,
                    content=chunk.content,
                    keyword_score=matched_count / len(terms),
                )
            )
    return sorted(
        matches,
        key=lambda item: (-item.keyword_score, item.document_id, item.chunk_index),
    )[:recall_k]


def hybrid_retrieve(
    db: Session,
    knowledge_base_id: int,
    question: str,
    vector_store: VectorStore,
    recall_k: int,
) -> HybridRetrievalResult:
    keyword_started_at = perf_counter()
    keyword_results = keyword_retrieve(db, knowledge_base_id, question, recall_k)
    keyword_latency_ms = int((perf_counter() - keyword_started_at) * 1000)

    vector_started_at = perf_counter()
    vector_results = vector_store.query(knowledge_base_id, question, recall_k)
    vector_latency_ms = int((perf_counter() - vector_started_at) * 1000)

    fusion_started_at = perf_counter()
    candidates_by_chunk_id: dict[int, dict] = {}
    for rank, item in enumerate(keyword_results, start=1):
        candidates_by_chunk_id[item.chunk_id] = {
            "chunk_id": item.chunk_id,
            "document_id": item.document_id,
            "document_title": item.document_title,
            "chunk_index": item.chunk_index,
            "content": item.content,
            "keyword_rank": rank,
            "keyword_score": item.keyword_score,
            "vector_rank": None,
            "vector_distance": None,
            "rrf_score": 1 / (RRF_K + rank),
        }
    for rank, item in enumerate(vector_results, start=1):
        candidate = candidates_by_chunk_id.setdefault(
            item.chunk_id,
            {
                "chunk_id": item.chunk_id,
                "document_id": item.document_id,
                "document_title": item.document_title,
                "chunk_index": item.chunk_index,
                "content": item.content,
                "keyword_rank": None,
                "keyword_score": None,
                "vector_rank": None,
                "vector_distance": None,
                "rrf_score": 0.0,
            },
        )
        candidate["vector_rank"] = rank
        candidate["vector_distance"] = item.distance
        candidate["rrf_score"] += 1 / (RRF_K + rank)
    fused_candidates = list(candidates_by_chunk_id.values())
    fusion_latency_ms = int((perf_counter() - fusion_started_at) * 1000)

    rerank_started_at = perf_counter()
    for candidate in fused_candidates:
        keyword_score = candidate["keyword_score"] or 0.0
        vector_similarity = (
            1 / (1 + candidate["vector_distance"])
            if candidate["vector_distance"] is not None
            else 0.0
        )
        candidate["rerank_score"] = candidate["rrf_score"] * 1000 + keyword_score * 10 + vector_similarity
    fused_candidates.sort(
        key=lambda item: (
            -item["rerank_score"],
            -item["rrf_score"],
            item["document_id"],
            item["chunk_index"],
        )
    )
    candidates = [
        RankedRetrievedChunk(final_rank=rank, **candidate)
        for rank, candidate in enumerate(fused_candidates, start=1)
    ]
    rerank_latency_ms = int((perf_counter() - rerank_started_at) * 1000)

    return HybridRetrievalResult(
        candidates=candidates,
        keyword_latency_ms=keyword_latency_ms,
        vector_latency_ms=vector_latency_ms,
        fusion_latency_ms=fusion_latency_ms,
        rerank_latency_ms=rerank_latency_ms,
    )


def candidates_to_evidence(candidates: list[RankedRetrievedChunk]) -> list[RetrievedChunk]:
    return [
        RetrievedChunk(
            chunk_id=item.chunk_id,
            document_id=item.document_id,
            document_title=item.document_title,
            chunk_index=item.chunk_index,
            content=item.content,
            distance=item.vector_distance if item.vector_distance is not None else 0.0,
        )
        for item in candidates
    ]


class ChromaVectorStore:
    collection_name = "repomind_chunks"

    def __init__(self) -> None:
        settings = get_settings()
        settings.chroma_path.mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(path=str(settings.chroma_path))
        self.collection = self.client.get_or_create_collection(name=self.collection_name)

    def replace_knowledge_base(self, knowledge_base_id: int, chunks: list[IndexableChunk]) -> int:
        self.collection.delete(where={"knowledge_base_id": knowledge_base_id})
        if not chunks:
            return 0
        self.collection.upsert(
            ids=[str(chunk.chunk_id) for chunk in chunks],
            documents=[chunk.content for chunk in chunks],
            metadatas=[
                {
                    "knowledge_base_id": knowledge_base_id,
                    "document_id": chunk.document_id,
                    "document_title": chunk.document_title,
                    "chunk_index": chunk.chunk_index,
                }
                for chunk in chunks
            ],
        )
        return len(chunks)

    def query(self, knowledge_base_id: int, question: str, top_k: int) -> list[RetrievedChunk]:
        available = self.collection.get(where={"knowledge_base_id": knowledge_base_id}, include=[])
        available_count = len(available.get("ids", []))
        if available_count == 0:
            return []
        results = self.collection.query(
            query_texts=[question],
            n_results=min(top_k, available_count),
            where={"knowledge_base_id": knowledge_base_id},
            include=["documents", "metadatas", "distances"],
        )
        identifiers = results.get("ids", [[]])[0] or []
        documents = results.get("documents", [[]])[0] or []
        metadatas = results.get("metadatas", [[]])[0] or []
        distances = results.get("distances", [[]])[0] or []
        return [
            RetrievedChunk(
                chunk_id=int(chunk_id),
                document_id=int(metadata["document_id"]),
                document_title=str(metadata["document_title"]),
                chunk_index=int(metadata["chunk_index"]),
                content=str(content),
                distance=float(distance),
            )
            for chunk_id, content, metadata, distance in zip(identifiers, documents, metadatas, distances)
        ]


class DeepSeekAnswerGenerator:
    def __init__(self) -> None:
        settings = get_settings()
        if not settings.deepseek_api_key:
            raise RagServiceError("DEEPSEEK_API_KEY 未配置")
        self.model = settings.deepseek_model
        self.client = OpenAI(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
        )

    def generate(self, question: str, evidence: list[RetrievedChunk]) -> str:
        context = "\n\n".join(
            f"[证据 {rank}] 文档：{chunk.document_title}；片段：{chunk.chunk_index}\n{chunk.content}"
            for rank, chunk in enumerate(evidence, start=1)
        )
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "你是 RepoMind 的项目文档问答助手。只能依据用户提供的证据回答；"
                            "证据不足时必须明确说‘资料不足，无法确认’，不能补造事实。"
                        ),
                    },
                    {
                        "role": "user",
                        "content": f"问题：{question}\n\n已检索到的资料：\n{context}\n\n请基于资料简洁回答。",
                    },
                ],
                max_tokens=800,
                extra_body={"thinking": {"type": "disabled"}},
            )
        except OpenAIError as exc:
            raise RagServiceError("DeepSeek 调用失败，请检查密钥、网络和账户状态") from exc
        answer = (response.choices[0].message.content or "").strip()
        if not answer:
            raise RagServiceError("DeepSeek 未返回可用回答")
        return answer


@lru_cache
def get_vector_store() -> ChromaVectorStore:
    return ChromaVectorStore()


def get_answer_generator() -> DeepSeekAnswerGenerator:
    return DeepSeekAnswerGenerator()


def clear_knowledge_base_index(knowledge_base_id: int, vector_store: VectorStore | None = None) -> None:
    (vector_store or get_vector_store()).replace_knowledge_base(knowledge_base_id, [])


def measure_answer_generation(
    generator: AnswerGenerator,
    question: str,
    evidence: list[RetrievedChunk],
) -> tuple[str, int]:
    started_at = perf_counter()
    answer = generator.generate(question, evidence)
    latency_ms = int((perf_counter() - started_at) * 1000)
    return answer, latency_ms
