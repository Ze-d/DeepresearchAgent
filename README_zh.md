# DeepResearch Agent

基于 LangGraph 和 DeepSeek API 的深度调研智能体。

## 1. 功能特性

- **Plan → Research → Summary → Critique → Final Report** 多阶段工作流
- **LangGraph** 状态编排，支持条件路由和迭代循环
- **LangChain** 统一管理 Prompt、LLM、Tool 和结构化输出
- **DeepSeek API** 接入，通过 `langchain-deepseek` 集成
- **Critique 驱动迭代** — 自动检查报告质量并补充研究
- **基于证据的总结** — 每个结论关联来源和证据
- **Markdown 报告输出** — 保留完整中间产物（plan、sources、evidences、critique）
- **CLI 优先** — Typer + Rich 命令行体验
- **SDD+TDD 项目结构** — pytest + ruff 测试与代码检查

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
├── AGENTS.md                  # AI 助手指令
├── CLAUDE.md                  # 项目 AI 协作规范
├── README.md                  # 英文说明
├── README_zh.md               # 本文件
├── pyproject.toml             # 项目元数据与依赖
├── .env.example               # 环境变量模板
│
├── deepresearch/              # Python 源码包
│   └── __init__.py
│
├── docs/
│   ├── index.md               # 文档索引（顶层仅此文件）
│   ├── design/                # 设计与规划文档
│   │   ├── 00_project_overview.md   # 项目概述
│   │   ├── 01_v0_technical_route.md # v0 技术路线
│   │   ├── 05_prompts.md            # Prompt 设计
│   │   ├── 07_resume_packaging.md   # 简历包装
│   │   └── 08_roadmap.md            # 路线图
│   ├── architecture/          # 架构与数据模型文档
│   │   ├── overview.md              # 架构概览
│   │   ├── module-boundaries.md     # 模块边界
│   │   ├── 02_langgraph_architecture.md # LangGraph 架构
│   │   ├── 03_deepseek_compatibility.md # DeepSeek 兼容设计
│   │   ├── 04_state_schema.md       # 状态与数据结构
│   │   └── adr/                     # 架构决策记录
│   ├── testing/               # 测试策略与指南
│   │   ├── testing-strategy.md
│   │   ├── tdd-guide.md
│   │   └── test-data.md
│   ├── ai/                    # AI 协作文档
│   │   ├── coding-rules.md
│   │   ├── context-map.md
│   │   ├── review-checklist.md
│   │   └── 06_claude_code_execution_plan.md
│   └── specs/                 # 按功能模块的 spec（待开发时添加）
│
├── tests/
│   ├── conftest.py            # 共享 fixtures
│   ├── unit/                  # 单元测试
│   ├── integration/           # 集成测试
│   └── fixtures/              # 测试数据
│
├── scripts/                   # 构建/测试/部署脚本
└── .github/workflows/         # CI/CD 流水线
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
Critique 节点      — 检查覆盖度、证据质量、遗漏点
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
| 数据建模 | Pydantic + pydantic-settings |
| 配置管理 | python-dotenv (.env) |
| 搜索 | DuckDuckGo / Tavily（可选） |
| 网页抽取 | trafilatura / BeautifulSoup |
| HTTP | httpx |
| 测试 | pytest |
| 代码检查 | ruff |
| 类型检查 | mypy |

## 6. 输出结构

每次运行在 `outputs/` 下生成一个 session 目录：

```text
outputs/
└── session_20260611_001/
    ├── plan.json              # 研究计划和子问题
    ├── search_results.json    # 原始搜索结果
    ├── sources.json           # 整理后的来源列表
    ├── evidences.json         # 抽取的证据条目
    ├── draft_summary.md       # 阶段总结草稿
    ├── critique.json          # Critique 评分与问题列表
    └── final_report.md        # 最终 Markdown 报告
```

## 7. 常用命令

```bash
uv run pytest                 # 运行所有测试
uv run ruff check .           # 代码检查
uv run mypy deepresearch/     # 类型检查
uv run deepresearch --help    # CLI 帮助
```

## 8. 文档

完整文档索引见 [docs/index.md](docs/index.md)。

- [设计文档](docs/design/) — 项目概述、技术路线、Prompt、路线图
- [架构文档](docs/architecture/) — LangGraph 设计、DeepSeek 集成、数据模型
- [测试文档](docs/testing/) — 测试策略、TDD 指南、测试数据规范
- [AI 协作](docs/ai/) — 编码规范、上下文地图、审查清单、执行计划
