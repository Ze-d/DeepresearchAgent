# CLAUDE.md

## Project Goal

This project implements a DeepResearch Agent for resume and portfolio demonstration.

The core workflow is:

```text
Plan → Research → Summary → Critique → Final Report
```

v0 should use LangChain and LangGraph instead of building a custom agent framework from scratch.

The default LLM provider is DeepSeek API.

## Development Rules

1. Implement incrementally.
2. Keep each module small and testable.
3. Prefer working MVP over over-engineering.
4. Use LangGraph for workflow orchestration.
5. Use LangChain for LLM, prompt, tool, and output parser integration.
6. Use `langchain-deepseek` for DeepSeek API integration.
7. Do not hardcode API keys.
8. Use `.env` and `.env.example`.
9. Add tests for every core module.
10. Keep CLI runnable at every milestone.

## v0 Scope

v0 must include:

- Typer CLI
- LangGraph StateGraph
- Plan node
- Research node
- Summary node
- Critique node
- Final node
- DeepSeek LLM factory
- Markdown report output
- Local outputs directory

v0 does not need:

- frontend
- user login
- distributed workers
- production database
- complex crawler
- custom agent framework

## Verification Commands

Run before finishing each task:

```bash
uv run pytest
uv run ruff check .
uv run deepresearch --help
```

For full demo:

```bash
uv run deepresearch run "调研 Deep Research Agent 的主流架构"
```
