from deepresearch.evidence.dedup import deduplicate_evidences

try:
    from deepresearch.evidence.ranking import rank_sources  # noqa: F811
except ImportError:
    rank_sources = None  # Task 9.2 会创建 ranking 模块

__all__ = ["deduplicate_evidences", "rank_sources"]
