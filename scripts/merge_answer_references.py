"""Merge human-reviewed reference answers into a generated answer dataset."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def main() -> None:
    parser = argparse.ArgumentParser(description="合并人工参考答案到回答评测题集")
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--references", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()

    cases_payload = _load_object(arguments.cases, "回答题集")
    references = _load_object(arguments.references, "参考答案")
    samples = cases_payload.get("samples")
    if not isinstance(samples, list) or not samples:
        raise ValueError("回答题集必须包含非空 samples")

    missing: list[str] = []
    for sample in samples:
        if not isinstance(sample, dict):
            raise ValueError("回答题集中的 sample 必须是对象")
        case_key = str(sample.get("case_key") or "")
        reference = references.get(case_key)
        if not isinstance(reference, str) or not reference.strip():
            missing.append(case_key or "<missing-case-key>")
            continue
        sample["reference"] = reference.strip()
    if missing:
        raise ValueError(f"缺少人工参考答案：{', '.join(missing)}")

    cases_payload["source"] = "Generated from real RepoMind /ask interactions; references reviewed against the public source documents."
    arguments.output.write_text(
        json.dumps(cases_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": "ok", "total_cases": len(samples), "output": str(arguments.output)}, ensure_ascii=False))


def _load_object(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"无法读取{label}：{path}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{label}必须是 JSON 对象")
    return payload


if __name__ == "__main__":
    main()
