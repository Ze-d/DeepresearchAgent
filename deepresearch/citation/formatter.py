import re
import logging

from deepresearch.citation.extractor import Citation

logger = logging.getLogger(__name__)


def format_inline_citations(text: str, citations: list[Citation]) -> str:
    """Replace [来源: title](url) with [1] inline markers.

    Args:
        text: Original Markdown text.
        citations: Extracted citation list.

    Returns:
        Text with inline citations replaced by numbered markers.
    """
    if not citations:
        return text

    # Replace from highest id to lowest so earlier replacements don't shift
    # the positions of later ones.
    for c in sorted(citations, key=lambda c: c.id, reverse=True):
        escaped_title = re.escape(c.title)
        pattern = rf"\[来源:\s*{escaped_title}\]\({re.escape(c.url)}\)"
        text = re.sub(pattern, f"[{c.id}]", text)

    return text


def format_reference_list(citations: list[Citation]) -> str:
    """Generate a Markdown reference list.

    Args:
        citations: Extracted citation list.

    Returns:
        Markdown-formatted reference list.
    """
    if not citations:
        return ""

    lines = ["## 参考文献", ""]
    for c in sorted(citations, key=lambda c: c.id):
        lines.append(f"[{c.id}] {c.title} — {c.url}")
    lines.append("")

    return "\n".join(lines)


def merge_citations_into_report(report: str, citations: list[Citation]) -> str:
    """Merge inline citation markers and a reference list into the report.

    Args:
        report: Original report Markdown.
        citations: Extracted citation list.

    Returns:
        Report with inline citations replaced and a reference section appended.
    """
    if not citations:
        return report

    formatted = format_inline_citations(report, citations)
    ref_list = format_reference_list(citations)
    logger.info("Merged %d citations into final report", len(citations))
    return formatted + "\n\n" + ref_list
