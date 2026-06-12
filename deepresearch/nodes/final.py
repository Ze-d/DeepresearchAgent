# deepresearch/nodes/final.py
import logging

from langchain_core.language_models import BaseChatModel

from deepresearch.state import AgentState
from deepresearch.prompts import build_finalizer_messages

logger = logging.getLogger(__name__)


def make_final_node(llm: BaseChatModel):
    """创建 final_node（闭包注入 LLM）。"""

    def final_node(state: AgentState) -> dict:
        logger.info("Final node: generating report")
        messages = build_finalizer_messages(
            user_query=state["user_query"],
            draft_summary=state.get("draft_summary", ""),
            critique_result=state.get("critique_result", {}),
            sources=state.get("sources", []),
        )
        response = llm.invoke(messages)
        report = str(response.content) if hasattr(response, "content") else str(response)
        return {"final_report": report, "status": "completed"}

    return final_node


# 模块级 final_node —— 仅用于向后兼容 __init__.py / graph.py 的现有导入。
# 新代码应使用 make_final_node(llm) 工厂获取 LLM 驱动的节点。
def final_node(state: AgentState) -> dict:
    """Standalone final node (backward compat)."""
    logger.info("Final node (backward-compat mock): returning placeholder report")
    return {
        "final_report": (
            "# Deep Research Agent Architecture Research Report\n\n"
            "## Abstract\n\n"
            "This report investigates the mainstream architectures and representative "
            "projects of Deep Research Agents.\n\n"
            "## Key Findings\n\n"
            "1. Most adopt multi-stage workflows\n"
            "2. Critique-driven iteration is a common pattern\n\n"
            "## Limitations\n\n"
            "- Limited number of sources\n"
            "- Not all open source projects covered\n\n"
            "## References\n\n"
            "- [Deep Research Survey](https://example.com/survey)\n"
        ),
        "status": "completed",
    }
