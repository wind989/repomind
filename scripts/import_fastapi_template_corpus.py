"""Import a fixed, public FastAPI template document corpus through RepoMind's API.

The source documents remain in the separately cloned upstream repository. This
script records every upstream path and fixed commit URL on the imported records.
It does not call an LLM.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import httpx


DEFAULT_COMMIT = "75c388ba1cd60f39b43dd63a73978bae8c69cb87"
UPSTREAM = "https://github.com/fastapi/full-stack-fastapi-template"
DOCUMENTS = (
    ("README.md", "FastAPI 模板 / README.md", "README"),
    ("backend/README.md", "FastAPI 模板 / backend/README.md", "README"),
    ("development.md", "FastAPI 模板 / development.md", "OTHER"),
    ("deployment.md", "FastAPI 模板 / deployment.md", "DEPLOYMENT"),
    ("CONTRIBUTING.md", "FastAPI 模板 / CONTRIBUTING.md", "OTHER"),
    ("release-notes.md", "FastAPI 模板 / release-notes.md", "OTHER"),
    ("frontend/README.md", "FastAPI 模板 / frontend/README.md", "README"),
)


def cases_for(knowledge_base_id: int) -> dict:
    root = "FastAPI 模板 / README.md"
    backend = "FastAPI 模板 / backend/README.md"
    development = "FastAPI 模板 / development.md"
    deployment = "FastAPI 模板 / deployment.md"
    release_notes = "FastAPI 模板 / release-notes.md"
    return {
        "dataset_name": "FastAPI Full Stack Template public-docs evaluation (MIT)",
        "recall_k": 8,
        "cases": [
            {
                "case_key": "stack-backend-orm-database",
                "knowledge_base_id": knowledge_base_id,
                "question": "Which technologies does the template use for the backend API, ORM, and database?",
                "expected_document_title": root,
            },
            {
                "case_key": "deployment-secrets",
                "knowledge_base_id": knowledge_base_id,
                "question": "Which environment values must be changed before deployment?",
                "expected_document_title": root,
            },
            {
                "case_key": "generate-secret-key",
                "knowledge_base_id": knowledge_base_id,
                "question": "What Python command generates a secure secret key?",
                "expected_document_title": root,
            },
            {
                "case_key": "copier-create-project",
                "knowledge_base_id": knowledge_base_id,
                "question": "How can Copier create a new project from the template?",
                "expected_document_title": root,
            },
            {
                "case_key": "backend-requirements",
                "knowledge_base_id": knowledge_base_id,
                "question": "What tools are required for backend development?",
                "expected_document_title": backend,
            },
            {
                "case_key": "backend-dependency-manager",
                "knowledge_base_id": knowledge_base_id,
                "question": "Which tool manages the backend Python dependencies?",
                "expected_document_title": backend,
            },
            {
                "case_key": "backend-code-locations",
                "knowledge_base_id": knowledge_base_id,
                "question": "Where should models, API endpoints, and CRUD utilities be modified?",
                "expected_document_title": backend,
            },
            {
                "case_key": "backend-test-command",
                "knowledge_base_id": knowledge_base_id,
                "question": "How are the backend tests run?",
                "expected_document_title": backend,
            },
            {
                "case_key": "alembic-upgrade",
                "knowledge_base_id": knowledge_base_id,
                "question": "What Alembic command applies migrations to the database?",
                "expected_document_title": backend,
            },
            {
                "case_key": "start-local-stack",
                "knowledge_base_id": knowledge_base_id,
                "question": "Which command starts the local Docker Compose stack?",
                "expected_document_title": development,
            },
            {
                "case_key": "local-api-docs-url",
                "knowledge_base_id": knowledge_base_id,
                "question": "Where is the local Swagger UI available?",
                "expected_document_title": development,
            },
            {
                "case_key": "public-env-and-ci",
                "knowledge_base_id": knowledge_base_id,
                "question": "How should a public project handle the .env file in CI or deployment?",
                "expected_document_title": development,
            },
            {
                "case_key": "remote-server-preparation",
                "knowledge_base_id": knowledge_base_id,
                "question": "What needs to be prepared on a remote server before deployment?",
                "expected_document_title": deployment,
            },
            {
                "case_key": "traefik-network",
                "knowledge_base_id": knowledge_base_id,
                "question": "What public Docker network name does the Traefik proxy expect?",
                "expected_document_title": deployment,
            },
            {
                "case_key": "release-fastapi-entrypoint",
                "knowledge_base_id": knowledge_base_id,
                "question": "Which latest release feature added a FastAPI entrypoint?",
                "expected_document_title": release_notes,
            },
        ],
    }


def wait_for_task(client: httpx.Client, task_id: int) -> None:
    for _ in range(100):
        response = client.get(f"/document-processing-tasks/{task_id}")
        response.raise_for_status()
        task = response.json()
        if task["status"] == "completed":
            return
        if task["status"] == "failed":
            raise RuntimeError(f"Document task {task_id} failed: {task['error_message']}")
        time.sleep(0.2)
    raise TimeoutError(f"Document task {task_id} did not finish in time")


def main() -> None:
    parser = argparse.ArgumentParser(description="Import fixed FastAPI template public documentation")
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--commit", default=DEFAULT_COMMIT)
    parser.add_argument("--cases-output", type=Path, required=True)
    arguments = parser.parse_args()

    source_dir = arguments.source_dir.resolve()
    missing = [path for path, _, _ in DOCUMENTS if not (source_dir / path).is_file()]
    if missing:
        raise FileNotFoundError(f"Missing source documents: {', '.join(missing)}")

    knowledge_base_name = f"FastAPI Full Stack Template public docs ({arguments.commit[:12]})"
    description = "Public MIT-licensed documentation, imported from a fixed upstream commit for RepoMind evaluation."
    with httpx.Client(base_url=arguments.base_url.rstrip("/"), timeout=60.0) as client:
        response = client.post(
            "/knowledge-bases",
            json={"name": knowledge_base_name, "description": description},
        )
        response.raise_for_status()
        knowledge_base_id = response.json()["id"]

        imported = []
        for relative_path, title, source_type in DOCUMENTS:
            source_url = f"{UPSTREAM}/blob/{arguments.commit}/{relative_path}"
            response = client.post(
                "/documents",
                json={
                    "knowledge_base_id": knowledge_base_id,
                    "title": title,
                    "source_type": source_type,
                    "source_url": source_url,
                    "content_summary": "Public FastAPI template documentation imported for retrieval evaluation.",
                },
            )
            response.raise_for_status()
            document_id = response.json()["id"]
            file_path = source_dir / relative_path
            with file_path.open("rb") as handle:
                response = client.post(
                    f"/documents/{document_id}/upload",
                    files={"file": (file_path.name, handle, "text/markdown")},
                )
            response.raise_for_status()
            wait_for_task(client, response.json()["id"])
            imported.append({"id": document_id, "title": title, "source_path": relative_path})

        response = client.post(f"/knowledge-bases/{knowledge_base_id}/index")
        response.raise_for_status()
        index_result = response.json()

    arguments.cases_output.parent.mkdir(parents=True, exist_ok=True)
    arguments.cases_output.write_text(
        json.dumps(cases_for(knowledge_base_id), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "knowledge_base_id": knowledge_base_id,
                "documents": imported,
                "indexed_chunk_count": index_result["indexed_chunk_count"],
                "cases_output": str(arguments.cases_output),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
