# v0 执行计划

> 基于 [design/](../design/) 和 [architecture/](../architecture/) 文档，面向 Claude Code 执行的 v0 分阶段实现计划。
>
> 每个阶段独立可运行、可测试、可提交。

## 执行原则

1. **TDD 先行** — 先写测试，确认失败，再写实现
2. **每阶段可提交** — 完成后 `uv run pytest && uv run ruff check .` 通过
3. **Mock 优先于真实 API** — 先用 mock 跑通流程，再接入 DeepSeek
4. **最小增量** — 每阶段只产出一个核心模块

## 项目当前状态

| 项目 | 状态 |
|------|------|
| pyproject.toml | ✅ 依赖已声明 |
| .env.example | ✅ 已配置 |
| .gitignore | ✅ 已创建 |
| 目录骨架 | ✅ docs/design/, docs/architecture/, docs/testing/, docs/ai/, tests/ |
| 源码 | ❌ 仅有 `deepresearch/__init__.py` |
| 测试 | ❌ 仅有 `tests/conftest.py` |

---

## Phase 1：Config + State Models

**目标**：建立配置系统和数据模型，这是所有后续模块的基石。

### 文件清单

| 操作 | 文件 | 说明 |
|------|------|------|
| 新建 | `deepresearch/config.py` | pydantic-settings 配置类 |
| 新建 | `deepresearch/state.py` | Pydantic 数据模型 + AgentState TypedDict |
| 新建 | `tests/unit/test_config.py` | 配置加载测试 |
| 新建 | `tests/unit/test_state.py` | 数据模型序列化/校验测试 |

### 具体任务

1. **`deepresearch/config.py`**
   ```python
   from pydantic_settings import BaseSettings

   class Settings(BaseSettings):
       model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

       deepseek_api_key: str = ""
       deepseek_model: str = "deepseek-chat"
       search_provider: str = "duckduckgo"
       tavily_api_key: str = ""
       max_iterations: int = 2
       max_search_results: int = 5
       output_dir: str = "outputs"
       temperature: float = 0.0
       max_retries: int = 2
   ```

2. **`deepresearch/state.py`**
   - `SubQuestion`, `ResearchPlan` — 研究计划
   - `Source` — 来源
   - `Evidence` — 证据
   - `CritiqueIssue`, `CritiqueResult` — 批判结果
   - `FinalReport` — 最终报告
   - `AgentState(TypedDict)` — LangGraph 全局状态

3. **TDD 步骤**
   - Red: 写 `test_config.py` → `uv run pytest tests/unit/test_config.py` 失败
   - Green: 实现 `config.py` → 测试通过
   - Red: 写 `test_state.py` → 失败
   - Green: 实现 `state.py` → 测试通过
   - Refactor: 检查类型提示、import 整理

### 验收标准

```bash
uv run pytest tests/unit/test_config.py tests/unit/test_state.py  # 全部通过
```

---

## Phase 2：LLM Factory

**目标**：创建 LLM 工厂，支持 DeepSeek 和 Mock 两种模式。

### 文件清单

| 操作 | 文件 | 说明 |
|------|------|------|
| 新建 | `deepresearch/llm.py` | `build_llm()` 工厂函数 |
| 新建 | `tests/unit/test_llm.py` | LLM 工厂测试 |
| 新建 | `tests/fixtures/mock_llm.py` | Mock LLM（测试用） |

### 具体任务

1. **`deepresearch/llm.py`**
   ```python
   from langchain_deepseek import ChatDeepSeek
   from langchain_core.language_models import BaseChatModel
   from deepresearch.config import settings

   def build_llm() -> BaseChatModel:
       """返回 DeepSeek Chat 实例。若 API key 未配置则抛出明确错误。"""
       if not settings.deepseek_api_key:
           raise ValueError("DEEPSEEK_API_KEY not set. Copy .env.example to .env and fill in.")
       return ChatDeepSeek(
           model=settings.deepseek_model,
           temperature=settings.temperature,
           max_retries=settings.max_retries,
       )
   ```

2. **`tests/fixtures/mock_llm.py`** — Fake LLM，返回预设 JSON，用于不依赖网络的测试

3. **TDD 步骤**
   - Red: `test_llm.py` 测试 build_llm 无 API key 时抛错
   - Green: 实现基础 build_llm
   - Red: 测试 mock LLM 行为
   - Green: 实现 mock_llm fixture

### 验收标准

```bash
uv run pytest tests/unit/test_llm.py  # 全部通过
uv run python -c "from deepresearch.llm import build_llm; print(build_llm())"  # 有 API key 时成功
```

---

## Phase 3：CLI + Graph Skeleton（Mock Nodes）

**目标**：搭建 Typer CLI 和 LangGraph StateGraph，用 mock node 跑通全流程。

### 文件清单

| 操作 | 文件 | 说明 |
|------|------|------|
| 新建 | `deepresearch/cli.py` | Typer CLI 入口 |
| 新建 | `deepresearch/graph.py` | StateGraph 定义 + 条件路由 |
| 新建 | `deepresearch/nodes/__init__.py` | 节点包 |
| 新建 | `deepresearch/nodes/plan.py` | plan_node（mock） |
| 新建 | `deepresearch/nodes/research.py` | research_node（mock） |
| 新建 | `deepresearch/nodes/summary.py` | summary_node（mock） |
| 新建 | `deepresearch/nodes/critique.py` | critique_node（mock） |
| 新建 | `deepresearch/nodes/final.py` | final_node（mock） |
| 新建 | `tests/unit/test_graph.py` | Graph 编译 + 全流程测试 |
| 新建 | `tests/unit/test_cli.py` | CLI 基础测试 |

### 具体任务

1. **`deepresearch/graph.py`** — 定义 5 个节点 + 条件路由 `route_after_critique`
2. **`deepresearch/nodes/*.py`** — 每个 node 是 `(AgentState) -> dict` 的纯函数，先写死返回数据
3. **`deepresearch/cli.py`** — `deepresearch run <query>` 调用 `graph.compile().invoke(initial_state)`
4. **条件路由逻辑**：`critique.pass == True` 或 `iteration >= max_iterations` → final，否则 → research

### Mock 行为

| Node | Mock 输出 |
|------|----------|
| plan | 返回固定 `research_plan` dict |
| research | 追加固定 `sources` 和 `evidences` |
| summary | 返回固定 `draft_summary` 字符串 |
| critique | 返回 `{"pass": True, "score": 0.9, "issues": [], "new_search_queries": []}` |
| final | 返回固定 `final_report` Markdown |

### TDD 步骤

- Red: `test_graph.py` → `uv run pytest tests/unit/test_graph.py` 失败
- Green: 实现 `graph.py` + `nodes/*.py` → 测试通过
- Red: `test_cli.py` → 失败
- Green: 实现 `cli.py` → 测试通过

### 验收标准

```bash
uv run pytest                                  # 全部通过
uv run deepresearch --help                     # 显示 CLI 帮助
uv run deepresearch run "测试问题"               # 用 mock node 跑完全流程，打印最终报告
```

---

## Phase 4：Plan Node（真实 LLM）

**目标**：将 plan_node 从 mock 替换为真实 DeepSeek 调用，使用 Planner Prompt 生成 ResearchPlan。

### 文件清单

| 操作 | 文件 | 说明 |
|------|------|------|
| 修改 | `deepresearch/nodes/plan.py` | 真实 LLM 调用 + JSON 解析 |
| 新建 | `deepresearch/prompts.py` | Prompt 模板集中管理 |
| 新建 | `tests/unit/test_plan_node.py` | Planner 测试 |
| 新建 | `tests/unit/test_prompts.py` | Prompt 模板测试 |

### 具体任务

1. **`deepresearch/prompts.py`** — 集中定义所有 Prompt 模板（使用 LangChain `ChatPromptTemplate`）
2. **`deepresearch/nodes/plan.py`** — 调用 LLM → JSON 解析 → Pydantic 校验 → 返回 state 更新
3. **JSON fallback**：若 LLM 返回格式不合法，用正则提取 JSON 块，重试一次；仍失败则返回错误

### 测试策略

- 使用 `tests/fixtures/mock_llm.py` 的 Mock LLM 测试 plan_node 逻辑
- 测试正常 JSON 返回
- 测试畸形 JSON fallback 修复
- 测试空响应错误处理

### 验收标准

```bash
uv run pytest tests/unit/test_plan_node.py tests/unit/test_prompts.py  # 全部通过
```

---

## Phase 5：Research Node（搜索 + 资料抽取）

**目标**：实现搜索工具和 evidence 抽取。

### 文件清单

| 操作 | 文件 | 说明 |
|------|------|------|
| 新建 | `deepresearch/tools.py` | 搜索工具封装 |
| 修改 | `deepresearch/nodes/research.py` | 真实搜索 + 内容抽取 + evidence 抽取 |
| 新建 | `tests/unit/test_tools.py` | 搜索工具测试 |
| 新建 | `tests/unit/test_research_node.py` | Research 节点测试 |

### 具体任务

1. **`deepresearch/tools.py`**
   - 封装 DuckDuckGo 搜索（`duckduckgo_search` 包）
   - 可选 Tavily（有 API key 时优先）
   - 网页内容抽取（`trafilatura`）
   - 结果格式化为 `Source` 列表

2. **`deepresearch/nodes/research.py`**
   - 读取 `state["research_plan"]["sub_questions"]`
   - 按优先级遍历，执行搜索
   - 调用 LLM 从 source content 抽取 evidence
   - 返回 `{"sources": [...], "evidences": [...], "search_results": [...]}`

### 测试策略

- Mock 搜索 API 返回，测试 Source 格式化
- Mock LLM 返回，测试 evidence 抽取逻辑
- 空搜索结果处理

### 验收标准

```bash
uv run pytest tests/unit/test_tools.py tests/unit/test_research_node.py  # 全部通过
```

---

## Phase 6：Summary + Critique + Final + Output

**目标**：实现剩余三个核心节点和报告输出模块，完成完整闭环。

### 文件清单

| 操作 | 文件 | 说明 |
|------|------|------|
| 修改 | `deepresearch/nodes/summary.py` | 真实 LLM 调用 |
| 修改 | `deepresearch/nodes/critique.py` | 真实 LLM 调用 |
| 修改 | `deepresearch/nodes/final.py` | 真实 LLM 调用 |
| 新建 | `deepresearch/output.py` | Session 目录 + JSON/Markdown 写入 |
| 新建 | `tests/unit/test_summary_node.py` | |
| 新建 | `tests/unit/test_critique_node.py` | |
| 新建 | `tests/unit/test_final_node.py` | |
| 新建 | `tests/unit/test_output.py` | |

### 具体任务

1. **summary_node** — 使用 Summary Prompt，Mock LLM 测试
2. **critique_node** — 使用 Critique Prompt，Mock LLM 测试。`iteration += 1`
3. **final_node** — 使用 Finalizer Prompt，Mock LLM 测试
4. **`deepresearch/output.py`**
   - `init_session_dir() -> Path` — 创建 `outputs/session_YYYYMMDD_HHMMSS/`
   - `save_json(data, path)` — 保存 JSON
   - `save_markdown(content, path)` — 保存 Markdown
   - `save_all(state, session_dir)` — 保存所有中间产物

### 验收标准

```bash
uv run pytest tests/unit/test_summary_node.py tests/unit/test_critique_node.py tests/unit/test_final_node.py tests/unit/test_output.py  # 全部通过
```

---

## Phase 7：Integration + Polish

**目标**：集成测试、端到端 Demo、文档更新。

### 文件清单

| 操作 | 文件 | 说明 |
|------|------|------|
| 新建 | `tests/integration/test_workflow.py` | 全流程集成测试 |
| 修改 | `README.md` | 更新运行说明、Demo 截图 |
| 修改 | `docs/ai/context-map.md` | 补充新增文件 |

### 具体任务

1. **集成测试** — 用 Mock LLM + Mock Search 跑 `graph.invoke({"user_query": "test"})`，验证：
   - 5 个节点全部执行
   - 状态在各节点间正确传递
   - 条件路由正确（pass → final, !pass → research loop）
   - 最大迭代次数生效
   - output 目录生成正确

2. **真实 Demo**（需配置 `DEEPSEEK_API_KEY`）
   ```bash
   uv run deepresearch run "调研 Deep Research Agent 的主流架构"
   ```

### 验收标准

```bash
uv run pytest                                # 全部通过（单元 + 集成）
uv run ruff check .                          # 零警告
uv run deepresearch --help                   # CLI 帮助正常
uv run deepresearch run "测试问题"            # 完整流程跑通，outputs/ 生成报告
```

---

## 文件依赖图

```text
Phase 1: config.py ← state.py
              ↓
Phase 2:    llm.py
              ↓
Phase 3: prompts.py → nodes/*.py → graph.py → cli.py
              ↓
Phase 4: nodes/plan.py (真实 LLM)
              ↓
Phase 5: tools.py → nodes/research.py (搜索 + 抽取)
              ↓
Phase 6: nodes/summary.py, nodes/critique.py, nodes/final.py, output.py
              ↓
Phase 7: 集成测试 + Demo
```

## 每阶段通用检查清单

- [ ] `uv run pytest` 全部通过
- [ ] `uv run ruff check .` 零警告
- [ ] 新增模块有 `__init__.py` 导出
- [ ] 无硬编码 API key
- [ ] 类型提示完整
- [ ] `git add -A && git commit -m "feat: Phase X — <描述>"` 可提交

## 不在此计划的内容（v0 非目标）

- FastAPI / SSE / 前端
- 多 Agent 并发
- RAG / 本地知识库
- MCP 工具
- LangSmith / checkpoint / streaming
- 分布式 / 多用户
