# deepresearch/nodes/critique.py
import json
import logging
import re

from langchain_core.language_models import BaseChatModel

from deepresearch.state import AgentState
from deepresearch.prompts import build_critique_messages

logger = logging.getLogger(__name__)


def make_critique_node(llm: BaseChatModel):
    """创建 critique_node（闭包注入 LLM）。"""

    def critique_node(state: AgentState) -> dict:
        iteration = state.get("iteration", 0)
        new_iteration = iteration + 1

        messages = build_critique_messages(
            user_query=state["user_query"],
            draft_summary=state.get("draft_summary", ""),
            sources=state.get("sources", []),
            evidences=state.get("evidences", []),
        )

        response = llm.invoke(messages)
        raw = str(response.content) if hasattr(response, "content") else str(response)

        match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", raw, re.DOTALL)
        if match:
            raw = match.group(1).strip()

        try:
            data = json.loads(raw)
            critique = {
                "pass": data.get("pass", True),
                "score": data.get("score", 0.0),
                "issues": data.get("issues", []),
                "new_search_queries": data.get("new_search_queries", []),
            }
        except (json.JSONDecodeError, TypeError):
            logger.warning("Critique JSON parse failed, defaulting to pass=True")
            critique = {
                "pass": True,
                "score": 0.5,
                "issues": [],
                "new_search_queries": [],
            }

        return {
            "critique_result": critique,
            "iteration": new_iteration,
            "status": "critiqued",
        }

    return critique_node


# 模块级 critique_node —— 仅用于向后兼容 __init__.py / graph.py 的现有导入。
# 新代码应使用 make_critique_node(llm) 工厂获取 LLM 驱动的节点。
def critique_node(state: AgentState) -> dict:
    """Standalone critique node (backward compat mock)."""
    iteration = state.get("iteration", 0)
    new_iteration = iteration + 1
    logger.info("Critique node (backward-compat mock): pass=True")
    return {
        "critique_result": {
            "pass": True,
            "score": 0.9,
            "issues": [],
            "new_search_queries": [],
        },
        "iteration": new_iteration,
        "status": "critiqued",
    }
