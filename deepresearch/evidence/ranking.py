import logging
import re
from datetime import date
from urllib.parse import urlparse

from deepresearch.config import settings

logger = logging.getLogger(__name__)

# 域名权威映射 (TLD/domain → (name, score))
_DOMAIN_AUTHORITY: dict[str, tuple[str, float]] = {
    ".edu": ("edu", 1.0),
    ".gov": ("gov", 1.0),
    "arxiv.org": ("arxiv", 0.8),
    "github.com": ("github", 0.8),
    "stackoverflow.com": ("stackoverflow", 0.8),
    "pypi.org": ("pypi", 0.8),
    "readthedocs.io": ("readthedocs", 0.8),
    ".org": ("org", 0.6),
    ".io": ("io", 0.5),
    ".com": ("com", 0.5),
    ".net": ("net", 0.5),
}

_TYPE_KEYWORDS: list[tuple[list[str], str, float]] = [
    (["abstract", "doi", "et al", "propose", "conference", "journal", "preprint"], "academic", 1.0),
    (["api reference", "documentation", "class ", "function ", "parameter", "@param"], "official_docs", 0.9),
    (["blog", "tutorial", "how to", "guide", "introduction to"], "tech_blog", 0.6),
    (["news", "announced", "released", "update:"], "news", 0.5),
    (["question", "answer", "vote", "asked", "answered"], "forum", 0.3),
]

_SOCIAL_DOMAINS = {"reddit.com", "twitter.com", "x.com", "facebook.com", "youtube.com",
                    "zhihu.com", "weibo.com", "t.co"}


def _classify_domain(url: str) -> tuple[str, float]:
    try:
        hostname = urlparse(url).hostname or ""
    except Exception:
        return ("unknown", 0.4)

    for domain, (name, score) in _DOMAIN_AUTHORITY.items():
        if not domain.startswith("."):
            if hostname == domain or hostname.endswith("." + domain):
                return (name, score)

    for sd in _SOCIAL_DOMAINS:
        if sd in hostname:
            return ("social", 0.2)

    for domain, (name, score) in _DOMAIN_AUTHORITY.items():
        if domain.startswith(".") and hostname.endswith(domain):
            return (name, score)

    return ("other", 0.4)


def _classify_source_type(snippet: str, content: str | None) -> tuple[str, float]:
    text = (snippet + " " + (content or "")).lower()
    for keywords, tp, score in _TYPE_KEYWORDS:
        if any(kw in text for kw in keywords):
            return (tp, score)
    return ("unknown", 0.4)


def _estimate_freshness(content: str | None) -> float:
    if not content:
        return 0.5
    years = re.findall(r"\b(19\d{2}|20\d{2})\b", content)
    if not years:
        return 0.5
    try:
        recent_year = max(int(y) for y in years)
    except ValueError:
        return 0.5
    current_year = date.today().year
    age = current_year - recent_year
    if age <= 1:
        return 1.0
    elif age <= 3:
        return 0.7
    elif age <= 5:
        return 0.6
    else:
        return 0.4


def _compute_content_richness(content: str | None) -> float:
    if not content:
        return 0.3
    length = len(content)
    if length > 2000:
        return 1.0
    elif length > 500:
        return 0.6
    else:
        return 0.3


def rank_sources(sources: list[dict]) -> list[dict]:
    """为 sources 计算权威度综合评分并排序。

    权重: 域名权威 40% + 来源类型 30% + 时效性 20% + 内容丰富度 10%
    """
    if not settings.source_ranking_enabled:
        logger.debug("Source ranking disabled, returning original order")
        return list(sources)

    if not sources:
        return []

    scored = []
    for src in sources:
        url = src.get("url", "")
        snippet = src.get("snippet", "")
        content = src.get("content")

        _, domain_score = _classify_domain(url)
        type_name, type_score = _classify_source_type(snippet, content)
        freshness = _estimate_freshness(content)
        richness = _compute_content_richness(content)

        final_score = round(
            domain_score * 0.40 + type_score * 0.30 + freshness * 0.20 + richness * 0.10,
            2,
        )

        existing_type = src.get("source_type")
        if existing_type in (None, "unknown", ""):
            existing_type = type_name
        scored_src = {**src, "score": final_score,
                      "source_type": existing_type}
        scored.append(scored_src)

    scored.sort(key=lambda s: s["score"], reverse=True)
    logger.debug("Ranked %d sources, top score: %.2f", len(scored), scored[0]["score"] if scored else 0)
    return scored
