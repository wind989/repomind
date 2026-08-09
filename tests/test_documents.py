def create_knowledge_base(client, name: str) -> int:
    response = client.post("/knowledge-bases", json={"name": name})
    assert response.status_code == 201
    return response.json()["id"]


def test_document_crud_and_knowledge_base_validation(client) -> None:
    first_knowledge_base_id = create_knowledge_base(client, "订单服务")
    second_knowledge_base_id = create_knowledge_base(client, "支付服务")

    missing_knowledge_base = client.post(
        "/documents",
        json={"knowledge_base_id": 999, "title": "不存在", "source_type": "README"},
    )
    assert missing_knowledge_base.status_code == 404

    created = client.post(
        "/documents",
        json={
            "knowledge_base_id": first_knowledge_base_id,
            "title": "订单 OpenAPI",
            "source_type": "OPENAPI",
            "status": "draft",
        },
    )
    assert created.status_code == 201
    document_id = created.json()["id"]

    listed = client.get(f"/documents?knowledge_base_id={first_knowledge_base_id}")
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    updated = client.put(
        f"/documents/{document_id}",
        json={
            "knowledge_base_id": second_knowledge_base_id,
            "source_type": "DEPLOYMENT",
            "status": "active",
        },
    )
    assert updated.status_code == 200
    assert updated.json()["knowledge_base_id"] == second_knowledge_base_id
    assert updated.json()["source_type"] == "DEPLOYMENT"

    assert client.get(f"/documents/{document_id}").status_code == 200
    assert client.delete(f"/documents/{document_id}").status_code == 204
    assert client.get(f"/documents/{document_id}").status_code == 404


def test_document_rejects_invalid_source_type(client) -> None:
    knowledge_base_id = create_knowledge_base(client, "商品服务")
    response = client.post(
        "/documents",
        json={"knowledge_base_id": knowledge_base_id, "title": "商品说明", "source_type": "PDF"},
    )
    assert response.status_code == 422
