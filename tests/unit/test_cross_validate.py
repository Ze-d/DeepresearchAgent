# tests/unit/test_cross_validate.py
from tests.fixtures.mock_llm import FakeChatModel


class TestCrossValidate:
    def test_cross_validate_boosts_confidence_for_multi_agent_evidence(self):
        """多 Agent 独立确认同一 claim 时，confidence 提升（批量模式）"""
        from deepresearch.evidence.cross_validate import cross_validate_evidences
        # 批量聚类：返回 e1+e2 聚类在一起
        llm = FakeChatModel(default_response='{"clusters": [["e1", "e2"]]}')
        evidences = [
            {"id": "e1", "claim": "Transformers outperform RNNs", "confidence": 0.8,
             "source_agent": "paper", "source_id": "s1", "quote": "q1"},
            {"id": "e2", "claim": "Transformers outperform RNNs", "confidence": 0.8,
             "source_agent": "blog", "source_id": "s2", "quote": "q1"},
            {"id": "e3", "claim": "unique finding only in docs", "confidence": 0.7,
             "source_agent": "docs", "source_id": "s3", "quote": "q2"},
        ]
        result = cross_validate_evidences(evidences, llm)
        for ev in result:
            if ev["id"] in ("e1", "e2"):
                assert ev["confidence"] > 0.8, f"Expected boosted confidence for {ev['id']}"
                assert ev.get("cross_validated") is True

    def test_cross_validate_marks_solo_findings(self):
        """单一 Agent 独有的发现标记 source_bias=True（批量模式）"""
        from deepresearch.evidence.cross_validate import cross_validate_evidences
        # 返回空 clusters — 所有 evidence 独立
        llm = FakeChatModel(default_response='{"clusters": []}')
        evidences = [
            {"id": "e1", "claim": "unique claim A", "confidence": 0.9,
             "source_agent": "paper", "source_id": "s1"},
            {"id": "e2", "claim": "unique claim B different", "confidence": 0.8,
             "source_agent": "blog", "source_id": "s2"},
        ]
        result = cross_validate_evidences(evidences, llm)
        for ev in result:
            assert ev.get("cross_validated") is False
            assert ev.get("source_bias") is True

    def test_cross_validate_empty_input(self):
        """空 evidences 返回空列表"""
        from deepresearch.evidence.cross_validate import cross_validate_evidences
        llm = FakeChatModel()
        result = cross_validate_evidences([], llm)
        assert result == []

    def test_cross_validate_batch_clusters_correctly(self):
        """批量聚类正确分组多条 evidence"""
        from deepresearch.evidence.cross_validate import cross_validate_evidences
        # 两组聚类: (e1,e3) 和 (e2,e4)
        llm = FakeChatModel(default_response='{"clusters": [["e1", "e3"], ["e2", "e4"]]}')
        evidences = [
            {"id": "e1", "claim": "claim A", "confidence": 0.9,
             "source_agent": "paper", "source_id": "s1"},
            {"id": "e2", "claim": "claim B", "confidence": 0.85,
             "source_agent": "paper", "source_id": "s1"},
            {"id": "e3", "claim": "claim A variant", "confidence": 0.8,
             "source_agent": "blog", "source_id": "s2"},
            {"id": "e4", "claim": "claim B variant", "confidence": 0.75,
             "source_agent": "blog", "source_id": "s2"},
        ]
        result = cross_validate_evidences(evidences, llm)
        for ev in result:
            assert ev.get("cross_validated") is True, f"{ev['id']} should be cross-validated"
            assert ev["confidence"] > 0.8  # all boosted


class TestDetectConflicts:
    def test_detect_conflicts_when_two_agents_disagree(self):
        """两个 Agent 对同一事实给出矛盾结论时，返回 conflicts（批量模式）"""
        from deepresearch.evidence.cross_validate import detect_conflicts
        # 批量 conflict 格式：按 cluster_index 指示
        llm = FakeChatModel(default_response='{"conflicts": [{"cluster_index": 0, "severity": "major"}]}')
        clusters = [[
            {"id": "e1", "claim": "Python is fastest language", "source_agent": "blog"},
            {"id": "e2", "claim": "Python is slow compared to C++", "source_agent": "paper"},
        ]]
        conflicts = detect_conflicts(clusters, llm)
        assert len(conflicts) > 0
        assert conflicts[0]["severity"] == "major"

    def test_detect_conflicts_no_contradiction(self):
        """相同 claim 无矛盾时不报告冲突（批量模式）"""
        from deepresearch.evidence.cross_validate import detect_conflicts
        # 返回空 conflicts
        llm = FakeChatModel(default_response='{"conflicts": []}')
        clusters = [[
            {"id": "e1", "claim": "Python is popular", "source_agent": "blog"},
            {"id": "e2", "claim": "Python is popular", "source_agent": "paper"},
        ]]
        conflicts = detect_conflicts(clusters, llm)
        assert len(conflicts) == 0
