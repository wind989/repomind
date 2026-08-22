from app.main import app
from app.services.evaluation import EvaluationCase, evaluate_retrieval_cases


def test_evaluation_run_persists_retrieval_metrics(client, test_db) -> None:
    knowledge_base = client.post("/knowledge-bases", json={"name": "评测知识库"})
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
    upload = client.post(
        f"/documents/{document.json()['id']}/upload",
        files={
            "file": (
                "orders.md",
                "# 创建订单\n创建订单需要商品编号、数量和收货地址。",
                "text/markdown",
            )
        },
    )
    assert upload.status_code == 202
    assert client.post(f"/knowledge-bases/{knowledge_base_id}/index").status_code == 200

    evaluation_run = evaluate_retrieval_cases(
        test_db,
        [
            EvaluationCase(
                case_key="order-create-parameters",
                knowledge_base_id=knowledge_base_id,
                question="创建订单需要什么参数？",
                expected_document_title="订单服务接口说明",
            )
        ],
        "隔离测试题集",
        app.state.vector_store,
    )
    test_db.add(evaluation_run)
    test_db.commit()
    test_db.refresh(evaluation_run)

    assert evaluation_run.total_cases == 1
    assert evaluation_run.top1_hit_count == 1
    assert evaluation_run.recall_hit_count == 1
    assert evaluation_run.mrr == 1.0
    assert evaluation_run.ragas_context_precision == 1.0
    assert evaluation_run.ragas_context_recall == 1.0
    assert len(evaluation_run.results) == 1
    assert evaluation_run.results[0].expected_rank == 1
    assert evaluation_run.results[0].ragas_context_precision == 1.0
    assert evaluation_run.results[0].ragas_context_recall == 1.0
    assert evaluation_run.results[0].candidate_titles_json == '["订单服务接口说明"]'

    response = client.get(f"/evaluation-runs/{evaluation_run.id}")
    assert response.status_code == 200
    assert response.json()["top1_hit_count"] == 1
    assert response.json()["mrr"] == 1.0
    assert response.json()["ragas_context_precision"] == 1.0
    assert response.json()["ragas_context_recall"] == 1.0
