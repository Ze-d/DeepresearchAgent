# tests/unit/test_prompts.py
from deepresearch.prompts import (
    build_planner_messages,
    build_researcher_messages,
    build_summarizer_messages,
    build_critique_messages,
    build_finalizer_messages,
)


class TestPlannerPrompt:
    def test_build_messages(self):
        messages = build_planner_messages(user_query="什么是 LangGraph?")
        assert len(messages) == 1
        content = str(messages[0].content)
        assert "什么是 LangGraph?" in content
        assert "研究规划 Agent" in content
        assert "research_goal" in content
        assert "sub_questions" in content


class TestResearcherPrompt:
    def test_build_messages(self):
        messages = build_researcher_messages(
            sub_question="LangGraph 是什么?",
            source_content="LangGraph 是用于构建有状态 Agent 的库。",
        )
        assert len(messages) == 1
        content = str(messages[0].content)
        assert "LangGraph 是什么?" in content
        assert "LangGraph 是用于构建" in content
        assert "evidences" in content


class TestSummarizerPrompt:
    def test_build_messages(self):
        messages = build_summarizer_messages(
            user_query="调研 Deep Research",
            research_plan={"research_goal": "test"},
            evidences=[{"claim": "test"}],
        )
        assert len(messages) == 1
        content = str(messages[0].content)
        assert "调研 Deep Research" in content
        assert "研究总结 Agent" in content


class TestCritiquePrompt:
    def test_build_messages(self):
        messages = build_critique_messages(
            user_query="test query",
            draft_summary="draft content",
            sources=[{"title": "src1"}],
            evidences=[{"claim": "c1"}],
        )
        assert len(messages) == 1
        content = str(messages[0].content)
        assert "研究审稿 Agent" in content
        assert "pass" in content


class TestFinalizerPrompt:
    def test_build_messages(self):
        messages = build_finalizer_messages(
            user_query="test query",
            draft_summary="draft",
            critique_result={"score": 0.9},
            sources=[{"title": "s1"}],
        )
        assert len(messages) == 1
        content = str(messages[0].content)
        assert "技术报告写作 Agent" in content
        assert "摘要" in content
