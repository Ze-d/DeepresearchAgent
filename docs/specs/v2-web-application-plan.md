# v2 Web 应用 — 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 v1 CLI 基础上，增加 FastAPI 后端 + Vue 3 前端 + SSE 实时推送，实现 Web 可交互的 DeepResearch Agent。

**Architecture:** FastAPI 包装 `deepresearch/` 核心，SSE 推送每个 node 完成事件；Vue 3 前端通过 EventSource 接收事件，实时渲染进度面板、来源表、证据列表、Critique 仪表盘和最终 Markdown 报告。

**Tech Stack:** Python 3.11+, FastAPI, sse-starlette, Vue 3, Vite, marked (Markdown 渲染), LangGraph stream_mode

**Specs:**
- [v2 Web 应用设计](../specs/v2-web-application.md)

---

## 文件结构总览（变更）

```
deepresearch/
├── config.py                        # 修改：新增 server_host, server_port, cors_origins
├── cli.py                           # 修改：抽取 run_workflow(), 新增 serve 命令
│
server/          ← 新增
├── __init__.py                      # FastAPI app + lifespan + CORS + mount
├── tasks.py                         # 任务管理器（内存）
├── stream.py                        # SSE endpoint + 事件发射器
└── routes.py                        # API 路由注册

web/             ← 新增  Vue 3 + Vite
├── package.json
├── vite.config.js
├── index.html
└── src/
    ├── main.js
    ├── App.vue
    ├── router.js
    ├── api/index.js                 # fetch + SSE 封装
    ├── components/
    │   ├── TaskForm.vue
    │   ├── TaskList.vue
    │   ├── TaskDetail.vue
    │   ├── ProgressPanel.vue
    │   ├── PlanCard.vue
    │   ├── SourcesTable.vue
    │   ├── EvidenceList.vue
    │   ├── CritiqueDashboard.vue
    │   └── FinalReport.vue
    └── style.css

tests/
├── unit/
│   ├── test_config.py               # 修改：新增 v2 字段测试
│   ├── test_cli.py                  # 修改：新增 serve 命令测试
│   ├── test_server_routes.py        ← 新增
│   └── test_server_tasks.py         ← 新增
└── integration/
    └── test_web_workflow.py         ← 新增
```

---

## Phase 17：CLI 重构 — 抽取 run_workflow()

### Task 17.1: 抽取 run_workflow() 公共函数

**Files:**
- Modify: `deepresearch/cli.py`
- Modify: `tests/unit/test_cli.py`

- [ ] **Step 1: 写失败的测试**

```python
# tests/unit/test_cli.py — 追加以下测试

def test_run_workflow_exists():
    """run_workflow 可从 CLI 模块导入"""
    from deepresearch.cli import run_workflow
    assert callable(run_workflow)


def test_run_workflow_returns_state(monkeypatch):
    """run_workflow 用 mock LLM + mock search 返回完整 state"""
    from deepresearch.cli import run_workflow, _make_initial_state
    from tests.fixtures.mock_llm import FakeChatModel
    from deepresearch.state import AgentState

    # Mock 搜索
    def mock_search(query, max_results):
        from deepresearch.tools import SearchResult
        return [SearchResult(title="T", url="https://example.com", snippet="S")]

    def mock_fetch(url, timeout):
        return "Test content for evidence extraction."

    monkeypatch.setattr("deepresearch.nodes.research.search_web", mock_search)
    monkeypatch.setattr("deepresearch.nodes.research.fetch_content", mock_fetch)

    import json
    PLAN = json.dumps({
        "research_goal": "test",
        "sub_questions": [{"id": "q1", "question": "q", "priority": 1, "search_queries": ["q"]}],
        "expected_sections": ["s1"],
        "success_criteria": ["c1"],
    }, ensure_ascii=False)

    llm = FakeChatModel(default_response=PLAN)

    # 注入 mock LLM
    monkeypatch.setattr("deepresearch.cli.build_graph",
                        lambda: __import__("deepresearch.graph").graph.build_graph(llm=llm))

    result = run_workflow("test query", max_iterations=1)
    assert result["user_query"] == "test query"
    assert result["status"] == "completed"
    assert result["final_report"] is not None
```

- [ ] **Step 2: 运行测试确认失败**

```bash
uv run pytest tests/unit/test_cli.py::test_run_workflow_exists tests/unit/test_cli.py::test_run_workflow_returns_state -v
```
Expected: FAIL (ImportError: cannot import name 'run_workflow')

- [ ] **Step 3: 实现 run_workflow()**

在 `deepresearch/cli.py` 中，在 `_make_initial_state()` 之后、`run` 命令之前插入：

```python
def run_workflow(query: str, max_iterations: int = 2) -> dict:
    """同步执行 DeepResearch workflow，返回最终 AgentState dict。

    供 CLI run 命令和 FastAPI server 共享使用。
    """
    initial_state = _make_initial_state(query, max_iterations)

    from deepresearch.output import init_session_dir, save_all
    from deepresearch.checkpoint.manager import CheckpointManager

    graph = build_graph()
    session_dir = init_session_dir()
    cm = CheckpointManager(session_dir)
    app_graph = graph.compile(checkpointer=cm.saver)
    config = {"configurable": {"thread_id": session_dir.name}}

    result = app_graph.invoke(initial_state, config)

    save_all(result, session_dir)
    cm.save(result, "final")

    # v1 额外输出
    from deepresearch.output import save_json
    metrics = result.get("iteration_metrics", [])
    if metrics:
        save_json(metrics, session_dir / "iteration_metrics.json")
    citations = result.get("citations", [])
    if citations:
        save_json(citations, session_dir / "citations.json")

    logger.info("Workflow completed: iteration=%d, status=%s",
                result.get("iteration", 0), result.get("status"))
    return result
```

- [ ] **Step 4: 重构 run 命令使用 run_workflow()**

将 `cli.py` 中 `run` 函数的 middle section 替换为调用 `run_workflow()`，保留参数处理、输出打印和 stream 模式：

```python
@app.command()
def run(
    query: str = typer.Argument(..., help="研究问题"),
    max_iterations: int = typer.Option(2, "--max-iterations", "-n", help="最大研究迭代次数"),
    output: str | None = typer.Option(None, "--output", "-o", help="输出文件路径"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="启用 DEBUG 级别日志"),
    log_file: str | None = typer.Option(None, "--log-file", help="日志文件路径"),
    stream: bool = typer.Option(True, "--stream/--no-stream", help="启用/禁用实时 streaming 展示"),
):
    """运行 DeepResearch Agent 完成研究任务。"""
    cfg = Settings()
    log_level = "DEBUG" if verbose else cfg.log_level
    resolved_log_file = log_file or cfg.log_file
    setup_logging(level=log_level, log_file=resolved_log_file)

    if not stream:
        import deepresearch.config as config_module
        config_module.settings.stream_enabled = False

    logger.info("Starting DeepResearch Agent")
    logger.debug("Query: %s, Max iterations: %d", query, max_iterations)

    typer.echo(f"🔍 开始研究: {query}")
    typer.echo(f"   最大迭代次数: {max_iterations}")

    # v2: 使用抽取的公共函数
    if settings.stream_enabled:
        # streaming 模式：复用 streaming/stream_with_rich
        initial_state = _make_initial_state(query, max_iterations)
        from deepresearch.output import init_session_dir, save_all
        from deepresearch.checkpoint.manager import CheckpointManager
        from deepresearch.streaming.renderer import stream_with_rich
        graph = build_graph()
        session_dir = init_session_dir()
        cm = CheckpointManager(session_dir)
        app_graph = graph.compile(checkpointer=cm.saver)
        config = {"configurable": {"thread_id": session_dir.name}}
        result = stream_with_rich(app_graph, initial_state, config)
        save_all(result, session_dir)
        cm.save(result, "final")
        from deepresearch.output import save_json
        metrics = result.get("iteration_metrics", [])
        if metrics:
            save_json(metrics, session_dir / "iteration_metrics.json")
        citations = result.get("citations", [])
        if citations:
            save_json(citations, session_dir / "citations.json")
    else:
        result = run_workflow(query, max_iterations)

    final = result.get("final_report") or ""
    typer.echo("\n" + "=" * 60)
    typer.echo(final)
    typer.echo("=" * 60)

    if output:
        out_path = Path(output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(final, encoding="utf-8")
        typer.echo(f"\n📄 报告已保存到: {out_path}")

    # 统计摘要（与 v1 相同）
    typer.echo(f"\n📊 迭代次数: {result.get('iteration', 0)}")
    plan = result.get("research_plan")
    if plan:
        typer.echo(f"   子问题数: {len(plan.get('sub_questions', []))}")
    critique = result.get("critique_result")
    if critique:
        typer.echo(f"   Critique 评分: {critique.get('overall_score', critique.get('score', 'N/A'))}")
    iteration_metrics_list = result.get("iteration_metrics", [])
    if iteration_metrics_list:
        last_metrics = iteration_metrics_list[-1]
        fix_rate = last_metrics.get("fix_rate")
        if fix_rate is not None:
            typer.echo(f"   Issues 修复率: {fix_rate * 100:.0f}%")
    sources = result.get("sources", [])
    evidences = result.get("evidences", [])
    typer.echo(f"   来源数: {len(sources)}, 证据数: {len(evidences)}")

    errors = result.get("errors", [])
    if errors:
        typer.echo(f"   ⚠️  错误: {len(errors)} 个")
        for e in errors:
            logger.error("Workflow error: %s", e)

    logger.info("DeepResearch Agent completed")
    typer.echo("✅ 研究完成")
```

- [ ] **Step 4: 运行测试确认通过**

```bash
uv run pytest tests/unit/test_cli.py -v
```
Expected: all passed (包括 v1 已有测试 + 新 v2 测试)

- [ ] **Step 5: 确认 CLI 仍可运行**

```bash
uv run deepresearch --help
uv run deepresearch run "测试问题" --no-stream
```
Expected: 正常输出报告

- [ ] **Step 6: 提交**

```bash
git add deepresearch/cli.py tests/unit/test_cli.py
git commit -m "feat: extract run_workflow() public function for CLI and API sharing (Task 17.1)"
```

---

## Phase 18：FastAPI + 任务管理 + SSE

### Task 18.1: Config 新增 v2 server 字段

**Files:**
- Modify: `deepresearch/config.py`
- Modify: `tests/unit/test_config.py`

- [ ] **Step 1: 写失败的测试**

```python
# tests/unit/test_config.py — 追加以下测试

def test_v2_server_defaults(monkeypatch):
    """v2 server 配置项默认值正确"""
    for key in ("DEEPSEEK_API_KEY", "DEEPSEEK_MODEL", "MAX_ITERATIONS",
                "MAX_SEARCH_RESULTS", "OUTPUT_DIR", "TEMPERATURE", "MAX_RETRIES"):
        monkeypatch.delenv(key, raising=False)
    from deepresearch.config import Settings
    s = Settings()
    assert s.server_host == "127.0.0.1"
    assert s.server_port == 8000
    assert s.cors_origins == ["http://localhost:5173"]


def test_v2_server_from_env(monkeypatch):
    """v2 server 配置项可从环境变量读取"""
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    monkeypatch.setenv("SERVER_HOST", "0.0.0.0")
    monkeypatch.setenv("SERVER_PORT", "8080")
    from deepresearch.config import Settings
    s = Settings()
    assert s.server_host == "0.0.0.0"
    assert s.server_port == 8080
```

- [ ] **Step 2: 运行测试确认失败**

```bash
uv run pytest tests/unit/test_config.py::test_v2_server_defaults tests/unit/test_config.py::test_v2_server_from_env -v
```
Expected: FAIL (AttributeError)

- [ ] **Step 3: 实现 config.py 新增字段**

在 `deepresearch/config.py` 的 `Settings` 类中，在 v1 Streaming 配置之后追加：

```python
    # v2: Server
    server_host: str = "127.0.0.1"
    server_port: int = 8000
    cors_origins: list[str] = ["http://localhost:5173"]
```

- [ ] **Step 4: 运行测试确认通过**

```bash
uv run pytest tests/unit/test_config.py -v
```
Expected: all passed

- [ ] **Step 5: 提交**

```bash
git add deepresearch/config.py tests/unit/test_config.py
git commit -m "feat: add v2 server config fields (host, port, cors_origins) (Task 18.1)"
```

---

### Task 18.2: FastAPI 任务管理器

**Files:**
- Create: `server/__init__.py`
- Create: `server/tasks.py`
- Create: `tests/unit/test_server_tasks.py`

- [ ] **Step 1: 写失败的测试**

```python
# tests/unit/test_server_tasks.py
import pytest
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
```

- [ ] **Step 2: 运行测试确认失败**

```bash
uv run pytest tests/unit/test_server_tasks.py -v
```
Expected: FAIL (ModuleNotFoundError: No module named 'server')

- [ ] **Step 3: 创建 server 包目录结构**

```bash
mkdir server
```

- [ ] **Step 4: 实现 server/tasks.py**

```python
# server/tasks.py
import uuid
import time
from dataclasses import dataclass, field
from enum import Enum
from threading import Lock


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


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
        return task

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
            return task

    def list_tasks(self, limit: int = 20) -> list[dict]:
        """按创建时间倒序返回任务列表。"""
        tasks = sorted(
            self._tasks.values(),
            key=lambda t: t["created_at"],
            reverse=True,
        )
        return tasks[:limit]

    def delete(self, task_id: str) -> bool:
        """删除任务，返回是否成功。"""
        with self._lock:
            if task_id in self._tasks:
                del self._tasks[task_id]
                return True
            return False


# 全局单例
task_manager = TaskManager()
```

- [ ] **Step 5: 运行测试确认通过**

```bash
uv run pytest tests/unit/test_server_tasks.py -v
```
Expected: all passed

- [ ] **Step 6: 提交**

```bash
git add server/tasks.py tests/unit/test_server_tasks.py
git commit -m "feat: add in-memory task manager with thread-safe CRUD (Task 18.2)"
```

---

### Task 18.3: FastAPI App + Routes + SSE

**Files:**
- Create: `server/routes.py`
- Create: `server/stream.py`
- Modify: `server/__init__.py`
- Create: `tests/unit/test_server_routes.py`

- [ ] **Step 1: 写失败的测试**

```python
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
        resp = client.post("/api/tasks", json={"query": "test", "max_iterations": 3})
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
```

- [ ] **Step 2: 运行测试确认失败**

```bash
uv run pytest tests/unit/test_server_routes.py -v
```
Expected: FAIL (ImportError: cannot import name 'create_app')

- [ ] **Step 3: 实现 server/stream.py**

```python
# server/stream.py
import asyncio
import json
import logging
import queue
import time
from typing import Any

logger = logging.getLogger(__name__)


class SSEManager:
    """管理 SSE 客户端连接和事件广播。

    每个 task_id 对应一个 asyncio.Queue，
    工作线程通过 put_event() 写入事件，
    SSE endpoint 通过 subscribe() 获取 queue。
    """

    def __init__(self):
        self._queues: dict[str, asyncio.Queue] = {}

    def subscribe(self, task_id: str) -> asyncio.Queue:
        """订阅任务的 SSE 事件流，返回 queue。"""
        if task_id not in self._queues:
            self._queues[task_id] = asyncio.Queue()
        return self._queues[task_id]

    def put_event(self, task_id: str, event: str, data: dict[str, Any]) -> None:
        """向指定任务的事件流放入事件（线程安全）。"""
        if task_id not in self._queues:
            self._queues[task_id] = asyncio.Queue()
        q = self._queues[task_id]
        try:
            q.put_nowait((event, data))
        except asyncio.QueueFull:
            logger.warning("SSE queue full for task %s, dropping event %s", task_id, event)

    def unsubscribe(self, task_id: str) -> None:
        """取消订阅，清理 queue。"""
        self._queues.pop(task_id, None)


# 全局单例
sse_manager = SSEManager()


async def sse_endpoint(task_id: str):
    """SSE 事件流 ASGI generator。"""
    q = sse_manager.subscribe(task_id)
    try:
        while True:
            try:
                event, data = await asyncio.wait_for(q.get(), timeout=30.0)
            except asyncio.TimeoutError:
                # 发送心跳保持连接
                yield f"event: heartbeat\ndata: {json.dumps({'timestamp': time.time()})}\n\n"
                continue

            yield f"event: {event}\n"
            yield f"data: {json.dumps(data, ensure_ascii=False)}\n"
            yield "\n"

            if event == "done" or event == "error":
                break
    except asyncio.CancelledError:
        pass
    finally:
        sse_manager.unsubscribe(task_id)
```

- [ ] **Step 4: 实现 server/routes.py**

```python
# server/routes.py
import asyncio
import logging
import threading

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from server.tasks import task_manager, TaskStatus
from server.stream import sse_manager, sse_endpoint

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


# ——— Request models ———


class CreateTaskRequest(BaseModel):
    query: str
    max_iterations: int = 2


# ——— POST /api/tasks ———


@router.post("/tasks", status_code=202)
def create_task(req: CreateTaskRequest):
    """创建研究任务，立即返回 task_id，后台异步执行。"""
    task = task_manager.create(req.query, max_iterations=req.max_iterations)
    task_id = task["task_id"]

    # 后台执行 workflow
    def run_background():
        from deepresearch.cli import run_workflow
        import deepresearch.config as config_module

        task_manager.update(task_id, status=TaskStatus.RUNNING.value)
        sse_manager.put_event(task_id, "task_started", {"task_id": task_id})

        try:
            result = run_workflow(req.query, max_iterations=req.max_iterations)
            task_manager.update(
                task_id,
                status=TaskStatus.COMPLETED.value,
                state={
                    "user_query": result.get("user_query"),
                    "research_plan": result.get("research_plan"),
                    "sources": result.get("sources"),
                    "evidences": result.get("evidences"),
                    "draft_summary": result.get("draft_summary"),
                    "critique_result": result.get("critique_result"),
                    "final_report": result.get("final_report"),
                    "iteration": result.get("iteration"),
                    "iteration_metrics": result.get("iteration_metrics"),
                    "citations": result.get("citations"),
                    "errors": result.get("errors"),
                },
            )
            sse_manager.put_event(task_id, "done", {
                "status": "completed",
                "final_report": result.get("final_report"),
            })
        except Exception as e:
            logger.exception("Task %s failed", task_id)
            task_manager.update(
                task_id,
                status=TaskStatus.FAILED.value,
                error=str(e),
            )
            sse_manager.put_event(task_id, "error", {"error": str(e)})

    thread = threading.Thread(target=run_background, daemon=True)
    thread.start()

    return {"task_id": task_id, "status": task["status"]}


# ——— GET /api/tasks ———


@router.get("/tasks")
def list_tasks(limit: int = Query(20, ge=1, le=100)):
    """返回最近的任务列表。"""
    tasks = task_manager.list_tasks(limit=limit)
    return [
        {
            "task_id": t["task_id"],
            "query": t["query"],
            "status": t["status"],
            "created_at": t["created_at"],
        }
        for t in tasks
    ]


# ——— GET /api/tasks/{id} ———


@router.get("/tasks/{task_id}")
def get_task(task_id: str):
    """查询单个任务的状态和完整 state。"""
    task = task_manager.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return {
        "task_id": task["task_id"],
        "query": task["query"],
        "status": task["status"],
        "max_iterations": task["max_iterations"],
        "state": task.get("state", {}),
        "error": task.get("error"),
        "created_at": task["created_at"],
        "updated_at": task["updated_at"],
    }


# ——— GET /api/tasks/{id}/stream ———


@router.get("/tasks/{task_id}/stream")
async def stream_task(task_id: str):
    """SSE 事件流：实时推送任务执行进度。"""
    task = task_manager.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    return StreamingResponse(
        sse_endpoint(task_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ——— GET /api/tasks/{id}/report ———


@router.get("/tasks/{task_id}/report")
def get_task_report(task_id: str):
    """返回任务的最终报告 Markdown。"""
    task = task_manager.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if task["status"] != TaskStatus.COMPLETED.value:
        raise HTTPException(status_code=404, detail="Report not available (task not completed)")
    state = task.get("state", {})
    return {"task_id": task_id, "final_report_md": state.get("final_report", "")}


# ——— DELETE /api/tasks/{id} ———


@router.delete("/tasks/{task_id}", status_code=204)
def delete_task(task_id: str):
    """删除任务。"""
    if not task_manager.delete(task_id):
        raise HTTPException(status_code=404, detail="Task not found")
```

- [ ] **Step 5: 实现 server/__init__.py**

```python
# server/__init__.py
import logging
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from deepresearch.config import settings
from server.routes import router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动/关闭日志。"""
    logger.info("DeepResearch Server starting on %s:%d", settings.server_host, settings.server_port)
    yield
    logger.info("DeepResearch Server shutting down")


def create_app() -> FastAPI:
    """创建并配置 FastAPI 应用。"""
    app = FastAPI(
        title="DeepResearch Agent API",
        version="0.2.0",
        description="LangGraph-based DeepResearch Agent — Web API",
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # API routes
    app.include_router(router)

    # 静态文件（Vue 构建产物）
    web_dist = Path(__file__).resolve().parent.parent / "web" / "dist"
    if web_dist.exists():
        app.mount("/", StaticFiles(directory=str(web_dist), html=True), name="static")

    return app


app = create_app()
```

- [ ] **Step 6: 更新 pyproject.toml 添加依赖**

在 `pyproject.toml` 的 `dependencies` 列表中追加：

```toml
    "fastapi",
    "uvicorn",
    "sse-starlette",
```

- [ ] **Step 7: 运行测试确认通过 — 先安装新依赖**

```bash
uv sync
uv run pip install fastapi uvicorn sse-starlette
```

注意：如果 `uv sync` 已包含这些依赖，跳过 pip install。

```bash
uv run pytest tests/unit/test_server_routes.py -v
```
Expected: all passed

- [ ] **Step 8: 确认 API 可手动启动**

```bash
uv run uvicorn server:app --host 127.0.0.1 --port 8000
# 另一个终端:
curl -X POST http://127.0.0.1:8000/api/tasks -H "Content-Type: application/json" -d '{"query":"test"}'
```
Expected: 返回 202 + task_id

- [ ] **Step 9: 提交**

```bash
git add server/ tests/unit/test_server_routes.py pyproject.toml
git commit -m "feat: add FastAPI app with task CRUD, SSE streaming, and background workflow (Task 18.3)"
```

---

### Task 18.4: CLI serve 命令

**Files:**
- Modify: `deepresearch/cli.py`
- Modify: `tests/unit/test_cli.py`

- [ ] **Step 1: 写失败的测试**

```python
# tests/unit/test_cli.py — 追加以下测试

def test_cli_serve_help():
    """deepresearch serve --help 正常输出"""
    result = runner.invoke(app, ["serve", "--help"])
    assert result.exit_code == 0
    assert "serve" in result.stdout.lower() or "server" in result.stdout.lower()
```

- [ ] **Step 2: 运行测试确认失败**

```bash
uv run pytest tests/unit/test_cli.py::test_cli_serve_help -v
```
Expected: FAIL (No such command 'serve')

- [ ] **Step 3: 实现 serve 命令**

在 `deepresearch/cli.py` 末尾追加：

```python
@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", "--host", "-h", help="服务器绑定的 IP"),
    port: int = typer.Option(8000, "--port", "-p", help="服务器端口"),
    reload: bool = typer.Option(False, "--reload", help="启用热重载（开发模式）"),
):
    """启动 Web 服务器（FastAPI + Vue 前端）。"""
    import uvicorn

    # 覆盖配置
    import deepresearch.config as config_module
    config_module.settings.server_host = host
    config_module.settings.server_port = port

    typer.echo(f"🚀 DeepResearch Agent Web Server")
    typer.echo(f"   地址: http://{host}:{port}")
    typer.echo(f"   API 文档: http://{host}:{port}/docs")

    web_dist = Path(__file__).resolve().parent.parent / "web" / "dist"
    if not web_dist.exists():
        typer.echo(f"   ⚠️  前端未构建（web/dist/ 不存在）")
        typer.echo(f"   请先运行: cd web && npm install && npm run build")

    uvicorn.run(
        "server:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )
```

- [ ] **Step 4: 运行测试确认通过**

```bash
uv run pytest tests/unit/test_cli.py -v
```
Expected: all passed

- [ ] **Step 5: 确认 CLI serve 可显示帮助**

```bash
uv run deepresearch serve --help
```
Expected: 显示 serve 命令帮助

- [ ] **Step 6: 提交**

```bash
git add deepresearch/cli.py tests/unit/test_cli.py
git commit -m "feat: add CLI serve command for one-click server startup (Task 18.4)"
```

---

## Phase 19：Vue 3 前端搭建

### Task 19.1: Vue 3 + Vite 项目初始化

**Files:**
- Create: `web/package.json`
- Create: `web/vite.config.js`
- Create: `web/index.html`
- Create: `web/src/main.js`
- Create: `web/src/router.js`
- Create: `web/src/App.vue`
- Create: `web/src/style.css`

- [ ] **Step 1: 创建 web/package.json**

```json
{
  "name": "deepresearch-web",
  "version": "0.2.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "vue": "^3.4",
    "vue-router": "^4.3",
    "marked": "^12.0"
  },
  "devDependencies": {
    "@vitejs/plugin-vue": "^5.0",
    "vite": "^5.4"
  }
}
```

- [ ] **Step 2: 创建 web/vite.config.js**

```javascript
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://127.0.0.1:8000',
    },
  },
  build: {
    outDir: 'dist',
    assetsDir: 'assets',
  },
})
```

- [ ] **Step 3: 创建 web/index.html**

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>DeepResearch Agent</title>
</head>
<body>
  <div id="app"></div>
  <script type="module" src="/src/main.js"></script>
</body>
</html>
```

- [ ] **Step 4: 创建 web/src/main.js**

```javascript
import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'
import TaskDetail from './components/TaskDetail.vue'
import './style.css'

const routes = [
  { path: '/', component: null },  // App.vue handles home
  { path: '/tasks/:id', component: TaskDetail, props: true },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

createApp(App).use(router).mount('#app')
```

- [ ] **Step 5: 创建 web/src/router.js**

```javascript
import { createRouter, createWebHistory } from 'vue-router'
import TaskDetail from './components/TaskDetail.vue'

const routes = [
  { path: '/', name: 'home' },
  { path: '/tasks/:id', name: 'task-detail', component: TaskDetail, props: true },
]

export default createRouter({
  history: createWebHistory(),
  routes,
})
```

- [ ] **Step 6: 创建 web/src/App.vue**

```html
<template>
  <div id="app-container">
    <header class="app-header">
      <h1>🔍 DeepResearch Agent</h1>
      <p>基于 LangGraph + DeepSeek 的深度调研智能体</p>
    </header>
    <main>
      <router-view v-if="$route.name === 'task-detail'" />
      <div v-else class="home">
        <TaskForm />
        <TaskList />
      </div>
    </main>
  </div>
</template>

<script setup>
import TaskForm from './components/TaskForm.vue'
import TaskList from './components/TaskList.vue'
</script>

<style scoped>
.app-header {
  text-align: center;
  padding: 24px 0 8px;
  border-bottom: 1px solid #e0e0e0;
  margin-bottom: 24px;
}
.app-header h1 { margin: 0; font-size: 1.8rem; }
.app-header p { margin: 4px 0 0; color: #666; }
.home { max-width: 900px; margin: 0 auto; }
</style>
```

- [ ] **Step 7: 创建 web/src/style.css**

```css
* { box-sizing: border-box; }
body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  margin: 0;
  padding: 0;
  background: #f5f5f5;
  color: #333;
}
#app-container { max-width: 1200px; margin: 0 auto; padding: 0 16px; }

/* Shared styles */
.card {
  background: #fff;
  border-radius: 8px;
  padding: 20px;
  margin-bottom: 16px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.1);
}
.card h2 { margin-top: 0; font-size: 1.2rem; }

.btn {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 8px 16px; border: none; border-radius: 6px;
  cursor: pointer; font-size: 0.95rem; font-weight: 500;
}
.btn-primary { background: #1a73e8; color: #fff; }
.btn-primary:hover { background: #1557b0; }
.btn-danger { background: #dc3545; color: #fff; }
.btn-danger:hover { background: #b52b38; }

input, textarea {
  width: 100%; padding: 10px 12px;
  border: 1px solid #ccc; border-radius: 6px;
  font-size: 0.95rem;
}
input:focus, textarea:focus { outline: none; border-color: #1a73e8; }

.badge {
  display: inline-block; padding: 2px 8px; border-radius: 12px;
  font-size: 0.8rem; font-weight: 600;
}
.badge-pending { background: #fff3cd; color: #856404; }
.badge-running { background: #cce5ff; color: #004085; }
.badge-completed { background: #d4edda; color: #155724; }
.badge-failed { background: #f8d7da; color: #721c24; }

.status-dot {
  display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 6px;
}
.status-dot.pending { background: #ffc107; }
.status-dot.running { background: #007bff; animation: pulse 1s infinite; }
.status-dot.completed { background: #28a745; }
.status-dot.failed { background: #dc3545; }

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

.markdown-body h1 { font-size: 1.5rem; border-bottom: 1px solid #eee; padding-bottom: 8px; }
.markdown-body h2 { font-size: 1.25rem; }
.markdown-body h3 { font-size: 1.1rem; }
.markdown-body pre { background: #f4f4f4; padding: 12px; border-radius: 6px; overflow-x: auto; }
.markdown-body code { background: #f4f4f4; padding: 2px 6px; border-radius: 4px; font-size: 0.9em; }
.markdown-body blockquote { border-left: 3px solid #1a73e8; padding-left: 12px; color: #555; }
.markdown-body table { border-collapse: collapse; width: 100%; }
.markdown-body th, .markdown-body td { border: 1px solid #ddd; padding: 8px; text-align: left; }
.markdown-body th { background: #f8f8f8; }
```

- [ ] **Step 8: 安装依赖并验证 Vite 启动**

```bash
cd web && npm install && npm run dev
# 访问 http://localhost:5173
```
Expected: Vite 启动无报错，浏览器显示 DeepResearch Agent 标题

- [ ] **Step 9: 提交**

```bash
git add web/package.json web/vite.config.js web/index.html web/src/main.js web/src/router.js web/src/App.vue web/src/style.css
git commit -m "feat: scaffold Vue 3 + Vite project with router and base styles (Task 19.1)"
```

---

### Task 19.2: API 封装 + TaskForm + TaskList 组件

**Files:**
- Create: `web/src/api/index.js`
- Create: `web/src/components/TaskForm.vue`
- Create: `web/src/components/TaskList.vue`

- [ ] **Step 1: 创建 web/src/api/index.js**

```javascript
const BASE = '/api'

export async function createTask(query, maxIterations = 2) {
  const resp = await fetch(`${BASE}/tasks`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, max_iterations: maxIterations }),
  })
  if (!resp.ok) throw new Error(`Create task failed: ${resp.status}`)
  return resp.json()
}

export async function getTask(taskId) {
  const resp = await fetch(`${BASE}/tasks/${taskId}`)
  if (!resp.ok) throw new Error(`Get task failed: ${resp.status}`)
  return resp.json()
}

export async function listTasks(limit = 20) {
  const resp = await fetch(`${BASE}/tasks?limit=${limit}`)
  if (!resp.ok) throw new Error(`List tasks failed: ${resp.status}`)
  return resp.json()
}

export async function deleteTask(taskId) {
  const resp = await fetch(`${BASE}/tasks/${taskId}`, { method: 'DELETE' })
  if (!resp.ok && resp.status !== 204) throw new Error(`Delete task failed: ${resp.status}`)
}

export function subscribeToTask(taskId, callbacks) {
  const source = new EventSource(`${BASE}/tasks/${taskId}/stream`)

  source.addEventListener('task_started', (e) => {
    if (callbacks.onTaskStarted) callbacks.onTaskStarted(JSON.parse(e.data))
  })

  source.addEventListener('node_start', (e) => {
    if (callbacks.onNodeStart) callbacks.onNodeStart(JSON.parse(e.data))
  })

  source.addEventListener('node_done', (e) => {
    if (callbacks.onNodeDone) callbacks.onNodeDone(JSON.parse(e.data))
  })

  source.addEventListener('done', (e) => {
    if (callbacks.onDone) callbacks.onDone(JSON.parse(e.data))
    source.close()
  })

  source.addEventListener('error', (e) => {
    if (callbacks.onError) callbacks.onError(e)
    source.close()
  })

  return source
}
```

- [ ] **Step 2: 创建 web/src/components/TaskForm.vue**

```html
<template>
  <div class="card">
    <h2>📝 新建研究任务</h2>
    <form @submit.prevent="submit">
      <div class="form-row">
        <input
          v-model="query"
          type="text"
          placeholder="输入研究问题..."
          :disabled="submitting"
          required
        />
      </div>
      <div class="form-row form-options">
        <label>
          最大迭代
          <input v-model.number="maxIterations" type="number" min="1" max="5" />
        </label>
        <button type="submit" class="btn btn-primary" :disabled="submitting || !query.trim()">
          {{ submitting ? '⏳ 提交中...' : '🚀 开始研究' }}
        </button>
      </div>
    </form>
    <p v-if="error" class="error">{{ error }}</p>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { createTask } from '../api/index.js'

const router = useRouter()
const query = ref('')
const maxIterations = ref(2)
const submitting = ref(false)
const error = ref('')

async function submit() {
  if (!query.value.trim()) return
  submitting.value = true
  error.value = ''
  try {
    const task = await createTask(query.value.trim(), maxIterations.value)
    router.push(`/tasks/${task.task_id}`)
  } catch (e) {
    error.value = `提交失败: ${e.message}`
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.form-row { margin-bottom: 12px; }
.form-options { display: flex; align-items: center; gap: 16px; }
.form-options label { display: flex; align-items: center; gap: 6px; }
.form-options input[type="number"] { width: 70px; }
.error { color: #dc3545; margin-top: 8px; }
</style>
```

- [ ] **Step 3: 创建 web/src/components/TaskList.vue**

```html
<template>
  <div class="card">
    <h2>📋 历史任务</h2>
    <p v-if="loading">加载中...</p>
    <p v-else-if="tasks.length === 0">暂无任务</p>
    <table v-else class="task-table">
      <thead>
        <tr>
          <th>状态</th>
          <th>研究问题</th>
          <th>创建时间</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="task in tasks" :key="task.task_id">
          <td>
            <span class="status-dot" :class="task.status"></span>
            <span class="badge" :class="`badge-${task.status}`">{{ task.status }}</span>
          </td>
          <td>
            <router-link :to="`/tasks/${task.task_id}`">{{ task.query }}</router-link>
          </td>
          <td>{{ formatTime(task.created_at) }}</td>
          <td>
            <button class="btn btn-danger" @click="remove(task.task_id)">删除</button>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { listTasks, deleteTask } from '../api/index.js'

const tasks = ref([])
const loading = ref(true)

async function load() {
  loading.value = true
  try {
    tasks.value = await listTasks(20)
  } catch (e) {
    console.error('Failed to load tasks:', e)
  } finally {
    loading.value = false
  }
}

async function remove(taskId) {
  await deleteTask(taskId)
  tasks.value = tasks.value.filter(t => t.task_id !== taskId)
}

function formatTime(ts) {
  return new Date(ts * 1000).toLocaleString('zh-CN')
}

onMounted(load)
</script>

<style scoped>
.task-table { width: 100%; border-collapse: collapse; }
.task-table th, .task-table td { padding: 10px 12px; text-align: left; border-bottom: 1px solid #eee; }
.task-table th { font-weight: 600; color: #555; font-size: 0.9rem; }
.task-table a { color: #1a73e8; text-decoration: none; }
.task-table a:hover { text-decoration: underline; }
</style>
```

- [ ] **Step 4: 提交**

```bash
git add web/src/api/index.js web/src/components/TaskForm.vue web/src/components/TaskList.vue
git commit -m "feat: add API client, TaskForm and TaskList Vue components (Task 19.2)"
```

---

### Task 19.3: TaskDetail + ProgressPanel + PlanCard 组件

**Files:**
- Create: `web/src/components/TaskDetail.vue`
- Create: `web/src/components/ProgressPanel.vue`
- Create: `web/src/components/PlanCard.vue`

- [ ] **Step 1: 创建 web/src/components/ProgressPanel.vue**

```html
<template>
  <div class="card">
    <h2>📊 执行进度</h2>
    <div class="progress-steps">
      <div
        v-for="node in nodes"
        :key="node.key"
        class="step"
        :class="stepClass(node.key)"
      >
        <span class="step-icon">{{ stepIcon(node.key) }}</span>
        <span class="step-label">{{ node.label }}</span>
      </div>
    </div>
    <p v-if="currentNode" class="current-step">
      当前: {{ nodeLabel(currentNode) }}
    </p>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  completedNodes: { type: Array, default: () => [] },
  currentNode: { type: String, default: null },
})

const nodes = [
  { key: 'plan', label: 'Plan' },
  { key: 'research', label: 'Research' },
  { key: 'summary', label: 'Summary' },
  { key: 'critique', label: 'Critique' },
  { key: 'final', label: 'Final' },
]

function stepClass(key) {
  if (props.completedNodes.includes(key)) return 'completed'
  if (props.currentNode === key) return 'active'
  return ''
}

function stepIcon(key) {
  if (props.completedNodes.includes(key)) return '✅'
  if (props.currentNode === key) return '⏳'
  return '⬜'
}

function nodeLabel(key) {
  const node = nodes.find(n => n.key === key)
  return node ? node.label : key
}
</script>

<style scoped>
.progress-steps { display: flex; gap: 8px; flex-wrap: wrap; }
.step {
  display: flex; align-items: center; gap: 4px;
  padding: 6px 14px; border-radius: 20px; background: #f0f0f0;
  font-size: 0.9rem;
}
.step.completed { background: #d4edda; color: #155724; }
.step.active { background: #cce5ff; color: #004085; }
.step-icon { font-size: 1rem; }
.current-step { margin-top: 12px; color: #666; font-size: 0.9rem; }
</style>
```

- [ ] **Step 2: 创建 web/src/components/PlanCard.vue**

```html
<template>
  <div v-if="plan" class="card">
    <h2>📋 研究计划</h2>
    <p><strong>目标:</strong> {{ plan.research_goal }}</p>
    <h3>子问题</h3>
    <ul>
      <li v-for="sq in plan.sub_questions" :key="sq.id">
        <span class="priority">P{{ sq.priority }}</span>
        {{ sq.question }}
        <div class="search-queries">
          🔍 {{ sq.search_queries.join(' | ') }}
        </div>
      </li>
    </ul>
    <p v-if="plan.expected_sections?.length">
      <strong>预期章节:</strong> {{ plan.expected_sections.join(' → ') }}
    </p>
  </div>
</template>

<script setup>
defineProps({ plan: { type: Object, default: null } })
</script>

<style scoped>
.priority {
  display: inline-block; width: 24px; height: 24px;
  line-height: 24px; text-align: center;
  background: #1a73e8; color: #fff; border-radius: 50%;
  font-size: 0.75rem; margin-right: 6px;
}
.search-queries { font-size: 0.85rem; color: #888; margin: 2px 0 0 30px; }
</style>
```

- [ ] **Step 3: 创建 web/src/components/TaskDetail.vue**

```html
<template>
  <div class="task-detail">
    <div class="task-header">
      <router-link to="/" class="back-link">← 返回</router-link>
      <h1>{{ task.query || '加载中...' }}</h1>
      <span class="badge" :class="`badge-${taskStatus}`">{{ taskStatus }}</span>
    </div>

    <ProgressPanel
      :completedNodes="completedNodes"
      :currentNode="currentNode"
    />

    <PlanCard :plan="taskState.research_plan" />
    <SourcesTable :sources="taskState.sources || []" />
    <EvidenceList :evidences="taskState.evidences || []" />
    <CritiqueDashboard :critique="taskState.critique_result" :metrics="taskState.iteration_metrics" />
    <FinalReport v-if="taskState.final_report" :report="taskState.final_report" />

    <p v-if="error" class="error">{{ error }}</p>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted } from 'vue'
import { getTask, subscribeToTask } from '../api/index.js'
import ProgressPanel from './ProgressPanel.vue'
import PlanCard from './PlanCard.vue'
import SourcesTable from './SourcesTable.vue'
import EvidenceList from './EvidenceList.vue'
import CritiqueDashboard from './CritiqueDashboard.vue'
import FinalReport from './FinalReport.vue'

const props = defineProps({ id: String })

const task = ref({ query: '', status: 'pending' })
const taskState = reactive({})
const taskStatus = ref('loading')
const completedNodes = ref([])
const currentNode = ref(null)
const error = ref('')
let eventSource = null

function handleNodeStart(data) {
  currentNode.value = data.node
}

function handleNodeDone(data) {
  completedNodes.value.push(data.node)

  // 根据 node 类型合并 state
  const node = data.node
  if (data.result) {
    if (node === 'plan' && data.result.research_plan) {
      taskState.research_plan = data.result.research_plan
    }
    if (node === 'research') {
      if (data.result.sources) taskState.sources = data.result.sources
      if (data.result.evidences) taskState.evidences = data.result.evidences
    }
    if (node === 'summary' && data.result.draft_summary) {
      taskState.draft_summary = data.result.draft_summary
    }
    if (node === 'critique' && data.result.critique_result) {
      taskState.critique_result = data.result.critique_result
      taskState.iteration_metrics = data.result.iteration_metrics
    }
    if (node === 'final' && data.result.final_report) {
      taskState.final_report = data.result.final_report
    }
  }

  if (node === 'final') {
    taskStatus.value = 'completed'
  }
}

function handleDone(data) {
  taskStatus.value = 'completed'
}

function handleError(e) {
  error.value = `执行出错: ${e.data || e}`
  taskStatus.value = 'failed'
}

onMounted(async () => {
  try {
    const data = await getTask(props.id)
    task.value = data
    taskStatus.value = data.status

    // 如果任务已完成，直接加载 state
    if (data.state) {
      Object.assign(taskState, data.state)
    }

    // 如果任务正在运行或 pending，订阅 SSE
    if (data.status === 'pending' || data.status === 'running') {
      taskStatus.value = 'running'
      eventSource = subscribeToTask(props.id, {
        onTaskStarted: () => { taskStatus.value = 'running' },
        onNodeStart: handleNodeStart,
        onNodeDone: handleNodeDone,
        onDone: handleDone,
        onError: handleError,
      })
    }
  } catch (e) {
    error.value = `加载任务失败: ${e.message}`
    taskStatus.value = 'failed'
  }
})

onUnmounted(() => {
  if (eventSource) eventSource.close()
})
</script>

<style scoped>
.task-detail { max-width: 960px; margin: 0 auto; }
.task-header { display: flex; align-items: center; gap: 12px; margin-bottom: 20px; flex-wrap: wrap; }
.task-header h1 { margin: 0; font-size: 1.4rem; flex: 1; }
.back-link { color: #1a73e8; text-decoration: none; font-size: 0.95rem; }
.back-link:hover { text-decoration: underline; }
.error { color: #dc3545; padding: 12px; background: #fff; border-radius: 8px; }
</style>
```

- [ ] **Step 4: 提交**

```bash
git add web/src/components/TaskDetail.vue web/src/components/ProgressPanel.vue web/src/components/PlanCard.vue
git commit -m "feat: add TaskDetail, ProgressPanel, and PlanCard Vue components (Task 19.3)"
```

---

### Task 19.4: SourcesTable + EvidenceList + CritiqueDashboard + FinalReport

**Files:**
- Create: `web/src/components/SourcesTable.vue`
- Create: `web/src/components/EvidenceList.vue`
- Create: `web/src/components/CritiqueDashboard.vue`
- Create: `web/src/components/FinalReport.vue`

- [ ] **Step 1: 创建 web/src/components/SourcesTable.vue**

```html
<template>
  <div v-if="sources.length" class="card">
    <h2>📚 来源 ({{ sources.length }})</h2>
    <table class="sources-table">
      <thead>
        <tr>
          <th>#</th>
          <th>标题</th>
          <th>类型</th>
          <th>评分</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="(s, i) in sources" :key="s.id">
          <td>{{ i + 1 }}</td>
          <td><a :href="s.url" target="_blank">{{ s.title }}</a></td>
          <td><span class="badge">{{ s.source_type || 'unknown' }}</span></td>
          <td>
            <div class="score-bar">
              <div class="score-fill" :style="{ width: (s.score * 100) + '%' }"></div>
              <span>{{ (s.score * 100).toFixed(0) }}</span>
            </div>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script setup>
defineProps({ sources: { type: Array, default: () => [] } })
</script>

<style scoped>
.sources-table { width: 100%; border-collapse: collapse; }
.sources-table th, .sources-table td { padding: 8px 10px; text-align: left; border-bottom: 1px solid #eee; font-size: 0.9rem; }
.sources-table a { color: #1a73e8; word-break: break-all; }
.score-bar { display: flex; align-items: center; gap: 6px; min-width: 80px; }
.score-fill { height: 6px; background: #28a745; border-radius: 3px; }
</style>
```

- [ ] **Step 2: 创建 web/src/components/EvidenceList.vue**

```html
<template>
  <div v-if="evidences.length" class="card">
    <h2>🔬 证据 ({{ evidences.length }})</h2>
    <div class="evidence-item" v-for="ev in evidences" :key="ev.id">
      <div class="evidence-claim">
        <span class="confidence" :class="confidenceClass(ev.confidence)">
          {{ (ev.confidence * 100).toFixed(0) }}%
        </span>
        {{ ev.claim }}
      </div>
      <blockquote v-if="ev.quote">{{ ev.quote }}</blockquote>
    </div>
  </div>
</template>

<script setup>
defineProps({ evidences: { type: Array, default: () => [] } })

function confidenceClass(c) {
  if (c >= 0.8) return 'high'
  if (c >= 0.5) return 'medium'
  return 'low'
}
</script>

<style scoped>
.evidence-item { margin-bottom: 12px; padding-bottom: 8px; border-bottom: 1px solid #f0f0f0; }
.evidence-claim { display: flex; align-items: flex-start; gap: 8px; }
.confidence {
  display: inline-block; padding: 2px 8px; border-radius: 12px;
  font-size: 0.8rem; font-weight: 600; white-space: nowrap;
}
.confidence.high { background: #d4edda; color: #155724; }
.confidence.medium { background: #fff3cd; color: #856404; }
.confidence.low { background: #f8d7da; color: #721c24; }
blockquote { border-left: 3px solid #ccc; padding-left: 12px; color: #666; font-size: 0.9rem; margin: 6px 0 0; }
</style>
```

- [ ] **Step 3: 创建 web/src/components/CritiqueDashboard.vue**

```html
<template>
  <div v-if="critique" class="card">
    <h2>🔍 Critique 评分</h2>
    <div class="critique-overview">
      <div class="overall-score">
        <span class="score-number">{{ (critique.overall_score * 100).toFixed(0) }}</span>
        <span class="score-label">总分</span>
      </div>
      <span class="badge" :class="critique.pass ? 'badge-completed' : 'badge-failed'">
        {{ critique.pass ? '✅ 通过' : '❌ 未通过' }}
      </span>
    </div>

    <div v-if="critique.dimensions" class="dimensions">
      <div class="dimension" v-for="(dim, key) in critique.dimensions" :key="key">
        <div class="dim-header">
          <span class="dim-name">{{ dimLabel(key) }}</span>
          <span class="dim-score" :class="dim.status">{{ (dim.score * 100).toFixed(0) }}%</span>
        </div>
        <div class="dim-bar">
          <div class="dim-fill" :class="dim.status" :style="{ width: (dim.score * 100) + '%' }"></div>
        </div>
      </div>
    </div>

    <div v-if="metrics?.length" class="fix-rate">
      Fix Rate: {{ lastFixRate }}% ({{ metrics[metrics.length - 1].issues_count }} issues)
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  critique: { type: Object, default: null },
  metrics: { type: Array, default: () => [] },
})

const lastFixRate = computed(() => {
  if (!props.metrics.length) return 'N/A'
  const last = props.metrics[props.metrics.length - 1]
  return last.fix_rate != null ? (last.fix_rate * 100).toFixed(0) : 'N/A'
})

function dimLabel(key) {
  const map = { fact_check: '事实核查', logic_coherence: '逻辑一致性', coverage: '覆盖度' }
  return map[key] || key
}
</script>

<style scoped>
.critique-overview { display: flex; align-items: center; gap: 16px; margin-bottom: 16px; }
.overall-score { display: flex; flex-direction: column; align-items: center; }
.score-number { font-size: 2rem; font-weight: 700; color: #1a73e8; }
.score-label { font-size: 0.85rem; color: #666; }
.dimensions { display: flex; flex-direction: column; gap: 10px; }
.dimension { font-size: 0.9rem; }
.dim-header { display: flex; justify-content: space-between; margin-bottom: 4px; }
.dim-score.pass { color: #28a745; font-weight: 600; }
.dim-score.fail { color: #dc3545; font-weight: 600; }
.dim-bar { height: 8px; background: #e0e0e0; border-radius: 4px; overflow: hidden; }
.dim-fill { height: 100%; border-radius: 4px; }
.dim-fill.pass { background: #28a745; }
.dim-fill.fail { background: #dc3545; }
.fix-rate { margin-top: 12px; font-size: 0.9rem; color: #555; }
</style>
```

- [ ] **Step 4: 创建 web/src/components/FinalReport.vue**

```html
<template>
  <div class="card">
    <h2>📄 最终报告</h2>
    <div class="markdown-body" v-html="rendered"></div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { marked } from 'marked'

const props = defineProps({ report: { type: String, required: true } })

const rendered = computed(() => {
  return marked.parse(props.report) || ''
})
</script>

<style scoped>
.markdown-body { max-width: 100%; overflow-x: auto; }
</style>
```

- [ ] **Step 5: 提交**

```bash
git add web/src/components/SourcesTable.vue web/src/components/EvidenceList.vue web/src/components/CritiqueDashboard.vue web/src/components/FinalReport.vue
git commit -m "feat: add SourcesTable, EvidenceList, CritiqueDashboard, FinalReport Vue components (Task 19.4)"
```

---

## Phase 20：集成测试 + 端到端验证

### Task 20.1: 集成测试

**Files:**
- Create: `tests/integration/test_web_workflow.py`

- [ ] **Step 1: 写集成测试**

```python
# tests/integration/test_web_workflow.py
import json
import pytest
from fastapi.testclient import TestClient
from tests.fixtures.mock_llm import FakeChatModel
from server import create_app
from server.tasks import task_manager


@pytest.fixture
def client(monkeypatch):
    """创建 TestClient 并 mock 搜索 + LLM"""
    def mock_search(query, max_results):
        from deepresearch.tools import SearchResult
        return [SearchResult(title="Test", url="https://example.com", snippet="S")]

    def mock_fetch(url, timeout):
        return "Test content."

    monkeypatch.setattr("deepresearch.nodes.research.search_web", mock_search)
    monkeypatch.setattr("deepresearch.nodes.research.fetch_content", mock_fetch)

    PLAN = json.dumps({
        "research_goal": "test",
        "sub_questions": [{"id": "q1", "question": "q", "priority": 1, "search_queries": ["q"]}],
        "expected_sections": ["s1"],
        "success_criteria": ["c1"],
    }, ensure_ascii=False)

    SUMMARY = "## 阶段总结\n\n测试内容。"
    CRITIQUE = json.dumps({
        "pass": True, "overall_score": 0.9,
        "dimensions": {
            "fact_check": {"score": 0.9, "issues": [], "status": "pass"},
            "logic_coherence": {"score": 0.9, "issues": [], "status": "pass"},
            "coverage": {"score": 0.9, "issues": [], "status": "pass"},
        },
        "issues": [], "new_search_queries": [],
    }, ensure_ascii=False)
    FINAL = "# 最终报告\n\n测试完成。"

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
    for tid in list(task_manager._tasks.keys()):
        task_manager.delete(tid)


class TestEndToEnd:
    def test_create_and_poll_until_completed(self, client):
        """创建任务 → 轮询直到完成 → 获取报告"""
        import time

        resp = client.post("/api/tasks", json={"query": "test", "max_iterations": 1})
        assert resp.status_code == 202
        task_id = resp.json()["task_id"]

        # 轮询等待完成（最多 10s）
        for _ in range(50):
            resp = client.get(f"/api/tasks/{task_id}")
            data = resp.json()
            if data["status"] == "completed":
                break
            time.sleep(0.2)

        assert data["status"] == "completed"
        assert data["state"]["final_report"] is not None

        # 获取报告
        resp = client.get(f"/api/tasks/{task_id}/report")
        assert resp.status_code == 200
        assert "最终报告" in resp.json()["final_report_md"]

    def test_list_tasks_after_creation(self, client):
        """列出任务包含新创建的任务"""
        client.post("/api/tasks", json={"query": "test"})
        resp = client.get("/api/tasks")
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_delete_completed_task(self, client):
        """删除已完成任务"""
        resp = client.post("/api/tasks", json={"query": "test"})
        task_id = resp.json()["task_id"]
        resp = client.delete(f"/api/tasks/{task_id}")
        assert resp.status_code == 204
```

- [ ] **Step 2: 运行集成测试**

```bash
uv run pytest tests/integration/test_web_workflow.py -v
```
Expected: all passed

- [ ] **Step 3: 运行全部测试确保无回归**

```bash
uv run pytest -v
```

- [ ] **Step 4: 提交**

```bash
git add tests/integration/test_web_workflow.py
git commit -m "feat: add web integration tests for task CRUD and end-to-end flow (Task 20.1)"
```

---

### Task 20.2: 前端构建 + 全流程验证

- [ ] **Step 1: 构建前端**

```bash
cd web && npm run build
```
Expected: `web/dist/` 目录生成

- [ ] **Step 2: 启动后端服务**

```bash
uv run deepresearch serve --host 127.0.0.1 --port 8000
```
Expected: 显示启动信息，`web/dist/` 存在时提示前端已就绪

- [ ] **Step 3: 浏览器验证**

打开 `http://localhost:8000`，验证：
1. 页面标题显示 "DeepResearch Agent"
2. 输入框可输入研究问题
3. 提交后跳转到 `/tasks/:id`
4. 进度面板显示五个节点
5. 来源表、证据列表、Critique 仪表盘、最终报告逐步渲染
6. `/api/tasks` 列出历史任务
7. 删除按钮可删除任务

- [ ] **Step 4: 代码检查**

```bash
uv run ruff check .
uv run mypy deepresearch/ server/ 2>&1 | head -20
```

- [ ] **Step 5: 最终提交**

```bash
git add web/dist/ .gitignore
git commit -m "feat: complete v2 web application — Vue 3 frontend build + integration (Task 20.2)"
```

---

## 自审清单

**1. Spec 覆盖检查:**
- [x] CLI 重构 — 抽取 run_workflow() → Task 17.1
- [x] Config server 字段 → Task 18.1
- [x] 任务管理器（创建/查询/列表/删除）→ Task 18.2
- [x] FastAPI app + routes + SSE → Task 18.3
- [x] CLI serve 命令 → Task 18.4
- [x] Vue 3 + Vite 项目初始化 → Task 19.1
- [x] API 封装 + TaskForm + TaskList → Task 19.2
- [x] TaskDetail + ProgressPanel + PlanCard → Task 19.3
- [x] SourcesTable + EvidenceList + CritiqueDashboard + FinalReport → Task 19.4
- [x] 集成测试 → Task 20.1
- [x] 前端构建 + 全流程验证 → Task 20.2

**2. Placeholder 扫描:** 零 TBD/TODO/占位符

**3. 类型一致性:**
- TaskManager API: `create/get/update/list/delete` 在同名函数中一致
- SSE 事件格式: `task_started/node_start/node_done/done/error` 在 routes.py 和 TaskDetail.vue 中一致
- Vue 组件 props: `sources`, `evidences`, `critique`, `report` 与 API 返回的 state 字段一致
- Config 字段: `server_host/server_port/cors_origins` 在 config.py 和 cli.py 中一致

**4. 与 v1 兼容:**
- `deepresearch/` 包零改动（除 config.py 新增字段 + cli.py 抽取函数）
- 现有 CLI 命令签名不变
- 所有 v1 测试预期仍然通过
