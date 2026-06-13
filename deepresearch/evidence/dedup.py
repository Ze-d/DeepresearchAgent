import logging

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import SystemMessage

from deepresearch.config import settings

logger = logging.getLogger(__name__)

# Rich console for progress output
_console = None


def _get_console():
    global _console
    if _console is None:
        from rich.console import Console
        _console = Console()
    return _console

_DEDUP_PROMPT = """你是一个文本去重助手。以下是两条 evidence，判断它们是否表达相同的信息。

Evidence A:
claim: "{claim_a}"
quote: "{quote_a}"

Evidence B:
claim: "{claim_b}"
quote: "{quote_b}"

只回答 YES 或 NO。如果两条 evidence 的核心信息一致（即使措辞不同），回答 YES。"""


def _group_by_source(evidences: list[dict]) -> dict[str, list[dict]]:
    """按 source_id 分组。"""
    groups: dict[str, list[dict]] = {}
    for ev in evidences:
        sid = ev.get("source_id", "")
        groups.setdefault(sid, []).append(ev)
    return groups


def _are_duplicates(ev_a: dict, ev_b: dict, llm: BaseChatModel) -> bool:
    """用 LLM 判断两条 evidence 是否语义重复。"""
    prompt = _DEDUP_PROMPT.format(
        claim_a=ev_a.get("claim", ""),
        quote_a=ev_a.get("quote", ""),
        claim_b=ev_b.get("claim", ""),
        quote_b=ev_b.get("quote", ""),
    )
    try:
        response = llm.invoke([SystemMessage(content=prompt)])
        text = str(response.content).strip().upper() if hasattr(response, "content") else ""
        return "YES" in text
    except Exception:
        logger.warning("Dedup LLM call failed, treating as non-duplicate", exc_info=True)
        return False


def _dedup_within_group(evidences: list[dict], llm: BaseChatModel, max_calls: int) -> list[dict]:
    """对同一 source 组内的 evidence 进行语义去重。"""
    if len(evidences) <= 1:
        return evidences

    # 按 confidence 降序排列
    sorted_evs = sorted(evidences, key=lambda e: e.get("confidence", 0), reverse=True)
    kept: list[dict] = []
    removed_ids: set[str] = set()
    call_count = 0

    total_pairs = min(len(sorted_evs) * (len(sorted_evs) - 1) // 2, max_calls)
    _get_console().print(f"      去重: 最多 {total_pairs} 对比较...")
    for i, ev_a in enumerate(sorted_evs):
        if ev_a["id"] in removed_ids:
            continue
        kept.append(ev_a)
        for ev_b in sorted_evs[i + 1:]:
            if ev_b["id"] in removed_ids:
                continue
            if call_count >= max_calls:
                break
            if _are_duplicates(ev_a, ev_b, llm):
                removed_ids.add(ev_b["id"])
                logger.debug("Dedup: removed %s (duplicate of %s)", ev_b["id"], ev_a["id"])
            call_count += 1
    if removed_ids:
        _get_console().print(f"      去重完成: 移除 {len(removed_ids)} 条重复")

    return kept


def deduplicate_evidences(evidences: list[dict], llm: BaseChatModel) -> list[dict]:
    """语义去重入口：按 source 分组，组内 LLM 判断重复，保留 confidence 更高者。"""
    if not settings.dedup_enabled:
        logger.debug("Dedup disabled, skipping")
        return evidences

    if not evidences:
        return []

    groups = _group_by_source(evidences)
    max_calls = settings.dedup_max_calls_per_run
    result: list[dict] = []

    for source_id, group in groups.items():
        deduped = _dedup_within_group(group, llm, max_calls)
        result.extend(deduped)

    dropped = len(evidences) - len(result)
    if dropped > 0:
        logger.info("Dedup: removed %d duplicate evidences (%d → %d)", dropped, len(evidences), len(result))

    return result
