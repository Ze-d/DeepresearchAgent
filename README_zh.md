# DeepResearch Agent

基于 LangGraph 和 DeepSeek API 的深度调研智能体。

## 1. 功能特性

- **Plan → Research → Summary → Critique → Final Report** 多阶段工作流
- **LangGraph** 状态编排，支持条件路由和迭代循环
- **LangChain** 统一管理 Prompt、LLM、Tool 和结构化输出
- **DeepSeek API** 接入，通过 `langchain-deepseek` 集成
- **Critique 驱动迭代** — 三维度评分（事实核查/逻辑一致性/覆盖度）
- **Evidence 质量管理** — 语义去重 + 来源权威度评分
- **Citation 管理** — 内联引用提取 + 参考文献格式化
- **Streaming 输出** — Rich 控制台实时渲染
- **Checkpoint 持久化** — SqliteSaver + JSON 快照 + 中断恢复
- **Observability** — 每节点 Token/延迟/错误统计
- **Markdown 报告输出** — 保留完整中间产物
- **CLI 优先** — Typer + Rich 命令行体验
- **v2: Web 界面** — FastAPI + Vue 3 + SSE 实时可视化

## 2. 快速开始

```bash
# 前置条件：Python 3.11+, uv
uv sync --dev
cp .env.example .env        # 编辑填入 DEEPSEEK_API_KEY
uv run deepresearch --help
uv run deepresearch run "调研 Deep Research Agent 的主流架构"
```

## 3. 项目结构

```text
DeepresearchAgent/
├── AGENTS.md
├── CLAUDE.md
├── README.md
├── README_zh.md
├── roadmap.md
├── pyproject.toml
├── .env.example
│
├── deepresearch/              # Python 源码包
│   ├── config.py              # pydantic-settings 配置
│   ├── state.py               # Pydantic 模型 + AgentState
│   ├── llm.py                 # DeepSeek LLM 工厂
│   ├── prompts.py             # Prompt 模板集中管理
│   ├── graph.py               # LangGraph StateGraph
│   ├── cli.py                 # Typer CLI 入口
│   ├── tools.py               # 搜索 + 网页内容抽取
│   ├── output.py              # Session 目录 + JSON/MD 写入
│   ├── logging.py             # 结构化日志
│   ├── nodes/                 # Plan / Research / Summary / Critique / Final
│   ├── evidence/              # 语义去重 + 来源权威度评分
│   ├── citation/              # Citation 提取 + 格式化
│   ├── checkpoint/            # SqliteSaver 管理
│   ├── streaming/             # Rich Live 渲染器
│   └── observability/         # Callbacks + 指标收集器
│
├── server/                    # v2: FastAPI 后端
│   ├── __init__.py
│   ├── tasks.py
│   ├── stream.py
│   └── routes.py
│
├── web/                       # v2: Vue 3 + Vite 前端
│   └── src/components/
│
├── docs/
│   ├── index.md
│   ├── specs/                 # v0 / v1 / v2 设计 + 计划
│   ├── architecture/          # 概览 / LangGraph / State / DeepSeek
│   ├── design/                # 技术路线 / Prompt / 简历
│   ├── testing/               # 测试策略 / TDD 指南 / 测试数据
│   ├── ai/                    # 编码规范 / 上下文地图
│   └── workflows/             # CI/CD
│
├── tests/
└── .github/workflows/
```

## 4. 架构设计

```text
用户输入研究问题
  ↓
Plan 节点          — 拆解问题，生成研究计划
  ↓
Research 节点      — 执行搜索，抽取来源和证据
  ↓
Summary 节点       — 基于证据生成阶段总结
  ↓
Critique 节点      — 三维度评分（事实核查/逻辑一致性/覆盖度）
  ↓
条件路由
    ├── 继续研究   →  Research 节点（最多 max_iterations 轮）
    └── 最终报告   →  Final 节点
                          ↓
                   Markdown 最终报告
```

基于 **LangGraph StateGraph** 构建 — 所有中间状态（研究计划、来源、证据、批判结果、草稿）均保留并可追溯。

## 5. 技术栈

| 类别 | 技术 |
|------|------|
| 语言 | Python 3.11+ |
| 包管理 | uv |
| Agent 编排 | LangGraph |
| LLM 框架 | LangChain |
| LLM 提供商 | DeepSeek API (`langchain-deepseek`) |
| CLI | Typer + Rich |
| 日志 | Rich (RichHandler) + logging |
| 数据建模 | Pydantic + pydantic-settings |
| 配置管理 | python-dotenv (.env) |
| 搜索 | DuckDuckGo / Tavily（可选） |
| 网页抽取 | trafilatura / BeautifulSoup |
| HTTP | httpx |
| 测试 | pytest |
| 代码检查 | ruff |
| 类型检查 | mypy |
| v2 后端 | FastAPI + SSE |
| v2 前端 | Vue 3 + Vite |

## 6. 输出结构

每次运行在 `outputs/` 下生成一个 session 目录：

```text
outputs/
└── session_20260613_001/
    ├── plan.json
    ├── search_results.json
    ├── sources.json
    ├── evidences.json
    ├── draft_summary.md
    ├── critique.json
    ├── final_report.md
    ├── citations.json
    ├── iteration_metrics.json
    ├── metrics.json
    ├── checkpoint.db
    └── run.log
```

## 7. 常用命令

```bash
uv run pytest                 # 运行所有测试
uv run ruff check .           # 代码检查
uv run mypy deepresearch/     # 类型检查
uv run deepresearch --help    # CLI 帮助
uv run deepresearch run "问题" --stream             # 实时流式运行
uv run deepresearch run "问题" -v --log-file run.log # 调试模式
uv run deepresearch resume outputs/session_xxx/      # 从中断恢复
uv run deepresearch checkpoints outputs/session_xxx/  # 列出 checkpoint
uv run deepresearch serve                            # v2: 启动 Web 服务
```

## 8. 文档

完整文档索引见 [docs/index.md](docs/index.md)。

- [路线图](roadmap.md)
- [Specs](docs/specs/) — v0 / v1 / v2 设计 + 实施计划
- [架构文档](docs/architecture/) — 概览、LangGraph 工作流、状态模型、DeepSeek 集成
- [设计文档](docs/design/) — 技术路线、Prompt、简历包装
- [测试文档](docs/testing/) — 策略、TDD 指南、测试数据
