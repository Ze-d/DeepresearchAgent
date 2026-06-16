# deepresearch/state.py
import operator
from typing import Annotated, TypedDict, Any

from pydantic import BaseModel, Field


# ——— 研究计划 ———


class SubQuestion(BaseModel):
    id: str
    question: str
    priority: int
    search_queries: list[str]
    source_types: list[str] = ["blog"]  # v2.1 新增


class ResearchPlan(BaseModel):
    research_goal: str
    sub_questions: list[SubQuestion]
    expected_sections: list[str]
    success_criteria: list[str]


# ——— 来源与证据 ———


class Source(BaseModel):
    id: str
    title: str
    url: str
    snippet: str | None = None
    content: str | None = None
    source_type: str = "unknown"
    score: float = 0.0
    source_agent: str = "unknown"  # v2.1: which agent found this source


class Evidence(BaseModel):
    id: str
    source_id: str
    claim: str
    quote: str | None = None
    confidence: float = 0.0
    source_agent: str = "unknown"  # v2.1: which agent found this evidence


# ——— Critique ———


class CritiqueIssue(BaseModel):
    type: str
    severity: str
    description: str
    suggested_action: str


class CritiqueResult(BaseModel):
    model_config = {"populate_by_name": True}
    pass_: bool = Field(alias="pass")
    score: float
    issues: list[CritiqueIssue]
    new_search_queries: list[str]

    def model_dump(self, **kwargs):
        kwargs.setdefault("by_alias", True)
        return super().model_dump(**kwargs)


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


# ——— 最终报告 ———


class FinalReport(BaseModel):
    title: str
    markdown: str
    sources: list[Source]
    limitations: list[str]


# ——— v2.1: Merge 质量报告 ———


class MergeSummary(BaseModel):
    """v2.1: Merge 节点的质量报告，汇总并行 Agent 产出的交叉验证结果。"""
    total_sources: int = 0
    total_evidences: int = 0
    cross_validated_count: int = 0
    unique_findings_per_agent: dict[str, int] = {}
    conflicts: list[dict[str, Any]] = []
    source_bias_warnings: list[str] = []
    coverage_gaps: list[str] = []


# ——— AgentState (LangGraph TypedDict) ———


class AgentState(TypedDict):
    user_query: str
    research_plan: dict[str, Any] | None
    # 以下三个字段使用 operator.add reducer，支持多个并行 research_agent
    # 在同一 superstep 中并发写入（Send API fan-out）
    search_results: Annotated[list[dict[str, Any]], operator.add]
    sources: Annotated[list[dict[str, Any]], operator.add]
    evidences: Annotated[list[dict[str, Any]], operator.add]
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
    checkpoint_ref: str | None
    # v2.1 新增
    agent_outputs: list[dict[str, Any]]   # 每个 Agent 的中间产出
    merge_summary: dict[str, Any] | None  # MergeSummary dict
    human_review: dict[str, Any] | None   # 人工审核结果
    agent_profile: str | None             # research_agent 的 profile key（Send API 注入）
    sub_question: dict[str, Any] | None   # 单个 sub_question（Send API 注入）
