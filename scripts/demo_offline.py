"""Run an offline, reproducible RepoMind API demonstration.

The selected tests use an in-memory SQLite database plus fake vector and answer
services. They do not use MySQL, DeepSeek, network access, or a real API key.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    command = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "-s",
        "tests/test_rag.py::test_index_ask_and_read_retrieval_logs",
        "tests/test_feedback.py::test_answer_feedback_can_be_created_updated_and_read",
    ]
    return subprocess.run(command, cwd=PROJECT_ROOT, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
