# deepresearch/nodes/final.py
import logging
import time

from langchain_core.language_models import BaseChatModel

from deepresearch.state import AgentState
from deepresearch.prompts import build_finalizer_messages

logger = logging.getLogger(__name__)


def make_final_node(llm: BaseChatModel):
    """创建 final_node（闭包注入 LLM）。"""

    def final_node(state: AgentState) -> dict:
        t0 = time.perf_counter()
        iteration = state.get("iteration", 0)
        logger.info("[final] 开始: iteration=%d", iteration)
        print(f"\n📄 Final: 正在生成最终报告 (iteration {iteration})...")

        messages = build_finalizer_messages(
            user_query=state["user_query"],
            draft_summary=state.get("draft_summary") or "",
            critique_result=state.get("critique_result") or {},
            sources=state.get("sources", []),
        )
        response = llm.invoke(messages)
        report = str(response.content) if hasattr(response, "content") else str(response)

        # v1: 提取并格式化 citation
        from deepresearch.citation.extractor import extract_citations, validate_citations
        from deepresearch.citation.formatter import merge_citations_into_report

        citations = extract_citations(report)
        if citations:
            validated = validate_citations(citations, state.get("sources", []))
            report = merge_citations_into_report(report, validated)

        elapsed = time.perf_counter() - t0
        logger.info(
            "[final] 完成: %d 字符, %d citations (%.1fs)",
            len(report), len(citations or []), elapsed,
        )
        print(f"📄 Final: 完成 → {len(report)} 字符, {len(citations or [])} citations ({elapsed:.1f}s)")

        return {
            "final_report": report,
            "status": "completed",
            "citations": [{"id": c.id, "title": c.title, "url": c.url}
                          for c in (citations or [])],
        }

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
