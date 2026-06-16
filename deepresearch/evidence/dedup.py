import json
import logging
import re
import time

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

_BATCH_DEDUP_PROMPT = """你是一个文本去重助手。以下是来自同一来源的多条 evidence，找出表达相同信息的重复条目。

对于每一组表达相同核心信息的 evidence，只保留 confidence 最高的那条，其余标记为重复。

证据列表（JSON）：
{evidences_json}

要求：
1. 仔细比较每条 evidence 的 claim，判断核心信息是否一致。
2. 对于每组重复，只标记 confidence 较低的需要移除。
3. 如果多条 evidence 互不重复，返回空列表。

返回 JSON（只包含 remove_ids 数组）：
{{"remove_ids": ["id2", "id4", ...]}}"""


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


def _dedup_within_group(
    evidences: list[dict], llm: BaseChatModel
) -> tuple[list[dict], int]:
    """对同一 source 组内的 evidence 进行批量语义去重。

    不同于逐对比较，此函数使用一次 LLM 调用识别组内所有重复条目，
    将 N*(N-1)/2 次 API 调用压缩为 1 次。

    Returns:
        (去重后的 evidence 列表, LLM 调用次数: 0 或 1)
    """
    if len(evidences) <= 1:
        return evidences, 0

    # 按 confidence 降序排列
    sorted_evs = sorted(evidences, key=lambda e: e.get("confidence", 0), reverse=True)

    # 构建紧凑的 evidence 列表，截断过长的 claim 以控制 token
    ev_list = []
    for i, ev in enumerate(sorted_evs):
        claim = ev.get("claim", "")
        ev_list.append({
            "index": i,
            "id": ev.get("id", ""),
            "claim": claim[:300],
            "confidence": round(ev.get("confidence", 0), 2),
        })

    prompt = _BATCH_DEDUP_PROMPT.format(
        evidences_json=json.dumps(ev_list, ensure_ascii=False)
    )

    try:
        response = llm.invoke([SystemMessage(content=prompt)])
        text = str(response.content) if hasattr(response, "content") else str(response)

        # 提取 JSON（支持 ```json ... ``` 包裹）
        match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
        if match:
            text = match.group(1).strip()

        data = json.loads(text)
        remove_ids: set[str] = set(data.get("remove_ids", []))
    except Exception:
        logger.warning("Batch dedup LLM call failed, keeping all", exc_info=True)
        return sorted_evs, 1

    kept = [ev for ev in sorted_evs if ev.get("id") not in remove_ids]
    removed = len(sorted_evs) - len(kept)

    if removed:
        _get_console().print(
            f"      去重: {len(sorted_evs)}→{len(kept)} (移除 {removed})"
        )
    else:
        _get_console().print(
            f"      去重: {len(sorted_evs)} 条无重复"
        )

    return kept, 1  # 1 次 LLM 调用


def deduplicate_evidences(evidences: list[dict], llm: BaseChatModel) -> list[dict]:
    """语义去重入口：按 source 分组，每组一次批量 LLM 调用识别重复。

    策略：
    - 按证据数量降序处理（大组 priority 更高，重复概率更大）
    - 每组使用 1 次批量 LLM 调用，而非逐对比较
    - dedup_max_calls_per_run 限制最大处理组数（防止去重时间过长）
    - 超出预算的组直接保留全部 evidence
    """
    if not settings.dedup_enabled:
        logger.debug("Dedup disabled, skipping")
        return evidences

    if not evidences:
        return []

    groups = _group_by_source(evidences)
    result: list[dict] = []

    # 分离多证据组（需要 LLM 去重）和单证据组（无需调用 LLM）
    multi_groups = [(sid, g) for sid, g in groups.items() if len(g) > 1]
    single_groups = [(sid, g) for sid, g in groups.items() if len(g) <= 1]

    # 单证据组直接保留
    for _, group in single_groups:
        result.extend(group)

    if not multi_groups:
        return result

    # 按证据数量降序排列——大组优先（重复概率更高，ROI 更大）
    multi_groups.sort(key=lambda x: len(x[1]), reverse=True)

    total_multi = len(multi_groups)
    max_groups = settings.dedup_max_calls_per_run

    if total_multi > max_groups:
        _get_console().print(
            f"   🔄 语义去重: {total_multi} 组 → 处理前 {max_groups} 大组"
        )
        # 超出预算的组合直接保留
        for _, group in multi_groups[max_groups:]:
            result.extend(group)
        multi_groups = multi_groups[:max_groups]
    else:
        _get_console().print(
            f"   🔄 语义去重: {total_multi} 组，每组 1 次批量 LLM 调用"
        )

    t0 = time.perf_counter()
    for _, group in multi_groups:
        deduped, _ = _dedup_within_group(group, llm)
        result.extend(deduped)

    elapsed = time.perf_counter() - t0
    dropped = len(evidences) - len(result)

    if dropped > 0:
        logger.info(
            "Dedup: %d groups in %.1fs — removed %d duplicates (%d → %d)",
            len(multi_groups), elapsed, dropped, len(evidences), len(result),
        )
    else:
        logger.info(
            "Dedup: %d groups in %.1fs — no duplicates found",
            len(multi_groups), elapsed,
        )

    return result
