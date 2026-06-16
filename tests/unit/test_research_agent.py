# tests/unit/test_research_agent.py
from tests.fixtures.mock_llm import FakeChatModel


class TestAgentProfile:
    def test_agent_profile_exists(self):
        """AgentProfile 可从 research_agent 模块导入"""
        from deepresearch.nodes.research_agent import AgentProfile, AGENT_PROFILES
        assert isinstance(AGENT_PROFILES, dict)
        paper = AGENT_PROFILES["paper"]
        assert isinstance(paper, AgentProfile)
        assert "paper" in AGENT_PROFILES
        assert "github" in AGENT_PROFILES
        assert "blog" in AGENT_PROFILES
        assert "docs" in AGENT_PROFILES

    def test_agent_profile_fields(self):
        """AgentProfile 有 name, search_modifiers, system_prompt, evidence_instruction"""
        from deepresearch.nodes.research_agent import AGENT_PROFILES
        paper = AGENT_PROFILES["paper"]
        assert paper.name == "学术论文 Agent"
        # DuckDuckGo 仅支持单 site: — modifier 存储纯域名，不含 site: 前缀
        assert "arxiv.org" in paper.search_modifiers
        assert len(paper.system_prompt) > 0
        assert len(paper.evidence_instruction) > 0


class TestResearchAgentNode:
    def test_research_agent_returns_sources_and_evidences(self, monkeypatch):
        """research_agent 用给定 profile 搜索并返回 sources + evidences"""
        from deepresearch.nodes.research_agent import make_research_agent
        from deepresearch.tools import SearchResult

        def mock_search(query, max_results=5, site_filter=None):
            return [SearchResult(title="Test", url="https://example.com", snippet="S")]

        def mock_fetch(url, timeout=8.0):
            return "Test content."

        monkeypatch.setattr("deepresearch.tools.search_web", mock_search)
        monkeypatch.setattr("deepresearch.tools.fetch_content", mock_fetch)

        evidence_json = '{"evidences": [{"claim": "test", "quote": "q", "confidence": 0.9}]}'
        llm = FakeChatModel(default_response=evidence_json)

        node = make_research_agent(llm)

        state = {
            "user_query": "test query",
            "research_plan": None,
            "search_results": [],
            "sources": [],
            "evidences": [],
            "draft_summary": None,
            "critique_result": None,
            "final_report": None,
            "iteration": 0,
            "max_iterations": 2,
            "status": "planned",
            "errors": [],
            "citations": [],
            "iteration_metrics": [],
            "checkpoint_ref": None,
            "agent_outputs": [],
            "merge_summary": None,
            "human_review": None,
            "agent_profile": "paper",
            "sub_question": {
                "id": "q1", "question": "test", "priority": 1,
                "search_queries": ["test query"], "source_types": ["paper"],
            },
            "task_id": "test-123",
        }
        result = node(state)
        assert len(result["sources"]) > 0
        assert len(result["evidences"]) > 0
        # agent_profile 不再返回 — 它是 Send API 注入的输入参数，多个并行 Agent
        # 并发写入同一 key 会触发 InvalidUpdateError，且下游节点不需要此字段

    def test_research_agent_search_modifiers_applied(self, monkeypatch):
        """research_agent 将 profile 的 search_modifiers 作为 site_filter 传递给 search_web"""
        from deepresearch.nodes.research_agent import make_research_agent

        searched_calls = []

        def mock_search(query, max_results=5, site_filter=None):
            searched_calls.append({"query": query, "site_filter": site_filter})
            return []

        monkeypatch.setattr("deepresearch.tools.search_web", mock_search)
        monkeypatch.setattr("deepresearch.tools.fetch_content",
                           lambda url, timeout=8.0: "")

        llm = FakeChatModel(default_response='{"evidences": []}')
        node = make_research_agent(llm)

        state = {
            "user_query": "test", "research_plan": None,
            "search_results": [], "sources": [], "evidences": [],
            "draft_summary": None, "critique_result": None, "final_report": None,
            "iteration": 0, "max_iterations": 2, "status": "planned", "errors": [],
            "citations": [], "iteration_metrics": [], "checkpoint_ref": None,
            "agent_outputs": [], "merge_summary": None, "human_review": None,
            "agent_profile": "paper",
            "sub_question": {
                "id": "q1", "question": "test", "priority": 1,
                "search_queries": ["transformer architecture"],
                "source_types": ["paper"],
            },
        }
        node(state)
        assert len(searched_calls) > 0
        call = searched_calls[0]
        assert "transformer architecture" in call["query"]
        # site_filter 作为独立参数传递，不在 query 中
        assert "site:" not in call["query"]
        assert call["site_filter"] == "arxiv.org"
