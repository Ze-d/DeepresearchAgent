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
