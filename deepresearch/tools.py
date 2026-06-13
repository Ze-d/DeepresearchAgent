# deepresearch/tools.py
import importlib
import logging
from dataclasses import dataclass
from typing import Any

import httpx
from trafilatura import extract

logger = logging.getLogger(__name__)

# 伪装浏览器 UA，避免被目标网站 403 拒绝
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
}

# 模块级导入 DDGS，方便测试 mock（优先 ddgs，回退 duckduckgo_search）
def _load_ddgs() -> Any:
    for module_name in ("ddgs", "duckduckgo_search"):
        try:
            module = importlib.import_module(module_name)
        except ImportError:
            continue
        return getattr(module, "DDGS", None)
    return None


DDGS: Any = _load_ddgs()


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str


def search_web(query: str, max_results: int = 5) -> list[SearchResult]:
    """使用 DuckDuckGo 搜索网页（通过 ddgs 包）。"""
    if DDGS is None:
        logger.warning("Neither ddgs nor duckduckgo_search is installed")
        return []

    try:
        with DDGS() as ddgs:
            raw = list(ddgs.text(query, max_results=max_results))
    except Exception:
        logger.warning("DuckDuckGo search failed for: %s", query)
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
        resp = httpx.get(url, timeout=timeout, follow_redirects=True, headers=_HEADERS)
        resp.raise_for_status()
        text = extract(resp.text)
        return text or ""
    except Exception:
        logger.warning("Content fetch failed for: %s", url)
        return ""
