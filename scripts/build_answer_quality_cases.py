"""Build answer-quality cases from real RepoMind /ask interactions.

The script reads a retrieval question set, calls the protected RepoMind API,
and stores the actual cited contexts and generated answers.  References are
deliberately supplied separately by a human so that answer evaluation does
not compare a model answer with a model-generated reference.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import httpx
from dotenv import dotenv_values

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def main() -> None:
    parser = argparse.ArgumentParser(description="从真实 /ask 交互生成回答评测题集")
    parser.add_argument("--retrieval-cases", type=Path, required=True, help="已有检索题集 JSON")
    parser.add_argument("--output", type=Path, required=True, help="回答题集输出 JSON")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument(
        "--knowledge-base-id",
        type=int,
        help="覆盖检索题集中的知识库 ID（例如重新导入公开语料后）",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=Path(".env"),
        help="包含 BOOTSTRAP_ADMIN_USERNAME/PASSWORD 的本地环境文件（不会上传或打印）",
    )
    arguments = parser.parse_args()

    retrieval_payload = _load_json(arguments.retrieval_cases, "检索题集")
    raw_cases = retrieval_payload.get("cases")
    if not isinstance(raw_cases, list) or not raw_cases:
        raise ValueError("检索题集必须包含非空 cases")

    env = dotenv_values(arguments.env_file)
    username = str(env.get("BOOTSTRAP_ADMIN_USERNAME") or "").strip()
    password = str(env.get("BOOTSTRAP_ADMIN_PASSWORD") or "").strip()
    if not username or not password:
        raise ValueError(
            "请在 --env-file 中配置 BOOTSTRAP_ADMIN_USERNAME 和 BOOTSTRAP_ADMIN_PASSWORD"
        )

    generated_cases: list[dict[str, Any]] = []
    with httpx.Client(base_url=arguments.base_url.rstrip("/"), timeout=180.0) as client:
        token_response = client.post(
            "/auth/token",
            data={"username": username, "password": password},
        )
        token_response.raise_for_status()
        client.headers.update({"Authorization": f"Bearer {token_response.json()['access_token']}"})

        for index, raw_case in enumerate(raw_cases, start=1):
            if not isinstance(raw_case, dict):
                raise ValueError(f"第 {index} 道检索题必须是对象")
            knowledge_base_id = arguments.knowledge_base_id or raw_case.get("knowledge_base_id")
            question = raw_case.get("question")
            if not isinstance(knowledge_base_id, int) or not isinstance(question, str) or not question.strip():
                raise ValueError(f"第 {index} 道检索题缺少 knowledge_base_id 或 question")

            response = client.post(
                f"/knowledge-bases/{knowledge_base_id}/ask",
                json={
                    "question": question.strip(),
                    "top_k": int(raw_case.get("top_k") or 3),
                    "recall_k": int(raw_case.get("recall_k") or retrieval_payload.get("recall_k") or 8),
                },
            )
            response.raise_for_status()
            result = response.json()
            citations = result.get("citations")
            if not isinstance(citations, list) or not citations:
                raise ValueError(f"第 {index} 道题没有返回引用上下文")

            generated_cases.append(
                {
                    "case_key": str(raw_case.get("case_key") or f"case-{index}"),
                    "user_input": question.strip(),
                    "retrieved_contexts": [
                        str(citation["content_excerpt"]).strip()
                        for citation in citations
                        if isinstance(citation, dict) and str(citation.get("content_excerpt") or "").strip()
                    ],
                    "response": str(result.get("answer") or "").strip(),
                    "reference": None,
                }
            )

    if any(not case["retrieved_contexts"] or not case["response"] for case in generated_cases):
        raise ValueError("至少有一道题缺少检索上下文或回答")

    output_payload = {
        "dataset_name": "FastAPI Full Stack Template public-docs answer evaluation",
        "source": "Generated from real RepoMind /ask interactions; references require human review.",
        "samples": generated_cases,
    }
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(
        json.dumps(output_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {"status": "ok", "total_cases": len(generated_cases), "output": str(arguments.output)},
            ensure_ascii=False,
        )
    )


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"无法读取{label}：{path}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{label}必须是 JSON 对象")
    return payload


if __name__ == "__main__":
    main()
