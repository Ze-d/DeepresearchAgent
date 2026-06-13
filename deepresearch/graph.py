# deepresearch/graph.py
import logging

from langchain_core.language_models import BaseChatModel
from langgraph.graph import StateGraph, START, END

from deepresearch.state import AgentState
from deepresearch.nodes import (
    make_plan_node,
    make_research_node,
    make_summary_node,
    make_critique_node,
    make_final_node,
)
from deepresearch.llm import build_llm

logger = logging.getLogger(__name__)


def route_after_critique(state: AgentState) -> str:
    """Conditional routing: decide whether to continue research or go to final.

    Returns:
        "final" — critique passed or max iterations exceeded
        "research" — need further research
    """
    critique = state.get("critique_result") or {}
    iteration = state.get("iteration", 0)
    max_iterations = state.get("max_iterations", 2)

    if critique.get("pass") is True:
        logger.info("Critique passed (iteration %d/%d) → routing to final", iteration, max_iterations)
        return "final"

    if iteration >= max_iterations:
        logger.info("Max iterations reached (%d/%d) → routing to final", iteration, max_iterations)
        return "final"

    logger.info("Critique not passed (iteration %d/%d) → continuing research", iteration, max_iterations)
    return "research"


def route_after_plan(state: AgentState) -> str:
    """Conditional routing: stop the workflow when planning failed."""
    if state.get("status") == "error" or not state.get("research_plan"):
        logger.info("Planning failed → ending workflow")
        return "end"

    logger.info("Planning succeeded → routing to research")
    return "research"


def build_graph(llm: BaseChatModel | None = None) -> StateGraph:
    """构建 DeepResearch Agent StateGraph。

    Args:
        llm: LLM 实例。为 None 时自动调用 build_llm()。
    """
    if llm is None:
        llm = build_llm()

    logger.info("Building StateGraph: plan → research → summary → critique → {final|research}")

    graph = StateGraph(AgentState)

    graph.add_node("plan", make_plan_node(llm))
    graph.add_node("research", make_research_node(llm))
    graph.add_node("summary", make_summary_node(llm))
    graph.add_node("critique", make_critique_node(llm))
    graph.add_node("final", make_final_node(llm))

    graph.add_edge(START, "plan")
    graph.add_conditional_edges(
        "plan",
        route_after_plan,
        {
            "research": "research",
            "end": END,
        },
    )
    graph.add_edge("research", "summary")
    graph.add_edge("summary", "critique")

    graph.add_conditional_edges(
        "critique",
        route_after_critique,
        {
            "research": "research",
            "final": "final",
        },
    )

    graph.add_edge("final", END)

    logger.debug("StateGraph built successfully with %d nodes", 5)
    return graph
