# Coding Rules

## Conventions

- Follow CLAUDE.md development rules
- Use type hints for all public functions
- Use Pydantic for data models
- Use LangChain patterns for LLM integration
- Keep nodes as pure functions: `(State) -> dict`
- Use `uv run` for all project commands

## Pre-Commit Review Checklist

- [ ] Tests pass (`uv run pytest`)
- [ ] Lint passes (`uv run ruff check .`)
- [ ] CLI runs (`uv run deepresearch --help`)
- [ ] No hardcoded secrets
- [ ] Follows CLAUDE.md conventions
- [ ] Type hints on public functions
- [ ] New modules have tests
