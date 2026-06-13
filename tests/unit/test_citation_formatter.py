from deepresearch.citation.extractor import Citation
from deepresearch.citation.formatter import (
    format_inline_citations,
    format_reference_list,
    merge_citations_into_report,
)


class TestFormatInlineCitations:
    def test_replace_with_numbers(self):
        text = "根据[来源: Docs](https://docs.com)和[来源: Paper](https://paper.com)的研究。"
        citations = [
            Citation(id=1, title="Docs", url="https://docs.com"),
            Citation(id=2, title="Paper", url="https://paper.com"),
        ]
        result = format_inline_citations(text, citations)
        assert "[来源: Docs](https://docs.com)" not in result
        assert "[来源: Paper](https://paper.com)" not in result
        assert "[1]" in result
        assert "[2]" in result

    def test_no_citations(self):
        text = "Plain text without citations."
        result = format_inline_citations(text, [])
        assert result == text


class TestFormatReferenceList:
    def test_format_list(self):
        citations = [
            Citation(id=1, title="LangGraph Docs", url="https://langchain-ai.github.io/langgraph/"),
            Citation(id=2, title="Survey Paper", url="https://arxiv.org/abs/2401.xxx"),
        ]
        result = format_reference_list(citations)
        assert "## 参考文献" in result
        assert "[1] LangGraph Docs" in result
        assert "https://langchain-ai.github.io/langgraph/" in result
        assert "[2] Survey Paper" in result

    def test_empty_list(self):
        result = format_reference_list([])
        assert result == ""


class TestMergeCitationsIntoReport:
    def test_full_merge(self):
        report = "根据[来源: Docs](https://docs.com)的研究得出结论。"
        citations = [
            Citation(id=1, title="Docs", url="https://docs.com"),
        ]
        result = merge_citations_into_report(report, citations)
        assert "## 参考文献" in result
        assert "[1]" in result
        assert "[来源: Docs](https://docs.com)" not in result

    def test_no_citations_unchanged(self):
        report = "# Report\n\nContent without citations."
        result = merge_citations_into_report(report, [])
        assert result == report
