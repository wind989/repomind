def test_chat_message_crud_and_filter(client) -> None:
    knowledge_base = client.post("/knowledge-bases", json={"name": "库存服务"})
    knowledge_base_id = knowledge_base.json()["id"]

    created = client.post(
        "/chat-messages",
        json={
            "knowledge_base_id": knowledge_base_id,
            "role": "user",
            "content": "库存扣减接口需要什么参数？",
        },
    )
    assert created.status_code == 201
    chat_message_id = created.json()["id"]

    listed = client.get(f"/chat-messages?knowledge_base_id={knowledge_base_id}")
    assert listed.status_code == 200
    assert listed.json()[0]["role"] == "user"

    assert client.get(f"/chat-messages/{chat_message_id}").status_code == 200
    assert client.delete(f"/chat-messages/{chat_message_id}").status_code == 204
    assert client.get(f"/chat-messages/{chat_message_id}").status_code == 404


def test_chat_message_rejects_invalid_role_and_missing_knowledge_base(client) -> None:
    invalid_role = client.post(
        "/chat-messages",
        json={"knowledge_base_id": 1, "role": "system", "content": "测试"},
    )
    assert invalid_role.status_code == 422

    missing_knowledge_base = client.post(
        "/chat-messages",
        json={"knowledge_base_id": 999, "role": "user", "content": "测试"},
    )
    assert missing_knowledge_base.status_code == 404
