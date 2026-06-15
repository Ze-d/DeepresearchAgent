# Context Map

## Key Files

| File | Purpose |
|------|---------|
| `pyproject.toml` | Project metadata, dependencies, entry points |
| `CLAUDE.md` | AI assistant instructions |
| `AGENTS.md` | Agent conventions |
| `roadmap.md` | Version roadmap |
| `.env.example` | Environment variable template |
| `deepresearch/__init__.py` | Package root |
| `deepresearch/config.py` | pydantic-settings configuration |
| `deepresearch/state.py` | Pydantic data models + AgentState TypedDict |
| `deepresearch/llm.py` | DeepSeek LLM factory |
| `deepresearch/logging.py` | Centralized log config (RichHandler + file) |
| `deepresearch/prompts.py` | Centralized prompt templates |
| `deepresearch/graph.py` | LangGraph StateGraph + conditional routing |
| `deepresearch/nodes/__init__.py` | Node package exports |
| `deepresearch/nodes/plan.py` | Plan node (LLM-powered) |
| `deepresearch/nodes/research.py` | Research node (search + evidence extraction + dedup/ranking) |
| `deepresearch/nodes/summary.py` | Summary node (LLM + citation instructions) |
| `deepresearch/nodes/critique.py` | Critique node (3D scoring + fix rate) |
| `deepresearch/nodes/final.py` | Final report node (LLM + citation formatting) |
| `deepresearch/tools.py` | Search + content extraction tools |
| `deepresearch/output.py` | Session directory + JSON/Markdown writer |
| `deepresearch/cli.py` | Typer CLI entry point + serve command |
| `deepresearch/evidence/` | Evidence dedup + source ranking |
| `deepresearch/citation/` | Citation extractor + formatter |
| `deepresearch/checkpoint/` | SqliteSaver manager + JSON snapshots |
| `deepresearch/streaming/` | Rich Live renderer for graph streaming |
| `deepresearch/observability/` | LangChain callbacks + metrics collector |
| `server/` | v2: FastAPI backend (tasks, SSE streaming, routes) |
| `web/` | v2: Vue 3 + Vite frontend |
| `tests/conftest.py` | Shared pytest fixtures |
| `tests/fixtures/mock_llm.py` | Mock LLM for testing |
| `tests/unit/` | Unit tests |
| `tests/integration/` | Integration tests |

## Key Docs

| File | Purpose |
|------|---------|
| `docs/index.md` | Documentation index |
| `roadmap.md` | Version roadmap (v0–v5) |
| `docs/specs/v0-mvp.md` | v0 design + implementation plan |
| `docs/specs/v1-quality-and-infra.md` | v1 design + plan |
| `docs/specs/v2-web-application.md` | v2 design (FastAPI + Vue 3 + SSE) |
| `docs/architecture/overview.md` | Project positioning, tech stack, module boundaries |
| `docs/architecture/langgraph-workflow.md` | LangGraph StateGraph design |
| `docs/architecture/state-schema.md` | Data model definitions |
| `docs/architecture/deepseek-integration.md` | DeepSeek API integration |
| `docs/design/technical-route.md` | v0 technical decisions |
| `docs/design/prompts.md` | Prompt templates |
| `docs/design/resume-packaging.md` | Resume packaging & interview prep |
| `docs/testing/testing-strategy.md` | Testing layers & principles |
| `docs/testing/tdd-guide.md` | TDD workflow guide |
| `docs/testing/test-data.md` | Test data conventions |
| `docs/ai/coding-rules.md` | Coding conventions + review checklist |
| `docs/workflows/README.md` | CI/CD pipelines & PR template |
