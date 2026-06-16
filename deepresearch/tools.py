# deepresearch/tools.py
import importlib
import logging
import time
from dataclasses import dataclass
from typing import Any

import certifi
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

# 搜索重试配置
_MAX_RETRIES = 3
_RETRY_BACKOFF_BASE = 2.0  # seconds

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


def search_web(
    query: str,
    max_results: int = 5,
    site_filter: str | None = None,
) -> list[SearchResult]:
    """使用 DuckDuckGo 搜索网页（通过 ddgs 包），带重试和指数退避。

    Args:
        query: 搜索查询（不含 site: 前缀）。
        max_results: 最大结果数。
        site_filter: 可选单一站点过滤（仅域名，如 "arxiv.org"，不含 "site:" 前缀）。

    Note:
        DuckDuckGo 的 site: 操作符仅支持单个站点。多个 site: 会导致查询失败。
    """
    if DDGS is None:
        logger.warning("Neither ddgs nor duckduckgo_search is installed")
        return []

    # 构建搜索查询：DuckDuckGo 仅支持单个 site: 操作符
    if site_filter:
        search_query = f"{query} site:{site_filter}"
    else:
        search_query = query

    last_exc: Exception | None = None
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            with DDGS() as ddgs:
                raw = list(ddgs.text(search_query, max_results=max_results))
            break  # 成功，跳出重试循环
        except Exception as exc:
            last_exc = exc
            if attempt < _MAX_RETRIES:
                backoff = _RETRY_BACKOFF_BASE ** attempt
                logger.debug(
                    "DuckDuckGo search attempt %d/%d failed for: %s — retrying in %.1fs",
                    attempt, _MAX_RETRIES, search_query, backoff,
                )
                time.sleep(backoff)
    else:
        # for 循环未被 break 中断 → 所有重试均失败
        logger.warning(
            "DuckDuckGo search failed after %d attempts for: %s — %s: %s",
            _MAX_RETRIES, search_query, type(last_exc).__name__, last_exc,
        )
        return []

    results = []
    for item in raw:
        results.append(SearchResult(
            title=item.get("title", ""),
            url=item.get("href", ""),
            snippet=item.get("body", ""),
        ))
    return results


def fetch_content(url: str, timeout: float = 8.0) -> str:
    """从 URL 抓取并抽取网页正文。

    使用 certifi CA bundle 显式指定证书链，避免 Windows 上系统证书存储不可达
    导致的 "unable to get local issuer certificate" 错误。
    """
    try:
        resp = httpx.get(
            url,
            timeout=timeout,
            follow_redirects=True,
            headers=_HEADERS,
            verify=certifi.where(),
        )
        resp.raise_for_status()
        text = extract(resp.text)
        return text or ""
    except Exception as exc:
        logger.warning("Content fetch failed for: %s — %s: %s", url, type(exc).__name__, exc)
        return ""
