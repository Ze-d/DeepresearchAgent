# DeepResearch Agent

A LangGraph-based DeepResearch Agent powered by DeepSeek API.

## 1. Features

- **Plan → Research → Summary → Critique → Final Report** workflow
- **LangGraph** stateful orchestration with conditional routing
- **LangChain** prompt/tool/model integration
- **DeepSeek API** support via `langchain-deepseek`
- **Critique-driven iteration** — 3D scoring (fact check / logic coherence / coverage)
- **Evidence quality** — semantic dedup + source authority ranking
- **Citation management** — inline extraction + reference formatting
- **Streaming** — Rich console live display
- **Checkpoint** — SqliteSaver persistence + resume support
- **Observability** — token/latency/error tracking per node
- **Markdown report** output with intermediate artifacts
- **CLI-first** design via Typer + Rich
- **v2: Web UI** — FastAPI + Vue 3 + SSE real-time visualization

## 2. Quick Start

```bash
# Prerequisites: Python 3.11+, uv
uv sync --dev
cp .env.example .env   # then fill in DEEPSEEK_API_KEY
uv run deepresearch --help
uv run deepresearch run "调研 Deep Research Agent 的主流架构"
```

## 3. Project Structure

```text
DeepresearchAgent/
├── AGENTS.md
├── CLAUDE.md
├── README.md
├── README_zh.md
├── roadmap.md
├── pyproject.toml
├── .env.example
│
├── deepresearch/              # Python package
│   ├── config.py              # pydantic-settings
│   ├── state.py               # Pydantic models + AgentState
│   ├── llm.py                 # DeepSeek LLM factory
│   ├── prompts.py             # Centralized prompt templates
│   ├── graph.py               # LangGraph StateGraph
│   ├── cli.py                 # Typer CLI
│   ├── tools.py               # Search + content extraction
│   ├── output.py              # Session dir + JSON/MD writer
│   ├── logging.py             # Structured logging
│   ├── nodes/                 # Plan / Research / Summary / Critique / Final
│   ├── evidence/              # Dedup + Source ranking
│   ├── citation/              # Citation extractor + formatter
│   ├── checkpoint/            # SqliteSaver manager
│   ├── streaming/             # Rich Live renderer
│   └── observability/         # Callbacks + metrics collector
│
├── server/                    # v2: FastAPI backend
│   ├── __init__.py
│   ├── tasks.py
│   ├── stream.py
│   └── routes.py
│
├── web/                       # v2: Vue 3 + Vite frontend
│   └── src/components/
│
├── docs/
│   ├── index.md
│   ├── specs/                 # v0 / v1 / v2 design + plan
│   ├── architecture/          # Overview / LangGraph / State / DeepSeek
│   ├── design/                # Technical route / Prompts / Resume
│   ├── testing/               # Strategy / TDD guide / Test data
│   ├── ai/                    # Coding rules / Context map
│   └── workflows/             # CI/CD
│
├── tests/
└── .github/workflows/
```

## 4. Architecture

```text
User Query
  ↓
Plan Node          — decompose question, generate research plan
  ↓
Research Node      — execute search, extract sources & evidence
  ↓
Summary Node       — synthesize evidence into draft summary
  ↓
Critique Node      — 3D scoring (fact check / logic coherence / coverage)
  ↓
Conditional Route
    ├── Continue Research  →  Research Node (up to max_iterations)
    └── Final Report       →  Final Node
                                  ↓
                            Markdown Report
```

Built on **LangGraph StateGraph** — all intermediate state (plan, sources, evidences, critique, draft) is preserved and traceable.

## 5. Tech Stack

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
| v2 Backend | FastAPI + SSE |
| v2 Frontend | Vue 3 + Vite |

## 6. Output

Each run creates a session directory under `outputs/`:

```text
outputs/
└── session_20260613_001/
    ├── plan.json
    ├── search_results.json
    ├── sources.json
    ├── evidences.json
    ├── draft_summary.md
    ├── critique.json
    ├── final_report.md
    ├── citations.json
    ├── iteration_metrics.json
    ├── metrics.json
    ├── checkpoint.db
    └── run.log
```

## 7. Commands

```bash
uv run pytest                 # Run all tests
uv run ruff check .           # Lint
uv run mypy deepresearch/     # Type check
uv run deepresearch --help    # CLI help
uv run deepresearch run "query" --stream             # Run with live streaming
uv run deepresearch run "query" -v --log-file run.log # Debug mode
uv run deepresearch resume outputs/session_xxx/       # Resume from checkpoint
uv run deepresearch checkpoints outputs/session_xxx/   # List checkpoints
uv run deepresearch serve                             # v2: Start web server
```

## 8. Documentation

See [docs/index.md](docs/index.md) for the full documentation index.

- [Roadmap](roadmap.md)
- [Specs](docs/specs/) — v0 / v1 / v2 design + plan
- [Architecture](docs/architecture/) — LangGraph workflow, state schema, DeepSeek integration
- [Design](docs/design/) — prompts, technical route, resume packaging
- [Testing](docs/testing/) — strategy, TDD guide, test data
