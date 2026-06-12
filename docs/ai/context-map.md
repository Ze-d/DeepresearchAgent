# Context Map

## Key Files

| File | Purpose |
|------|---------|
| `pyproject.toml` | Project metadata, dependencies, entry points |
| `CLAUDE.md` | AI assistant instructions |
| `.env.example` | Environment variable template |
| `deepresearch/__init__.py` | Package root |
| `deepresearch/config.py` | pydantic-settings configuration (Phase 1) |
| `deepresearch/state.py` | Pydantic data models + AgentState TypedDict (Phase 1) |
| `deepresearch/llm.py` | DeepSeek LLM factory (Phase 2) |
| `deepresearch/prompts.py` | Centralized prompt templates (Phase 4+) |
| `deepresearch/graph.py` | LangGraph StateGraph + conditional routing (Phase 3) |
| `deepresearch/nodes/__init__.py` | Node package |
| `deepresearch/nodes/plan.py` | Plan node (Phase 3 mock → Phase 4 real) |
| `deepresearch/nodes/research.py` | Research node (Phase 3 mock → Phase 5 real) |
| `deepresearch/nodes/summary.py` | Summary node (Phase 3 mock → Phase 6 real) |
| `deepresearch/nodes/critique.py` | Critique node (Phase 3 mock → Phase 6 real) |
| `deepresearch/nodes/final.py` | Final report node (Phase 3 mock → Phase 6 real) |
| `deepresearch/tools.py` | Search + content extraction tools (Phase 5) |
| `deepresearch/output.py` | Session directory + JSON/Markdown writer (Phase 6) |
| `deepresearch/cli.py` | Typer CLI entry point (Phase 3) |
| `tests/conftest.py` | Shared pytest fixtures |
| `tests/fixtures/mock_llm.py` | Mock LLM for testing |
| `tests/unit/` | Unit tests |
| `tests/integration/` | Integration tests (Phase 7) |

## Key Docs

| File | Purpose |
|------|---------|
| `docs/index.md` | Documentation index |
| `docs/design/00_project_overview.md` | Project positioning & goals |
| `docs/design/01_v0_technical_route.md` | v0 technical decisions |
| `docs/design/05_prompts.md` | Prompt templates |
| `docs/design/08_roadmap.md` | Version roadmap |
| `docs/architecture/02_langgraph_architecture.md` | LangGraph design |
| `docs/architecture/03_deepseek_compatibility.md` | DeepSeek integration |
| `docs/architecture/04_state_schema.md` | Data model definitions |
| `docs/architecture/module-boundaries.md` | Module dependency map |
| `docs/ai/v0_execution_plan.md` | **v0 phase-by-phase execution plan** |
| `docs/ai/06_claude_code_execution_plan.md` | Original Claude Code plan |
