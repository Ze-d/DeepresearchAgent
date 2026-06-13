# Architecture Overview

## Tech Stack

- Python >=3.11
- LangGraph (workflow orchestration)
- LangChain (LLM, prompt, tool integration)
- DeepSeek API (LLM provider)
- Typer (CLI)
- Rich (console logging + formatting)
- Pydantic (data modeling)
- logging (structured logging with RichHandler + file handler)

## Key Design Decisions

- StateGraph-based agent workflow
- Five-node pipeline: Plan → Research → Summary → Critique → Final
- Flat `deepresearch/` Python package (not src layout)
- Markdown report output to local `outputs/` directory
- Centralized logging via `setup_logging()` with test-aware no-op mode
