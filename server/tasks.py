# server/tasks.py
import uuid
import time
from enum import Enum
from threading import Lock


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    REVIEW_REQUIRED = "review_required"  # v2.1 Phase 3


class TaskManager:
    """内存任务管理器（单进程，线程安全）。"""

    def __init__(self):
        self._tasks: dict[str, dict] = {}
        self._lock = Lock()

    def create(self, query: str, max_iterations: int = 2) -> dict:
        """创建新任务，返回任务 dict。"""
        task_id = uuid.uuid4().hex[:12]
        task = {
            "task_id": task_id,
            "query": query,
            "max_iterations": max_iterations,
            "status": TaskStatus.PENDING.value,
            "state": {},
            "created_at": time.time(),
            "updated_at": time.time(),
            "error": None,
        }
        with self._lock:
            self._tasks[task_id] = task
        return dict(task)

    def get(self, task_id: str) -> dict | None:
        """获取任务，不存在返回 None。"""
        return self._tasks.get(task_id)

    def update(self, task_id: str, **kwargs) -> dict | None:
        """更新任务字段。"""
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return None
            task.update(kwargs)
            task["updated_at"] = time.time()
            return dict(task)

    def list_tasks(self, limit: int = 20) -> list[dict]:
        """按创建时间倒序返回任务列表。"""
        tasks = sorted(
            self._tasks.values(),
            key=lambda t: t["created_at"],
            reverse=True,
        )
        return [dict(t) for t in tasks[:limit]]

    def delete(self, task_id: str) -> bool:
        """删除任务，返回是否成功。"""
        with self._lock:
            if task_id in self._tasks:
                del self._tasks[task_id]
                return True
            return False


# 全局单例
task_manager = TaskManager()
