# deepresearch/tools.py
import logging
from dataclasses import dataclass

import httpx
from trafilatura import extract

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str


def search_web(query: str, max_results: int = 5) -> list[SearchResult]:
    """使用 DuckDuckGo 搜索网页。"""
    try:
        from duckduckgo_search import DDGS

        with DDGS() as ddgs:
            raw = list(ddgs.text(query, max_results=max_results))
    except Exception:
        logger.warning("DuckDuckGo search failed for: %s", query, exc_info=True)
        return []

    results = []
    for item in raw:
        results.append(SearchResult(
            title=item.get("title", ""),
            url=item.get("href", ""),
            snippet=item.get("body", ""),
        ))
    return results


def fetch_content(url: str, timeout: float = 10.0) -> str:
    """从 URL 抓取并抽取网页正文。"""
    try:
        resp = httpx.get(url, timeout=timeout, follow_redirects=True)
        resp.raise_for_status()
        text = extract(resp.text)
        return text or ""
    except Exception:
        logger.warning("Content fetch failed for: %s", url, exc_info=True)
        return ""
