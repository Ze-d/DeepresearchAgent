# tests/unit/test_cross_validate.py
from tests.fixtures.mock_llm import FakeChatModel


class TestCrossValidate:
    def test_cross_validate_boosts_confidence_for_multi_agent_evidence(self):
        """多 Agent 独立确认同一 claim 时，confidence 提升"""
        from deepresearch.evidence.cross_validate import cross_validate_evidences
        # YES = same claim → will be clustered together
        llm = FakeChatModel(default_response="YES")
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
        """单一 Agent 独有的发现标记 source_bias=True"""
        from deepresearch.evidence.cross_validate import cross_validate_evidences
        llm = FakeChatModel(default_response="NO")
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


class TestDetectConflicts:
    def test_detect_conflicts_when_two_agents_disagree(self):
        """两个 Agent 对同一事实给出矛盾结论时，返回 conflicts"""
        from deepresearch.evidence.cross_validate import detect_conflicts
        CONFLICT_JSON = '{"conflict": true, "severity": "major"}'
        llm = FakeChatModel(default_response=CONFLICT_JSON)
        clusters = [[
            {"id": "e1", "claim": "Python is fastest language", "source_agent": "blog"},
            {"id": "e2", "claim": "Python is slow compared to C++", "source_agent": "paper"},
        ]]
        conflicts = detect_conflicts(clusters, llm)
        assert len(conflicts) > 0
        assert conflicts[0]["severity"] == "major"

    def test_detect_conflicts_no_contradiction(self):
        """相同 claim 无矛盾时不报告冲突"""
        from deepresearch.evidence.cross_validate import detect_conflicts
        NO_CONFLICT_JSON = '{"conflict": false, "severity": "none"}'
        llm = FakeChatModel(default_response=NO_CONFLICT_JSON)
        clusters = [[
            {"id": "e1", "claim": "Python is popular", "source_agent": "blog"},
            {"id": "e2", "claim": "Python is popular", "source_agent": "paper"},
        ]]
        conflicts = detect_conflicts(clusters, llm)
        assert len(conflicts) == 0
