# Architecture Overview

## 1. Project Positioning

DeepResearch Agent is a multi-stage agent system for complex research tasks, using:

```text
Plan → Research → Summary → Critique → Final Report
```

The project is designed for resume/portfolio demonstration, highlighting:

1. Agent workflow design skills
2. LangChain / LangGraph engineering practice
3. DeepSeek API integration
4. Search tool and content extraction capabilities
5. Structured state management
6. Report generation with self-critique
7. Structured logging and engineering observability

## 2. v0 Scope (Complete)

v0 prioritizes a stable, runnable closed-loop:

```text
User Query
  ↓
Planner generates research plan
  ↓
Researcher executes search and evidence collection
  ↓
Summarizer generates draft summary
  ↓
Critic checks quality
  ↓
Conditional Route: continue research or go to final
  ↓
Finalizer outputs Markdown report
```

### v0 Non-Goals

- No frontend
- No multi-user system
- No distributed task scheduling
- No custom agent framework
- No large-scale web crawler
- No long-running background tasks
- No enterprise permission system

## 2.1 v2 Web 应用 (Complete)

v2 adds FastAPI + Vue 3 frontend on top of v1 infrastructure:

```text
Browser (Vue 3 + Vite)
  │  SSE (text/event-stream)
  ▼
FastAPI Server (server/)
  ├── POST /api/tasks       创建任务 → 后台运行
  ├── GET  /api/tasks/{id}  查询任务状态/结果
  ├── GET  /api/tasks/{id}/stream  SSE 事件流
  ├── GET  /api/tasks/{id}/report  下载报告
  ├── GET  /api/tasks        任务列表
  └── DELETE /api/tasks/{id} 删除任务
```

## 2.2 v2.1 多 Agent 并发研究 (Complete)

v2.1 replaces the single-threaded research node with 4 parallel agents using LangGraph Send API:

```text
Plan (LLM 分类 source_types)
  │
  ▼  Send API 扇出 (并行)
┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
│  Paper   │ │  GitHub  │ │   Blog   │ │   Docs   │
│  Agent   │ │  Agent   │ │  Agent   │ │  Agent   │
│ (arXiv)  │ │  (repo)  │ │  (tech)  │ │(official)│
└────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘
     └─────────────┴────────────┴────────────┘
                         │  auto-barrier
                         ▼
                  Merge (三阶段流水线)
                         │
                   [Human Review]  ← 可选 interrupt
                         │
                   Summary → Critique → Final
```

Key additions:
- **AgentProfile** — unified node + strategy injection (4 profiles)
- **Merge node** — collect, cross-validate, conflict detect, rank, quality report
- **Human-in-the-Loop** — LangGraph interrupt() with approve/amend/redo actions

## 3. Tech Stack

| Category | Technology |
|----------|-----------|
| Language | Python 3.11+ |
| Package manager | uv |
| Agent orchestration | LangGraph |
| LLM framework | LangChain |
| LLM provider | DeepSeek API (`langchain-deepseek`) |
| CLI | Typer + Rich |
| Logging | Rich (RichHandler) + logging |
| Data modeling | Pydantic + pydantic-settings |
| Config | python-dotenv (.env) |
| Search | DuckDuckGo / Tavily (optional) |
| Content extraction | trafilatura / BeautifulSoup |
| HTTP | httpx |
| Testing | pytest |
| Linting | ruff |
| Type checking | mypy |
| v2 Frontend | Vue 3 + Vite |
| v2 Backend | FastAPI + SSE |

## 4. Key Design Decisions

- **StateGraph-based agent workflow** — explicit nodes, edges, and conditional routing
- **Five-node pipeline**: Plan → Research → Summary → Critique → Final
- **Critique-driven iteration** — automatic quality check with re-research loop
- **make_*_node(llm) factory pattern** — LLM injected via closures, enabling mock testing
- **Flat `deepresearch/` Python package** — not src layout
- **Markdown report output** to local `outputs/` session directory
- **Centralized logging** via `setup_logging()` with test-aware no-op mode
- **Provider-agnostic LLM** — `build_llm()` factory, default DeepSeek, extensible to OpenAI/Ollama

## 5. Module Boundaries

| Module | Responsibility | Dependencies |
|--------|---------------|--------------|
| `cli` | CLI entry point (Typer) | `graph`, `logging`, `config` |
| `graph` | LangGraph StateGraph definition | `nodes`, `state`, `llm` |
| `state` | Pydantic state models + AgentState TypedDict | none |
| `config` | pydantic-settings configuration | none |
| `llm` | DeepSeek LLM factory | `config` |
| `logging` | Centralized log config (console + file) | none |
| `prompts` | Centralized ChatPromptTemplate definitions | none |
| `tools` | Search + web content extraction tools | none |
| `output` | Session directory + JSON/MD writer | `state`, `config` |
| `nodes.plan` | Plan node — decompose question → research plan, classify source_types | `llm`, `prompts`, `state` |
| `nodes.research` | (v2) Research node — search + evidence extraction (v2.1 replaced by research_agent) | `llm`, `tools`, `state`, `prompts` |
| `nodes.research_agent` | (v2.1) Unified research agent node — AgentProfile strategy injection | `llm`, `tools`, `state`, `prompts` |
| `nodes.merge` | (v2.1) Merge node — 3-stage pipeline: collect, cross-validate, quality report | `llm`, `state`, `evidence`, `config` |
| `nodes.human_review` | (v2.1) Human-in-the-Loop review node — LangGraph interrupt() | `llm`, `state`, `config` |
| `nodes.summary` | Summary node — synthesize evidence | `llm`, `prompts`, `state` |
| `nodes.critique` | Critique node — 3D scoring + fix rate | `llm`, `prompts`, `state` |
| `nodes.final` | Final report node — format output | `llm`, `prompts`, `state` |
| `evidence` | Evidence dedup + source ranking + cross-validation (v2.1) | `llm`, `config` |
| `citation` | Citation extraction + formatting | none |
| `checkpoint` | SqliteSaver wrapper + JSON snapshots | `state`, `config` |
| `streaming` | Rich Live rendering for graph streaming | `config` |
| `observability` | LangChain callbacks + metrics collector | none |
| `server` | FastAPI + SSE + task management + HITL review endpoint (v2.1) | `graph`, `state`, `checkpoint`, `output` |

## 6. Source Code Structure

```text
deepresearch/
├── __init__.py
├── config.py
├── state.py
├── llm.py
├── logging.py
├── prompts.py
├── graph.py
├── cli.py
├── tools.py
├── output.py
├── nodes/
│   ├── __init__.py
│   ├── plan.py
│   ├── research.py
│   ├── research_agent.py    # v2.1: AgentProfile + unified agent node
│   ├── merge.py             # v2.1: 3-stage merge pipeline
│   ├── human_review.py      # v2.1: LangGraph interrupt HITL
│   ├── summary.py
│   ├── critique.py
│   └── final.py
├── evidence/
│   ├── __init__.py
│   ├── dedup.py
│   ├── ranking.py
│   └── cross_validate.py    # v2.1: cross-agent verification
├── citation/
│   ├── __init__.py
│   ├── extractor.py
│   └── formatter.py
├── checkpoint/
│   ├── __init__.py
│   └── manager.py
├── streaming/
│   ├── __init__.py
│   └── renderer.py
└── observability/
    ├── __init__.py
    ├── callbacks.py
    └── metrics.py

server/                     # v2: FastAPI backend (v2.1: +HITL review endpoint)
├── __init__.py
├── tasks.py
├── stream.py
└── routes.py

web/                        # v2: Vue 3 frontend (v2.1: +ReviewPanel)
├── src/
│   ├── App.vue
│   ├── main.js
│   ├── api/index.js
│   └── components/
│       ├── TaskForm.vue
│       ├── TaskList.vue
│       ├── TaskDetail.vue
│       ├── ProgressPanel.vue
│       ├── PlanCard.vue
│       ├── SourcesTable.vue
│       ├── EvidenceList.vue
│       ├── CritiqueDashboard.vue
│       ├── FinalReport.vue
│       └── ReviewPanel.vue    # v2.1: HITL review panel
├── index.html
├── vite.config.js
└── package.json

tests/
├── conftest.py
├── fixtures/mock_llm.py
├── unit/
└── integration/
```
