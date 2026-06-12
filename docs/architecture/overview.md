# Architecture Overview

## Tech Stack

- Python >=3.11
- LangGraph (workflow orchestration)
- LangChain (LLM, prompt, tool integration)
- DeepSeek API (LLM provider)
- Typer (CLI)
- Pydantic (data modeling)

## Key Design Decisions

- StateGraph-based agent workflow
- Five-node pipeline: Plan → Research → Summary → Critique → Final
- Flat `deepresearch/` Python package (not src layout)
- Markdown report output to local `outputs/` directory
