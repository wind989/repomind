def test_knowledge_base_crud(client) -> None:
    created = client.post(
        "/knowledge-bases",
        json={"name": "订单服务资料", "description": "接口和部署说明"},
    )
    assert created.status_code == 201
    knowledge_base_id = created.json()["id"]

    listed = client.get("/knowledge-bases")
    assert listed.status_code == 200
    assert listed.json()[0]["name"] == "订单服务资料"

    detail = client.get(f"/knowledge-bases/{knowledge_base_id}")
    assert detail.status_code == 200

    updated = client.put(
        f"/knowledge-bases/{knowledge_base_id}",
        json={"name": "订单服务文档", "description": "更新后的说明"},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "订单服务文档"

    deleted = client.delete(f"/knowledge-bases/{knowledge_base_id}")
    assert deleted.status_code == 204
    assert client.get(f"/knowledge-bases/{knowledge_base_id}").status_code == 404


def test_knowledge_base_validation_and_conflict(client) -> None:
    assert client.post("/knowledge-bases", json={"name": "   "}).status_code == 422
    assert client.post("/knowledge-bases", json={"name": "支付服务"}).status_code == 201

    duplicate = client.post("/knowledge-bases", json={"name": "支付服务"})
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"] == "知识库名称已存在"
