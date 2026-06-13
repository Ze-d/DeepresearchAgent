# deepresearch/state.py
from typing import TypedDict, Any

from pydantic import BaseModel, Field


# ——— 研究计划 ———


class SubQuestion(BaseModel):
    id: str
    question: str
    priority: int
    search_queries: list[str]


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


class Evidence(BaseModel):
    id: str
    source_id: str
    claim: str
    quote: str | None = None
    confidence: float = 0.0


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


# ——— AgentState (LangGraph TypedDict) ———


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
    checkpoint_ref: str | None
