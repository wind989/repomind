from tests.test_rag import create_indexed_knowledge_base


def test_answer_feedback_can_be_created_updated_and_read(client) -> None:
    knowledge_base_id, _ = create_indexed_knowledge_base(client)
    assert client.post(f"/knowledge-bases/{knowledge_base_id}/index").status_code == 200
    answer = client.post(
        f"/knowledge-bases/{knowledge_base_id}/ask",
        json={"question": "创建订单需要什么参数？", "top_k": 1},
    )
    assert answer.status_code == 200
    log_id = answer.json()["retrieval_log_id"]

    created = client.put(
        f"/retrieval-logs/{log_id}/feedback",
        json={"helpful": True, "comment": "回答准确"},
    )
    assert created.status_code == 200
    assert created.json()["helpful"] is True

    updated = client.put(
        f"/retrieval-logs/{log_id}/feedback",
        json={"helpful": False, "comment": "希望补充示例"},
    )
    assert updated.status_code == 200
    assert updated.json()["id"] == created.json()["id"]
    assert updated.json()["helpful"] is False

    detail = client.get(f"/retrieval-logs/{log_id}")
    assert detail.status_code == 200
    assert detail.json()["feedback"]["comment"] == "希望补充示例"

    missing = client.put("/retrieval-logs/999/feedback", json={"helpful": True})
    assert missing.status_code == 404
