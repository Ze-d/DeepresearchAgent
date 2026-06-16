# deepresearch/nodes/research.py
import json
import logging
import re
import uuid
from typing import Any

from langchain_core.language_models import BaseChatModel

from deepresearch.state import AgentState
from deepresearch import tools as _tools
from deepresearch.prompts import build_researcher_messages
from deepresearch.config import Settings

logger = logging.getLogger(__name__)

# Rich console for real-time progress output (bypasses Live panel)
_console = None


def _get_console():
    global _console
    if _console is None:
        from rich.console import Console
        _console = Console()
    return _console


def _extract_evidences(sub_question: str, source_content: str, llm: BaseChatModel) -> list[dict]:
    """用 LLM 从 source content 中抽取 evidence 列表。"""
    messages = build_researcher_messages(sub_question, source_content)
    response = llm.invoke(messages)
    raw = str(response.content) if hasattr(response, "content") else str(response)

    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", raw, re.DOTALL)
    if match:
        raw = match.group(1).strip()

    try:
        data = json.loads(raw)
        return data.get("evidences", [])
    except json.JSONDecodeError:
        logger.warning("Failed to parse evidence JSON: %s", raw[:200])
        return []


def make_research_node(llm: BaseChatModel):
    """创建 research_node（闭包注入 LLM）。"""

    def research_node(state: AgentState) -> dict:
        plan = state.get("research_plan")
        if plan is None:
            return {
                "status": "error",
                "errors": ["No research plan found. Run plan node first."],
            }

        cfg = Settings()
        all_sources: list[dict] = []
        all_evidences: list[dict] = []
        all_search_results: list[dict] = []

        critique = state.get("critique_result") or {}
        follow_up_queries = critique.get("new_search_queries") or []
        sub_questions: list[dict[str, Any]]
        if critique.get("pass") is False and follow_up_queries:
            sub_questions = [{
                "question": state.get("user_query", ""),
                "priority": 1,
                "search_queries": follow_up_queries,
            }]
        else:
            raw_sub_questions = plan.get("sub_questions", [])
            sub_questions = raw_sub_questions if isinstance(raw_sub_questions, list) else []

        sorted_qs = sorted(sub_questions, key=lambda q: q.get("priority", 99))

        search_count = 0
        max_total_searches = 6  # 单轮最多 6 次搜索，防止 API 调用过多

        for sq in sorted_qs:
            if search_count >= max_total_searches:
                break
            queries = sq.get("search_queries", [])
            for query in queries[:2]:
                if search_count >= max_total_searches:
                    break
                _get_console().print(f"   🔎 搜索 ({search_count + 1}/{max_total_searches}): {query}")
                results = _tools.search_web(query, max_results=cfg.max_search_results)
                search_count += 1
                _get_console().print(f"       找到 {len(results)} 条结果")
                for idx_r, r in enumerate(results):
                    source_id = str(uuid.uuid4())[:8]
                    source_dict = {
                        "id": source_id,
                        "title": r.title,
                        "url": r.url,
                        "snippet": r.snippet,
                        "content": None,
                        "source_type": "web",
                        "score": 0.5,
                    }
                    _get_console().print(f"       📄 抓取 ({idx_r + 1}/{len(results)}): {r.url[:80]}...")
                    content = _tools.fetch_content(r.url)
                    if content:
                        _get_console().print(f"       📝 抽取证据 ({len(content)} 字符)...")
                        source_dict["content"] = content
                        evidences = _extract_evidences(
                            sq.get("question", ""), content, llm
                        )
                        _get_console().print(f"          ✓ 得到 {len(evidences)} 条证据")
                        for ev in evidences:
                            ev["id"] = str(uuid.uuid4())[:8]
                            ev["source_id"] = source_id
                            all_evidences.append(ev)

                    all_sources.append(source_dict)
                    all_search_results.append({
                        "query": query,
                        "url": r.url,
                        "title": r.title,
                    })

        # v2.1: 语义去重已移至 merge 节点统一处理，避免多 Agent 场景下重复调用
        # v1: 对 sources 做权威度评分排序
        _get_console().print(f"   📊 来源评分排序: {len(all_sources)} 条来源...")
        from deepresearch.evidence.ranking import rank_sources
        all_sources = rank_sources(all_sources)
        top = all_sources[0].get("title", "")[:50] if all_sources else ""
        if top:
            _get_console().print(f"       最高分: {top} (score={all_sources[0].get('score', 0)})")

        logger.info("Research done: %d sources, %d evidences", len(all_sources), len(all_evidences))

        return {
            "search_results": state.get("search_results", []) + all_search_results,
            "sources": state.get("sources", []) + all_sources,
            "evidences": state.get("evidences", []) + all_evidences,
            "status": "researched",
        }

    return research_node


# Backward-compatible module-level alias for __init__.py / graph.py
# These import "research_node" directly (not via make_research_node).
def research_node(state: AgentState) -> dict:
    """Backward-compatible entry point (uses default LLM from build_llm())."""
    from deepresearch.llm import build_llm

    llm = build_llm()
    return make_research_node(llm)(state)
