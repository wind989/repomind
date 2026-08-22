"""Run retrieval and Ragas document-context evaluation without calling an LLM."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db.session import get_session_factory
from app.services.evaluation import EvaluationCase, evaluate_retrieval_cases
from app.services.rag import get_vector_store


def load_cases(path: Path) -> tuple[str, int, list[EvaluationCase]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    dataset_name = str(payload["dataset_name"]).strip()
    recall_k = int(payload.get("recall_k", 8))
    if not dataset_name:
        raise ValueError("dataset_name 不能为空")
    if not 1 <= recall_k <= 20:
        raise ValueError("recall_k 必须在 1 到 20 之间")
    cases = [
        EvaluationCase(
            case_key=str(item["case_key"]).strip(),
            knowledge_base_id=int(item["knowledge_base_id"]),
            question=str(item["question"]).strip(),
            expected_document_title=str(item["expected_document_title"]).strip(),
        )
        for item in payload["cases"]
    ]
    if any(not all((case.case_key, case.question, case.expected_document_title)) for case in cases):
        raise ValueError("每条评测用例都必须填写 case_key、question 和 expected_document_title")
    return dataset_name, recall_k, cases


def main() -> None:
    parser = argparse.ArgumentParser(description="运行 RepoMind 检索与 Ragas 上下文评测题集")
    parser.add_argument("--cases", type=Path, required=True, help="人工标注题集 JSON 文件")
    arguments = parser.parse_args()

    dataset_name, recall_k, cases = load_cases(arguments.cases)
    with get_session_factory()() as db:
        evaluation_run = evaluate_retrieval_cases(
            db,
            cases,
            dataset_name,
            get_vector_store(),
            recall_k=recall_k,
        )
        db.add(evaluation_run)
        db.commit()
        db.refresh(evaluation_run)
        summary = {
            "evaluation_run_id": evaluation_run.id,
            "dataset_name": evaluation_run.dataset_name,
            "total_cases": evaluation_run.total_cases,
            "top1_hit_count": evaluation_run.top1_hit_count,
            "recall_hit_count": evaluation_run.recall_hit_count,
            "mrr": evaluation_run.mrr,
            "ragas_context_precision": evaluation_run.ragas_context_precision,
            "ragas_context_recall": evaluation_run.ragas_context_recall,
        }

    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
