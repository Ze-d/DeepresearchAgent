# DeepResearch Agent

A LangGraph-based DeepResearch Agent powered by DeepSeek API.

## 1. Features

- Plan → Research → Summary → Critique workflow
- LangGraph stateful orchestration
- LangChain prompt/tool/model integration
- DeepSeek API support
- Evidence-based summarization
- Critique-driven refinement
- Markdown report output
- CLI-first design

## 2. Quick Start

```bash
uv sync
cp .env.example .env
uv run deepresearch run "调研 Deep Research Agent 的主流架构"
```

## 3. Architecture

```text
User Query
  ↓
Plan Node
  ↓
Research Node
  ↓
Summary Node
  ↓
Critique Node
  ↓
Conditional Route
    ├── Continue Research
    └── Final Report
```

## 4. Tech Stack

- Python
- LangChain
- LangGraph
- DeepSeek API
- Typer
- Pydantic
- pytest
- ruff

## 5. Output

```text
outputs/
└── session_xxx/
    ├── plan.json
    ├── sources.json
    ├── evidences.json
    ├── critique.json
    └── final_report.md
```

## 6. Documentation

See the `docs/` directory:

```text
docs/
├── 00_project_overview.md
├── 01_v0_technical_route.md
├── 02_langgraph_architecture.md
├── 03_deepseek_compatibility.md
├── 04_state_schema.md
├── 05_prompts.md
├── 06_claude_code_execution_plan.md
├── 07_resume_packaging.md
└── 08_roadmap.md
```
