# tests/unit/test_tools.py
from unittest.mock import MagicMock

import httpx
from deepresearch.tools import search_web, fetch_content, SearchResult


class TestSearchWeb:
    def test_returns_list(self, monkeypatch):
        """搜索返回 SearchResult 列表"""
        from unittest.mock import MagicMock

        mock_ddgs_cls = MagicMock()
        mock_instance = MagicMock()
        mock_instance.text.return_value = [
            {"title": "Test", "href": "https://example.com", "body": "snippet"},
        ]
        mock_ddgs_cls.return_value.__enter__.return_value = mock_instance

        monkeypatch.setattr("deepresearch.tools.DDGS", mock_ddgs_cls)

        results = search_web("test query", max_results=3)
        assert len(results) > 0
        assert isinstance(results[0], SearchResult)
        assert results[0].title == "Test"
        assert results[0].url == "https://example.com"
        assert results[0].snippet == "snippet"

    def test_empty_results(self, monkeypatch):
        """无结果时返回空列表不报错"""
        from unittest.mock import MagicMock

        mock_ddgs_cls = MagicMock()
        mock_instance = MagicMock()
        mock_instance.text.return_value = []
        mock_ddgs_cls.return_value.__enter__.return_value = mock_instance

        monkeypatch.setattr("deepresearch.tools.DDGS", mock_ddgs_cls)
        results = search_web("no results", max_results=3)
        assert results == []


class TestFetchContent:
    def test_extracts_text(self, monkeypatch):
        """从 URL 抓取正文"""
        def mock_get(url, **kwargs):
            mock_resp = MagicMock(spec=httpx.Response)
            mock_resp.text = "<html><body>Hello</body></html>"
            return mock_resp

        def mock_extract(filecontent, **kwargs):
            return "Extracted text content"

        monkeypatch.setattr("httpx.get", mock_get)
        monkeypatch.setattr("deepresearch.tools.extract", mock_extract)
        content = fetch_content("https://example.com")
        assert content == "Extracted text content"

    def test_fetch_failure_returns_empty(self, monkeypatch):
        """抓取失败时返回空字符串"""
        def mock_get(url, **kwargs):
            raise httpx.RequestError("Connection failed")

        monkeypatch.setattr("httpx.get", mock_get)
        content = fetch_content("https://broken.com")
        assert content == ""
