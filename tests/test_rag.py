def create_indexed_knowledge_base(client) -> tuple[int, int]:
    knowledge_base = client.post("/knowledge-bases", json={"name": "RAG 测试知识库"})
    assert knowledge_base.status_code == 201
    knowledge_base_id = knowledge_base.json()["id"]

    document = client.post(
        "/documents",
        json={
            "knowledge_base_id": knowledge_base_id,
            "title": "订单服务接口说明",
            "source_type": "README",
        },
    )
    assert document.status_code == 201
    document_id = document.json()["id"]
    upload = client.post(
        f"/documents/{document_id}/upload",
        files={
            "file": (
                "orders.md",
                "# 创建订单\n创建订单需要商品编号、数量和收货地址。\n",
                "text/markdown",
            )
        },
    )
    assert upload.status_code == 202
    return knowledge_base_id, document_id


def test_index_ask_and_read_retrieval_logs(client) -> None:
    knowledge_base_id, document_id = create_indexed_knowledge_base(client)

    before_index = client.post(
        f"/knowledge-bases/{knowledge_base_id}/ask",
        json={"question": "创建订单需要什么参数？"},
    )
    assert before_index.status_code == 409

    indexed = client.post(f"/knowledge-bases/{knowledge_base_id}/index")
    assert indexed.status_code == 200
    assert indexed.json()["indexed_chunk_count"] >= 1

    answer = client.post(
        f"/knowledge-bases/{knowledge_base_id}/ask",
        json={"question": "创建订单需要什么参数？", "top_k": 1},
    )
    assert answer.status_code == 200
    body = answer.json()
    assert "商品编号" in body["answer"]
    assert len(body["citations"]) == 1
    assert body["citations"][0]["document_title"] == "订单服务接口说明"

    logs = client.get(f"/retrieval-logs?knowledge_base_id={knowledge_base_id}")
    assert logs.status_code == 200
    assert len(logs.json()) == 1
    assert logs.json()[0]["retrieved_count"] == 1

    detail = client.get(f"/retrieval-logs/{body['retrieval_log_id']}")
    assert detail.status_code == 200
    assert detail.json()["question"] == "创建订单需要什么参数？"

    chat_messages = client.get(f"/chat-messages?knowledge_base_id={knowledge_base_id}")
    assert [item["role"] for item in chat_messages.json()] == ["user", "assistant"]
    assert client.delete(f"/documents/{document_id}").status_code == 204


def test_ask_validates_question_and_missing_knowledge_base(client) -> None:
    invalid_question = client.post("/knowledge-bases/1/ask", json={"question": "   "})
    assert invalid_question.status_code == 422

    missing = client.post("/knowledge-bases/999/index")
    assert missing.status_code == 404


def test_health_and_ready_endpoints(client) -> None:
    health = client.get("/health", headers={"X-Request-ID": "release-check-1"})
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert health.headers["X-Request-ID"] == "release-check-1"

    ready = client.get("/ready")
    assert ready.status_code == 200
    assert ready.json()["components"]["database"] == "ok"


def test_document_change_invalidates_existing_index(client) -> None:
    knowledge_base_id, document_id = create_indexed_knowledge_base(client)
    assert client.post(f"/knowledge-bases/{knowledge_base_id}/index").status_code == 200

    before_change = client.post(
        f"/knowledge-bases/{knowledge_base_id}/ask",
        json={"question": "创建订单需要什么参数？"},
    )
    assert before_change.status_code == 200

    updated = client.put(
        f"/documents/{document_id}",
        json={"title": "更新后的订单接口说明"},
    )
    assert updated.status_code == 200

    after_change = client.post(
        f"/knowledge-bases/{knowledge_base_id}/ask",
        json={"question": "创建订单需要什么参数？"},
    )
    assert after_change.status_code == 409


def test_hybrid_retrieval_logs_keyword_vector_and_rerank_candidates(client) -> None:
    knowledge_base = client.post("/knowledge-bases", json={"name": "混合检索测试知识库"})
    assert knowledge_base.status_code == 201
    knowledge_base_id = knowledge_base.json()["id"]

    deployment_document = client.post(
        "/documents",
        json={
            "knowledge_base_id": knowledge_base_id,
            "title": "部署说明",
            "source_type": "DEPLOYMENT",
        },
    )
    order_document = client.post(
        "/documents",
        json={
            "knowledge_base_id": knowledge_base_id,
            "title": "订单接口说明",
            "source_type": "README",
        },
    )
    assert deployment_document.status_code == 201
    assert order_document.status_code == 201

    assert (
        client.post(
            f"/documents/{deployment_document.json()['id']}/upload",
            files={"file": ("deploy.md", "# 部署\n服务监听 8000 端口。", "text/markdown")},
        ).status_code
        == 202
    )
    assert (
        client.post(
            f"/documents/{order_document.json()['id']}/upload",
            files={
                "file": (
                    "orders.md",
                    "# 创建订单\n创建订单需要商品编号、数量和收货地址。",
                    "text/markdown",
                )
            },
        ).status_code
        == 202
    )
    assert client.post(f"/knowledge-bases/{knowledge_base_id}/index").status_code == 200

    answer = client.post(
        f"/knowledge-bases/{knowledge_base_id}/ask",
        json={"question": "创建订单需要什么参数？", "top_k": 1, "recall_k": 5},
    )
    assert answer.status_code == 200
    assert answer.json()["citations"][0]["document_title"] == "订单接口说明"

    log = client.get(f"/retrieval-logs/{answer.json()['retrieval_log_id']}")
    assert log.status_code == 200
    body = log.json()
    assert body["keyword_latency_ms"] >= 0
    assert body["vector_latency_ms"] >= 0
    assert body["fusion_latency_ms"] >= 0
    assert body["rerank_latency_ms"] >= 0
    assert len(body["candidates"]) == 2
    assert body["candidates"][0]["document_title"] == "订单接口说明"
    assert body["candidates"][0]["keyword_rank"] == 1
    assert body["candidates"][0]["vector_rank"] == 2
    assert body["candidates"][0]["rrf_score"] > 0
    assert body["candidates"][0]["rerank_score"] > body["candidates"][1]["rerank_score"]
