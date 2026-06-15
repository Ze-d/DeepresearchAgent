# tests/unit/test_server_routes.py
import pytest
from fastapi.testclient import TestClient
from server import create_app
from server.tasks import task_manager, TaskStatus


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)


@pytest.fixture(autouse=True)
def clear_tasks():
    """每个测试前清理 tasks"""
    for tid in list(task_manager._tasks.keys()):
        task_manager.delete(tid)


class TestCreateTask:
    def test_create_task_returns_202(self, client):
        resp = client.post("/api/tasks", json={"query": "test query"})
        assert resp.status_code == 202
        data = resp.json()
        assert "task_id" in data
        assert data["status"] == TaskStatus.PENDING.value

    def test_create_task_with_max_iterations(self, client):
        resp = client.post(
            "/api/tasks", json={"query": "test", "max_iterations": 3}
        )
        assert resp.status_code == 202
        task_id = resp.json()["task_id"]
        task = task_manager.get(task_id)
        assert task["max_iterations"] == 3

    def test_create_task_default_max_iterations(self, client):
        resp = client.post("/api/tasks", json={"query": "test"})
        task_id = resp.json()["task_id"]
        task = task_manager.get(task_id)
        assert task["max_iterations"] == 2

    def test_create_task_missing_query(self, client):
        resp = client.post("/api/tasks", json={})
        assert resp.status_code == 422


class TestGetTask:
    def test_get_existing_task(self, client):
        created = task_manager.create("test")
        resp = client.get(f"/api/tasks/{created['task_id']}")
        assert resp.status_code == 200
        assert resp.json()["query"] == "test"

    def test_get_nonexistent_task(self, client):
        resp = client.get("/api/tasks/nonexistent")
        assert resp.status_code == 404


class TestListTasks:
    def test_list_tasks(self, client):
        task_manager.create("query 1")
        task_manager.create("query 2")
        resp = client.get("/api/tasks")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_list_tasks_limit(self, client):
        for i in range(10):
            task_manager.create(f"query {i}")
        resp = client.get("/api/tasks?limit=3")
        assert len(resp.json()) == 3


class TestDeleteTask:
    def test_delete_task(self, client):
        created = task_manager.create("test")
        resp = client.delete(f"/api/tasks/{created['task_id']}")
        assert resp.status_code == 204
        assert task_manager.get(created["task_id"]) is None

    def test_delete_nonexistent(self, client):
        resp = client.delete("/api/tasks/nonexistent")
        assert resp.status_code == 404


class TestGetTaskReport:
    def test_report_for_completed_task(self, client):
        task = task_manager.create("test")
        task_manager.update(
            task["task_id"],
            status=TaskStatus.COMPLETED.value,
            state={"final_report": "# Report\n\nContent"},
        )
        resp = client.get(f"/api/tasks/{task['task_id']}/report")
        assert resp.status_code == 200
        assert resp.json()["final_report_md"] == "# Report\n\nContent"

    def test_report_for_incomplete_task(self, client):
        task = task_manager.create("test")
        resp = client.get(f"/api/tasks/{task['task_id']}/report")
        assert resp.status_code == 404
