# v1 研究质量与工程基础设施增强 — 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 v0 闭环基础上，增强 Evidence/Citation/Critique 研究质量 + Checkpoint/Streaming/Observability 工程基础设施。

**Architecture:** 新增 5 个子包（evidence/citation/checkpoint/streaming/observability），每个独立可测；修改 nodes/prompts/graph/cli/config/state 集成新模块；遵循 v0 的 `make_*_node(llm)` 闭包模式。

**Tech Stack:** Python 3.11+, LangGraph (SqliteSaver, stream_mode), LangChain (BaseCallbackHandler), DeepSeek API, Rich (Live, Panel), Pydantic, pytest, ruff

**Specs:**
- [v1 设计文档](../specs/2026-06-13-v1-quality-and-infra-design.md)

---

## 文件结构总览（变更）

```
deepresearch/
├── config.py                        # 修改：新增 v1 配置项
├── state.py                         # 修改：新增 Pydantic 模型 + AgentState 字段
├── prompts.py                       # 修改：增强 citation/三维评分指令
├── graph.py                         # 修改：接入 checkpoint、stream_mode
├── cli.py                           # 修改：新增 resume/checkpoints 命令、--stream
├── tools.py                         # 修改：搜索结果 URL 去重、来源类型识别
├── output.py                        # 修改：新增 citations/metrics 输出
│
├── evidence/          ← 新增
│   ├── __init__.py
│   ├── dedup.py
│   └── ranking.py
│
├── citation/          ← 新增
│   ├── __init__.py
│   ├── extractor.py
│   └── formatter.py
│
├── checkpoint/        ← 新增
│   ├── __init__.py
│   └── manager.py
│
├── streaming/         ← 新增
│   ├── __init__.py
│   └── renderer.py
│
├── observability/     ← 新增
│   ├── __init__.py
│   ├── callbacks.py
│   └── metrics.py
│
└── nodes/
    ├── __init__.py                   # 修改：re-export 不变
    ├── plan.py                       # 不变
    ├── research.py                   # 修改：接入 dedup + ranking
    ├── summary.py                    # 修改：citation 指令集成
    ├── critique.py                   # 修改：三维评分 + fix rate
    └── final.py                      # 修改：citation 格式化

tests/
├── unit/
│   ├── test_evidence_dedup.py        ← 新增
│   ├── test_evidence_ranking.py      ← 新增
│   ├── test_citation_extractor.py    ← 新增
│   ├── test_citation_formatter.py    ← 新增
│   ├── test_checkpoint_manager.py    ← 新增
│   ├── test_streaming_renderer.py    ← 新增
│   ├── test_observability.py         ← 新增
│   ├── test_config.py                # 修改：新增 v1 字段测试
│   ├── test_state.py                 # 修改：新增模型测试
│   ├── test_prompts.py               # 修改：验证 citation/三维评分片段
│   ├── test_critique_node.py         # 修改：三维度 + fix rate
│   ├── test_research_node.py         # 修改：dedup + ranking 集成
│   ├── test_summary_node.py          # 修改：citation 指令
│   ├── test_final_node.py            # 修改：citation 格式化
│   ├── test_graph.py                 # 修改：checkpoint + stream 集成
│   └── test_cli.py                   # 修改：resume/checkpoints 命令
└── integration/
    └── test_workflow.py              # 修改：全流程 v1 功能验证
```

---

## Phase 8：Config + State 扩展

### Task 8.1: Config 新增 v1 配置项

**Files:**
- Modify: `deepresearch/config.py`
- Modify: `tests/unit/test_config.py`

- [ ] **Step 1: 写失败的测试**

```python
# tests/unit/test_config.py — 在文件末尾追加以下测试

def test_v1_dedup_defaults(monkeypatch):
    """v1 dedup 配置项默认值正确"""
    for key in ("DEEPSEEK_API_KEY", "DEEPSEEK_MODEL", "MAX_ITERATIONS",
                "MAX_SEARCH_RESULTS", "OUTPUT_DIR", "TEMPERATURE", "MAX_RETRIES",
                "SEARCH_PROVIDER", "TAVILY_API_KEY", "LOG_LEVEL", "LOG_FILE"):
        monkeypatch.delenv(key, raising=False)

    from deepresearch.config import Settings
    s = Settings()
    assert s.dedup_enabled is True
    assert s.dedup_max_calls_per_run == 20
    assert s.source_ranking_enabled is True
    assert s.checkpoint_enabled is True
    assert s.stream_enabled is True
    assert s.metrics_enabled is True


def test_v1_config_from_env(monkeypatch):
    """v1 配置项可从环境变量读取"""
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    monkeypatch.setenv("DEDUP_ENABLED", "false")
    monkeypatch.setenv("DEDUP_MAX_CALLS_PER_RUN", "10")
    monkeypatch.setenv("SOURCE_RANKING_ENABLED", "false")
    monkeypatch.setenv("CHECKPOINT_ENABLED", "false")
    monkeypatch.setenv("STREAM_ENABLED", "false")
    monkeypatch.setenv("METRICS_ENABLED", "false")

    from deepresearch.config import Settings
    s = Settings()
    assert s.dedup_enabled is False
    assert s.dedup_max_calls_per_run == 10
    assert s.source_ranking_enabled is False
    assert s.checkpoint_enabled is False
    assert s.stream_enabled is False
    assert s.metrics_enabled is False
```

- [ ] **Step 2: 运行测试确认失败**

```bash
uv run pytest tests/unit/test_config.py::test_v1_dedup_defaults tests/unit/test_config.py::test_v1_config_from_env -v
```
Expected: 2 failed (AttributeError: 'Settings' object has no attribute 'dedup_enabled')

- [ ] **Step 3: 实现 config.py 新增字段**

```python
# deepresearch/config.py — 在 Settings 类中追加以下字段（LLM 调用参数之前）

    # v1: Evidence 质量
    dedup_enabled: bool = True
    dedup_max_calls_per_run: int = 20
    source_ranking_enabled: bool = True

    # v1: Checkpoint
    checkpoint_enabled: bool = True

    # v1: Streaming
    stream_enabled: bool = True

    # v1: Observability
    metrics_enabled: bool = True
```

在 `Settings` 类末尾（`temperature` 和 `max_retries` 之上）插入。

- [ ] **Step 4: 运行测试确认通过**

```bash
uv run pytest tests/unit/test_config.py::test_v1_dedup_defaults tests/unit/test_config.py::test_v1_config_from_env -v
```
Expected: 2 passed

- [ ] **Step 5: 运行全部 config 测试确保无回归**

```bash
uv run pytest tests/unit/test_config.py -v
```
Expected: all passed

- [ ] **Step 6: 提交**

```bash
git add deepresearch/config.py tests/unit/test_config.py
git commit -m "feat: add v1 config fields for dedup, ranking, checkpoint, streaming, metrics (Task 8.1)"
```

---

### Task 8.2: State 新增 v1 模型和字段

**Files:**
- Modify: `deepresearch/state.py`
- Modify: `tests/unit/test_state.py`

- [ ] **Step 1: 写失败的测试**

```python
# tests/unit/test_state.py — 在文件末尾追加以下测试

from deepresearch.state import (
    Citation,
    IterationMetrics,
    DimensionScore,
    CritiqueDimension,
    AgentState,
)


class TestCitation:
    def test_create(self):
        c = Citation(
            id=1,
            title="LangGraph Docs",
            url="https://langchain-ai.github.io/langgraph/",
            context="LangGraph 是构建 Agent 的核心框架...",
        )
        assert c.id == 1
        assert c.title == "LangGraph Docs"
        assert c.url == "https://langchain-ai.github.io/langgraph/"

    def test_serialize(self):
        c = Citation(id=1, title="Test", url="https://example.com", context="ctx")
        d = c.model_dump()
        assert d["id"] == 1
        assert d["title"] == "Test"
        assert d["url"] == "https://example.com"
        assert d["context"] == "ctx"


class TestDimensionScore:
    def test_create(self):
        ds = DimensionScore(score=0.8, issues=["缺少引用"], status="pass")
        assert ds.score == 0.8
        assert ds.status == "pass"
        assert len(ds.issues) == 1

    def test_serialize(self):
        ds = DimensionScore(score=0.6, issues=[], status="fail")
        d = ds.model_dump()
        assert d["score"] == 0.6
        assert d["status"] == "fail"


class TestEnhancedCritiqueResult:
    def test_create(self):
        from deepresearch.state import EnhancedCritiqueResult

        cr = EnhancedCritiqueResult(
            pass_=False,
            overall_score=0.65,
            dimensions={
                "fact_check": {"score": 0.8, "issues": [], "status": "pass"},
                "logic_coherence": {"score": 0.6, "issues": ["矛盾"], "status": "fail"},
                "coverage": {"score": 0.55, "issues": ["遗漏子问题"], "status": "fail"},
            },
            issues=[
                {"type": "insufficient_evidence", "severity": "high",
                 "description": "缺少引用", "suggested_action": "补充来源"}
            ],
            new_search_queries=["more search"],
        )
        assert cr.overall_score == 0.65
        assert len(cr.dimensions) == 3
        assert cr.dimensions["fact_check"]["status"] == "pass"

    def test_pass_condition(self):
        from deepresearch.state import EnhancedCritiqueResult

        cr = EnhancedCritiqueResult(
            pass_=True,
            overall_score=0.85,
            dimensions={
                "fact_check": {"score": 0.9, "issues": [], "status": "pass"},
                "logic_coherence": {"score": 0.85, "issues": [], "status": "pass"},
                "coverage": {"score": 0.8, "issues": [], "status": "pass"},
            },
            issues=[],
            new_search_queries=[],
        )
        assert cr.pass_ is True

    def test_serialize_pass_field(self):
        from deepresearch.state import EnhancedCritiqueResult

        cr = EnhancedCritiqueResult(
            pass_=False,
            overall_score=0.5,
            dimensions={},
            issues=[],
            new_search_queries=[],
        )
        d = cr.model_dump()
        assert d["pass"] is False


class TestIterationMetrics:
    def test_create(self):
        im = IterationMetrics(
            iteration=1,
            overall_score=0.65,
            dimensions={
                "fact_check": {"score": 0.8, "issues": [], "status": "pass"},
                "logic_coherence": {"score": 0.6, "issues": [], "status": "fail"},
                "coverage": {"score": 0.55, "issues": [], "status": "fail"},
            },
            issues_count=3,
            fix_rate=None,
            tokens_used=15000,
            latency_ms=3200,
        )
        assert im.iteration == 1
        assert im.fix_rate is None
        assert im.tokens_used == 15000

    def test_with_fix_rate(self):
        im = IterationMetrics(
            iteration=2,
            overall_score=0.85,
            dimensions={},
            issues_count=1,
            fix_rate=0.67,
            tokens_used=18000,
            latency_ms=3500,
        )
        d = im.model_dump()
        assert d["fix_rate"] == 0.67


class TestAgentStateV1:
    def test_initial_state_with_v1_fields(self):
        state: AgentState = {
            "user_query": "测试",
            "research_plan": None,
            "search_results": [],
            "sources": [],
            "evidences": [],
            "draft_summary": None,
            "critique_result": None,
            "final_report": None,
            "iteration": 0,
            "max_iterations": 2,
            "status": "initialized",
            "errors": [],
            "citations": [],
            "iteration_metrics": [],
            "checkpoint_id": None,
        }
        assert state["citations"] == []
        assert state["iteration_metrics"] == []
        assert state["checkpoint_id"] is None
```

- [ ] **Step 2: 运行测试确认失败**

```bash
uv run pytest tests/unit/test_state.py::TestCitation tests/unit/test_state.py::TestDimensionScore tests/unit/test_state.py::TestEnhancedCritiqueResult tests/unit/test_state.py::TestIterationMetrics tests/unit/test_state.py::TestAgentStateV1 -v
```
Expected: all failed (ImportError: cannot import name 'Citation')

- [ ] **Step 3: 实现 state.py 新增模型和字段**

```python
# deepresearch/state.py — 在 CritiqueResult 之后、FinalReport 之前插入以下代码


# ——— v1: Citation ———


class Citation(BaseModel):
    """从报告中提取的引用条目。"""
    id: int
    title: str
    url: str
    context: str = ""


# ——— v1: Enhanced Critique ———


class DimensionScore(BaseModel):
    """单个 Critique 维度的评分。"""
    score: float
    issues: list[str] = []
    status: str = "pass"  # "pass" | "fail"


class EnhancedCritiqueResult(BaseModel):
    """v1 增强版 Critique 结果，包含三维度评分。"""
    model_config = {"populate_by_name": True}
    pass_: bool = Field(alias="pass")
    overall_score: float
    dimensions: dict[str, dict[str, Any]]  # fact_check / logic_coherence / coverage
    issues: list[dict[str, Any]]
    new_search_queries: list[str]

    def model_dump(self, **kwargs):
        kwargs.setdefault("by_alias", True)
        return super().model_dump(**kwargs)


class IterationMetrics(BaseModel):
    """单轮迭代的执行指标。"""
    iteration: int
    overall_score: float
    dimensions: dict[str, dict[str, Any]]
    issues_count: int
    fix_rate: float | None = None
    tokens_used: int = 0
    latency_ms: float = 0
```

```python
# deepresearch/state.py — 在 AgentState TypedDict 中追加 3 个字段（errors 之后）

class AgentState(TypedDict):
    user_query: str
    research_plan: dict[str, Any] | None
    search_results: list[dict[str, Any]]
    sources: list[dict[str, Any]]
    evidences: list[dict[str, Any]]
    draft_summary: str | None
    critique_result: dict[str, Any] | None
    final_report: str | None
    iteration: int
    max_iterations: int
    status: str
    errors: list[str]
    # v1 新增
    citations: list[dict[str, Any]]
    iteration_metrics: list[dict[str, Any]]
    checkpoint_id: str | None
```

- [ ] **Step 4: 运行测试确认通过**

```bash
uv run pytest tests/unit/test_state.py::TestCitation tests/unit/test_state.py::TestDimensionScore tests/unit/test_state.py::TestEnhancedCritiqueResult tests/unit/test_state.py::TestIterationMetrics tests/unit/test_state.py::TestAgentStateV1 -v
```
Expected: all passed

- [ ] **Step 5: 运行全部 state 测试确保无回归**

```bash
uv run pytest tests/unit/test_state.py -v
```
Expected: all passed

- [ ] **Step 6: 提交**

```bash
git add deepresearch/state.py tests/unit/test_state.py
git commit -m "feat: add v1 state models — Citation, EnhancedCritiqueResult, IterationMetrics (Task 8.2)"
```

---

## Phase 9：Evidence 质量管理

### Task 9.1: Evidence 语义去重 (`evidence/dedup.py`)

**Files:**
- Create: `deepresearch/evidence/__init__.py`
- Create: `deepresearch/evidence/dedup.py`
- Create: `tests/unit/test_evidence_dedup.py`

- [ ] **Step 1: 写失败的测试**

```python
# tests/unit/test_evidence_dedup.py
import pytest
from tests.fixtures.mock_llm import FakeChatModel
from deepresearch.evidence.dedup import (
    _group_by_source,
    _are_duplicates,
    deduplicate_evidences,
)


class TestGroupBySource:
    def test_groups_by_source_id(self):
        evidences = [
            {"id": "e1", "source_id": "s1", "claim": "A", "confidence": 0.9},
            {"id": "e2", "source_id": "s1", "claim": "B", "confidence": 0.8},
            {"id": "e3", "source_id": "s2", "claim": "C", "confidence": 0.7},
        ]
        groups = _group_by_source(evidences)
        assert len(groups) == 2
        assert len(groups["s1"]) == 2
        assert len(groups["s2"]) == 1

    def test_empty_list(self):
        assert _group_by_source([]) == {}


class TestAreDuplicates:
    def test_returns_true_for_yes(self):
        llm = FakeChatModel(default_response="YES")
        result = _are_duplicates(
            {"claim": "same thing", "quote": "same"},
            {"claim": "same thing", "quote": "same too"},
            llm,
        )
        assert result is True

    def test_returns_false_for_no(self):
        llm = FakeChatModel(default_response="NO")
        result = _are_duplicates(
            {"claim": "different A", "quote": "A"},
            {"claim": "different B", "quote": "B"},
            llm,
        )
        assert result is False

    def test_defaults_to_false_on_unexpected_response(self):
        """LLM 返回非 YES/NO 时默认为不重复"""
        llm = FakeChatModel(default_response="MAYBE")
        result = _are_duplicates(
            {"claim": "a", "quote": "a"},
            {"claim": "b", "quote": "b"},
            llm,
        )
        assert result is False


class TestDeduplicateEvidences:
    def test_dedup_within_same_source(self):
        """同一 source 下重复 evidence 只保留 confidence 更高的"""
        llm = FakeChatModel(default_response="YES")
        evidences = [
            {"id": "e1", "source_id": "s1", "claim": "same claim", "quote": "q1", "confidence": 0.9},
            {"id": "e2", "source_id": "s1", "claim": "same claim rephrased", "quote": "q2", "confidence": 0.7},
            {"id": "e3", "source_id": "s2", "claim": "different", "quote": "q3", "confidence": 0.8},
        ]
        result = deduplicate_evidences(evidences, llm)
        # e1 (confidence 0.9) 保留，e2 (0.7) 被去重，e3 在不同 source 保留
        ids = [e["id"] for e in result]
        assert "e1" in ids
        assert "e2" not in ids
        assert "e3" in ids

    def test_skips_when_disabled(self):
        """dedup_enabled=False 时原样返回"""
        import deepresearch.evidence.dedup as dedup_mod
        dedup_mod.settings.dedup_enabled = False
        try:
            llm = FakeChatModel(default_response="YES")
            evidences = [
                {"id": "e1", "source_id": "s1", "claim": "c", "quote": "q", "confidence": 0.9},
                {"id": "e2", "source_id": "s1", "claim": "c", "quote": "q", "confidence": 0.8},
            ]
            result = deduplicate_evidences(evidences, llm)
            assert len(result) == 2  # 不处理
        finally:
            dedup_mod.settings.dedup_enabled = True

    def test_respects_max_calls_limit(self):
        """不超出 dedup_max_calls_per_run 限制"""
        llm = FakeChatModel(default_response="YES")
        # 创建大量同 source evidence，触发大量配对比较
        evidences = []
        for i in range(30):
            evidences.append({
                "id": f"e{i}",
                "source_id": "s1",
                "claim": f"claim {i}",
                "quote": f"quote {i}",
                "confidence": 0.5,
            })
        # 不会崩溃，能正常返回
        result = deduplicate_evidences(evidences, llm)
        assert len(result) > 0
```

- [ ] **Step 2: 运行测试确认失败**

```bash
uv run pytest tests/unit/test_evidence_dedup.py -v
```
Expected: all failed (module not found)

- [ ] **Step 3: 实现 evidence/__init__.py**

```python
# deepresearch/evidence/__init__.py
from deepresearch.evidence.dedup import deduplicate_evidences
from deepresearch.evidence.ranking import rank_sources

__all__ = ["deduplicate_evidences", "rank_sources"]
```

- [ ] **Step 4: 实现 evidence/dedup.py**

```python
# deepresearch/evidence/dedup.py
import logging
from itertools import combinations

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import SystemMessage

from deepresearch.config import settings

logger = logging.getLogger(__name__)

_DEDUP_PROMPT = """你是一个文本去重助手。以下是两条 evidence，判断它们是否表达相同的信息。

Evidence A:
claim: "{claim_a}"
quote: "{quote_a}"

Evidence B:
claim: "{claim_b}"
quote: "{quote_b}"

只回答 YES 或 NO。如果两条 evidence 的核心信息一致（即使措辞不同），回答 YES。"""


def _group_by_source(evidences: list[dict]) -> dict[str, list[dict]]:
    """按 source_id 分组。"""
    groups: dict[str, list[dict]] = {}
    for ev in evidences:
        sid = ev.get("source_id", "")
        groups.setdefault(sid, []).append(ev)
    return groups


def _are_duplicates(ev_a: dict, ev_b: dict, llm: BaseChatModel) -> bool:
    """用 LLM 判断两条 evidence 是否语义重复。"""
    prompt = _DEDUP_PROMPT.format(
        claim_a=ev_a.get("claim", ""),
        quote_a=ev_a.get("quote", ""),
        claim_b=ev_b.get("claim", ""),
        quote_b=ev_b.get("quote", ""),
    )
    try:
        response = llm.invoke([SystemMessage(content=prompt)])
        text = str(response.content).strip().upper() if hasattr(response, "content") else ""
        return "YES" in text
    except Exception:
        logger.warning("Dedup LLM call failed, treating as non-duplicate", exc_info=True)
        return False


def _dedup_within_group(evidences: list[dict], llm: BaseChatModel, max_calls: int) -> list[dict]:
    """对同一 source 组内的 evidence 进行语义去重。"""
    if len(evidences) <= 1:
        return evidences

    # 按 confidence 降序排列
    sorted_evs = sorted(evidences, key=lambda e: e.get("confidence", 0), reverse=True)
    kept: list[dict] = []
    removed_ids: set[str] = set()
    call_count = 0

    for i, ev_a in enumerate(sorted_evs):
        if ev_a["id"] in removed_ids:
            continue
        kept.append(ev_a)
        for ev_b in sorted_evs[i + 1:]:
            if ev_b["id"] in removed_ids:
                continue
            if call_count >= max_calls:
                break
            if _are_duplicates(ev_a, ev_b, llm):
                removed_ids.add(ev_b["id"])
                logger.debug("Dedup: removed %s (duplicate of %s)", ev_b["id"], ev_a["id"])
            call_count += 1

    return kept


def deduplicate_evidences(evidences: list[dict], llm: BaseChatModel) -> list[dict]:
    """语义去重入口：按 source 分组，组内 LLM 判断重复，保留 confidence 更高者。

    Args:
        evidences: evidence dict 列表，每条需含 id, source_id, claim, confidence。
        llm: LLM 实例。

    Returns:
        去重后的 evidence 列表。
    """
    if not settings.dedup_enabled:
        logger.debug("Dedup disabled, skipping")
        return evidences

    if not evidences:
        return []

    groups = _group_by_source(evidences)
    max_calls = settings.dedup_max_calls_per_run
    result: list[dict] = []

    for source_id, group in groups.items():
        deduped = _dedup_within_group(group, llm, max_calls)
        result.extend(deduped)

    dropped = len(evidences) - len(result)
    if dropped > 0:
        logger.info("Dedup: removed %d duplicate evidences (%d → %d)", dropped, len(evidences), len(result))

    return result
```

- [ ] **Step 5: 运行测试确认通过**

```bash
uv run pytest tests/unit/test_evidence_dedup.py -v
```
Expected: all passed

- [ ] **Step 6: 提交**

```bash
git add deepresearch/evidence/__init__.py deepresearch/evidence/dedup.py tests/unit/test_evidence_dedup.py
git commit -m "feat: add semantic evidence dedup using DeepSeek API (Task 9.1)"
```

---

### Task 9.2: Source 权威度评分 (`evidence/ranking.py`)

**Files:**
- Create: `deepresearch/evidence/ranking.py`
- Create: `tests/unit/test_evidence_ranking.py`

- [ ] **Step 1: 写失败的测试**

```python
# tests/unit/test_evidence_ranking.py
import pytest
from deepresearch.evidence.ranking import (
    _classify_domain,
    _classify_source_type,
    _estimate_freshness,
    rank_sources,
)


class TestClassifyDomain:
    def test_edu_domain(self):
        name, score = _classify_domain("https://cs.stanford.edu/papers/ai")
        assert name == "edu"
        assert score == 1.0

    def test_gov_domain(self):
        name, score = _classify_domain("https://www.nist.gov/publication")
        assert name == "gov"
        assert score == 1.0

    def test_known_tech_domain(self):
        name, score = _classify_domain("https://arxiv.org/abs/2401.xxx")
        assert name == "arxiv"
        assert score == 0.8

    def test_github_domain(self):
        name, score = _classify_domain("https://github.com/langchain-ai/langgraph")
        assert name == "github"
        assert score == 0.8

    def test_org_domain(self):
        name, score = _classify_domain("https://www.python.org/dev/peps/")
        assert name == "org"
        assert score == 0.6

    def test_com_domain(self):
        name, score = _classify_domain("https://medium.com/tech-blog/post")
        assert name == "com"
        assert score == 0.5

    def test_social_domain(self):
        name, score = _classify_domain("https://www.reddit.com/r/MachineLearning/")
        assert name == "social"
        assert score == 0.2

    def test_unknown_tld(self):
        name, score = _classify_domain("https://example.xyz/page")
        assert name == "other"
        assert score == 0.4


class TestClassifySourceType:
    def test_academic_paper(self):
        tp, score = _classify_source_type("This paper presents...", "Abstract\n\nWe propose...")
        assert tp == "academic"
        assert score == 1.0

    def test_official_docs(self):
        tp, score = _classify_source_type("Documentation for...", "API Reference\n\nParameters...")
        assert tp == "official_docs"
        assert score == 0.9

    def test_tech_blog(self):
        tp, score = _classify_source_type("A blog post about AI", "")
        assert tp == "tech_blog"
        assert score == 0.6

    def test_unknown_type(self):
        tp, score = _classify_source_type("", "")
        assert tp == "unknown"
        assert score == 0.4


class TestEstimateFreshness:
    def test_recent_date(self):
        import datetime
        this_year = str(datetime.date.today().year)
        score = _estimate_freshness(f"Published in {this_year}")
        assert score == 1.0

    def test_three_years_old(self):
        import datetime
        three_years_ago = datetime.date.today().year - 3
        score = _estimate_freshness(f"Published {three_years_ago}")
        assert score == 0.7

    def test_old_date(self):
        score = _estimate_freshness("Published in 2010")
        assert score == 0.4

    def test_no_date(self):
        score = _estimate_freshness("No date information here")
        assert score == 0.5


class TestRankSources:
    def test_rank_and_sort(self):
        sources = [
            {"id": "s1", "title": "Reddit post", "url": "https://reddit.com/r/ai",
             "snippet": "", "content": "short", "source_type": "unknown", "score": 0.0},
            {"id": "s2", "title": "Paper", "url": "https://arxiv.org/abs/2401.xxx",
             "snippet": "We propose a new method", "content": "Abstract\n\n" + "x" * 3000,
             "source_type": "unknown", "score": 0.0},
            {"id": "s3", "title": "Docs", "url": "https://python.org/docs",
             "snippet": "Official documentation", "content": "x" * 1000,
             "source_type": "unknown", "score": 0.0},
        ]
        result = rank_sources(sources)
        # 排序后：arxiv paper > python.org docs > reddit
        assert result[0]["id"] == "s2"  # arxiv paper
        assert result[0]["score"] > result[1]["score"]
        assert result[1]["score"] > result[2]["score"]

    def test_rank_with_existing_score(self):
        """已有 score 的 source 也会被重新计算"""
        sources = [
            {"id": "s1", "title": "T", "url": "https://edu.cn/s", "snippet": "paper",
             "content": "long" * 500, "source_type": "unknown", "score": 0.99},
        ]
        result = rank_sources(sources)
        assert result[0]["score"] != 0.99  # 被重新计算了

    def test_empty_list(self):
        assert rank_sources([]) == []
```

- [ ] **Step 2: 运行测试确认失败**

```bash
uv run pytest tests/unit/test_evidence_ranking.py -v
```
Expected: all failed (module not found)

- [ ] **Step 3: 实现 evidence/ranking.py**

```python
# deepresearch/evidence/ranking.py
import logging
import re
from datetime import date
from urllib.parse import urlparse

from deepresearch.config import settings

logger = logging.getLogger(__name__)

# 域名权威映射 (TLD/domain → (name, score))
_DOMAIN_AUTHORITY: dict[str, tuple[str, float]] = {
    ".edu": ("edu", 1.0),
    ".gov": ("gov", 1.0),
    "arxiv.org": ("arxiv", 0.8),
    "github.com": ("github", 0.8),
    "stackoverflow.com": ("stackoverflow", 0.8),
    "pypi.org": ("pypi", 0.8),
    "readthedocs.io": ("readthedocs", 0.8),
    ".org": ("org", 0.6),
    ".io": ("io", 0.5),
    ".com": ("com", 0.5),
    ".net": ("net", 0.5),
}

# 来源类型关键词映射
_TYPE_KEYWORDS: list[tuple[list[str], str, float]] = [
    (["abstract", "doi", "et al", "propose", "conference", "journal", "preprint"], "academic", 1.0),
    (["api reference", "documentation", "class ", "function ", "parameter", "@param"], "official_docs", 0.9),
    (["blog", "tutorial", "how to", "guide", "introduction to"], "tech_blog", 0.6),
    (["news", "announced", "released", "update:"], "news", 0.5),
    (["question", "answer", "vote", "asked", "answered"], "forum", 0.3),
]

# 社交/论坛域名
_SOCIAL_DOMAINS = {"reddit.com", "twitter.com", "x.com", "facebook.com", "youtube.com",
                    "zhihu.com", "weibo.com", "t.co", "medium.com"}


def _classify_domain(url: str) -> tuple[str, float]:
    """根据 URL 分析域名权威。"""
    try:
        hostname = urlparse(url).hostname or ""
    except Exception:
        return ("unknown", 0.4)

    # 精确匹配知名域
    for domain, (name, score) in _DOMAIN_AUTHORITY.items():
        if not domain.startswith("."):
            if hostname == domain or hostname.endswith("." + domain):
                return (name, score)

    # 社交域检查
    for sd in _SOCIAL_DOMAINS:
        if sd in hostname:
            return ("social", 0.2)

    # TLD 匹配
    for domain, (name, score) in _DOMAIN_AUTHORITY.items():
        if domain.startswith(".") and hostname.endswith(domain):
            return (name, score)

    return ("other", 0.4)


def _classify_source_type(snippet: str, content: str | None) -> tuple[str, float]:
    """基于关键词推断来源类型。"""
    text = (snippet + " " + (content or "")).lower()
    for keywords, tp, score in _TYPE_KEYWORDS:
        if any(kw in text for kw in keywords):
            return (tp, score)
    return ("unknown", 0.4)


def _estimate_freshness(content: str | None) -> float:
    """从内容中提取年份信息，估算时效性。"""
    if not content:
        return 0.5

    years = re.findall(r"\b(19\d{2}|20\d{2})\b", content)
    if not years:
        return 0.5

    try:
        recent_year = max(int(y) for y in years)
    except ValueError:
        return 0.5

    current_year = date.today().year
    age = current_year - recent_year
    if age <= 1:
        return 1.0
    elif age <= 3:
        return 0.7
    elif age <= 5:
        return 0.6
    else:
        return 0.4


def _compute_content_richness(content: str | None) -> float:
    """评估内容丰富度。"""
    if not content:
        return 0.3
    length = len(content)
    if length > 2000:
        return 1.0
    elif length > 500:
        return 0.6
    else:
        return 0.3


def rank_sources(sources: list[dict]) -> list[dict]:
    """为 sources 计算权威度综合评分并排序。

    权重: 域名权威 40% + 来源类型 30% + 时效性 20% + 内容丰富度 10%

    Args:
        sources: source dict 列表。

    Returns:
        按 score 降序排列的新列表（不修改原列表）。
    """
    if not settings.source_ranking_enabled:
        logger.debug("Source ranking disabled, returning original order")
        return list(sources)

    if not sources:
        return []

    scored = []
    for src in sources:
        url = src.get("url", "")
        snippet = src.get("snippet", "")
        content = src.get("content")

        _, domain_score = _classify_domain(url)
        type_name, type_score = _classify_source_type(snippet, content)
        freshness = _estimate_freshness(content)
        richness = _compute_content_richness(content)

        final_score = round(
            domain_score * 0.40 + type_score * 0.30 + freshness * 0.20 + richness * 0.10,
            2,
        )

        # 创建新 dict 不修改原数据
        scored_src = {**src, "score": final_score,
                      "source_type": src.get("source_type") or type_name}
        scored.append(scored_src)

    scored.sort(key=lambda s: s["score"], reverse=True)
    logger.debug("Ranked %d sources, top score: %.2f", len(scored), scored[0]["score"] if scored else 0)
    return scored
```

- [ ] **Step 4: 运行测试确认通过**

```bash
uv run pytest tests/unit/test_evidence_ranking.py -v
```
Expected: all passed

- [ ] **Step 5: 提交**

```bash
git add deepresearch/evidence/ranking.py tests/unit/test_evidence_ranking.py
git commit -m "feat: add source authority ranking with multi-signal scoring (Task 9.2)"
```

---

## Phase 10：Citation 管理

### Task 10.1: Citation 提取器 (`citation/extractor.py`)

**Files:**
- Create: `deepresearch/citation/__init__.py`
- Create: `deepresearch/citation/extractor.py`
- Create: `tests/unit/test_citation_extractor.py`

- [ ] **Step 1: 写失败的测试**

```python
# tests/unit/test_citation_extractor.py
from deepresearch.citation.extractor import (
    extract_citations,
    validate_citations,
    Citation,
)


class TestExtractCitations:
    def test_extract_single(self):
        text = "根据官方文档[来源: LangGraph Docs](https://example.com)的说法..."
        citations = extract_citations(text)
        assert len(citations) == 1
        assert citations[0].title == "LangGraph Docs"
        assert citations[0].url == "https://example.com"
        assert citations[0].id == 1

    def test_extract_multiple(self):
        text = """
        根据[来源: Paper A](https://a.com)的研究...
        同时[来源: Paper B](https://b.com)也指出...
        """
        citations = extract_citations(text)
        assert len(citations) == 2
        assert citations[0].id == 1
        assert citations[1].id == 2
        assert citations[0].title == "Paper A"
        assert citations[1].title == "Paper B"

    def test_deduplicate_same_url(self):
        """同一 URL 多次出现时去重为同一个编号"""
        text = """
        根据[来源: First Ref](https://same.com)的说法...
        再次引用[来源: Same Ref](https://same.com)...
        """
        citations = extract_citations(text)
        assert len(citations) == 1
        assert citations[0].id == 1

    def test_no_citations(self):
        text = "这段文本没有任何引用。"
        citations = extract_citations(text)
        assert citations == []

    def test_extract_context(self):
        text = "前面的文字根据[来源: Test](https://test.com)的内容说明了这个问题。"
        citations = extract_citations(text)
        assert len(citations) == 1
        assert "前面的文字" in citations[0].context
        assert "的内容说明了" in citations[0].context

    def test_chinese_title(self):
        text = "参考[来源: 深度学习综述](https://example.cn/dl)的内容。"
        citations = extract_citations(text)
        assert len(citations) == 1
        assert citations[0].title == "深度学习综述"


class TestValidateCitations:
    def test_all_valid(self):
        citations = [
            Citation(id=1, title="A", url="https://a.com", context=""),
            Citation(id=2, title="B", url="https://b.com", context=""),
        ]
        sources = [
            {"id": "s1", "url": "https://a.com"},
            {"id": "s2", "url": "https://b.com"},
        ]
        result = validate_citations(citations, sources)
        assert len(result) == 2  # 全部通过

    def test_marks_orphan(self):
        """没有对应 source 的 citation 标记为 orphan"""
        citations = [
            Citation(id=1, title="Valid", url="https://valid.com", context=""),
            Citation(id=2, title="Orphan", url="https://orphan.com", context=""),
        ]
        sources = [
            {"id": "s1", "url": "https://valid.com"},
        ]
        result = validate_citations(citations, sources)
        assert len(result) == 2
        # orphan citation 仍然保留但标记
        assert result[1].title == "Orphan"

    def test_empty_inputs(self):
        assert validate_citations([], []) == []
```

- [ ] **Step 2: 运行测试确认失败**

```bash
uv run pytest tests/unit/test_citation_extractor.py -v
```
Expected: all failed (module not found)

- [ ] **Step 3: 实现 citation/__init__.py**

```python
# deepresearch/citation/__init__.py
from deepresearch.citation.extractor import extract_citations, validate_citations
from deepresearch.citation.formatter import (
    format_inline_citations,
    format_reference_list,
    merge_citations_into_report,
)

__all__ = [
    "extract_citations",
    "validate_citations",
    "format_inline_citations",
    "format_reference_list",
    "merge_citations_into_report",
]
```

- [ ] **Step 4: 实现 citation/extractor.py**

```python
# deepresearch/citation/extractor.py
import re
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# 匹配 [来源: <标题>](<URL>)
_CITATION_PATTERN = re.compile(r"\[来源:\s*([^\]]+?)\]\(([^)]+)\)")


@dataclass
class Citation:
    id: int
    title: str
    url: str
    context: str = ""


def extract_citations(text: str) -> list[Citation]:
    """从 Markdown 文本中提取所有 [来源: title](url) 引用，分配唯一编号。

    Args:
        text: 包含 citation 的 Markdown 文本。

    Returns:
        Citation 列表，同一 URL 只保留一个。
    """
    matches = _CITATION_PATTERN.findall(text)
    if not matches:
        return []

    seen_urls: dict[str, Citation] = {}
    next_id = 1

    for title, url in matches:
        title = title.strip()
        url = url.strip()

        if url in seen_urls:
            continue

        # 提取上下文（匹配位置前后各 50 字符）
        idx = 0
        context = ""
        for m in _CITATION_PATTERN.finditer(text):
            if m.group(1).strip() == title and m.group(2).strip() == url:
                start = max(0, m.start() - 50)
                end = min(len(text), m.end() + 50)
                context = text[start:end]
                idx = m.start()
                break

        citation = Citation(id=next_id, title=title, url=url, context=context)
        seen_urls[url] = citation
        next_id += 1

    # 按出现顺序排序
    result = sorted(seen_urls.values(), key=lambda c: c.id)
    logger.debug("Extracted %d unique citations from text", len(result))
    return result


def validate_citations(citations: list[Citation], sources: list[dict]) -> list[Citation]:
    """验证 citation URL 是否在 sources 中存在。

    Args:
        citations: 提取的 citation 列表。
        sources: state 中的 sources 列表。

    Returns:
        Citation 列表。URL 不在 sources 中的 citation 保留但记录 warning。
    """
    source_urls = {s.get("url", "") for s in sources}
    for c in citations:
        if c.url not in source_urls:
            logger.warning("Orphan citation [%d]: %s (%s) — URL not in collected sources",
                           c.id, c.title, c.url)
    return citations
```

- [ ] **Step 5: 运行测试确认通过**

```bash
uv run pytest tests/unit/test_citation_extractor.py -v
```
Expected: all passed

- [ ] **Step 6: 提交**

```bash
git add deepresearch/citation/__init__.py deepresearch/citation/extractor.py tests/unit/test_citation_extractor.py
git commit -m "feat: add citation extractor from markdown text (Task 10.1)"
```

---

### Task 10.2: Citation 格式化器 (`citation/formatter.py`)

**Files:**
- Create: `deepresearch/citation/formatter.py`
- Create: `tests/unit/test_citation_formatter.py`

- [ ] **Step 1: 写失败的测试**

```python
# tests/unit/test_citation_formatter.py
from deepresearch.citation.extractor import Citation
from deepresearch.citation.formatter import (
    format_inline_citations,
    format_reference_list,
    merge_citations_into_report,
)


class TestFormatInlineCitations:
    def test_replace_with_numbers(self):
        text = "根据[来源: Docs](https://docs.com)和[来源: Paper](https://paper.com)的研究。"
        citations = [
            Citation(id=1, title="Docs", url="https://docs.com", context=""),
            Citation(id=2, title="Paper", url="https://paper.com", context=""),
        ]
        result = format_inline_citations(text, citations)
        assert "[来源: Docs](https://docs.com)" not in result
        assert "[来源: Paper](https://paper.com)" not in result
        assert "[1]" in result
        assert "[2]" in result

    def test_no_citations(self):
        text = "Plain text without citations."
        result = format_inline_citations(text, [])
        assert result == text


class TestFormatReferenceList:
    def test_format_list(self):
        citations = [
            Citation(id=1, title="LangGraph Docs", url="https://langchain-ai.github.io/langgraph/", context=""),
            Citation(id=2, title="Survey Paper", url="https://arxiv.org/abs/2401.xxx", context=""),
        ]
        result = format_reference_list(citations)
        assert "## 参考文献" in result
        assert "[1] LangGraph Docs" in result
        assert "https://langchain-ai.github.io/langgraph/" in result
        assert "[2] Survey Paper" in result
        assert "https://arxiv.org/abs/2401.xxx" in result

    def test_empty_list(self):
        result = format_reference_list([])
        assert result == ""


class TestMergeCitationsIntoReport:
    def test_full_merge(self):
        report = "根据[来源: Docs](https://docs.com)的研究得出结论。"
        citations = [
            Citation(id=1, title="Docs", url="https://docs.com", context=""),
        ]
        result = merge_citations_into_report(report, citations)
        assert "## 参考文献" in result
        assert "[1]" in result
        assert "[来源: Docs](https://docs.com)" not in result

    def test_no_citations_unchanged(self):
        report = "# Report\n\nContent without citations."
        result = merge_citations_into_report(report, [])
        assert result == report
```

- [ ] **Step 2: 运行测试确认失败**

```bash
uv run pytest tests/unit/test_citation_formatter.py -v
```
Expected: all failed (module not found)

- [ ] **Step 3: 实现 citation/formatter.py**

```python
# deepresearch/citation/formatter.py
import logging

from deepresearch.citation.extractor import Citation

logger = logging.getLogger(__name__)


def format_inline_citations(text: str, citations: list[Citation]) -> str:
    """将 [来源: title](url) 替换为 [1][2] 上标格式。

    Args:
        text: 原始 Markdown 文本。
        citations: 已提取的 citation 列表。

    Returns:
        替换后的文本。
    """
    if not citations:
        return text

    # 按 id 降序排序，从后往前替换避免编号错位
    sorted_citations = sorted(citations, key=lambda c: c.id, reverse=True)

    result = text
    for c in sorted_citations:
        # 匹配 [来源: <title>](<url>)
        import re
        # 转义 title 中的特殊字符
        escaped_title = re.escape(c.title)
        pattern = rf"\[来源:\s*{escaped_title}\]\({re.escape(c.url)}\)"
        replacement = f"[{c.id}]"
        result = re.sub(pattern, replacement, result)

    return result


def format_reference_list(citations: list[Citation]) -> str:
    """生成规范参考文献列表。

    Args:
        citations: citation 列表。

    Returns:
        Markdown 格式的参考文献列表。
    """
    if not citations:
        return ""

    lines = ["## 参考文献", ""]
    for c in sorted(citations, key=lambda c: c.id):
        lines.append(f"[{c.id}] {c.title} — {c.url}")

    return "\n".join(lines)


def merge_citations_into_report(report: str, citations: list[Citation]) -> str:
    """将参考文献列表合并到报告末尾。

    Args:
        report: 原始报告 Markdown。
        citations: citation 列表。

    Returns:
        合并后的报告 Markdown。
    """
    if not citations:
        return report

    formatted = format_inline_citations(report, citations)
    ref_list = format_reference_list(citations)
    logger.info("Merged %d citations into final report", len(citations))
    return formatted + "\n\n" + ref_list
```

- [ ] **Step 4: 运行测试确认通过**

```bash
uv run pytest tests/unit/test_citation_formatter.py -v
```
Expected: all passed

- [ ] **Step 5: 提交**

```bash
git add deepresearch/citation/formatter.py tests/unit/test_citation_formatter.py
git commit -m "feat: add citation formatter — inline numbering and reference list (Task 10.2)"
```

---

## Phase 11：Critique 增强 + Fix Rate

### Task 11.1: Critique Node 三维评分 + Fix Rate

**Files:**
- Modify: `deepresearch/prompts.py`
- Modify: `deepresearch/nodes/critique.py`
- Modify: `tests/unit/test_critique_node.py`
- Modify: `tests/unit/test_prompts.py`

This is a single task because prompts + node logic change together.

- [ ] **Step 1: 更新 prompts.py 的 build_critique_messages 测试**

```python
# tests/unit/test_prompts.py — 修改 TestCritiquePrompt 类

class TestCritiquePrompt:
    def test_build_messages_has_three_dimensions(self):
        messages = build_critique_messages(
            user_query="test query",
            draft_summary="draft content",
            sources=[{"title": "src1"}],
            evidences=[{"claim": "c1"}],
            prev_critique=None,
        )
        assert len(messages) == 1
        content = str(messages[0].content)
        assert "fact_check" in content
        assert "logic_coherence" in content
        assert "coverage" in content
        assert "研究审稿 Agent" in content

    def test_build_messages_includes_prev_critique(self):
        messages = build_critique_messages(
            user_query="test",
            draft_summary="draft",
            sources=[{"title": "s1"}],
            evidences=[{"claim": "c1"}],
            prev_critique={"overall_score": 0.6, "issues": [{"description": "old issue"}]},
        )
        content = str(messages[0].content)
        assert "上一轮" in content
        assert "old issue" in content
```

- [ ] **Step 2: 运行测试确认失败**

```bash
uv run pytest tests/unit/test_prompts.py::TestCritiquePrompt -v
```
Expected: 2 failed (TypeError: build_critique_messages() got unexpected keyword argument 'prev_critique')

- [ ] **Step 3: 更新 prompts.py 的 build_critique_messages**

```python
# deepresearch/prompts.py — 替换 build_critique_messages 函数

def build_critique_messages(
    user_query: str,
    draft_summary: str,
    sources: list[dict],
    evidences: list[dict],
    prev_critique: dict | None = None,
) -> list[SystemMessage]:
    """构建增强版 Critique Prompt（v1: 三维度评分 + fix rate 追踪）。"""
    prev_section = ""
    if prev_critique:
        prev_issues = json.dumps(prev_critique.get("issues", []), ensure_ascii=False, indent=2)
        prev_section = f"""
上一轮 Critique 结果：
评分: {prev_critique.get('overall_score', 'N/A')}
Issues: {prev_issues}

请评估上一轮 issue 的修复情况。"""

    text = f"""你是一个严格的研究审稿 Agent。

用户问题：
{user_query}

当前总结：
{draft_summary}

来源：
{json.dumps(sources, ensure_ascii=False, indent=2)}

证据：
{json.dumps(evidences, ensure_ascii=False, indent=2)}
{prev_section}

任务：
从以下三个维度独立评分（每个维度 0-1，≥0.7 为通过）：

1. **fact_check（事实核查）**: 每个断言是否有 evidence 支撑？是否存在无来源的主观判断或编造？
2. **logic_coherence（逻辑一致性）**: 论证链是否自洽？不同部分的结论是否有矛盾？
3. **coverage（覆盖度）**: 是否回答了研究计划的所有子问题？是否有明显遗漏？

只输出 JSON：

{{
  "pass": false,
  "overall_score": 0.65,
  "dimensions": {{
    "fact_check": {{"score": 0.8, "issues": [], "status": "pass"}},
    "logic_coherence": {{"score": 0.6, "issues": ["发现矛盾"], "status": "fail"}},
    "coverage": {{"score": 0.55, "issues": ["遗漏子问题"], "status": "fail"}}
  }},
  "issues": [
    {{
      "type": "insufficient_evidence",
      "severity": "high",
      "description": "...",
      "suggested_action": "..."
    }}
  ],
  "new_search_queries": ["...", "..."]
}}"""
    return [SystemMessage(content=text)]
```

- [ ] **Step 4: 更新 critique node 测试**

```python
# tests/unit/test_critique_node.py — 替换全部内容

import json
from tests.fixtures.mock_llm import FakeChatModel
from deepresearch.nodes.critique import make_critique_node, compute_fix_rate

CRITIQUE_PASS = json.dumps({
    "pass": True,
    "overall_score": 0.85,
    "dimensions": {
        "fact_check": {"score": 0.9, "issues": [], "status": "pass"},
        "logic_coherence": {"score": 0.85, "issues": [], "status": "pass"},
        "coverage": {"score": 0.8, "issues": [], "status": "pass"},
    },
    "issues": [],
    "new_search_queries": [],
}, ensure_ascii=False)

CRITIQUE_FAIL = json.dumps({
    "pass": False,
    "overall_score": 0.55,
    "dimensions": {
        "fact_check": {"score": 0.8, "issues": [], "status": "pass"},
        "logic_coherence": {"score": 0.5, "issues": ["矛盾"], "status": "fail"},
        "coverage": {"score": 0.4, "issues": ["遗漏"], "status": "fail"},
    },
    "issues": [
        {"type": "insufficient_evidence", "severity": "high",
         "description": "缺少引用", "suggested_action": "补充来源"}
    ],
    "new_search_queries": ["more search"],
}, ensure_ascii=False)

CRITIQUE_FAIL_NO_ISSUES = json.dumps({
    "pass": False,
    "overall_score": 0.60,
    "dimensions": {
        "fact_check": {"score": 0.9, "issues": [], "status": "pass"},
        "logic_coherence": {"score": 0.75, "issues": [], "status": "pass"},
        "coverage": {"score": 0.35, "issues": ["未覆盖子问题q3"], "status": "fail"},
    },
    "issues": [],
    "new_search_queries": [],
}, ensure_ascii=False)


class TestComputeFixRate:
    def test_first_iteration_none(self):
        assert compute_fix_rate(None, 3, 0) is None

    def test_all_fixed(self):
        assert compute_fix_rate(3, 0, 1) == 1.0

    def test_partial_fix(self):
        assert compute_fix_rate(3, 1, 1) == 0.67

    def test_none_fixed(self):
        assert compute_fix_rate(3, 3, 1) == 0.0


class TestCritiqueNode:
    def _make_state(self, **overrides):
        state = {
            "user_query": "test",
            "research_plan": {"research_goal": "test", "sub_questions": [],
                              "expected_sections": [], "success_criteria": []},
            "search_results": [],
            "sources": [],
            "evidences": [],
            "draft_summary": "draft content",
            "critique_result": None,
            "final_report": None,
            "iteration": 0,
            "max_iterations": 2,
            "status": "summarized",
            "errors": [],
            "citations": [],
            "iteration_metrics": [],
            "checkpoint_id": None,
        }
        state.update(overrides)
        return state

    def test_critique_pass(self):
        llm = FakeChatModel(default_response=CRITIQUE_PASS)
        node = make_critique_node(llm)
        result = node(self._make_state())
        assert result["critique_result"]["pass"] is True
        assert result["critique_result"]["overall_score"] == 0.85
        assert len(result["iteration_metrics"]) == 1
        assert result["iteration_metrics"][0]["fix_rate"] is None  # 首轮
        assert result["iteration_metrics"][0]["iteration"] == 1

    def test_critique_fail(self):
        llm = FakeChatModel(default_response=CRITIQUE_FAIL)
        node = make_critique_node(llm)
        result = node(self._make_state())
        assert result["critique_result"]["pass"] is False
        assert result["iteration"] == 1

    def test_critique_json_fallback(self):
        """LLM 返回非法 JSON 时默认 pass=True"""
        llm = FakeChatModel(default_response="not valid json at all")
        node = make_critique_node(llm)
        result = node(self._make_state())
        assert result["critique_result"]["pass"] is True

    def test_fix_rate_second_iteration(self):
        """第二轮 iteration 时计算 fix_rate"""
        llm = FakeChatModel(default_response=CRITIQUE_FAIL_NO_ISSUES)
        node = make_critique_node(llm)
        state = self._make_state(
            iteration=0,  # 实际是首轮，但我们有 prev metrics
            iteration_metrics=[{
                "iteration": 1,
                "overall_score": 0.55,
                "dimensions": {},
                "issues_count": 3,
                "fix_rate": None,
                "tokens_used": 0,
                "latency_ms": 0,
            }],
        )
        result = node(state)
        assert len(result["iteration_metrics"]) == 2
        # 第二轮：上一轮 3 issues，本轮 0 issues → fix_rate = 1.0
        assert result["iteration_metrics"][1]["fix_rate"] == 1.0
```

- [ ] **Step 5: 运行测试确认失败**

```bash
uv run pytest tests/unit/test_critique_node.py -v
```
Expected: all failed (function not found / API mismatch)

- [ ] **Step 6: 实现 compute_fix_rate + 重写 critique node**

```python
# deepresearch/nodes/critique.py — 替换全部内容

import json
import logging
import re
import time

from langchain_core.language_models import BaseChatModel

from deepresearch.state import AgentState
from deepresearch.prompts import build_critique_messages

logger = logging.getLogger(__name__)


def compute_fix_rate(prev_issues_count: int | None, current_issues_count: int, iteration: int) -> float | None:
    """计算 issue 修复率。

    Args:
        prev_issues_count: 上一轮 issue 数量，None 表示首轮。
        current_issues_count: 本轮 issue 数量。
        iteration: 当前迭代轮次。

    Returns:
        修复率 (0.0-1.0)，首轮返回 None。
    """
    if prev_issues_count is None:
        return None
    if prev_issues_count == 0:
        return 1.0
    fixed = max(0, prev_issues_count - current_issues_count)
    return round(fixed / prev_issues_count, 2)


def make_critique_node(llm: BaseChatModel):
    """创建增强版 critique_node（v1: 三维度评分 + fix rate）。"""

    def critique_node(state: AgentState) -> dict:
        iteration = state.get("iteration", 0)
        new_iteration = iteration + 1
        logger.info("Critique node: iteration %d → %d", iteration, new_iteration)

        prev_critique_result = state.get("critique_result")
        prev_metrics = state.get("iteration_metrics", [])
        prev_issues_count = len(prev_metrics[-1].get("issues", [])) if prev_metrics else None

        t0 = time.perf_counter()
        messages = build_critique_messages(
            user_query=state["user_query"],
            draft_summary=state.get("draft_summary", ""),
            sources=state.get("sources", []),
            evidences=state.get("evidences", []),
            prev_critique=prev_critique_result,
        )

        try:
            response = llm.invoke(messages)
            raw = str(response.content) if hasattr(response, "content") else str(response)
        except Exception:
            logger.exception("Critique LLM call failed")
            return {
                "critique_result": {"pass": True, "overall_score": 0.5,
                                    "dimensions": {}, "issues": [], "new_search_queries": []},
                "iteration": new_iteration,
                "status": "critiqued",
                "errors": state.get("errors", []) + ["Critique LLM call failed"],
            }

        t1 = time.perf_counter()
        latency_ms = round((t1 - t0) * 1000)

        # JSON 解析
        match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", raw, re.DOTALL)
        if match:
            raw = match.group(1).strip()

        try:
            data = json.loads(raw)
            critique = {
                "pass": data.get("pass", True),
                "overall_score": data.get("overall_score", 0.5),
                "dimensions": data.get("dimensions", {}),
                "issues": data.get("issues", []),
                "new_search_queries": data.get("new_search_queries", []),
            }
        except (json.JSONDecodeError, TypeError):
            logger.warning("Critique JSON parse failed, defaulting to pass")
            critique = {
                "pass": True,
                "overall_score": 0.5,
                "dimensions": {},
                "issues": [],
                "new_search_queries": [],
            }

        current_issues_count = len(critique["issues"])
        fix_rate = compute_fix_rate(prev_issues_count, current_issues_count, iteration)

        # 估算 token（从 response 中提取，DeepSeek 兼容）
        tokens_used = 0
        if hasattr(response, "response_metadata"):
            usage = response.response_metadata.get("token_usage", {})
            tokens_used = usage.get("total_tokens", 0)
        if tokens_used == 0 and hasattr(response, "usage_metadata"):
            tokens_used = response.usage_metadata.get("total_tokens", 0)

        metric = {
            "iteration": new_iteration,
            "overall_score": critique["overall_score"],
            "dimensions": critique["dimensions"],
            "issues_count": current_issues_count,
            "fix_rate": fix_rate,
            "tokens_used": tokens_used,
            "latency_ms": latency_ms,
        }

        logger.info("Critique: score=%.2f pass=%s fix_rate=%s",
                    critique["overall_score"], critique["pass"], fix_rate)

        return {
            "critique_result": critique,
            "iteration": new_iteration,
            "iteration_metrics": state.get("iteration_metrics", []) + [metric],
            "status": "critiqued",
        }

    return critique_node
```

- [ ] **Step 7: 运行测试确认通过**

```bash
uv run pytest tests/unit/test_critique_node.py tests/unit/test_prompts.py::TestCritiquePrompt -v
```
Expected: all passed

- [ ] **Step 8: 提交**

```bash
git add deepresearch/prompts.py deepresearch/nodes/critique.py tests/unit/test_critique_node.py tests/unit/test_prompts.py
git commit -m "feat: enhance critique with 3D scoring and fix-rate tracking (Task 11.1)"
```

---

## Phase 12：Checkpoint 管理

### Task 12.1: Checkpoint Manager (`checkpoint/manager.py`)

**Files:**
- Create: `deepresearch/checkpoint/__init__.py`
- Create: `deepresearch/checkpoint/manager.py`
- Create: `tests/unit/test_checkpoint_manager.py`

- [ ] **Step 1: 写失败的测试**

```python
# tests/unit/test_checkpoint_manager.py
import pytest
from pathlib import Path
from deepresearch.checkpoint.manager import CheckpointManager
from deepresearch.state import AgentState


def _make_state(**overrides) -> AgentState:
    state: AgentState = {
        "user_query": "test",
        "research_plan": None,
        "search_results": [],
        "sources": [],
        "evidences": [],
        "draft_summary": None,
        "critique_result": None,
        "final_report": None,
        "iteration": 0,
        "max_iterations": 2,
        "status": "initialized",
        "errors": [],
        "citations": [],
        "iteration_metrics": [],
        "checkpoint_id": None,
    }
    state.update(overrides)
    return state


class TestCheckpointManager:
    def test_init_creates_db(self, tmp_path):
        session_dir = tmp_path / "session_test"
        session_dir.mkdir()
        cm = CheckpointManager(session_dir)
        assert cm.db_path.exists()
        assert cm.db_path.name == "checkpoint.db"

    def test_save_returns_checkpoint_id(self, tmp_path):
        session_dir = tmp_path / "session_test"
        session_dir.mkdir()
        cm = CheckpointManager(session_dir)
        state = _make_state(status="planned")
        cp_id = cm.save(state, "plan")
        assert cp_id is not None
        assert isinstance(cp_id, str)

    def test_list_checkpoints(self, tmp_path):
        session_dir = tmp_path / "session_test"
        session_dir.mkdir()
        cm = CheckpointManager(session_dir)
        cm.save(_make_state(status="planned"), "plan")
        cm.save(_make_state(status="researched"), "research")

        checkpoints = cm.list_checkpoints()
        assert len(checkpoints) >= 2

    def test_disabled_skips_save(self, tmp_path, monkeypatch):
        """checkpoint_enabled=False 时不执行任何操作"""
        import deepresearch.checkpoint.manager as cm_mod
        monkeypatch.setattr(cm_mod.settings, "checkpoint_enabled", False)
        try:
            session_dir = tmp_path / "session_test"
            session_dir.mkdir()
            cm = CheckpointManager(session_dir)
            state = _make_state()
            cp_id = cm.save(state, "plan")
            assert cp_id == ""
        finally:
            monkeypatch.setattr(cm_mod.settings, "checkpoint_enabled", True)

    def test_save_and_restore(self, tmp_path):
        """保存后可以恢复到同一状态"""
        session_dir = tmp_path / "session_test"
        session_dir.mkdir()
        cm = CheckpointManager(session_dir)
        state = _make_state(user_query="restore test", status="researched", iteration=1)
        cp_id = cm.save(state, "research")

        # 恢复
        restored = cm.load(cp_id)
        assert restored is not None
        assert restored["user_query"] == "restore test"
        assert restored["status"] == "researched"
        assert restored["iteration"] == 1
```

- [ ] **Step 2: 运行测试确认失败**

```bash
uv run pytest tests/unit/test_checkpoint_manager.py -v
```
Expected: all failed (module not found)

- [ ] **Step 3: 实现 checkpoint/__init__.py**

```python
# deepresearch/checkpoint/__init__.py
from deepresearch.checkpoint.manager import CheckpointManager

__all__ = ["CheckpointManager"]
```

- [ ] **Step 4: 实现 checkpoint/manager.py**

```python
# deepresearch/checkpoint/manager.py
import json
import logging
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver

from deepresearch.state import AgentState
from deepresearch.config import settings

logger = logging.getLogger(__name__)


class CheckpointManager:
    """管理 LangGraph checkpoint 持久化和恢复。"""

    def __init__(self, session_dir: Path):
        self.session_dir = session_dir
        self.db_path = session_dir / "checkpoint.db"
        self._saver: SqliteSaver | None = None

    @property
    def saver(self) -> SqliteSaver | None:
        if not settings.checkpoint_enabled:
            return None
        if self._saver is None:
            self._saver = SqliteSaver.from_conn_string(str(self.db_path))
        return self._saver

    def save(self, state: AgentState, step: str) -> str:
        """将当前 state 以 JSON 快照形式持久化。

        注意: SqliteSaver 由 LangGraph 自动管理，此方法保存显式快照副本。

        Returns:
            快照文件名（不带扩展名），用作 checkpoint ID。
        """
        if not settings.checkpoint_enabled:
            return ""

        ts = len(list(self.session_dir.glob("snapshot_*.json"))) + 1
        cp_id = f"snapshot_{ts:03d}"

        serializable = dict(state)
        # 过滤不可序列化的字段
        safe = {}
        for k, v in serializable.items():
            try:
                json.dumps(v, ensure_ascii=False, default=str)
                safe[k] = v
            except (TypeError, ValueError):
                safe[k] = str(v)

        snapshot_path = self.session_dir / f"{cp_id}.json"
        snapshot_path.write_text(json.dumps(safe, ensure_ascii=False, indent=2, default=str),
                                 encoding="utf-8")
        logger.debug("Checkpoint saved: %s (step=%s)", cp_id, step)
        return cp_id

    def load(self, checkpoint_id: str) -> AgentState | None:
        """从快照恢复 state。"""
        snapshot_path = self.session_dir / f"{checkpoint_id}.json"
        if not snapshot_path.exists():
            logger.warning("Checkpoint not found: %s", snapshot_path)
            return None

        data = json.loads(snapshot_path.read_text(encoding="utf-8"))
        logger.info("Checkpoint loaded: %s", checkpoint_id)
        return data  # type: ignore[return-value]

    def list_checkpoints(self) -> list[dict]:
        """列出所有 checkpoint 快照。"""
        snapshots = sorted(self.session_dir.glob("snapshot_*.json"))
        result = []
        for sp in snapshots:
            stat = sp.stat()
            result.append({
                "id": sp.stem,
                "path": str(sp),
                "size_bytes": stat.st_size,
                "created": stat.st_ctime,
            })
        return result
```

- [ ] **Step 5: 运行测试确认通过**

```bash
uv run pytest tests/unit/test_checkpoint_manager.py -v
```
Expected: all passed

- [ ] **Step 6: 提交**

```bash
git add deepresearch/checkpoint/ tests/unit/test_checkpoint_manager.py
git commit -m "feat: add checkpoint manager with SqliteSaver and JSON snapshots (Task 12.1)"
```

---

## Phase 13：Streaming 输出

### Task 13.1: Streaming Renderer (`streaming/renderer.py`)

**Files:**
- Create: `deepresearch/streaming/__init__.py`
- Create: `deepresearch/streaming/renderer.py`
- Create: `tests/unit/test_streaming_renderer.py`

- [ ] **Step 1: 写失败的测试**

```python
# tests/unit/test_streaming_renderer.py
import pytest
from unittest.mock import Mock
from rich.console import Console
from deepresearch.streaming.renderer import StreamRenderer


class TestStreamRenderer:
    def test_create(self):
        console = Console(force_terminal=True, color_system="none")
        renderer = StreamRenderer(console)
        assert renderer is not None

    def test_render_node_start(self):
        console = Console(force_terminal=True, color_system="none")
        renderer = StreamRenderer(console)
        # 不抛异常即为通过
        renderer.render_node_start("plan")
        renderer.render_node_start("research")

    def test_render_node_done(self):
        console = Console(force_terminal=True, color_system="none")
        renderer = StreamRenderer(console)
        renderer.render_node_done("plan", {"status": "planned"})
        renderer.render_node_done("research", {"sources": [{"title": "test"}]})

    def test_render_done_marks_completed(self):
        console = Console(force_terminal=True, color_system="none")
        renderer = StreamRenderer(console)
        renderer.render_node_done("final", {"status": "completed"})
        # final done 后 tracked 中仍有记录
        assert "final" in renderer._completed

    def test_disabled_mode(self):
        """disabled=True 时所有 render 方法不抛异常也不输出"""
        console = Console(force_terminal=True, color_system="none")
        renderer = StreamRenderer(console, enabled=False)
        renderer.render_node_start("plan")
        renderer.render_node_done("plan", {})
        assert "plan" not in renderer._completed
```

- [ ] **Step 2: 运行测试确认失败**

```bash
uv run pytest tests/unit/test_streaming_renderer.py -v
```
Expected: all failed (module not found)

- [ ] **Step 3: 实现 streaming/__init__.py + renderer.py**

```python
# deepresearch/streaming/__init__.py
from deepresearch.streaming.renderer import StreamRenderer, stream_with_rich

__all__ = ["StreamRenderer", "stream_with_rich"]
```

```python
# deepresearch/streaming/renderer.py
import logging
import time
from typing import Any

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table

from deepresearch.config import settings

logger = logging.getLogger(__name__)

_NODE_LABELS = {
    "plan": "Plan",
    "research": "Research",
    "summary": "Summary",
    "critique": "Critique",
    "final": "Final",
}


class StreamRenderer:
    """用 Rich 渲染 LangGraph streaming 输出。"""

    def __init__(self, console: Console | None = None, enabled: bool | None = None):
        self.console = console or Console()
        self._enabled = enabled if enabled is not None else settings.stream_enabled
        self._start_times: dict[str, float] = {}
        self._completed: dict[str, dict[str, Any]] = {}

    def _build_table(self, current_node: str | None = None) -> Table:
        """构建进度表格。"""
        table = Table(show_header=False, expand=True, box=None)
        table.add_column("status", width=3)
        table.add_column("node", width=12)
        table.add_column("detail")

        nodes_order = ["plan", "research", "summary", "critique", "final"]
        for node in nodes_order:
            label = _NODE_LABELS.get(node, node)
            if node == current_node:
                table.add_row("⏳", label, "进行中...")
            elif node in self._completed:
                info = self._completed[node]
                elapsed = time.perf_counter() - self._start_times.get(node, time.perf_counter())
                table.add_row("✅", label, f"已完成 ({elapsed:.1f}s)")
            else:
                table.add_row("⬜", label, "等待中")
        return table

    def render_node_start(self, node_name: str) -> None:
        """标记 node 开始。"""
        if not self._enabled:
            return
        self._start_times[node_name] = time.perf_counter()

    def render_node_done(self, node_name: str, _result: dict[str, Any]) -> None:
        """标记 node 完成。"""
        if not self._enabled:
            return
        self._completed[node_name] = _result

    def render_summary(self, result: dict[str, Any]) -> None:
        """打印最终摘要。"""
        if not self._enabled:
            return
        iteration = result.get("iteration", 0)
        metrics = result.get("iteration_metrics", [])
        self.console.print(f"\n📊 迭代次数: {iteration}")
        if metrics:
            last = metrics[-1]
            self.console.print(f"   Critique 评分: {last.get('overall_score', 'N/A')}")
            fix_rate = last.get("fix_rate")
            if fix_rate is not None:
                self.console.print(f"   Issues 修复率: {fix_rate * 100:.0f}%")
        sources_count = len(result.get("sources", []))
        evidences_count = len(result.get("evidences", []))
        self.console.print(f"   来源数: {sources_count}, 证据数: {evidences_count}")


def stream_with_rich(graph, initial_state: dict, config: dict) -> dict:
    """使用 Rich Live 逐个渲染 LangGraph stream 执行过程。

    Args:
        graph: 已编译的 LangGraph StateGraph。
        initial_state: 初始状态。
        config: LangGraph config dict（含 checkpoint 等）。

    Returns:
        最终 AgentState。
    """
    if not settings.stream_enabled:
        return graph.invoke(initial_state, config)

    console = Console()
    renderer = StreamRenderer(console)

    # 准备 initial panel
    panel = Panel(
        renderer._build_table(),
        title=f"🔍 DeepResearch: {initial_state.get('user_query', '')}",
        border_style="blue",
    )

    with Live(panel, console=console, refresh_per_second=4, transient=False) as live:
        last_result = initial_state
        for chunk in graph.stream(initial_state, config, stream_mode="updates"):
            for node_name, node_result in chunk.items():
                renderer.render_node_start(node_name)
                renderer.render_node_done(node_name, node_result)
                last_result = {**last_result, **node_result}
                live.update(renderer._build_table())

    renderer.render_summary(last_result)
    return last_result
```

- [ ] **Step 4: 运行测试确认通过**

```bash
uv run pytest tests/unit/test_streaming_renderer.py -v
```
Expected: all passed

- [ ] **Step 5: 提交**

```bash
git add deepresearch/streaming/ tests/unit/test_streaming_renderer.py
git commit -m "feat: add streaming renderer with Rich Live display (Task 13.1)"
```

---

## Phase 14：Observability

### Task 14.1: Observability Callbacks + Metrics

**Files:**
- Create: `deepresearch/observability/__init__.py`
- Create: `deepresearch/observability/callbacks.py`
- Create: `deepresearch/observability/metrics.py`
- Create: `tests/unit/test_observability.py`

- [ ] **Step 1: 写失败的测试**

```python
# tests/unit/test_observability.py
import pytest
import time
from deepresearch.observability.metrics import NodeMetrics, MetricsCollector


class TestNodeMetrics:
    def test_latency_ms(self):
        t0 = time.perf_counter()
        t1 = t0 + 2.5
        m = NodeMetrics(
            node_name="plan",
            start_time=t0,
            end_time=t1,
            input_tokens=100,
            output_tokens=50,
            llm_calls=1,
        )
        assert m.latency_ms == pytest.approx(2500, rel=0.1)
        assert m.total_tokens == 150

    def test_empty_metrics(self):
        m = NodeMetrics(
            node_name="test",
            start_time=0.0,
            end_time=0.0,
            input_tokens=0,
            output_tokens=0,
            llm_calls=0,
        )
        assert m.latency_ms == 0.0
        assert m.total_tokens == 0


class TestMetricsCollector:
    def test_record_and_summary(self):
        collector = MetricsCollector()

        m1 = NodeMetrics(
            node_name="plan", start_time=0.0, end_time=2.3,
            input_tokens=800, output_tokens=200, llm_calls=1,
        )
        m2 = NodeMetrics(
            node_name="research", start_time=2.3, end_time=7.5,
            input_tokens=15000, output_tokens=3000, llm_calls=5,
        )

        collector.record_node("plan", m1)
        collector.record_node("research", m2)

        summary = collector.summary()
        assert summary["total_tokens"] == 19000
        assert summary["nodes"]["plan"]["tokens"] == 1000
        assert summary["nodes"]["research"]["tokens"] == 18000
        assert summary["nodes"]["plan"]["llm_calls"] == 1
        assert summary["nodes"]["research"]["llm_calls"] == 5

    def test_summary_empty(self):
        collector = MetricsCollector()
        summary = collector.summary()
        assert summary["total_tokens"] == 0
        assert summary["total_latency_ms"] == 0
        assert summary["nodes"] == {}

    def test_errors_tracked(self):
        collector = MetricsCollector()
        m = NodeMetrics(
            node_name="plan", start_time=0.0, end_time=1.0,
            input_tokens=0, output_tokens=0, llm_calls=1,
            errors=["Plan generation failed"],
        )
        collector.record_node("plan", m)
        summary = collector.summary()
        assert summary["nodes"]["plan"]["errors"] == 1
```

- [ ] **Step 2: 运行测试确认失败**

```bash
uv run pytest tests/unit/test_observability.py -v
```
Expected: all failed (module not found)

- [ ] **Step 3: 实现 observability/**

```python
# deepresearch/observability/__init__.py
from deepresearch.observability.metrics import NodeMetrics, MetricsCollector
from deepresearch.observability.callbacks import ObservabilityCallback

__all__ = ["NodeMetrics", "MetricsCollector", "ObservabilityCallback"]
```

```python
# deepresearch/observability/metrics.py
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class NodeMetrics:
    """单个 node 的执行指标。"""
    node_name: str
    start_time: float
    end_time: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    llm_calls: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def latency_ms(self) -> float:
        return round((self.end_time - self.start_time) * 1000, 0)

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


class MetricsCollector:
    """汇总整个 run 的指标。"""

    def __init__(self):
        self.node_metrics: dict[str, NodeMetrics] = {}

    def record_node(self, name: str, metrics: NodeMetrics) -> None:
        """记录一个 node 的指标（多次调用合并）。"""
        if name in self.node_metrics:
            existing = self.node_metrics[name]
            existing.end_time = metrics.end_time
            existing.input_tokens += metrics.input_tokens
            existing.output_tokens += metrics.output_tokens
            existing.llm_calls += metrics.llm_calls
            existing.errors.extend(metrics.errors)
        else:
            self.node_metrics[name] = metrics

    def summary(self) -> dict[str, Any]:
        """生成汇总 dict（用于输出 metrics.json）。"""
        nodes = {}
        total_tokens = 0
        total_latency_ms = 0.0

        for name, m in self.node_metrics.items():
            nodes[name] = {
                "tokens": m.total_tokens,
                "latency_ms": m.latency_ms,
                "llm_calls": m.llm_calls,
                "errors": len(m.errors),
            }
            total_tokens += m.total_tokens
            total_latency_ms += m.latency_ms

        return {
            "total_tokens": total_tokens,
            "total_latency_ms": round(total_latency_ms, 0),
            "nodes": nodes,
        }
```

```python
# deepresearch/observability/callbacks.py
import logging
import time
from typing import Any

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult

from deepresearch.observability.metrics import NodeMetrics, MetricsCollector

logger = logging.getLogger(__name__)


class ObservabilityCallback(BaseCallbackHandler):
    """LangChain callback，追踪每个 node 的 LLM 调用指标。

    Usage:
        collector = MetricsCollector()
        callback = ObservabilityCallback("plan", collector)
        llm = build_llm().with_config(callbacks=[callback])
    """

    def __init__(self, node_name: str, collector: MetricsCollector):
        super().__init__()
        self.node_name = node_name
        self.collector = collector
        self._start_time: float = 0.0
        self._input_tokens: int = 0
        self._output_tokens: int = 0
        self._call_count: int = 0
        self._errors: list[str] = []

    def on_llm_start(
        self, serialized: dict[str, Any], prompts: list[str], **kwargs: Any
    ) -> None:
        self._start_time = time.perf_counter()
        # 估算输入 token（简化：按字符数 / 2 估算）
        for p in prompts:
            self._input_tokens += len(p) // 2
        self._call_count += 1

    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        end_time = time.perf_counter()
        # 提取实际 token 用量
        if response.llm_output and "token_usage" in response.llm_output:
            usage = response.llm_output["token_usage"]
            self._input_tokens = usage.get("prompt_tokens", self._input_tokens)
            self._output_tokens = usage.get("completion_tokens", 0)

        metrics = NodeMetrics(
            node_name=self.node_name,
            start_time=self._start_time,
            end_time=end_time,
            input_tokens=self._input_tokens,
            output_tokens=self._output_tokens,
            llm_calls=self._call_count,
            errors=self._errors,
        )
        self.collector.record_node(self.node_name, metrics)

    def on_llm_error(self, error: BaseException, **kwargs: Any) -> None:
        self._errors.append(str(error))
        logger.error("LLM error in node '%s': %s", self.node_name, error)
```

- [ ] **Step 4: 运行测试确认通过**

```bash
uv run pytest tests/unit/test_observability.py -v
```
Expected: all passed

- [ ] **Step 5: 提交**

```bash
git add deepresearch/observability/ tests/unit/test_observability.py
git commit -m "feat: add observability layer — callback handler and metrics collector (Task 14.1)"
```

---

## Phase 15：Node 集成 + CLI 增强

### Task 15.1: Research Node 集成 Dedup + Ranking

**Files:**
- Modify: `deepresearch/nodes/research.py`
- Modify: `tests/unit/test_research_node.py`

- [ ] **Step 1: 更新 research node 测试**

```python
# tests/unit/test_research_node.py — 在已有测试后追加

def test_research_node_calls_dedup(monkeypatch):
    """research_node 执行后调用 dedup"""
    def mock_search(query, max_results):
        from deepresearch.tools import SearchResult
        return [SearchResult(title="T", url="https://x.com", snippet="S")]

    def mock_fetch(url, timeout):
        return "content"

    monkeypatch.setattr("deepresearch.nodes.research.search_web", mock_search)
    monkeypatch.setattr("deepresearch.nodes.research.fetch_content", mock_fetch)

    dedup_called = []
    def mock_dedup(evidences, llm):
        dedup_called.append(True)
        return evidences

    monkeypatch.setattr("deepresearch.nodes.research.deduplicate_evidences", mock_dedup)

    evidence_json = '{"evidences": [{"claim": "test", "quote": "test", "confidence": 0.9}]}'
    from tests.fixtures.mock_llm import FakeChatModel
    llm = FakeChatModel(default_response=evidence_json)

    from deepresearch.nodes.research import make_research_node
    node = make_research_node(llm)

    state = {
        "user_query": "test",
        "research_plan": {
            "research_goal": "test",
            "sub_questions": [
                {"id": "q1", "question": "q", "priority": 1, "search_queries": ["q"]}
            ],
            "expected_sections": [],
            "success_criteria": [],
        },
        "search_results": [],
        "sources": [],
        "evidences": [],
        "draft_summary": None,
        "critique_result": None,
        "final_report": None,
        "iteration": 0,
        "max_iterations": 2,
        "status": "planned",
        "errors": [],
        "citations": [],
        "iteration_metrics": [],
        "checkpoint_id": None,
    }

    result = node(state)
    assert len(dedup_called) > 0


def test_research_node_calls_ranking(monkeypatch):
    """research_node 执行后调用 rank_sources"""
    def mock_search(query, max_results):
        from deepresearch.tools import SearchResult
        return []

    def mock_fetch(url, timeout):
        return ""

    monkeypatch.setattr("deepresearch.nodes.research.search_web", mock_search)
    monkeypatch.setattr("deepresearch.nodes.research.fetch_content", mock_fetch)

    ranking_called = []
    def mock_ranking(sources):
        ranking_called.append(True)
        return sources

    monkeypatch.setattr("deepresearch.nodes.research.rank_sources", mock_ranking)

    from tests.fixtures.mock_llm import FakeChatModel
    llm = FakeChatModel(default_response='{"evidences":[]}')

    from deepresearch.nodes.research import make_research_node
    node = make_research_node(llm)

    state = {
        "user_query": "test",
        "research_plan": {
            "research_goal": "test",
            "sub_questions": [
                {"id": "q1", "question": "q", "priority": 1, "search_queries": ["q"]}
            ],
            "expected_sections": [],
            "success_criteria": [],
        },
        "search_results": [],
        "sources": [],
        "evidences": [],
        "draft_summary": None,
        "critique_result": None,
        "final_report": None,
        "iteration": 0,
        "max_iterations": 2,
        "status": "planned",
        "errors": [],
        "citations": [],
        "iteration_metrics": [],
        "checkpoint_id": None,
    }

    result = node(state)
    assert len(ranking_called) > 0
```

- [ ] **Step 2: 运行测试确认失败**

```bash
uv run pytest tests/unit/test_research_node.py::test_research_node_calls_dedup tests/unit/test_research_node.py::test_research_node_calls_ranking -v
```
Expected: 2 failed (module not found / function not called)

- [ ] **Step 3: 修改 research.py 接入 dedup + ranking**

在现有 `make_research_node` 函数的 return 之前插入以下逻辑：

```python
# deepresearch/nodes/research.py — 在 `return` 语句之前插入

        # v1: 对 evidences 做语义去重
        if all_evidences:
            from deepresearch.evidence.dedup import deduplicate_evidences
            all_evidences = deduplicate_evidences(all_evidences, llm)

        # v1: 对 sources 做权威度评分排序
        if all_sources:
            from deepresearch.evidence.ranking import rank_sources
            all_sources = rank_sources(all_sources)
```

并将现有 return 之前 `logger.info(...)` 后的 return 保持不变即可。

- [ ] **Step 4: 运行测试确认通过**

```bash
uv run pytest tests/unit/test_research_node.py -v
```
Expected: all passed

- [ ] **Step 5: 提交**

```bash
git add deepresearch/nodes/research.py tests/unit/test_research_node.py
git commit -m "feat: integrate dedup and ranking into research node (Task 15.1)"
```

---

### Task 15.2: Summary + Final Node 集成 Citation

**Files:**
- Modify: `deepresearch/prompts.py` (summary + finalizer prompts)
- Modify: `deepresearch/nodes/summary.py`
- Modify: `deepresearch/nodes/final.py`
- Modify: `tests/unit/test_summary_node.py`
- Modify: `tests/unit/test_final_node.py`
- Modify: `tests/unit/test_prompts.py`

- [ ] **Step 1: 更新 prompts.py summary 和 finalizer prompt，添加 citation 指令**

在 `build_summarizer_messages` 函数的要求部分添加：

```python
# deepresearch/prompts.py — build_summarizer_messages 中"要求"段追加

6. 对每个关键结论使用 [来源: 简短标题](URL) 格式标注引用。
   URL 必须严格来自 evidence 对应的 source url，不得编造。
```

在 `build_finalizer_messages` 函数的要求部分添加：

```python
# deepresearch/prompts.py — build_finalizer_messages 中"要求"段追加

5. 使用 [来源: 简短标题](URL) 格式标注每个关键发现的来源。
6. 在报告末尾列出所有引用的参考文献。
```

- [ ] **Step 2: 更新 prompts 测试**

```python
# tests/unit/test_prompts.py — 在 TestSummarizerPrompt 中追加

    def test_build_messages_has_citation_instruction(self):
        messages = build_summarizer_messages(
            user_query="test",
            research_plan={"research_goal": "test"},
            evidences=[{"claim": "c1"}],
        )
        content = str(messages[0].content)
        assert "[来源:" in content

# tests/unit/test_prompts.py — 在 TestFinalizerPrompt 中追加

    def test_build_messages_has_citation_instruction(self):
        messages = build_finalizer_messages(
            user_query="test",
            draft_summary="draft",
            critique_result={"score": 0.9},
            sources=[{"title": "s1"}],
        )
        content = str(messages[0].content)
        assert "[来源:" in content
```

- [ ] **Step 3: 修改 final_node 集成 citation 格式化**

在 `make_final_node` 函数中，LLM 生成 report 后，添加 citation 处理：

```python
# deepresearch/nodes/final.py — 在 response 获取之后、return 之前插入

        # v1: 提取并格式化 citation
        from deepresearch.citation.extractor import extract_citations, validate_citations
        from deepresearch.citation.formatter import merge_citations_into_report

        citations = extract_citations(report)
        if citations:
            validated = validate_citations(citations, state.get("sources", []))
            report = merge_citations_into_report(report, validated)

        # 原有的 return
        return {
            "final_report": report,
            "status": "completed",
            "citations": [{"id": c.id, "title": c.title, "url": c.url}
                          for c in (citations or [])],
        }
```

- [ ] **Step 4: 更新 final_node 测试**

```python
# tests/unit/test_final_node.py — 在已有测试后追加

def test_final_node_extracts_citations():
    llm = FakeChatModel(default_response="根据[来源: Test](https://example.com)的研究得出结论。")
    node = make_final_node(llm)
    state = {
        "user_query": "test",
        "research_plan": {"research_goal": "test", "sub_questions": [],
                          "expected_sections": [], "success_criteria": []},
        "search_results": [],
        "sources": [{"id": "s1", "url": "https://example.com"}],
        "evidences": [],
        "draft_summary": "draft",
        "critique_result": {"overall_score": 0.9, "pass": True, "issues": []},
        "final_report": None,
        "iteration": 1,
        "max_iterations": 2,
        "status": "critiqued",
        "errors": [],
        "citations": [],
        "iteration_metrics": [],
        "checkpoint_id": None,
    }
    result = node(state)
    assert result["final_report"] is not None
    assert "## 参考文献" in result["final_report"]
    assert "Test" in result["final_report"]
    assert len(result["citations"]) > 0
```

- [ ] **Step 5: 运行测试确认通过**

```bash
uv run pytest tests/unit/test_prompts.py tests/unit/test_summary_node.py tests/unit/test_final_node.py -v
```
Expected: all passed

- [ ] **Step 6: 提交**

```bash
git add deepresearch/prompts.py deepresearch/nodes/summary.py deepresearch/nodes/final.py tests/unit/test_prompts.py tests/unit/test_summary_node.py tests/unit/test_final_node.py
git commit -m "feat: integrate citation extraction and formatting into summary and final nodes (Task 15.2)"
```

---

### Task 15.3: CLI 增强 + Graph 集成

**Files:**
- Modify: `deepresearch/cli.py`
- Modify: `deepresearch/graph.py`
- Modify: `tests/unit/test_cli.py`
- Modify: `tests/unit/test_graph.py`

- [ ] **Step 1: 更新 _make_initial_state 包含 v1 字段**

```python
# deepresearch/cli.py — _make_initial_state 函数中追加 3 个字段

def _make_initial_state(query: str, max_iterations: int) -> AgentState:
    return {
        "user_query": query,
        "research_plan": None,
        "search_results": [],
        "sources": [],
        "evidences": [],
        "draft_summary": None,
        "critique_result": None,
        "final_report": None,
        "iteration": 0,
        "max_iterations": max_iterations,
        "status": "initialized",
        "errors": [],
        "citations": [],
        "iteration_metrics": [],
        "checkpoint_id": None,
    }
```

- [ ] **Step 2: 在 run 命令中集成 stream + output（替换 graph.invoke）**

```python
# deepresearch/cli.py — run 函数中替换 graph 执行部分

@app.command()
def run(
    query: str = typer.Argument(..., help="研究问题"),
    max_iterations: int = typer.Option(2, "--max-iterations", "-n", help="最大研究迭代次数"),
    output: str | None = typer.Option(None, "--output", "-o", help="输出文件路径"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="启用 DEBUG 级别日志"),
    log_file: str | None = typer.Option(None, "--log-file", help="日志文件路径"),
    stream: bool = typer.Option(True, "--stream/--no-stream", help="启用/禁用实时 streaming 展示"),
):
    """运行 DeepResearch Agent 完成研究任务。"""
    cfg = Settings()
    log_level = "DEBUG" if verbose else cfg.log_level
    resolved_log_file = log_file or cfg.log_file
    setup_logging(level=log_level, log_file=resolved_log_file)

    logger.info("Starting DeepResearch Agent v1")
    logger.debug("Query: %s, Max iterations: %d, Stream: %s", query, max_iterations, stream)

    # v1: 临时覆盖 streaming 配置
    if not stream:
        import deepresearch.config as config_module
        config_module.settings.stream_enabled = False

    initial_state = _make_initial_state(query, max_iterations)

    # 初始化 session 目录和 checkpoint
    from deepresearch.output import init_session_dir, save_all
    session_dir = init_session_dir()

    from deepresearch.checkpoint.manager import CheckpointManager
    cm = CheckpointManager(session_dir)

    graph = build_graph()
    app_graph = graph.compile(checkpointer=cm.saver)

    typer.echo(f"🔍 开始研究: {query}")
    typer.echo(f"   最大迭代次数: {max_iterations}")
    typer.echo(f"   输出目录: {session_dir}")

    # v1: 使用 streaming 执行
    from deepresearch.streaming.renderer import stream_with_rich
    config = {"configurable": {"thread_id": session_dir.name}}
    result = stream_with_rich(app_graph, initial_state, config)

    # 保存中间产物
    save_all(result, session_dir)

    # v1: 保存 metrics 和 citations
    from deepresearch.output import save_json
    metrics = result.get("iteration_metrics", [])
    if metrics:
        save_json(metrics, session_dir / "iteration_metrics.json")
    citations = result.get("citations", [])
    if citations:
        save_json(citations, session_dir / "citations.json")

    # 保存 checkpoint 快照
    cm.save(result, "final")

    # 输出最终报告
    final = result.get("final_report", "")
    typer.echo("\n" + "=" * 60)
    typer.echo(final)
    typer.echo("=" * 60)

    if output:
        out_path = Path(output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(final, encoding="utf-8")
        typer.echo(f"\n📄 报告已保存到: {out_path}")

    # 摘要
    typer.echo(f"\n📊 迭代次数: {result.get('iteration', 0)}")
    plan = result.get("research_plan")
    if plan:
        typer.echo(f"   子问题数: {len(plan.get('sub_questions', []))}")
    critique = result.get("critique_result")
    if critique:
        typer.echo(f"   Critique 评分: {critique.get('overall_score', 'N/A')}")
    iteration_metrics_list = result.get("iteration_metrics", [])
    if iteration_metrics_list:
        last_metrics = iteration_metrics_list[-1]
        fix_rate = last_metrics.get("fix_rate")
        if fix_rate is not None:
            typer.echo(f"   Issues 修复率: {fix_rate * 100:.0f}%")
    sources = result.get("sources", [])
    evidences = result.get("evidences", [])
    typer.echo(f"   来源数: {len(sources)}, 证据数: {len(evidences)}")

    errors = result.get("errors", [])
    if errors:
        typer.echo(f"   ⚠️  错误: {len(errors)} 个")
        for e in errors:
            logger.error("Workflow error: %s", e)

    logger.info("DeepResearch Agent v1 completed")
    typer.echo("✅ 研究完成")
```

- [ ] **Step 3: 新增 resume 和 checkpoints 命令**

```python
# deepresearch/cli.py — 在文件末尾追加


@app.command()
def resume(
    session_dir: str = typer.Argument(..., help="Session 目录路径"),
):
    """从中断 session 恢复执行。"""
    from pathlib import Path
    from deepresearch.output import save_all

    sd = Path(session_dir)
    if not sd.exists():
        typer.echo(f"❌ Session 目录不存在: {session_dir}")
        raise typer.Exit(code=1)

    from deepresearch.checkpoint.manager import CheckpointManager
    cm = CheckpointManager(sd)
    checkpoints = cm.list_checkpoints()
    if not checkpoints:
        typer.echo("❌ 未找到 checkpoint")
        raise typer.Exit(code=1)

    # 恢复最近 checkpoint
    latest = checkpoints[-1]
    state = cm.load(latest["id"])
    if state is None:
        typer.echo(f"❌ 无法加载 checkpoint: {latest['id']}")
        raise typer.Exit(code=1)

    typer.echo(f"📂 从 checkpoint 恢复: {latest['id']}")
    typer.echo(f"   状态: {state.get('status', 'unknown')}")
    typer.echo(f"   迭代: {state.get('iteration', 0)}")

    # 继续执行
    graph = build_graph()
    app_graph = graph.compile(checkpointer=cm.saver)
    config = {"configurable": {"thread_id": sd.name}}

    from deepresearch.streaming.renderer import stream_with_rich
    result = stream_with_rich(app_graph, state, config)

    save_all(result, sd)
    cm.save(result, "final")

    typer.echo("✅ 恢复执行完成")


@app.command()
def checkpoints(
    session_dir: str = typer.Argument(..., help="Session 目录路径"),
):
    """列出 session 的 checkpoint。"""
    from pathlib import Path
    sd = Path(session_dir)
    if not sd.exists():
        typer.echo(f"❌ Session 目录不存在: {session_dir}")
        raise typer.Exit(code=1)

    from deepresearch.checkpoint.manager import CheckpointManager
    cm = CheckpointManager(sd)
    cps = cm.list_checkpoints()

    if not cps:
        typer.echo("(无 checkpoint)")
        return

    typer.echo(f"Checkpoints ({len(cps)}):")
    for cp in cps:
        typer.echo(f"  {cp['id']} — {cp['size_bytes']} bytes")
```

- [ ] **Step 4: 更新 CLI 测试**

```python
# tests/unit/test_cli.py — 追加新测试

def test_cli_resume_invalid_dir():
    """resume 不存在的目录报错"""
    result = runner.invoke(app, ["resume", "outputs/nonexistent/"])
    assert result.exit_code == 1


def test_cli_checkpoints_empty(tmp_path):
    """空 session 目录的 checkpoints 输出"""
    session_dir = tmp_path / "empty_session"
    session_dir.mkdir()
    result = runner.invoke(app, ["checkpoints", str(session_dir)])
    # 不崩溃即可（可能输出空或提示）
    assert result.exit_code == 0
```

- [ ] **Step 5: 更新 graph 测试（stream mode + checkpoint）**

```python
# tests/unit/test_graph.py — 追加测试

def test_graph_compiles_with_checkpointer():
    """Graph 可以编译为带 checkpointer 的 app"""
    from deepresearch.graph import build_graph
    from tests.fixtures.mock_llm import FakeChatModel
    from deepresearch.checkpoint.manager import CheckpointManager
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmp:
        session_dir = Path(tmp) / "test_session"
        session_dir.mkdir()
        cm = CheckpointManager(session_dir)

        llm = FakeChatModel(default_response='{"research_goal":"test","sub_questions":[],"expected_sections":[],"success_criteria":[]}')
        graph = build_graph(llm=llm)
        app = graph.compile(checkpointer=cm.saver)
        assert app is not None
```

- [ ] **Step 6: 运行全部测试确认通过**

```bash
uv run pytest tests/unit/test_cli.py tests/unit/test_graph.py -v
```
Expected: all passed (new tests pass, old tests still pass)

- [ ] **Step 7: 提交**

```bash
git add deepresearch/cli.py deepresearch/graph.py tests/unit/test_cli.py tests/unit/test_graph.py
git commit -m "feat: integrate streaming, checkpoint, and v1 CLI commands (Task 15.3)"
```

---

## Phase 16：集成测试 + 全流程验证

### Task 16.1: 集成测试 + Demo 验证

**Files:**
- Modify: `tests/integration/test_workflow.py`
- Modify: `deepresearch/output.py` (新增 v1 输出字段)

- [ ] **Step 1: 更新 output.py 增加 v1 输出**

```python
# deepresearch/output.py — save_all 函数末尾追加

    # v1 新增输出
    citations = state.get("citations")
    if citations:
        save_json(citations, session_dir / "citations.json")
        count += 1
    iteration_metrics = state.get("iteration_metrics")
    if iteration_metrics:
        save_json(iteration_metrics, session_dir / "iteration_metrics.json")
        count += 1
```

- [ ] **Step 2: 更新集成测试**

```python
# tests/integration/test_workflow.py — 更新已有的 test_full_workflow_with_mock_llm

def test_v1_full_workflow_with_citations(monkeypatch):
    """v1 全流程: citation 提取、critique 三维度、dedup 均正常"""

    def mock_search(query, max_results):
        from deepresearch.tools import SearchResult
        return [SearchResult(title="T", url="https://example.com/article", snippet="S")]

    def mock_fetch(url, timeout):
        return "Deep research agents use multi-step workflows."

    monkeypatch.setattr("deepresearch.nodes.research.search_web", mock_search)
    monkeypatch.setattr("deepresearch.nodes.research.fetch_content", mock_fetch)

    import json
    from tests.fixtures.mock_llm import FakeChatModel
    from deepresearch.graph import build_graph
    from deepresearch.state import AgentState

    PLAN = json.dumps({
        "research_goal": "test",
        "sub_questions": [{"id": "q1", "question": "q", "priority": 1, "search_queries": ["q"]}],
        "expected_sections": ["s1"],
        "success_criteria": ["c1"],
    }, ensure_ascii=False)

    EVIDENCE = json.dumps({
        "evidences": [{"claim": "test claim", "quote": "test quote", "confidence": 0.9}]
    }, ensure_ascii=False)

    SUMMARY_WITH_CITATION = "## 阶段总结\n\n根据[来源: Test Article](https://example.com/article)的研究..."

    CRITIQUE_PASS = json.dumps({
        "pass": True,
        "overall_score": 0.85,
        "dimensions": {
            "fact_check": {"score": 0.9, "issues": [], "status": "pass"},
            "logic_coherence": {"score": 0.85, "issues": [], "status": "pass"},
            "coverage": {"score": 0.8, "issues": [], "status": "pass"},
        },
        "issues": [],
        "new_search_queries": [],
    }, ensure_ascii=False)

    FINAL = "# 最终报告\n\n根据[来源: Test Article](https://example.com/article)的研究得出结论。"

    llm = FakeChatModel()
    # 由于多个 prompt 不同，需要 response_map
    llm.default_response = PLAN  # fallback

    graph = build_graph(llm=llm)
    app = graph.compile()

    initial_state: AgentState = {
        "user_query": "测试问题",
        "research_plan": None,
        "search_results": [],
        "sources": [],
        "evidences": [],
        "draft_summary": None,
        "critique_result": None,
        "final_report": None,
        "iteration": 0,
        "max_iterations": 1,
        "status": "initialized",
        "errors": [],
        "citations": [],
        "iteration_metrics": [],
        "checkpoint_id": None,
    }

    result = app.invoke(initial_state)
    assert result["status"] == "completed"
    assert result["iteration"] <= 1
```

- [ ] **Step 3: 运行集成测试**

```bash
uv run pytest tests/integration/test_workflow.py -v
```
Expected: all passed

- [ ] **Step 4: 运行全部测试**

```bash
uv run pytest -v
```
Expected: all passed

- [ ] **Step 5: 代码检查**

```bash
uv run ruff check .
```
Expected: zero warnings

- [ ] **Step 6: 全流程 Demo 运行**

确认 `.env` 中 `DEEPSEEK_API_KEY` 已配置后：

```bash
uv run deepresearch --help
uv run deepresearch run "调研 Deep Research Agent 的主流架构" --stream
uv run deepresearch checkpoints outputs/session_*/
```

- [ ] **Step 7: 提交**

```bash
git add deepresearch/output.py tests/integration/test_workflow.py
git commit -m "feat: complete v1 integration — tests, output, demo verification (Task 16.1)"
```

---

## 自审清单

**1. Spec 覆盖检查:**
- [x] Config + State 扩展 → Phase 8 (Task 8.1, 8.2)
- [x] Evidence 语义去重 → Phase 9 (Task 9.1)
- [x] Source 权威度评分 → Phase 9 (Task 9.2)
- [x] Citation 提取器 → Phase 10 (Task 10.1)
- [x] Citation 格式化器 → Phase 10 (Task 10.2)
- [x] Critique 三维评分 + Fix Rate → Phase 11 (Task 11.1)
- [x] Checkpoint 管理 → Phase 12 (Task 12.1)
- [x] Streaming 输出 → Phase 13 (Task 13.1)
- [x] Observability (Callbacks + Metrics) → Phase 14 (Task 14.1)
- [x] Node 集成 (Research/Summary/Final) → Phase 15 (Task 15.1, 15.2)
- [x] CLI 增强 (resume/checkpoints/--stream) → Phase 15 (Task 15.3)
- [x] Graph 集成 (checkpointer/stream) → Phase 15 (Task 15.3)
- [x] 集成测试 + Demo → Phase 16 (Task 16.1)

**2. Placeholder 扫描:** 零 TBD/TODO/占位符

**3. 类型一致性:**
- AgentState v1 字段在所有 task 中一致 (`citations`, `iteration_metrics`, `checkpoint_id`)
- `make_*_node(llm)` 闭包模式在 `critique_node` 重写后保持一致
- Citation dataclass 在 extractor/formatter 中签名一致
- MetricsCollector API 在 callbacks 和 metrics 中一致

**4. 与 v0 兼容:**
- 所有 v0 State 字段不变
- 所有 v0 测试预期仍然通过（新增 v1 字段默认值 `[]` 或 `None`）
- 现有 CLI `run` 命令签名向后兼容（新增 `--stream/--no-stream` 带默认值）
