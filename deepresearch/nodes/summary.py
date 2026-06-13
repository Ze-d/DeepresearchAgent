# deepresearch/nodes/summary.py
import logging

from langchain_core.language_models import BaseChatModel

from deepresearch.state import AgentState
from deepresearch.prompts import build_summarizer_messages

logger = logging.getLogger(__name__)


def make_summary_node(llm: BaseChatModel):
    """创建 summary_node（闭包注入 LLM）。"""

    def summary_node(state: AgentState) -> dict:
        logger.info("Summary node: generating draft summary")

        plan = state.get("research_plan") or {}
        evidences = state.get("evidences", [])

        messages = build_summarizer_messages(
            user_query=state["user_query"],
            research_plan=plan,
            evidences=evidences,
        )

        response = llm.invoke(messages)
        draft = str(response.content) if hasattr(response, "content") else str(response)

        return {
            "draft_summary": draft,
            "status": "summarized",
        }

    return summary_node


# 模块级 summary_node —— 仅用于向后兼容 __init__.py / graph.py 的现有导入。
# 新代码应使用 make_summary_node(llm) 工厂获取 LLM 驱动的节点。
def summary_node(state: AgentState) -> dict:
    """Standalone summary node (backward compat mock)."""
    logger.info("Summary node (backward-compat mock): returning placeholder")
    return {
        "draft_summary": "Backward compat summary placeholder.",
        "status": "summarized",
    }
