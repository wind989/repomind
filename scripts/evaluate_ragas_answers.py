"""Run opt-in Ragas answer-quality metrics on completed RAG interactions.

This script intentionally requires ``--allow-model-calls``.  The default
retrieval evaluation remains deterministic and model-free for local runs and
CI.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.logging import redact_secrets
from app.services.ragas_answer_evaluation import (
    AnswerEvaluationSample,
    build_chroma_evaluator_embeddings,
    build_deepseek_evaluator_llm,
    evaluate_answer_quality,
)


def load_answer_samples(path: Path) -> tuple[str, list[AnswerEvaluationSample]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"无法读取回答评测题集：{path}") from exc

    if not isinstance(payload, dict):
        raise ValueError("回答评测文件必须是 JSON 对象")
    dataset_name = str(payload.get("dataset_name") or path.stem).strip()
    raw_samples = payload.get("samples")
    if not dataset_name or not isinstance(raw_samples, list) or not raw_samples:
        raise ValueError("回答评测文件必须包含非空 dataset_name 和 samples")

    samples: list[AnswerEvaluationSample] = []
    for index, raw_sample in enumerate(raw_samples, start=1):
        if not isinstance(raw_sample, dict):
            raise ValueError(f"第 {index} 道回答评测题必须是对象")
        contexts = raw_sample.get("retrieved_contexts")
        if not isinstance(contexts, list) or not contexts or not all(
            isinstance(context, str) and context.strip() for context in contexts
        ):
            raise ValueError(f"第 {index} 道题必须包含非空 retrieved_contexts")
        user_input = _required_text(raw_sample, ("user_input", "question"), index)
        response = _required_text(raw_sample, ("response", "answer"), index)
        reference = _optional_text(raw_sample, ("reference", "reference_answer"), index)
        samples.append(
            AnswerEvaluationSample(
                case_key=str(raw_sample.get("case_key") or f"case-{index}"),
                user_input=user_input,
                retrieved_contexts=[context.strip() for context in contexts],
                response=response,
                reference=reference,
            )
        )
    return dataset_name, samples


def main() -> None:
    parser = argparse.ArgumentParser(description="运行 RepoMind 的 Ragas 回答质量评测")
    parser.add_argument("--cases", type=Path, required=True, help="回答评测题集 JSON 文件")
    parser.add_argument(
        "--allow-model-calls",
        action="store_true",
        help="明确允许调用 DeepSeek 作为 Ragas 评测模型",
    )
    parser.add_argument(
        "--answer-relevancy",
        action="store_true",
        help="额外评测 Answer Relevancy（会初始化 Chroma 本地向量模型）",
    )
    parser.add_argument(
        "--factual-correctness",
        action="store_true",
        help="额外评测 Factual Correctness（每题必须有 reference）",
    )
    arguments = parser.parse_args()

    if not arguments.allow_model_calls:
        parser.error("回答质量评测会调用模型；请明确追加 --allow-model-calls")

    try:
        dataset_name, samples = load_answer_samples(arguments.cases)
        evaluator_llm = build_deepseek_evaluator_llm()
        evaluator_embeddings = (
            build_chroma_evaluator_embeddings() if arguments.answer_relevancy else None
        )
        evaluation = evaluate_answer_quality(
            samples,
            evaluator_llm=evaluator_llm,
            evaluator_embeddings=evaluator_embeddings,
            include_answer_relevancy=arguments.answer_relevancy,
            include_factual_correctness=arguments.factual_correctness,
        )
    except Exception as exc:
        raise SystemExit(f"回答质量评测失败：{redact_secrets(str(exc))}") from exc

    cases: list[dict[str, Any]] = []
    for index, sample in enumerate(samples):
        item: dict[str, Any] = {
            "case_key": sample.case_key,
            "faithfulness": evaluation.faithfulness_scores[index],
        }
        if evaluation.answer_relevancy_scores is not None:
            item["answer_relevancy"] = evaluation.answer_relevancy_scores[index]
        if evaluation.factual_correctness_scores is not None:
            item["factual_correctness"] = evaluation.factual_correctness_scores[index]
        cases.append(item)

    print(
        json.dumps(
            {
                "dataset_name": dataset_name,
                "total_cases": len(samples),
                "faithfulness": evaluation.average_faithfulness,
                "answer_relevancy": evaluation.average_answer_relevancy,
                "factual_correctness": evaluation.average_factual_correctness,
                "cases": cases,
            },
            ensure_ascii=False,
        )
    )


def _required_text(payload: dict[str, Any], keys: tuple[str, ...], index: int) -> str:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    raise ValueError(f"第 {index} 道题缺少非空 {'/'.join(keys)}")


def _optional_text(payload: dict[str, Any], keys: tuple[str, ...], index: int) -> str | None:
    for key in keys:
        if key not in payload or payload[key] is None:
            continue
        if isinstance(payload[key], str) and payload[key].strip():
            return payload[key].strip()
        raise ValueError(f"第 {index} 道题的 {key} 必须是字符串")
    return None


if __name__ == "__main__":
    main()
