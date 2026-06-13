# deepresearch/nodes/critique.py
import json
import logging
import re
import time

from langchain_core.language_models import BaseChatModel

from deepresearch.state import AgentState
from deepresearch.prompts import build_critique_messages

logger = logging.getLogger(__name__)


def compute_fix_rate(prev_issues_count: int | None, current_issues_count: int, iteration: int) -> float | None:
    """计算 issue 修复率。首轮返回 None。"""
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

        prev_metrics = state.get("iteration_metrics", [])
        prev_issues_count = len(prev_metrics[-1].get("issues", [])) if prev_metrics else None

        t0 = time.perf_counter()
        messages = build_critique_messages(
            user_query=state["user_query"],
            draft_summary=state.get("draft_summary", ""),
            sources=state.get("sources", []),
            evidences=state.get("evidences", []),
            prev_critique=state.get("critique_result"),
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

        # JSON parse with markdown fence extraction
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

        metric = {
            "iteration": new_iteration,
            "overall_score": critique["overall_score"],
            "dimensions": critique["dimensions"],
            "issues_count": current_issues_count,
            "fix_rate": fix_rate,
            "tokens_used": 0,
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
