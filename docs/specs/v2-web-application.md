# v2 Web 应用 — 设计文档

> **状态:** 设计审核 | **日期:** 2026-06-13 | **基于:** v1 完整实现

## 1. 目标

在 v1 CLI + 工程基础设施之上，将 DeepResearch Agent 包装为可交互的 Web 应用，实现 FastAPI 后端 + Vue 3 前端 + SSE 实时进度推送。

### 1.1 范围

| 优先级 | 领域 | 模块 |
|--------|------|------|
| A | FastAPI 后端 | 任务 CRUD、SSE 事件流、CLI 与 API 共享代码 |
| A | SSE 流式推送 | 每个 node 完成时推送状态变更事件 |
| A | Vue 3 前端 | 任务表单、进度面板、来源表、证据列表、Critique 仪表盘、最终报告 |
| B | 静态文件托管 | FastAPI 托管 Vue 构建产物（单命令启动） |
| C | CLI `serve` 命令 | 一键启动后端 + 前端 |

### 1.2 非范围

- WebSocket 双向通信（SSE 已满足需求）
- 用户认证/授权
- 生产数据库（使用内存 + JSON 快照）
- 多 Agent 并发（推迟到 v2.1）
- 人工审核节点（推迟到 v2.1）
- 本地知识库 / RAG / MCP（推迟到 v2.1）
- Docker 部署（后续添加）

---

## 2. 架构

### 2.1 整体架构

```text
Browser (Vue 3 + Vite)
  │
  │  SSE (text/event-stream)
  ▼
FastAPI Server (server/)
  ├── POST /api/tasks             创建任务 → 后台运行
  ├── GET  /api/tasks/{id}        查询任务状态/结果
  ├── GET  /api/tasks/{id}/stream SSE 事件流
  ├── GET  /api/tasks/{id}/report 下载最终报告
  ├── GET  /api/tasks             任务列表
  └── DELETE /api/tasks/{id}      删除任务
  │
  ▼
deepresearch/ (v1 复用，零改动)
  ├── graph.py     → build_graph() + stream_mode="updates"
  ├── state.py     → AgentState
  ├── nodes/       → plan/research/summary/critique/final
  ├── checkpoint/  → CheckpointManager
  └── output/      → save_all()
```

### 2.2 新增模块

```
server/              ← 新增
├── __init__.py      # FastAPI app 入口 + lifespan + CORS
├── tasks.py         # 任务管理（创建、查询、列表、删除）
├── stream.py        # SSE endpoint + 事件发射器
└── routes.py        # API 路由注册

web/                 ← 新增  Vue 3 + Vite
├── src/
│   ├── App.vue
│   ├── main.js
│   ├── components/
│   │   ├── TaskForm.vue          # 输入 query + 参数 → POST /api/tasks
│   │   ├── TaskList.vue          # GET /api/tasks → 历史列表
│   │   └── TaskDetail.vue        # 单个任务详情页
│   │       ├── ProgressPanel.vue    # 5 节点进度条 + 状态图标
│   │       ├── PlanCard.vue         # research_plan 展示
│   │       ├── SourcesTable.vue     # sources 表格（含 score）
│   │       ├── EvidenceList.vue     # evidences 列表（含 confidence）
│   │       ├── CritiqueDashboard.vue # 三维度评分 + fix_rate
│   │       └── FinalReport.vue      # Markdown 渲染 + citation 上标
│   └── api/
│       └── index.js              # fetch + SSE 封装
├── index.html
├── vite.config.js
└── package.json
```

### 2.3 修改模块

| 模块 | 变更内容 |
|------|---------|
| `config.py` | 新增 `server_host`、`server_port`、`cors_origins` |
| `cli.py` | 抽取 `run_workflow()` 公共函数；新增 `serve` 命令 |
| `output.py` | 无改动（v2 session 结构与 v1 相同） |

### 2.4 数据流

```text
用户提交 query
  → Vue 调用 POST /api/tasks {query, max_iterations}
  → FastAPI 创建 task_id，返回 202 + task_id
  → 后台 asyncio.create_task() 启动 workflow
  → 每个 node 完成后，SSE 推送:
      event: node_start  data: {node: "plan", timestamp: ...}
      event: node_done   data: {node: "plan", result: {...}}
  → 前端 SSE 连接接收事件，更新 ProgressPanel + 子组件
  → workflow 完成后 SSE 推送:
      event: done  data: {status: "completed", final_report: "...", metrics: {...}
  → 前端渲染 FinalReport
```

---

## 3. API 设计

### 3.1 端点

| Method | Path | Request Body | Response | Status |
|--------|------|-------------|----------|--------|
| `POST` | `/api/tasks` | `{query: str, max_iterations?: int}` | `{task_id: str, status: str}` | 202 |
| `GET` | `/api/tasks/{id}` | — | `{task_id, status, state: dict}` | 200 |
| `GET` | `/api/tasks/{id}/stream` | — | `text/event-stream` | 200 |
| `GET` | `/api/tasks/{id}/report` | — | `{task_id, final_report_md: str}` | 200 |
| `GET` | `/api/tasks` | `?limit=20` | `[{task_id, query, status, created_at}]` | 200 |
| `DELETE` | `/api/tasks/{id}` | — | — | 204 |

### 3.2 SSE 事件格式

```
event: node_start
data: {"node": "plan", "timestamp": 1718000000}

event: node_done
data: {"node": "plan", "result": {"status": "planned"}, "timestamp": 1718000002}

event: node_done
data: {"node": "research", "result": {"sources_count": 5, "evidences_count": 12}, ...}

event: done
data: {"status": "completed", "final_report": "...", "metrics": {...}}

event: error
data: {"node": "research", "error": "Search failed"}
```

---

## 4. 前端组件设计

### 4.1 组件树

```
App.vue
├── TaskForm.vue              # 输入 query + max_iterations → POST /api/tasks
├── TaskList.vue              # GET /api/tasks → 历史任务列表
└── TaskDetail.vue            # 单个任务详情页（路由: /tasks/:id）
    ├── ProgressPanel.vue     # 5 个 node 的进度条 + 状态图标
    ├── PlanCard.vue          # research_plan 展示
    ├── SourcesTable.vue      # sources 表格（含 score 列 + 排序）
    ├── EvidenceList.vue      # evidences 列表（含 confidence badge）
    ├── CritiqueDashboard.vue # 三维度评分柱状图 + fix_rate
    └── FinalReport.vue       # Markdown 渲染 + citation 上标
```

### 4.2 路由

```
/                → TaskForm + TaskList（首页）
/tasks/:id       → TaskDetail（任务详情）
```

### 4.3 SSE 集成

前端使用 `EventSource` API 连接 `/api/tasks/{id}/stream`：

```javascript
const source = new EventSource(`/api/tasks/${taskId}/stream`)
source.addEventListener('node_start', (e) => { ... })
source.addEventListener('node_done', (e) => { ... })
source.addEventListener('done', (e) => { source.close() })
source.addEventListener('error', (e) => { ... })
```

### 4.4 状态管理

使用 Vue 3 `reactive()` 管理任务执行状态，无需引入 Pinia：

```javascript
const taskState = reactive({
  status: 'idle',
  current_node: null,
  plan: null,
  sources: [],
  evidences: [],
  critique: null,
  final_report: null,
  metrics: null,
  errors: [],
})
```

---

## 5. CLI 重构

### 5.1 抽取公共 `run_workflow()`

```python
# 从 cli.py 抽取，供 CLI 和 API 共享
def run_workflow(query: str, max_iterations: int = 2) -> dict:
    """同步执行 DeepResearch workflow，返回最终 AgentState。"""
    initial_state = _make_initial_state(query, max_iterations)
    graph = build_graph()
    session_dir = init_session_dir()
    cm = CheckpointManager(session_dir)
    app_graph = graph.compile(checkpointer=cm.saver)
    config = {"configurable": {"thread_id": session_dir.name}}
    result = app_graph.invoke(initial_state, config)
    save_all(result, session_dir)
    cm.save(result, "final")
    return result  # 完整的 AgentState
```

### 5.2 新增 `serve` 命令

```bash
uv run deepresearch serve                      # 默认 127.0.0.1:8000
uv run deepresearch serve --host 0.0.0.0 --port 8080
```

serve 命令启动 FastAPI + 托管 Vue 构建产物（`web/dist/`）。

---

## 6. 配置新增项

```python
# deepresearch/config.py 新增字段

class Settings(BaseSettings):
    # ... v0/v1 字段不变 ...

    # v2: Server
    server_host: str = "127.0.0.1"
    server_port: int = 8000
    cors_origins: list[str] = ["http://localhost:5173"]  # Vite dev server
```

---

## 7. 实现顺序

| Phase | 内容 | 依赖 |
|-------|------|------|
| Phase 17 | CLI 重构 — 抽取 `run_workflow()` 公共函数 | v1 Phase 16 |
| Phase 18 | FastAPI + 任务管理 + SSE | Phase 17 |
| Phase 19 | Vue 3 项目搭建 + 核心组件 | Phase 18 |
| Phase 20 | SSE 前端对接 + 实时渲染 | Phase 19 |
| Phase 21 | CLI `serve` 命令 + 静态文件托管 | Phase 18 |
| Phase 22 | 集成测试 + 端到端验证 | Phase 21 |

---

## 8. 验收标准

```bash
# 后端测试
uv run pytest tests/unit/ tests/integration/

# 代码检查
uv run ruff check .

# CLI 兼容性（v1 命令仍可用）
uv run deepresearch --help
uv run deepresearch run "调研问题" --stream

# v2 启动
uv run deepresearch serve
# 访问 http://localhost:8000 → 看到 Vue 前端
# 输入 query 提交 → SSE 实时更新 → 看到完整报告

# 前端开发
cd web && npm install && npm run dev
# 访问 http://localhost:5173 → 支持 HMR 热更新

# 前端构建
cd web && npm run build
# 产物在 web/dist/ → FastAPI 托管
```
