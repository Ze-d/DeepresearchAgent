# tests/unit/test_server_tasks.py
from server.tasks import TaskManager, TaskStatus


class TestTaskManager:
    def test_create_task(self):
        manager = TaskManager()
        task = manager.create("test query", max_iterations=1)
        assert task["task_id"] is not None
        assert task["query"] == "test query"
        assert task["status"] == TaskStatus.PENDING.value
        assert task["max_iterations"] == 1
        assert "created_at" in task

    def test_get_task(self):
        manager = TaskManager()
        created = manager.create("test")
        task_id = created["task_id"]
        fetched = manager.get(task_id)
        assert fetched is not None
        assert fetched["query"] == "test"

    def test_get_nonexistent_task(self):
        manager = TaskManager()
        assert manager.get("nonexistent") is None

    def test_update_task(self):
        manager = TaskManager()
        created = manager.create("test")
        task_id = created["task_id"]
        manager.update(task_id, status=TaskStatus.RUNNING.value)
        fetched = manager.get(task_id)
        assert fetched["status"] == "running"

    def test_update_task_state(self):
        manager = TaskManager()
        created = manager.create("test")
        task_id = created["task_id"]
        manager.update(task_id, state={"research_plan": {"goal": "test"}})
        fetched = manager.get(task_id)
        assert fetched["state"]["research_plan"]["goal"] == "test"

    def test_list_tasks(self):
        manager = TaskManager()
        manager.create("query 1")
        manager.create("query 2")
        tasks = manager.list_tasks(limit=10)
        assert len(tasks) == 2
        assert tasks[0]["query"] == "query 2"  # newest first

    def test_list_tasks_respects_limit(self):
        manager = TaskManager()
        for i in range(5):
            manager.create(f"query {i}")
        tasks = manager.list_tasks(limit=3)
        assert len(tasks) == 3

    def test_delete_task(self):
        manager = TaskManager()
        created = manager.create("test")
        task_id = created["task_id"]
        assert manager.delete(task_id) is True
        assert manager.get(task_id) is None

    def test_delete_nonexistent(self):
        manager = TaskManager()
        assert manager.delete("nonexistent") is False
