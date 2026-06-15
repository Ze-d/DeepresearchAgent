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
        "research_agent" — need further research (loops back)
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
    return "research_agent"


def route_after_plan(state: AgentState) -> str:
    """Conditional routing: stop the workflow when planning failed."""
    if state.get("status") == "error" or not state.get("research_plan"):
        logger.info("Planning failed → ending workflow")
        return "end"

    logger.info("Planning succeeded → routing to research_agent")
    return "research_agent"


def fanout_to_agents(state: AgentState) -> list[Send]:
    """根据每个 sub_question 的 source_types 创建并行 Send"""
    if state.get("status") == "error" or not state.get("research_plan"):
        logger.info("Fan-out: plan error or missing → no Sends")
        return []
    plan = state.get("research_plan") or {}
    sub_questions = plan.get("sub_questions", [])

    # Handle critique follow-up: route to all agents
    critique = state.get("critique_result") or {}
    if critique.get("pass") is False and critique.get("new_search_queries"):
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
    logger.info("Fan-out: %d Send(s) to research_agent", len(sends))
    return sends


def build_graph(llm: BaseChatModel | None = None) -> StateGraph:
    """构建 DeepResearch V2.1 StateGraph。

    Args:
        llm: LLM 实例。为 None 时自动调用 build_llm()。
    """
    if llm is None:
        llm = build_llm()

    logger.info("Building V2.1 StateGraph: plan → research_agent(×N) → merge → summary → critique")

    graph = StateGraph(AgentState)

    graph.add_node("plan", make_plan_node(llm))
    graph.add_node("research_agent", make_research_agent(llm))
    graph.add_node("merge", make_merge_node(llm))
    graph.add_node("summary", make_summary_node(llm))
    graph.add_node("critique", make_critique_node(llm))
    graph.add_node("final", make_final_node(llm))

    graph.add_edge(START, "plan")
    graph.add_conditional_edges(
        "plan",
        fanout_to_agents,
        path_map=["research_agent"],
    )
    graph.add_edge("research_agent", "merge")
    graph.add_edge("merge", "summary")
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
