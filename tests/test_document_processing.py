def create_document(client) -> int:
    knowledge_base = client.post("/knowledge-bases", json={"name": "文档处理测试知识库"})
    assert knowledge_base.status_code == 201

    document = client.post(
        "/documents",
        json={
            "knowledge_base_id": knowledge_base.json()["id"],
            "title": "订单接口说明",
            "source_type": "README",
        },
    )
    assert document.status_code == 201
    return document.json()["id"]


def test_upload_markdown_creates_completed_task_and_chunks(client) -> None:
    document_id = create_document(client)
    markdown = "# 订单接口\n\n" + ("创建订单需要商品编号、数量和收货地址。\n" * 180)

    uploaded = client.post(
        f"/documents/{document_id}/upload",
        files={"file": ("orders.md", markdown.encode("utf-8"), "text/markdown")},
    )
    assert uploaded.status_code == 202
    task_id = uploaded.json()["id"]

    task = client.get(f"/document-processing-tasks/{task_id}")
    assert task.status_code == 200
    assert task.json()["status"] == "completed"
    assert task.json()["operation"] == "upload"

    document = client.get(f"/documents/{document_id}")
    assert document.status_code == 200
    assert document.json()["processing_status"] == "completed"
    assert document.json()["original_filename"] == "orders.md"

    chunks = client.get(f"/documents/{document_id}/chunks")
    assert chunks.status_code == 200
    assert len(chunks.json()) >= 2
    assert chunks.json()[0]["chunk_index"] == 0
    assert "创建订单" in chunks.json()[0]["content"]

    reprocessed = client.post(f"/documents/{document_id}/reprocess")
    assert reprocessed.status_code == 202
    reprocess_task = client.get(f"/document-processing-tasks/{reprocessed.json()['id']}")
    assert reprocess_task.json()["status"] == "completed"

    assert client.delete(f"/documents/{document_id}").status_code == 204


def test_document_processing_rejects_invalid_upload_and_missing_file(client) -> None:
    document_id = create_document(client)

    missing_file = client.post(f"/documents/{document_id}/reprocess")
    assert missing_file.status_code == 409
    assert missing_file.json()["detail"] == "文档尚未上传文件，无法重新处理"

    unsupported_type = client.post(
        f"/documents/{document_id}/upload",
        files={"file": ("archive.exe", b"not a document", "application/octet-stream")},
    )
    assert unsupported_type.status_code == 422
    assert "暂只支持" in unsupported_type.json()["detail"]
