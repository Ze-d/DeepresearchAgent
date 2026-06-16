from tests.fixtures.mock_llm import FakeChatModel
from deepresearch.evidence.dedup import (
    _group_by_source,
    _are_duplicates,
    deduplicate_evidences,
)


class TestGroupBySource:
    def test_groups_by_source_id(self):
        evidences = [
            {"id": "e1", "source_id": "s1", "claim": "A", "confidence": 0.9},
            {"id": "e2", "source_id": "s1", "claim": "B", "confidence": 0.8},
            {"id": "e3", "source_id": "s2", "claim": "C", "confidence": 0.7},
        ]
        groups = _group_by_source(evidences)
        assert len(groups) == 2
        assert len(groups["s1"]) == 2
        assert len(groups["s2"]) == 1

    def test_empty_list(self):
        assert _group_by_source([]) == {}


class TestAreDuplicates:
    def test_returns_true_for_yes(self):
        llm = FakeChatModel(default_response="YES")
        result = _are_duplicates(
            {"claim": "same thing", "quote": "same"},
            {"claim": "same thing", "quote": "same too"},
            llm,
        )
        assert result is True

    def test_returns_false_for_no(self):
        llm = FakeChatModel(default_response="NO")
        result = _are_duplicates(
            {"claim": "different A", "quote": "A"},
            {"claim": "different B", "quote": "B"},
            llm,
        )
        assert result is False

    def test_defaults_to_false_on_unexpected_response(self):
        """LLM 返回非 YES/NO 时默认为不重复"""
        llm = FakeChatModel(default_response="MAYBE")
        result = _are_duplicates(
            {"claim": "a", "quote": "a"},
            {"claim": "b", "quote": "b"},
            llm,
        )
        assert result is False


class TestDeduplicateEvidences:
    def test_dedup_within_same_source(self):
        """同一 source 下重复 evidence 只保留 confidence 更高的（批量模式）"""
        # 批量去重：LLM 返回 JSON 指定要移除的 evidence ID
        llm = FakeChatModel(default_response='{"remove_ids": ["e2"]}')
        evidences = [
            {"id": "e1", "source_id": "s1", "claim": "same claim", "quote": "q1", "confidence": 0.9},
            {"id": "e2", "source_id": "s1", "claim": "same claim rephrased", "quote": "q2", "confidence": 0.7},
            {"id": "e3", "source_id": "s2", "claim": "different", "quote": "q3", "confidence": 0.8},
        ]
        result = deduplicate_evidences(evidences, llm)
        ids = [e["id"] for e in result]
        assert "e1" in ids  # 保留 confidence 高的
        assert "e2" not in ids  # 被去重
        assert "e3" in ids  # 不同 source 的保留

    def test_batch_dedup_no_duplicates(self):
        """批量去重：LLM 返回空列表时所有 evidence 保留"""
        llm = FakeChatModel(default_response='{"remove_ids": []}')
        evidences = [
            {"id": "e1", "source_id": "s1", "claim": "claim A", "quote": "q1", "confidence": 0.9},
            {"id": "e2", "source_id": "s1", "claim": "claim B", "quote": "q2", "confidence": 0.8},
            {"id": "e3", "source_id": "s1", "claim": "claim C", "quote": "q3", "confidence": 0.7},
        ]
        result = deduplicate_evidences(evidences, llm)
        assert len(result) == 3

    def test_skips_when_disabled(self, monkeypatch):
        """dedup_enabled=False 时原样返回"""
        monkeypatch.setattr("deepresearch.evidence.dedup.settings.dedup_enabled", False)
        llm = FakeChatModel(default_response='{"remove_ids": ["e2"]}')
        evidences = [
            {"id": "e1", "source_id": "s1", "claim": "c", "quote": "q", "confidence": 0.9},
            {"id": "e2", "source_id": "s1", "claim": "c", "quote": "q", "confidence": 0.8},
        ]
        result = deduplicate_evidences(evidences, llm)
        assert len(result) == 2

    def test_respects_max_groups_limit(self, monkeypatch):
        """超出 max_groups 限制时仅处理前 N 大组，其余直接保留"""
        monkeypatch.setattr("deepresearch.evidence.dedup.settings.dedup_max_calls_per_run", 3)
        llm = FakeChatModel(default_response='{"remove_ids": []}')
        evidences = []
        for g in range(10):
            source_id = f"s{g}"
            for i in range(3):
                evidences.append({
                    "id": f"e{g}_{i}",
                    "source_id": source_id,
                    "claim": f"claim {g}_{i}",
                    "quote": f"quote {g}_{i}",
                    "confidence": 0.5,
                })
        result = deduplicate_evidences(evidences, llm)
        # 所有 evidence 都应保留（无重复），但仅前 3 大组经过 LLM 处理
        assert len(result) == 30

    def test_batch_dedup_removes_multiple(self):
        """批量去重可以一次移除多条重复 evidence"""
        llm = FakeChatModel(default_response='{"remove_ids": ["e2", "e4"]}')
        evidences = [
            {"id": "e1", "source_id": "s1", "claim": "original", "quote": "q1", "confidence": 0.9},
            {"id": "e2", "source_id": "s1", "claim": "copy1", "quote": "q2", "confidence": 0.8},
            {"id": "e3", "source_id": "s1", "claim": "distinct", "quote": "q3", "confidence": 0.85},
            {"id": "e4", "source_id": "s1", "claim": "copy2", "quote": "q4", "confidence": 0.6},
        ]
        result = deduplicate_evidences(evidences, llm)
        ids = [e["id"] for e in result]
        assert "e1" in ids
        assert "e2" not in ids
        assert "e3" in ids
        assert "e4" not in ids

    def test_batch_dedup_invalid_json_keeps_all(self):
        """LLM 返回无效 JSON 时保留所有 evidence（fail-safe）"""
        llm = FakeChatModel(default_response="not valid json at all")
        evidences = [
            {"id": "e1", "source_id": "s1", "claim": "claim A", "quote": "q1", "confidence": 0.9},
            {"id": "e2", "source_id": "s1", "claim": "claim B", "quote": "q2", "confidence": 0.8},
        ]
        result = deduplicate_evidences(evidences, llm)
        assert len(result) == 2
