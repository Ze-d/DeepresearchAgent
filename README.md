# DeepResearch Agent

A LangGraph-based DeepResearch Agent powered by DeepSeek API.

## 1. Features

- **Plan → Research → Summary → Critique → Final Report** workflow
- **LangGraph** stateful orchestration with conditional routing
- **LangChain** prompt/tool/model integration
- **DeepSeek API** support via `langchain-deepseek`
- **Critique-driven iteration** — automatic quality check and re-research
- **Evidence-based summarization** with source tracking
- **Markdown report** output with intermediate artifacts
- **CLI-first** design via Typer + Rich
- **Structured logging** — Rich console output + file persistence, `--verbose` debug mode
- **SDD+TDD** project structure with pytest and ruff

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
├── AGENTS.md                  # AI assistant conventions
├── CLAUDE.md                  # Project instructions for AI
├── README.md                  # This file
├── pyproject.toml             # Project metadata & dependencies
├── .env.example               # Environment variable template
│
├── deepresearch/              # Python package
│   └── __init__.py
│
├── docs/
│   ├── index.md               # Documentation index (only top-level doc)
│   ├── design/                # Design & planning docs
│   │   ├── 00_project_overview.md
│   │   ├── 01_v0_technical_route.md
│   │   ├── 05_prompts.md
│   │   ├── 07_resume_packaging.md
│   │   └── 08_roadmap.md
│   ├── architecture/          # Architecture & data model docs
│   │   ├── overview.md
│   │   ├── module-boundaries.md
│   │   ├── 02_langgraph_architecture.md
│   │   ├── 03_deepseek_compatibility.md
│   │   ├── 04_state_schema.md
│   │   └── adr/
│   ├── testing/               # Testing strategy & guides
│   │   ├── testing-strategy.md
│   │   ├── tdd-guide.md
│   │   └── test-data.md
│   ├── ai/                    # AI collaboration docs
│   │   ├── coding-rules.md
│   │   ├── context-map.md
│   │   ├── review-checklist.md
│   │   └── 06_claude_code_execution_plan.md
│   └── specs/                 # Feature specs (per-module)
│
├── tests/
│   ├── conftest.py            # Shared fixtures
│   ├── unit/                  # Unit tests
│   ├── integration/           # Integration tests
│   └── fixtures/              # Test data
│
├── scripts/                   # Build/test/deploy scripts
└── .github/workflows/         # CI/CD pipelines
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
Critique Node      — check coverage, evidence quality, gaps
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

## 6. Output

Each run creates a session directory under `outputs/`:

```text
outputs/
└── session_20260611_001/
    ├── plan.json              # Research plan & sub-questions
    ├── search_results.json    # Raw search results
    ├── sources.json           # Curated source list
    ├── evidences.json         # Extracted evidence items
    ├── draft_summary.md       # Intermediate summary
    ├── critique.json          # Critique findings & score
    └── final_report.md        # Final Markdown report
```

## 7. Commands

```bash
uv run pytest                 # Run all tests
uv run ruff check .           # Lint
uv run mypy deepresearch/     # Type check
uv run deepresearch --help    # CLI help
uv run deepresearch run "query" -v            # Debug mode (verbose logging)
uv run deepresearch run "query" --log-file outputs/run.log  # Persist logs to file
```

## 8. Documentation

See [docs/index.md](docs/index.md) for the full documentation index.

- [Design Docs](docs/design/) — project overview, technical route, prompts, roadmap
- [Architecture Docs](docs/architecture/) — LangGraph design, DeepSeek integration, state schema
- [Testing Docs](docs/testing/) — strategy, TDD guide, test data conventions
- [AI Collaboration](docs/ai/) — coding rules, context map, review checklist, execution plan
