# deepresearch/nodes/human_review.py
"""V2.1 Phase 3: Human-in-the-Loop review node using LangGraph interrupt()."""

import logging
from langchain_core.language_models import BaseChatModel
from langgraph.types import interrupt
from deepresearch.state import AgentState
from deepresearch.config import settings

logger = logging.getLogger(__name__)


def make_human_review_node(llm: BaseChatModel):
    def human_review_node(state: AgentState) -> dict:
        if not settings.human_review_enabled:
            logger.debug("Human review disabled — auto-approving")
            return {
                "human_review": {"action": "approved", "notes": "auto: human review disabled"},
                "status": "reviewed_approved",
            }

        merge_summary = state.get("merge_summary", {})
        sources = state.get("sources", [])
        evidences = state.get("evidences", [])
        conflicts = merge_summary.get("conflicts", [])

        logger.info("Human review required: %d sources, %d evidences, %d conflicts",
                    len(sources), len(evidences), len(conflicts))

        human_decision = interrupt({
            "action": "review_requested",
            "merge_summary": {
                "total_sources": merge_summary.get("total_sources", len(sources)),
                "total_evidences": merge_summary.get("total_evidences", len(evidences)),
                "cross_validated_count": merge_summary.get("cross_validated_count", 0),
                "unique_findings_per_agent": merge_summary.get("unique_findings_per_agent", {}),
                "conflicts": conflicts,
                "source_bias_warnings": merge_summary.get("source_bias_warnings", []),
                "coverage_gaps": merge_summary.get("coverage_gaps", []),
            },
            "sources": [
                {"id": s.get("id"), "title": s.get("title"), "url": s.get("url"),
                 "source_agent": s.get("source_agent", "unknown"), "score": s.get("score", 0)}
                for s in sources[:30]
            ],
            "evidences": [
                {"id": e.get("id"), "claim": e.get("claim"),
                 "confidence": e.get("confidence", 0),
                 "source_agent": e.get("source_agent", "unknown"),
                 "cross_validated": e.get("cross_validated", False)}
                for e in evidences[:50]
            ],
            "prompt": "请审核研究结果，选择 approve / amend / redo",
        })

        action = human_decision.get("action", "approve")
        logger.info("Human review decision: %s", action)

        if action == "amend":
            return {
                "human_review": human_decision,
                "critique_result": {
                    "pass": False,
                    "overall_score": 0.0,
                    "dimensions": {
                        "fact_check": {"score": 0.0, "issues": [], "status": "pass"},
                        "logic_coherence": {"score": 0.0, "issues": [], "status": "pass"},
                        "coverage": {"score": 0.0, "issues": [], "status": "pass"},
                    },
                    "issues": [{
                        "type": "human_amendment",
                        "severity": "high",
                        "description": human_decision.get("notes", "Human requested amendments"),
                        "suggested_action": "execute new search queries",
                    }],
                    "new_search_queries": human_decision.get("new_queries", []),
                },
                "status": "reviewed_amend",
            }
        elif action == "redo":
            return {
                "human_review": human_decision,
                "status": "reviewed_redo",
                "errors": [f"Human requested redo: {human_decision.get('notes', '')}"],
            }
        else:  # approve
            return {
                "human_review": human_decision,
                "status": "reviewed_approved",
            }

    return human_review_node
