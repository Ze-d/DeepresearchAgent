# v1 研究质量与工程基础设施增强 — 设计文档

> **状态:** 待实施 | **日期:** 2026-06-13 | **基于:** v0 MVP (Phase 1-7 完成)

## 1. 目标

v1 在 v0 完整闭环基础上，增强**研究质量**（Evidence / Citation / Critique）和**工程基础设施**（Checkpoint / Streaming / Observability）。不做前端和 API。

### 1.1 范围

| 优先级 | 领域 | 模块 |
|--------|------|------|
| B | Evidence 质量 | 语义去重、Source 权威度评分、Confidence 校准 |
| C | Citation 管理 | 内联引用、自动编号、参考文献格式化、溯源链接 |
| D | Critique 增强 | 三维评分、Fix rate 追踪、迭代间质量对比 |
| A | Checkpoint | SqliteSaver 持久化、中断恢复、session 管理 |
| B | Streaming | LangGraph stream_mode + Rich 实时渲染 |
| C | Observability | LangChain Callback + Token/延迟/错误统计 |

### 1.2 非范围

- FastAPI / SSE / 前端（推迟到 v2）
- 多 Agent 并发（推迟到 v3）
- RAG / MCP / 本地知识库（推迟到 v4）
- sentence-transformers / 新重量级依赖
- LangSmith 云服务（使用自建 Callback 替代）

---

## 2. 架构变更

### 2.1 新增模块

```
deepresearch/
├── evidence/          ← 新增  Evidence 质量管理
│   ├── __init__.py
│   ├── dedup.py               语义去重（DeepSeek API 批处理）
│   └── ranking.py             Source 权威度多信号评分
│
├── citation/          ← 新增  Citation 管理
│   ├── __init__.py
│   ├── extractor.py           从 Markdown 提取 citation
│   └── formatter.py           参考文献列表格式化
│
├── checkpoint/        ← 新增  Checkpoint 管理
│   ├── __init__.py
│   └── manager.py             SqliteSaver 封装 + session 恢复
│
├── streaming/         ← 新增  Streaming 输出
│   ├── __init__.py
│   └── renderer.py            Rich Panel 实时渲染
│
└── observability/     ← 新增  可观测性
    ├── __init__.py
    ├── callbacks.py           LangChain BaseCallbackHandler
    └── metrics.py             Token/延迟/错误统计
```

### 2.2 修改模块

| 模块 | 变更内容 |
|------|---------|
| `config.py` | 新增 checkpoint、streaming、ranking、dedup 配置项 |
| `state.py` | 新增 Citation、IterationMetrics、CheckpointInfo 字段 |
| `prompts.py` | Summary/Critique/Finalizer Prompt 增强 citation 和多维评分指令 |
| `graph.py` | 接入 SqliteSaver、支持 stream_mode |
| `cli.py` | 新增 `resume` 命令、`--stream`/`--no-stream` 选项 |
| `tools.py` | 搜索结果去重、来源类型自动识别 |
| `output.py` | 新增 citations.json、iteration_metrics.json、metrics.json 输出 |
| `nodes/research.py` | 接入 source ranking + evidence dedup |
| `nodes/summary.py` | 要求输出带 citation 标记的总结 |
| `nodes/critique.py` | 三维评分 + fix rate 计算 |
| `nodes/final.py` | Citation 格式化 + 参考文献列表 |

### 2.3 State 新增字段

```python
class AgentState(TypedDict):
    # v0 字段（不变）
    user_query: str
    research_plan: dict | None
    search_results: list[dict]
    sources: list[dict]
    evidences: list[dict]
    draft_summary: str | None
    critique_result: dict | None
    final_report: str | None
    iteration: int
    max_iterations: int
    status: str
    errors: list[str]

    # v1 新增
    citations: list[dict]              # 提取的 Citation 列表
    iteration_metrics: list[dict]      # 每轮迭代指标（含 fix_rate）
    checkpoint_id: str | None          # 当前 checkpoint ID
```

### 2.4 数据流

```text
                          ┌──────────────────────────┐
                          │   Observability Layer    │
                          │   (callbacks + metrics)  │
                          └──────────┬───────────────┘
                                     │ 贯穿全流程
                                     ▼
START → Plan → Research → Summary → Critique ──→ Final → END
                 │           │           │            │
                 ▼           ▼           ▼            ▼
            evidence/    citation/   critique      citation/
            dedup.py     extractor   三维+fix rate  formatter.py
            ranking.py
                 │
                 ▼
            checkpoint/
            manager.py  ← 每个 node 后可持久化
```

---

## 3. Evidence 质量管理 (`evidence/`)

### 3.1 语义去重 (`dedup.py`)

**策略**: 不引入 embedding 模型，用 DeepSeek API 做语义判断。

**流程**:
```text
evidences (N条) → 按 source_id 分组 → 组内两两比较 → 合并重复项（保留 confidence 更高者）
```

**Prompt 设计**:
```text
你是一个文本去重助手。以下是两条 evidence，判断它们是否表达相同的信息。

Evidence A:
claim: "{claim_a}"
quote: "{quote_a}"

Evidence B:
claim: "{claim_b}"
quote: "{quote_b}"

只回答 YES 或 NO。如果两条 evidence 的核心信息一致（即使措辞不同），回答 YES。
```

**核心函数**:
- `deduplicate_evidences(evidences, llm) -> list[dict]` — 入口函数
- `_group_by_source(evidences) -> dict[str, list[dict]]` — 按 source_id 分组
- `_dedup_within_group(group, llm) -> list[dict]` — 组内去重
- `_are_duplicates(ev_a, ev_b, llm) -> bool` — LLM 判断两两重复

**成本控制**:
- 仅对同一 `source_id` 内的 evidence 去重（不跨来源比较）
- 配置项 `dedup_max_calls_per_run: int = 20`
- 每轮迭代最多 20 次 LLM 去重调用

### 3.2 Source 权威度评分 (`ranking.py`)

**多信号规则评分**（纯规则，不调 LLM）：

| 信号 | 权重 | 评分规则 |
|------|------|---------|
| 域名权威 | 40% | `.edu`/`.gov` = 1.0, 知名技术域(arxiv.org, github.com, stackoverflow.com) = 0.8, `.org` = 0.6, `.com`/`.io` = 0.5, 论坛/社交 = 0.2 |
| 来源类型 | 30% | 学术论文 = 1.0, 官方文档 = 0.9, 技术博客 = 0.6, 新闻报道 = 0.5, 论坛/问答 = 0.3, 未知 = 0.4 |
| 内容时效 | 20% | 1年内 = 1.0, 3年内 = 0.7, 5年以上 = 0.4, 未知 = 0.5 |
| 内容丰富度 | 10% | content 长度 > 2000字符 = 1.0, > 500 = 0.6, < 500 = 0.3 |

**核心函数**:
- `rank_sources(sources) -> list[dict]` — 入口，计算评分后排序
- `_classify_domain(url) -> tuple[str, float]` — 域名分类
- `_classify_source_type(snippet, content) -> tuple[str, float]` — 类型推断
- `_estimate_freshness(content) -> float` — 日期提取 + 时效计算

**可配置**: 域名权威表存储为代码内常量 `DOMAIN_AUTHORITY_MAP`，后续可迁移到配置文件。

---

## 4. Citation 管理 (`citation/`)

### 4.1 设计理念

用 **Prompt 约定 + 正则提取**，不在代码里做 NLP 解析。

### 4.2 引用格式约定

Summary 和 Finalizer 的 Prompt 要求 LLM 使用统一格式：

```markdown
[来源: <简短标题>](<URL>)
```

### 4.3 提取器 (`extractor.py`)

```python
@dataclass
class Citation:
    id: int              # [1], [2], ...
    title: str           # 简短标题
    url: str             # 来源 URL
    context: str         # 引用上下文（前后各 50 字符）

def extract_citations(text: str) -> list[Citation]:
    """正则提取所有 [来源: xxx](url) 并分配编号"""

def validate_citations(citations: list[Citation], sources: list[dict]) -> list[Citation]:
    """验证 URL 在 sources 中，标记孤立引用"""
```

### 4.4 格式化器 (`formatter.py`)

```python
def format_inline_citations(text: str, citations: list[Citation]) -> str:
    """将 [来源: xxx](url) 替换为上标 [1][2]"""

def format_reference_list(citations: list[Citation]) -> str:
    """生成参考文献列表"""

def merge_citations_into_report(report: str, citations: list[Citation]) -> str:
    """将参考文献列表追加到报告末尾"""
```

### 4.5 集成点

| 节点 | 集成 |
|------|------|
| `summary_node` | Prompt 要求用 `[来源: title](url)` 格式 |
| `final_node` | Prompt 要求同格式 + 列出参考文献 |
| `output.py` | `save_all()` 增加 `citations.json` |

### 4.6 输出

Final report 末尾追加：

```markdown
## 参考文献

[1] LangGraph Documentation — https://langchain-ai.github.io/langgraph/
[2] Deep Research Agent Survey — https://arxiv.org/abs/2401.xxx
```

---

## 5. Critique 增强

### 5.1 三维度评分模型

| 维度 | 标识 | 内容 |
|------|------|------|
| 事实核查 | `fact_check` | claim 是否有 evidence 支撑？无来源断言？ |
| 逻辑一致性 | `logic_coherence` | 论证自洽？不同部分矛盾？ |
| 覆盖度 | `coverage` | 所有子问题已回答？遗漏维度？ |

**Pass 条件**: 三个维度全部 ≥ 0.7

### 5.2 数据结构

```json
{
  "pass": false,
  "overall_score": 0.65,
  "dimensions": {
    "fact_check": {"score": 0.8, "issues": ["问题1"], "status": "pass"},
    "logic_coherence": {"score": 0.6, "issues": ["问题2"], "status": "fail"},
    "coverage": {"score": 0.55, "issues": ["问题3"], "status": "fail"}
  },
  "issues": [...],
  "new_search_queries": [...]
}
```

### 5.3 Fix Rate 追踪

```python
def compute_fix_rate(prev_issues: list[dict], current_issues: list[dict]) -> float:
    """对比两轮 issues，计算修复率。
    通过 issue type + description 模糊匹配判断是否"同一问题"。
    """

# State 存储 per-iteration metrics:
iteration_metrics: [{
    "iteration": 1,
    "overall_score": 0.65,
    "dimensions": {...},
    "issues_count": 3,
    "fix_rate": null,
    "tokens_used": 15000,
    "latency_ms": 3200,
}]
```

### 5.4 CLI 展示

```text
📊 迭代 #2 完成
   ├── 总体评分: 0.85 (+0.20)
   ├── 事实核查: 0.90 ✅
   ├── 逻辑一致性: 0.82 ✅
   ├── 覆盖度: 0.83 ✅
   ├── Issues 修复率: 67% (2/3)
   └── Token 消耗: 18,000
```

---

## 6. 工程基础设施

### 6.1 Checkpoint (`checkpoint/manager.py`)

**实现**: LangGraph 内置 `SqliteSaver`，每个 session 独立 db。

```python
class CheckpointManager:
    def __init__(self, session_dir: Path):
        self.db_path = session_dir / "checkpoint.db"
        self.saver = SqliteSaver.from_conn_string(str(self.db_path))

    def save(self, state: AgentState, step: str) -> str: ...
    def load(self, checkpoint_id: str) -> AgentState | None: ...
    def list_checkpoints(self) -> list[dict]: ...
```

**CLI 新增**:
```bash
uv run deepresearch resume outputs/session_xxx/       # 恢复最近 checkpoint
uv run deepresearch checkpoints outputs/session_xxx/   # 列出 checkpoints
```

### 6.2 Streaming (`streaming/renderer.py`)

**实现**: `graph.stream(initial_state, config, stream_mode="updates")` + Rich Live。

```python
class StreamRenderer:
    def render_node_start(self, node_name: str) -> None: ...
    def render_node_done(self, node_name: str, result: dict) -> None: ...

def stream_with_rich(graph, initial_state, config):
    """逐个 node 渲染执行进度"""
```

**CLI 新增**:
```bash
uv run deepresearch run "query" --stream      # 实时展示
uv run deepresearch run "query" --no-stream   # 仅最终输出（默认）
```

### 6.3 Observability (`observability/`)

**实现**: 自定义 `BaseCallbackHandler` + `MetricsCollector`。

```python
class ObservabilityCallback(BaseCallbackHandler):
    def on_llm_start(...):   # 记录开始
    def on_llm_end(...):     # 提取 token_usage
    def on_llm_error(...):   # 记录错误

@dataclass
class NodeMetrics:
    node_name: str
    start_time: float
    end_time: float
    input_tokens: int
    output_tokens: int
    llm_calls: int
    errors: list[str]

    @property
    def latency_ms(self) -> float: ...
    @property
    def total_tokens(self) -> int: ...

class MetricsCollector:
    def record_node(self, name: str, metrics: NodeMetrics) -> None: ...
    def summary(self) -> dict: ...
```

**输出 `metrics.json`**:
```json
{
  "total_tokens": 45000,
  "total_latency_ms": 12500,
  "nodes": {
    "plan":     {"tokens": 2000,  "latency_ms": 2300,  "llm_calls": 1},
    "research": {"tokens": 25000, "latency_ms": 5200,  "llm_calls": 5},
    "summary":  {"tokens": 8000,  "latency_ms": 1800,  "llm_calls": 1},
    "critique": {"tokens": 5000,  "latency_ms": 1500,  "llm_calls": 1},
    "final":    {"tokens": 5000,  "latency_ms": 1700,  "llm_calls": 1}
  },
  "iterations": 2,
  "fix_rate_final": 0.67
}
```

---

## 7. Session 输出结构（v1）

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
    ├── citations.json            ← v1 新增
    ├── iteration_metrics.json    ← v1 新增
    ├── metrics.json              ← v1 新增
    ├── checkpoint.db             ← v1 新增
    └── run.log
```

---

## 8. 配置新增项

```python
# deepresearch/config.py 新增字段

class Settings(BaseSettings):
    # ... v0 字段不变 ...

    # v1: Evidence
    dedup_enabled: bool = True
    dedup_max_calls_per_run: int = 20
    source_ranking_enabled: bool = True

    # v1: Checkpoint
    checkpoint_enabled: bool = True

    # v1: Streaming
    stream_enabled: bool = True  # 默认开启 streaming

    # v1: Observability
    metrics_enabled: bool = True
```

---

## 9. 实现顺序

| Phase | 内容 | 依赖 |
|-------|------|------|
| Phase 8 | Config + State 扩展 | v0 Phase 1 |
| Phase 9 | Evidence Dedup + Source Ranking | Phase 8 |
| Phase 10 | Citation 管理 | Phase 8 |
| Phase 11 | Critique 增强 + Fix Rate | Phase 8 |
| Phase 12 | Checkpoint 管理 | Phase 8 |
| Phase 13 | Streaming 输出 | Phase 8 |
| Phase 14 | Observability (Callbacks + Metrics) | Phase 8 |
| Phase 15 | Node 集成 + CLI 增强 | Phase 9-14 |
| Phase 16 | 集成测试 + Demo | Phase 15 |

Phase 9-14 之间独立，可并行开发。

---

## 10. 验收标准

```bash
# 完整测试
uv run pytest

# 代码检查
uv run ruff check .

# CLI
uv run deepresearch --help
uv run deepresearch run "调研问题" --stream       # Streaming 展示
uv run deepresearch resume outputs/session_xxx/   # 中断恢复
uv run deepresearch checkpoints outputs/session_xxx/

# 输出验证
# outputs/session_xxx/ 包含:
#   - citations.json（有内容）
#   - iteration_metrics.json（含 fix_rate）
#   - metrics.json（含 token 统计）
#   - checkpoint.db（存在且可恢复）
```
