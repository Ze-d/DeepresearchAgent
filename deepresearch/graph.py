# deepresearch/graph.py
import logging

from langchain_core.language_models import BaseChatModel
from langgraph.graph import StateGraph, START, END
from langgraph.types import Send

from deepresearch.state import AgentState
from deepresearch.nodes import (
    make_plan_node,
    make_research_agent,
    make_merge_node,
    make_human_review_node,         # v2.1 Phase 3
    make_summary_node,
    make_critique_node,
    make_final_node,
)
from deepresearch.llm import build_llm
from deepresearch.config import settings

logger = logging.getLogger(__name__)


def route_after_critique(state: AgentState) -> str:
    """Conditional routing: decide whether to continue research or go to final.

    Returns:
        "final" — critique passed or max iterations exceeded
        "research_agent" — need further research (loops back)
    """
    critique = state.get("critique_result") or {}
    iteration = state.get("iteration", 0)
    max_iterations = state.get("max_iterations", 2)

    if critique.get("pass") is True:
        logger.info("[route] Critique passed (iteration %d/%d) → final", iteration, max_iterations)
        print(f"\n✅ Critique: 通过 (iteration {iteration}/{max_iterations}) → 生成最终报告")
        return "final"

    if iteration >= max_iterations:
        logger.info("[route] Max iterations reached (%d/%d) → final", iteration, max_iterations)
        print(f"\n⏰ Max iterations ({max_iterations}) → 生成最终报告")
        return "final"

    logger.info("[route] Critique not passed (iteration %d/%d) → re-research", iteration, max_iterations)
    print(f"\n🔄 Critique: 不通过 (iteration {iteration}/{max_iterations}) → 追加研究")
    return "research_agent"


def route_after_plan(state: AgentState) -> str:
    """Conditional routing: stop the workflow when planning failed."""
    if state.get("status") == "error" or not state.get("research_plan"):
        logger.info("[route] Planning failed → ending workflow")
        return "end"

    logger.info("[route] Planning succeeded → fan-out to research_agent")
    return "research_agent"


def fanout_to_agents(state: AgentState) -> list[Send]:
    """根据每个 sub_question 的 source_types 创建并行 Send"""
    if state.get("status") == "error" or not state.get("research_plan"):
        logger.info("[fan-out] Plan error or missing → no Sends")
        return []
    plan = state.get("research_plan") or {}
    sub_questions = plan.get("sub_questions", [])

    # Handle critique follow-up: route to all agents
    critique = state.get("critique_result") or {}
    if critique.get("pass") is False and critique.get("new_search_queries"):
        logger.info("[fan-out] Critique follow-up with %d new queries", len(critique["new_search_queries"]))
        follow_up_sq = {
            "id": "critique_followup",
            "question": state.get("user_query", ""),
            "priority": 1,
            "search_queries": critique["new_search_queries"],
            "source_types": ["paper", "github", "blog", "docs"],
        }
        sub_questions = [follow_up_sq]

    sends: list[Send] = []
    for sq in sub_questions:
        source_types = sq.get("source_types", ["blog"])
        for st in source_types:
            sends.append(Send("research_agent", {"agent_profile": st, "sub_question": sq}))
    if not sends:
        sends.append(Send("research_agent", {
            "agent_profile": "blog",
            "sub_question": {"id": "default", "question": state["user_query"],
                             "priority": 1, "search_queries": [state["user_query"]],
                             "source_types": ["blog"]},
        }))
    logger.info("[fan-out] %d Send(s) to research_agent", len(sends))
    return sends


def build_graph(llm: BaseChatModel | None = None) -> StateGraph:
    """构建 DeepResearch V2.1 StateGraph。

    Args:
        llm: LLM 实例。为 None 时自动调用 build_llm()。
             若 settings.otel_enabled=True，自动附加 OTelCallbackHandler。
    """
    # ——— OTel 条件初始化 ———
    otel_handler = None
    _trace_node = None  # type: ignore[assignment]
    if settings.otel_enabled:
        try:
            from deepresearch.observability.otel import setup_otel
            from deepresearch.observability.otel_callback import (
                OTelCallbackHandler,
                _trace_node as _tn,
            )
            setup_otel()
            otel_handler = OTelCallbackHandler()
            _trace_node = _tn
            logger.info("[graph] OTel tracing enabled")
        except ImportError:
            logger.warning("[graph] OTel packages not installed; tracing disabled")
        except Exception:
            logger.warning("[graph] OTel setup failed; tracing disabled", exc_info=True)

    if llm is None:
        llm = build_llm(callbacks=[otel_handler] if otel_handler else None)

    wrap = _trace_node if _trace_node is not None else lambda name, fn: fn  # type: ignore[assignment]

    logger.info(
        "[graph] Building V2.1: plan → fan-out → research_agent(×N) → merge → human_review → summary → critique"
    )

    graph = StateGraph(AgentState)

    graph.add_node("plan", wrap("plan", make_plan_node(llm)))
    graph.add_node("research_agent", wrap("research_agent", make_research_agent(llm)))
    graph.add_node("merge", wrap("merge", make_merge_node(llm)))
    graph.add_node("human_review", wrap("human_review", make_human_review_node(llm)))
    graph.add_node("summary", wrap("summary", make_summary_node(llm)))
    graph.add_node("critique", wrap("critique", make_critique_node(llm)))
    graph.add_node("final", wrap("final", make_final_node(llm)))

    graph.add_edge(START, "plan")
    graph.add_conditional_edges(
        "plan",
        fanout_to_agents,
        path_map=["research_agent"],
    )
    graph.add_edge("research_agent", "merge")
    graph.add_edge("merge", "human_review")
    graph.add_edge("human_review", "summary")
    graph.add_edge("summary", "critique")

    graph.add_conditional_edges(
        "critique",
        route_after_critique,
        {
            "research_agent": "research_agent",
            "final": "final",
        },
    )

    graph.add_edge("final", END)

    logger.info("V2.1 StateGraph built: %d nodes", len(graph.nodes))
    return graph
