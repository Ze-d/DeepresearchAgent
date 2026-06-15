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
