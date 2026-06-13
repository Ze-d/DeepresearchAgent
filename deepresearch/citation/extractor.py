import re
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# 匹配 [来源: <标题>](<URL>)
_CITATION_PATTERN = re.compile(r"\[来源:\s*([^\]]+?)\]\(([^)]+)\)")


@dataclass
class Citation:
    id: int
    title: str
    url: str
    context: str = ""


def extract_citations(text: str) -> list[Citation]:
    """从 Markdown 文本中提取所有 [来源: title](url) 引用，分配唯一编号。

    Args:
        text: 包含 citation 的 Markdown 文本。

    Returns:
        Citation 列表，同一 URL 只保留一个（按首次出现顺序）。
    """
    matches = _CITATION_PATTERN.findall(text)
    if not matches:
        return []

    seen_urls: dict[str, Citation] = {}
    next_id = 1

    for title, url in matches:
        title = title.strip()
        url = url.strip()

        if url in seen_urls:
            continue

        # 提取上下文（匹配位置前后各 50 字符）
        context = ""
        for m in _CITATION_PATTERN.finditer(text):
            if m.group(1).strip() == title and m.group(2).strip() == url:
                start = max(0, m.start() - 50)
                end = min(len(text), m.end() + 50)
                context = text[start:end]
                break

        citation = Citation(id=next_id, title=title, url=url, context=context)
        seen_urls[url] = citation
        next_id += 1

    result = sorted(seen_urls.values(), key=lambda c: c.id)
    logger.debug("Extracted %d unique citations from text", len(result))
    return result


def validate_citations(citations: list[Citation], sources: list[dict]) -> list[Citation]:
    """验证 citation URL 是否在 sources 中存在。

    Args:
        citations: 提取的 citation 列表。
        sources: state 中的 sources 列表。

    Returns:
        Citation 列表。URL 不在 sources 中的 citation 记录 warning 但仍保留。
    """
    source_urls = {s.get("url", "") for s in sources}
    for c in citations:
        if c.url not in source_urls:
            logger.warning(
                "Orphan citation [%d]: %s (%s) -- URL not in collected sources",
                c.id,
                c.title,
                c.url,
            )
    return citations
