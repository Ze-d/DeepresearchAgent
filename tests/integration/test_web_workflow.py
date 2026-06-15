# tests/integration/test_web_workflow.py
import time
import pytest
from fastapi.testclient import TestClient
from server import create_app
from server.tasks import task_manager


@pytest.fixture
def client(monkeypatch):
    """创建 TestClient 并 mock run_workflow。"""

    # Mock run_workflow 返回完成的 state（已验证各 node 的单元测试覆盖）
    FINAL = "# 最终报告\n\n测试完成。"
    def mock_run_workflow(query, max_iterations=2):
        return {
            "user_query": query,
            "research_plan": {"research_goal": "test"},
            "sources": [{"id": "s1", "title": "T", "url": "https://x.com", "score": 0.8}],
            "evidences": [{"id": "e1", "claim": "test", "confidence": 0.9}],
            "draft_summary": "draft",
            "critique_result": {"pass": True, "overall_score": 0.9},
            "final_report": FINAL,
            "iteration": 1,
            "max_iterations": 1,
            "iteration_metrics": [{"iteration": 1, "fix_rate": None}],
            "citations": [],
            "search_results": [],
            "status": "completed",
            "errors": [],
        }
    monkeypatch.setattr("deepresearch.cli.run_workflow", mock_run_workflow)

    app = create_app()
    return TestClient(app)


@pytest.fixture(autouse=True)
def clear_tasks():
    """每个测试前清理 tasks"""
    for tid in list(task_manager._tasks.keys()):
        task_manager.delete(tid)


class TestEndToEnd:
    def test_create_and_poll_until_completed(self, client):
        """创建任务 → 轮询直到完成 → 获取报告"""
        resp = client.post("/api/tasks", json={"query": "test", "max_iterations": 1})
        assert resp.status_code == 202
        task_id = resp.json()["task_id"]
        assert resp.json()["status"] == "pending"

        # 轮询等待完成（最多 10s）
        for _ in range(50):
            resp = client.get(f"/api/tasks/{task_id}")
            data = resp.json()
            if data["status"] == "completed":
                break
            time.sleep(0.2)
        else:
            pytest.fail("Task did not complete within 10 seconds")

        assert data["status"] == "completed"
        assert data["state"]["final_report"] is not None
        assert "最终报告" in data["state"]["final_report"]

        # 获取报告
        resp = client.get(f"/api/tasks/{task_id}/report")
        assert resp.status_code == 200
        assert "最终报告" in resp.json()["final_report_md"]


    def test_list_tasks_after_creation(self, client):
        """列出任务包含新创建的任务"""
        client.post("/api/tasks", json={"query": "test query"})
        resp = client.get("/api/tasks")
        assert resp.status_code == 200
        assert len(resp.json()) >= 1
        assert resp.json()[0]["query"] == "test query"


    def test_delete_completed_task(self, client):
        """删除已完成任务"""
        resp = client.post("/api/tasks", json={"query": "test"})
        task_id = resp.json()["task_id"]

        # 等待任务完成
        for _ in range(50):
            r = client.get(f"/api/tasks/{task_id}")
            if r.json()["status"] == "completed":
                break
            time.sleep(0.2)

        resp = client.delete(f"/api/tasks/{task_id}")
        assert resp.status_code == 204
        assert task_manager.get(task_id) is None


    def test_get_nonexistent_task(self, client):
        """不存在的任务返回 404"""
        resp = client.get("/api/tasks/nonexistent")
        assert resp.status_code == 404


    def test_delete_nonexistent_task(self, client):
        """删除不存在的任务返回 404"""
        resp = client.delete("/api/tasks/nonexistent")
        assert resp.status_code == 404


    def test_report_for_incomplete_task(self, client):
        """未完成任务获取报告返回 404"""
        task = task_manager.create("test")
        resp = client.get(f"/api/tasks/{task['task_id']}/report")
        assert resp.status_code == 404


class TestTaskListLimit:
    def test_list_tasks_respects_limit(self, client):
        """任务列表支持 limit 参数"""
        for i in range(5):
            task_manager.create(f"query {i}")
        resp = client.get("/api/tasks?limit=3")
        assert resp.status_code == 200
        assert len(resp.json()) == 3


class TestCreateTaskValidation:
    def test_missing_query(self, client):
        """缺少 query 参数返回 422"""
        resp = client.post("/api/tasks", json={})
        assert resp.status_code == 422


    def test_custom_max_iterations(self, client):
        """自定义 max_iterations 参数生效"""
        resp = client.post("/api/tasks", json={"query": "test", "max_iterations": 4})
        assert resp.status_code == 202
        task_id = resp.json()["task_id"]
        task = task_manager.get(task_id)
        assert task["max_iterations"] == 4


class TestHumanInTheLoop:
    def test_review_endpoint_accepts_approve(self, client):
        """POST /api/tasks/{id}/review 接受 approve 决策"""
        resp = client.post("/api/tasks", json={"query": "test hitl", "max_iterations": 1})
        assert resp.status_code == 202
        task_id = resp.json()["task_id"]

        # Submit approve review
        resp = client.post(f"/api/tasks/{task_id}/review", json={
            "action": "approve",
            "notes": "Looks good",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["action"] == "approve"
        assert data["task_id"] == task_id

    def test_review_endpoint_accepts_amend(self, client):
        """POST /api/tasks/{id}/review 接受 amend 决策（含补充查询）"""
        resp = client.post("/api/tasks", json={"query": "test amend", "max_iterations": 1})
        assert resp.status_code == 202
        task_id = resp.json()["task_id"]

        resp = client.post(f"/api/tasks/{task_id}/review", json={
            "action": "amend",
            "notes": "Need more performance data",
            "new_queries": ["benchmark comparison", "performance metrics"],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["action"] == "amend"

    def test_review_endpoint_accepts_redo(self, client):
        """POST /api/tasks/{id}/review 接受 redo 决策"""
        resp = client.post("/api/tasks", json={"query": "test redo", "max_iterations": 1})
        assert resp.status_code == 202
        task_id = resp.json()["task_id"]

        resp = client.post(f"/api/tasks/{task_id}/review", json={
            "action": "redo",
            "notes": "Direction is completely wrong",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["action"] == "redo"

    def test_review_endpoint_404_for_nonexistent_task(self, client):
        """对不存在的任务返回 404"""
        resp = client.post("/api/tasks/nonexistent/review", json={
            "action": "approve",
            "notes": "",
        })
        assert resp.status_code == 404

    def test_review_endpoint_included_in_task_status_check(self, client):
        """review 提交后任务状态更新"""
        resp = client.post("/api/tasks", json={"query": "test status", "max_iterations": 1})
        assert resp.status_code == 202
        task_id = resp.json()["task_id"]

        # Submit review
        client.post(f"/api/tasks/{task_id}/review", json={
            "action": "approve", "notes": "ok",
        })

        # Check task updated
        resp = client.get(f"/api/tasks/{task_id}")
        assert resp.status_code == 200
        task = resp.json()
        assert task["status"] == "running"  # resumed after review
