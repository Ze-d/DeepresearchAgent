# tests/unit/test_state.py
from deepresearch.state import (
    SubQuestion,
    ResearchPlan,
    Source,
    Evidence,
    CritiqueIssue,
    CritiqueResult,
    FinalReport,
    AgentState,
    Citation,
    DimensionScore,
    EnhancedCritiqueResult,
    IterationMetrics,
)


class TestSubQuestion:
    def test_create(self):
        sq = SubQuestion(
            id="q1",
            question="什么是 LangGraph?",
            priority=1,
            search_queries=["LangGraph 介绍", "LangGraph tutorial"],
        )
        assert sq.id == "q1"
        assert sq.question == "什么是 LangGraph?"
        assert sq.priority == 1
        assert len(sq.search_queries) == 2

    def test_serialize(self):
        sq = SubQuestion(
            id="q1",
            question="test",
            priority=2,
            search_queries=["query1"],
        )
        d = sq.model_dump()
        assert d == {
            "id": "q1",
            "question": "test",
            "priority": 2,
            "search_queries": ["query1"],
            "source_types": ["blog"],
        }

    def test_source_types_default_and_custom(self):
        """SubQuestion 支持 source_types 字段，默认值为 ["blog"]"""
        sq = SubQuestion(id="q1", question="test", priority=1, search_queries=["q"])
        assert sq.source_types == ["blog"]

        sq2 = SubQuestion(id="q2", question="test", priority=2,
                          search_queries=["q"], source_types=["paper", "github"])
        assert sq2.source_types == ["paper", "github"]


class TestResearchPlan:
    def test_create(self):
        plan = ResearchPlan(
            research_goal="调研 Deep Research Agent 架构",
            sub_questions=[
                SubQuestion(
                    id="q1",
                    question="主流架构有哪些?",
                    priority=1,
                    search_queries=["Deep Research architecture"],
                )
            ],
            expected_sections=["架构总览", "代表项目"],
            success_criteria=["覆盖至少3个项目"],
        )
        assert plan.research_goal == "调研 Deep Research Agent 架构"
        assert len(plan.sub_questions) == 1
        assert plan.expected_sections == ["架构总览", "代表项目"]

    def test_serialize(self):
        plan = ResearchPlan(
            research_goal="test",
            sub_questions=[],
            expected_sections=[],
            success_criteria=[],
        )
        d = plan.model_dump()
        assert d["research_goal"] == "test"
        assert d["sub_questions"] == []


class TestSource:
    def test_create_minimal(self):
        s = Source(id="s1", title="Test Page", url="https://example.com")
        assert s.id == "s1"
        assert s.title == "Test Page"
        assert s.url == "https://example.com"
        assert s.snippet is None
        assert s.source_type == "unknown"
        assert s.score == 0.0

    def test_create_full(self):
        s = Source(
            id="s1",
            title="Test",
            url="https://a.com",
            snippet="A snippet",
            content="Full content",
            source_type="blog",
            score=0.8,
        )
        d = s.model_dump()
        assert d["snippet"] == "A snippet"
        assert d["content"] == "Full content"
        assert d["source_type"] == "blog"
        assert d["score"] == 0.8


class TestEvidence:
    def test_create(self):
        e = Evidence(
            id="e1",
            source_id="s1",
            claim="LangGraph 用于构建 Agent 工作流",
            quote="LangGraph is a library for building stateful agents",
            confidence=0.9,
        )
        assert e.id == "e1"
        assert e.source_id == "s1"
        assert e.confidence == 0.9

    def test_serialize(self):
        e = Evidence(
            id="e1",
            source_id="s1",
            claim="test",
            confidence=0.5,
        )
        d = e.model_dump()
        assert d["quote"] is None


class TestCritiqueIssue:
    def test_create(self):
        issue = CritiqueIssue(
            type="insufficient_evidence",
            severity="high",
            description="缺少关键引用",
            suggested_action="补充来源",
        )
        assert issue.type == "insufficient_evidence"
        assert issue.severity == "high"
        assert issue.description == "缺少关键引用"
        assert issue.suggested_action == "补充来源"

    def test_serialize(self):
        issue = CritiqueIssue(
            type="contradiction",
            severity="medium",
            description="前后矛盾",
            suggested_action="核实数据",
        )
        d = issue.model_dump()
        assert d["type"] == "contradiction"
        assert d["severity"] == "medium"
        assert d["description"] == "前后矛盾"
        assert d["suggested_action"] == "核实数据"


class TestCritiqueResult:
    def test_pass(self):
        cr = CritiqueResult(
            pass_=True,
            score=0.9,
            issues=[],
            new_search_queries=[],
        )
        assert cr.pass_ is True
        assert cr.score == 0.9

    def test_fail_with_issues(self):
        issue = CritiqueIssue(
            type="insufficient_evidence",
            severity="high",
            description="缺少对 LangGraph 的引用",
            suggested_action="搜索 LangGraph 官方文档",
        )
        cr = CritiqueResult(
            pass_=False,
            score=0.5,
            issues=[issue],
            new_search_queries=["LangGraph 官方文档"],
        )
        assert cr.pass_ is False
        assert len(cr.issues) == 1
        assert cr.issues[0].type == "insufficient_evidence"
        assert len(cr.new_search_queries) == 1

    def test_serialize_pass_field(self):
        """pass_ 字段序列化为 pass"""
        cr = CritiqueResult(
            pass_=False,
            score=0.0,
            issues=[],
            new_search_queries=[],
        )
        d = cr.model_dump()
        assert d["pass"] is False
        # 反序列化也能正确识别
        loaded = CritiqueResult(**d)
        assert loaded.pass_ is False


class TestFinalReport:
    def test_create(self):
        source = Source(id="s1", title="T", url="https://x.com")
        report = FinalReport(
            title="调研报告",
            markdown="# 报告\n\n内容",
            sources=[source],
            limitations=["样本量有限"],
        )
        assert report.title == "调研报告"
        assert report.markdown.startswith("# 报告")
        assert len(report.sources) == 1
        assert report.limitations == ["样本量有限"]


class TestCitation:
    def test_create(self):
        c = Citation(
            id=1,
            title="LangGraph Docs",
            url="https://langchain-ai.github.io/langgraph/",
            context="LangGraph 是构建 Agent 的核心框架...",
        )
        assert c.id == 1
        assert c.title == "LangGraph Docs"
        assert c.url == "https://langchain-ai.github.io/langgraph/"

    def test_serialize(self):
        c = Citation(id=1, title="Test", url="https://example.com", context="ctx")
        d = c.model_dump()
        assert d["id"] == 1
        assert d["title"] == "Test"
        assert d["url"] == "https://example.com"
        assert d["context"] == "ctx"


class TestDimensionScore:
    def test_create(self):
        ds = DimensionScore(score=0.8, issues=["缺少引用"], status="pass")
        assert ds.score == 0.8
        assert ds.status == "pass"
        assert len(ds.issues) == 1

    def test_serialize(self):
        ds = DimensionScore(score=0.6, issues=[], status="fail")
        d = ds.model_dump()
        assert d["score"] == 0.6
        assert d["status"] == "fail"


class TestEnhancedCritiqueResult:
    def test_create(self):
        cr = EnhancedCritiqueResult(
            pass_=False,
            overall_score=0.65,
            dimensions={
                "fact_check": {"score": 0.8, "issues": [], "status": "pass"},
                "logic_coherence": {"score": 0.6, "issues": ["矛盾"], "status": "fail"},
                "coverage": {"score": 0.55, "issues": ["遗漏子问题"], "status": "fail"},
            },
            issues=[
                {"type": "insufficient_evidence", "severity": "high",
                 "description": "缺少引用", "suggested_action": "补充来源"}
            ],
            new_search_queries=["more search"],
        )
        assert cr.overall_score == 0.65
        assert len(cr.dimensions) == 3
        assert cr.dimensions["fact_check"]["status"] == "pass"

    def test_pass_condition(self):
        cr = EnhancedCritiqueResult(
            pass_=True,
            overall_score=0.85,
            dimensions={
                "fact_check": {"score": 0.9, "issues": [], "status": "pass"},
                "logic_coherence": {"score": 0.85, "issues": [], "status": "pass"},
                "coverage": {"score": 0.8, "issues": [], "status": "pass"},
            },
            issues=[],
            new_search_queries=[],
        )
        assert cr.pass_ is True

    def test_serialize_pass_field(self):
        cr = EnhancedCritiqueResult(
            pass_=False,
            overall_score=0.5,
            dimensions={},
            issues=[],
            new_search_queries=[],
        )
        d = cr.model_dump()
        assert d["pass"] is False


class TestIterationMetrics:
    def test_create(self):
        im = IterationMetrics(
            iteration=1,
            overall_score=0.65,
            dimensions={
                "fact_check": {"score": 0.8, "issues": [], "status": "pass"},
                "logic_coherence": {"score": 0.6, "issues": [], "status": "fail"},
                "coverage": {"score": 0.55, "issues": [], "status": "fail"},
            },
            issues_count=3,
            fix_rate=None,
            tokens_used=15000,
            latency_ms=3200,
        )
        assert im.iteration == 1
        assert im.fix_rate is None
        assert im.tokens_used == 15000

    def test_with_fix_rate(self):
        im = IterationMetrics(
            iteration=2,
            overall_score=0.85,
            dimensions={},
            issues_count=1,
            fix_rate=0.67,
            tokens_used=18000,
            latency_ms=3500,
        )
        d = im.model_dump()
        assert d["fix_rate"] == 0.67


class TestAgentStateV1:
    def test_initial_state_with_v1_fields(self):
        state: AgentState = {
            "user_query": "测试",
            "research_plan": None,
            "search_results": [],
            "sources": [],
            "evidences": [],
            "draft_summary": None,
            "critique_result": None,
            "final_report": None,
            "iteration": 0,
            "max_iterations": 2,
            "status": "initialized",
            "errors": [],
            "citations": [],
            "iteration_metrics": [],
            "checkpoint_ref": None,
        }
        assert state["citations"] == []
        assert state["iteration_metrics"] == []
        assert state["checkpoint_ref"] is None

    def test_initial_state_with_v2_1_fields(self):
        """AgentState 包含 v2.1 新增字段 agent_outputs, merge_summary, human_review"""
        state: AgentState = {
            "user_query": "test",
            "research_plan": None,
            "search_results": [],
            "sources": [],
            "evidences": [],
            "draft_summary": None,
            "critique_result": None,
            "final_report": None,
            "iteration": 0,
            "max_iterations": 2,
            "status": "initialized",
            "errors": [],
            "citations": [],
            "iteration_metrics": [],
            "checkpoint_ref": None,
            "agent_outputs": [],
            "merge_summary": None,
            "human_review": None,
        }
        assert state["agent_outputs"] == []
        assert state["merge_summary"] is None
        assert state["human_review"] is None


class TestAgentState:
    def test_initial_state(self):
        """AgentState 初始状态各字段默认值正确"""
        state: AgentState = {
            "user_query": "测试问题",
            "research_plan": None,
            "search_results": [],
            "sources": [],
            "evidences": [],
            "draft_summary": None,
            "critique_result": None,
            "final_report": None,
            "iteration": 0,
            "max_iterations": 2,
            "status": "initialized",
            "errors": [],
        }
        assert state["user_query"] == "测试问题"
        assert state["iteration"] == 0
        assert state["max_iterations"] == 2
        assert state["status"] == "initialized"

    def test_update_state(self):
        """AgentState 允许更新字段"""
        state: AgentState = {
            "user_query": "测试",
            "research_plan": None,
            "search_results": [],
            "sources": [],
            "evidences": [],
            "draft_summary": None,
            "critique_result": None,
            "final_report": None,
            "iteration": 0,
            "max_iterations": 2,
            "status": "initialized",
            "errors": [],
        }
        state["research_plan"] = {"research_goal": "test"}
        state["iteration"] = 1
        assert state["research_plan"] is not None
        assert state["iteration"] == 1
