# Module Boundaries

## Modules

| Module | Responsibility | Dependencies |
|--------|---------------|--------------|
| `cli` | CLI entry point (Typer) | `graph` |
| `graph` | LangGraph StateGraph definition | `nodes`, `state` |
| `state` | Pydantic state schema | none |
| `nodes.plan` | Plan node logic | `llm`, `state` |
| `nodes.research` | Research node logic | `llm`, `tools`, `state` |
| `nodes.summary` | Summary node logic | `llm`, `state` |
| `nodes.critique` | Critique node logic | `llm`, `state` |
| `nodes.final` | Final report node | `state` |
| `llm` | DeepSeek LLM factory | none |
| `logging` | Centralized log config (console + file) | none |
| `tools` | Search/web tools | none |
| `output` | Markdown report writer | `state` |
