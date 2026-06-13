# v0 技术路线

## 1. 技术选型

| 模块 | 技术 |
|---|---|
| 语言 | Python 3.11+ |
| 包管理 | uv |
| Agent 编排 | LangGraph |
| LLM 应用框架 | LangChain |
| 默认模型 | DeepSeek API |
| DeepSeek 接入 | langchain-deepseek |
| CLI | Typer + Rich |
| 日志 | Rich (RichHandler) + logging |
| 配置管理 | pydantic-settings |
| 数据模型 | Pydantic |
| 搜索工具 | Tavily / DuckDuckGo fallback |
| 网页抽取 | trafilatura / BeautifulSoup |
| 报告格式 | Markdown |
| 测试 | pytest |
| 代码检查 | ruff |

## 2. 为什么 v0 使用 LangChain + LangGraph

v0 的目标是快速做出可运行闭环，而不是重复造轮子。

LangChain 负责：

- LLM 调用
- PromptTemplate
- Tool 封装
- Output Parser
- 模型 Provider 切换

LangGraph 负责：

- 工作流图编排
- 状态传递
- 条件路由
- 循环控制
- 后续可扩展 checkpoint / streaming / human-in-the-loop

## 3. v0 工作流

```text
START
  ↓
plan_node
  ↓
research_node
  ↓
summary_node
  ↓
critique_node
  ↓
route_after_critique
    ├── continue_research → research_node
    └── final_report → final_node
  ↓
END
```

## 4. v0 最小闭环

v0 只需要实现：

1. 用户输入 query
2. Planner 生成 research plan
3. Researcher 根据 plan 生成 search queries 并调用搜索工具
4. Researcher 抽取 sources 和 evidence
5. Summarizer 根据 evidence 生成 draft summary
6. Critic 检查 draft 是否足够
7. 如果不足，补充 research tasks
8. 如果足够，生成 final report

## 5. v0 输出结构

```text
outputs/
└── session_xxx/
    ├── plan.json
    ├── sources.json
    ├── evidences.json
    ├── critique.json
    └── final_report.md
```

## 6. 推荐运行方式

```bash
uv sync
cp .env.example .env
uv run deepresearch run "调研 Deep Research Agent 的主流架构"
```

## 7. 技术路线总结

```text
v0：LangChain + LangGraph + DeepSeek API (CLI MVP)
    ↓
v1：研究质量增强 (Evidence/Citation/Critique) + 工程基础设施 (Checkpoint/Streaming/Observability)
    ↓
v2：Web 应用化 (FastAPI + Vue 3 + SSE)
    ↓
v2.1：多 Agent 并发研究 (Paper/GitHub/Blog/Docs agents)
    ↓
v3：本地知识库 + RAG + MCP 集成
    ↓
v4：生产级增强 (Docker/Redis/PostgreSQL/Auth)
    ↓
v5：招聘展示增强 (截图/Demo/Benchmark/面试问答)
```
