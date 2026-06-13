from deepresearch.citation.extractor import (
    extract_citations,
    validate_citations,
    Citation,
)


class TestExtractCitations:
    def test_extract_single(self):
        text = "根据官方文档[来源: LangGraph Docs](https://example.com)的说法..."
        citations = extract_citations(text)
        assert len(citations) == 1
        assert citations[0].title == "LangGraph Docs"
        assert citations[0].url == "https://example.com"
        assert citations[0].id == 1

    def test_extract_multiple(self):
        text = """
        根据[来源: Paper A](https://a.com)的研究...
        同时[来源: Paper B](https://b.com)也指出...
        """
        citations = extract_citations(text)
        assert len(citations) == 2
        assert citations[0].id == 1
        assert citations[1].id == 2

    def test_deduplicate_same_url(self):
        """同一 URL 多次出现时去重为同一个编号"""
        text = """
        根据[来源: First Ref](https://same.com)的说法...
        再次引用[来源: Same Ref](https://same.com)...
        """
        citations = extract_citations(text)
        assert len(citations) == 1
        assert citations[0].id == 1

    def test_no_citations(self):
        text = "这段文本没有任何引用。"
        citations = extract_citations(text)
        assert citations == []

    def test_extract_context(self):
        text = "前面的文字根据[来源: Test](https://test.com)的内容说明了这个问题。"
        citations = extract_citations(text)
        assert len(citations) == 1
        assert "前面的文字" in citations[0].context
        assert "的内容说明了" in citations[0].context

    def test_chinese_title(self):
        text = "参考[来源: 深度学习综述](https://example.cn/dl)的内容。"
        citations = extract_citations(text)
        assert len(citations) == 1
        assert citations[0].title == "深度学习综述"


class TestValidateCitations:
    def test_all_valid(self):
        citations = [
            Citation(id=1, title="A", url="https://a.com"),
            Citation(id=2, title="B", url="https://b.com"),
        ]
        sources = [
            {"id": "s1", "url": "https://a.com"},
            {"id": "s2", "url": "https://b.com"},
        ]
        result = validate_citations(citations, sources)
        assert len(result) == 2

    def test_marks_orphan(self):
        """没有对应 source 的 citation 仍保留但记录 warning"""
        citations = [
            Citation(id=1, title="Valid", url="https://valid.com"),
            Citation(id=2, title="Orphan", url="https://orphan.com"),
        ]
        sources = [
            {"id": "s1", "url": "https://valid.com"},
        ]
        result = validate_citations(citations, sources)
        assert len(result) == 2
        # orphan citation 仍然保留

    def test_empty_inputs(self):
        assert validate_citations([], []) == []
