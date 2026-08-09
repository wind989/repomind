from collections.abc import Generator
import asyncio
from typing import Any

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models import AnswerCitation, ChatMessage, Document, KnowledgeBase, RetrievalCandidate, RetrievalLog, User  # noqa: F401
from app.services.auth import get_current_user
from app.services.rag import IndexableChunk, RetrievedChunk
from app.services.document_processing import process_document_task

test_engine = create_engine(
    "sqlite+pysqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


class ApiClient:
    """Use HTTPX directly while keeping synchronous pytest test functions readable."""

    def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        return asyncio.run(self._request(method, url, **kwargs))

    def get(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("POST", url, **kwargs)

    def put(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("PUT", url, **kwargs)

    def delete(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("DELETE", url, **kwargs)

    @staticmethod
    async def _request(method: str, url: str, **kwargs: Any) -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.request(method, url, **kwargs)


class FakeVectorStore:
    def __init__(self) -> None:
        self._chunks_by_knowledge_base: dict[int, list[IndexableChunk]] = {}

    def replace_knowledge_base(self, knowledge_base_id: int, chunks: list[IndexableChunk]) -> int:
        self._chunks_by_knowledge_base[knowledge_base_id] = list(chunks)
        return len(chunks)

    def query(self, knowledge_base_id: int, question: str, top_k: int) -> list[RetrievedChunk]:
        return [
            RetrievedChunk(
                chunk_id=chunk.chunk_id,
                document_id=chunk.document_id,
                document_title=chunk.document_title,
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                distance=0.1 + index / 100,
            )
            for index, chunk in enumerate(self._chunks_by_knowledge_base.get(knowledge_base_id, [])[:top_k])
        ]


class FakeAnswerGenerator:
    def generate(self, question: str, evidence: list[RetrievedChunk]) -> str:
        return f"根据《{evidence[0].document_title}》：{evidence[0].content[:80]}"


def override_get_db() -> Generator[Session, None, None]:
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def override_current_user() -> User:
    return User(id=1, username="test-admin", password_hash="unused", is_active=True, is_admin=True)


@pytest.fixture()
def client() -> Generator[ApiClient, None, None]:
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_current_user
    app.state.document_processing_runner = lambda task_id: process_document_task(task_id, TestingSessionLocal)
    app.state.vector_store = FakeVectorStore()
    app.state.answer_generator = FakeAnswerGenerator()
    app.state.readiness_probe = lambda: None
    yield ApiClient()
    app.dependency_overrides.clear()
    del app.state.document_processing_runner
    del app.state.vector_store
    del app.state.answer_generator
    del app.state.readiness_probe


@pytest.fixture()
def test_db() -> Generator[Session, None, None]:
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
