# tests/unit/test_merge_node.py
from tests.fixtures.mock_llm import FakeChatModel


class TestMergeNode:
    def test_merge_collects_sources_from_all_agents(self):
        """merge 节点汇总所有 Agent 的 sources"""
        from deepresearch.nodes.merge import make_merge_node

        llm = FakeChatModel()
        node = make_merge_node(llm)

        state = {
            "user_query": "test",
            "research_plan": {"research_goal": "test", "sub_questions": []},
            "search_results": [],
            "sources": [
                {"id": "s1", "title": "Paper A", "url": "https://arxiv.org/1", "source_agent": "paper"},
                {"id": "s2", "title": "Blog B", "url": "https://blog.com/1", "source_agent": "blog"},
            ],
            "evidences": [
                {"id": "e1", "claim": "test", "source_agent": "paper", "confidence": 0.9},
                {"id": "e2", "claim": "test2", "source_agent": "blog", "confidence": 0.7},
            ],
            "draft_summary": None, "critique_result": None, "final_report": None,
            "iteration": 0, "max_iterations": 2, "status": "researched", "errors": [],
            "citations": [], "iteration_metrics": [], "checkpoint_ref": None,
            "agent_outputs": [], "merge_summary": None, "human_review": None,
            "agent_profile": None, "sub_question": None,
        }
        result = node(state)
        assert result["status"] == "merged"
        assert len(result["sources"]) == 2
        assert len(result["evidences"]) == 2

    def test_merge_runs_dedup(self, monkeypatch):
        """merge 节点调用 dedup"""
        from deepresearch.nodes.merge import make_merge_node

        dedup_called = []
        def mock_dedup(evidences, llm):
            dedup_called.append(True)
            return evidences

        monkeypatch.setattr("deepresearch.evidence.dedup.deduplicate_evidences", mock_dedup)
        monkeypatch.setattr("deepresearch.evidence.ranking.rank_sources", lambda s: s)

        llm = FakeChatModel()
        node = make_merge_node(llm)

        state = {
            "user_query": "test",
            "research_plan": {"research_goal": "test", "sub_questions": []},
            "search_results": [], "draft_summary": None, "critique_result": None,
            "final_report": None, "iteration": 0, "max_iterations": 2,
            "status": "researched", "errors": [],
            "citations": [], "iteration_metrics": [], "checkpoint_ref": None,
            "agent_outputs": [], "merge_summary": None, "human_review": None,
            "agent_profile": None, "sub_question": None,
            "sources": [{"id": "s1", "title": "T", "url": "https://x.com"}],
            "evidences": [{"id": "e1", "claim": "test", "confidence": 0.9}],
        }
        node(state)
        assert len(dedup_called) > 0

    def test_merge_empty_inputs(self):
        """merge 节点处理空 sources/evidences"""
        from deepresearch.nodes.merge import make_merge_node
        llm = FakeChatModel()
        node = make_merge_node(llm)
        state = {
            "user_query": "test",
            "research_plan": {"research_goal": "test", "sub_questions": []},
            "search_results": [], "draft_summary": None, "critique_result": None,
            "final_report": None, "iteration": 0, "max_iterations": 2,
            "status": "researched", "errors": [],
            "citations": [], "iteration_metrics": [], "checkpoint_ref": None,
            "agent_outputs": [], "merge_summary": None, "human_review": None,
            "agent_profile": None, "sub_question": None,
            "sources": [], "evidences": [],
        }
        result = node(state)
        assert result["status"] == "merged"
        assert result["sources"] == []
        assert result["evidences"] == []

    def test_merge_phase2_runs_cross_validate(self, monkeypatch):
        """Phase 2 merge 调用 cross_validate_evidences"""
        from deepresearch.nodes.merge import make_merge_node

        cv_called = []
        def mock_cross_validate(evidences, llm):
            cv_called.append(True)
            for ev in evidences:
                ev["cross_validated"] = True
                ev["source_bias"] = False
            return evidences

        monkeypatch.setattr("deepresearch.nodes.merge.cross_validate_evidences", mock_cross_validate)
        monkeypatch.setattr("deepresearch.nodes.merge.detect_conflicts", lambda c, llm: [])
        monkeypatch.setattr("deepresearch.evidence.dedup.deduplicate_evidences", lambda e, llm: e)
        monkeypatch.setattr("deepresearch.evidence.ranking.rank_sources", lambda s: s)

        llm = FakeChatModel()
        node = make_merge_node(llm)

        state = {
            "user_query": "test",
            "research_plan": {"research_goal": "test", "sub_questions": []},
            "search_results": [], "draft_summary": None, "critique_result": None,
            "final_report": None, "iteration": 0, "max_iterations": 2,
            "status": "researched", "errors": [],
            "citations": [], "iteration_metrics": [], "checkpoint_ref": None,
            "agent_outputs": [], "merge_summary": None, "human_review": None,
            "agent_profile": None, "sub_question": None,
            "sources": [
                {"id": "s1", "title": "T1", "url": "https://x.com", "source_agent": "paper"},
                {"id": "s2", "title": "T2", "url": "https://y.com", "source_agent": "blog"},
            ],
            "evidences": [
                {"id": "e1", "claim": "test", "confidence": 0.9, "source_agent": "paper"},
                {"id": "e2", "claim": "test", "confidence": 0.8, "source_agent": "blog"},
            ],
        }
        result = node(state)
        assert len(cv_called) > 0, "cross_validate_evidences should be called"
        assert result["merge_summary"]["cross_validated_count"] > 0

    def test_merge_phase2_detects_conflicts(self, monkeypatch):
        """Phase 2 merge 调用 detect_conflicts 并填充到 merge_summary"""
        from deepresearch.nodes.merge import make_merge_node

        def mock_cv(evidences, llm):
            for ev in evidences:
                ev["cross_validated"] = False
                ev["source_bias"] = True
            return evidences

        def mock_conflicts(clusters, llm):
            return [{"topic": "test conflict", "severity": "major", "positions": {}}]

        monkeypatch.setattr("deepresearch.nodes.merge.cross_validate_evidences", mock_cv)
        monkeypatch.setattr("deepresearch.nodes.merge.detect_conflicts", mock_conflicts)
        monkeypatch.setattr("deepresearch.evidence.dedup.deduplicate_evidences", lambda e, llm: e)
        monkeypatch.setattr("deepresearch.evidence.ranking.rank_sources", lambda s: s)

        llm = FakeChatModel()
        node = make_merge_node(llm)

        state = {
            "user_query": "test",
            "research_plan": {"research_goal": "test", "sub_questions": []},
            "search_results": [], "draft_summary": None, "critique_result": None,
            "final_report": None, "iteration": 0, "max_iterations": 2,
            "status": "researched", "errors": [],
            "citations": [], "iteration_metrics": [], "checkpoint_ref": None,
            "agent_outputs": [], "merge_summary": None, "human_review": None,
            "agent_profile": None, "sub_question": None,
            "sources": [], "evidences": [
                {"id": "e1", "claim": "A", "confidence": 0.9, "source_agent": "paper"},
                {"id": "e2", "claim": "not A", "confidence": 0.8, "source_agent": "blog"},
            ],
        }
        result = node(state)
        assert len(result["merge_summary"]["conflicts"]) > 0

    def test_merge_deduplicates_sources_by_url(self):
        """merge 节点按 URL 去重 sources（保留首次出现）"""
        from deepresearch.nodes.merge import make_merge_node
        llm = FakeChatModel()
        node = make_merge_node(llm)
        state = {
            "user_query": "test",
            "research_plan": {"research_goal": "test", "sub_questions": []},
            "search_results": [], "draft_summary": None, "critique_result": None,
            "final_report": None, "iteration": 0, "max_iterations": 2,
            "status": "researched", "errors": [],
            "citations": [], "iteration_metrics": [], "checkpoint_ref": None,
            "agent_outputs": [], "merge_summary": None, "human_review": None,
            "agent_profile": None, "sub_question": None,
            "sources": [
                {"id": "s1", "title": "T", "url": "https://same-url.com"},
                {"id": "s2", "title": "T dup", "url": "https://same-url.com"},
            ],
            "evidences": [],
        }
        result = node(state)
        assert len(result["sources"]) == 1
