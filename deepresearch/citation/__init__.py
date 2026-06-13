from deepresearch.citation.extractor import extract_citations, validate_citations

try:
    from deepresearch.citation.formatter import (  # noqa: F401
        format_inline_citations,
        format_reference_list,
        merge_citations_into_report,
    )
except ImportError:
    # Task 10.2 会创建 formatter 模块
    format_inline_citations = None
    format_reference_list = None
    merge_citations_into_report = None

__all__ = [
    "extract_citations",
    "validate_citations",
    "format_inline_citations",
    "format_reference_list",
    "merge_citations_into_report",
]
