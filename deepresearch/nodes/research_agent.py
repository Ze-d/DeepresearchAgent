# deepresearch/nodes/research_agent.py
"""V2.1 战略注入式 Research Agent — 由 AgentProfile 驱动而非硬编码逻辑。"""

import json
import logging
import re
import uuid
from dataclasses import dataclass, field
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import SystemMessage

from deepresearch.state import AgentState
from deepresearch.tools import search_web, fetch_content

logger = logging.getLogger(__name__)


@dataclass
class AgentProfile:
    """Agent 配置描述体。

    4 个字段驱动 Agent 的搜索策略与证据抽取行为：

    - name:                 Agent 展示名称
    - search_modifiers:     搜索修饰符（site: 等），自动追加到搜索查询
    - system_prompt:        System prompt，定义 Agent 的分析视角
    - evidence_instruction: 证据抽取指令，告诉 LLM 从资料中重点提取什么
    """
    name: str
    search_modifiers: list[str] = field(default_factory=list)
    system_prompt: str = ""
    evidence_instruction: str = ""


# ── 4 个内置 Agent Profile ──────────────────────────────────────────

AGENT_PROFILES: dict[str, AgentProfile] = {
    "paper": AgentProfile(
        name="学术论文 Agent",
        search_modifiers=["site:arxiv.org", "site:scholar.google.com"],
        system_prompt="你是一个学术研究分析专家，擅长从学术论文中提取关键发现和技术细节。",
        evidence_instruction=(
            "从学术角度分析，重点提取：研究方法、实验结果、关键技术指标、对比基线。"
        ),
    ),
    "github": AgentProfile(
        name="代码仓库 Agent",
        search_modifiers=["site:github.com", "site:gitlab.com"],
        system_prompt="你是一个开源代码分析专家，擅长从代码仓库中提取架构设计、API 使用和工程实现细节。",
        evidence_instruction=(
            "从工程实践角度分析，重点提取：代码架构、核心实现、依赖关系、使用方式。"
        ),
    ),
    "blog": AgentProfile(
        name="技术博客 Agent",
        search_modifiers=["site:medium.com", "site:dev.to"],
        system_prompt="你是一个技术博客分析专家，擅长从技术文章中提取实践经验和最佳实践。",
        evidence_instruction=(
            "从实践经验角度分析，重点提取：技术选型考量、踩坑记录、性能对比、实施步骤。"
        ),
    ),
    "docs": AgentProfile(
        name="文档 Agent",
        search_modifiers=["site:docs.python.org", "site:developer.mozilla.org"],
        system_prompt="你是一个技术文档分析专家，擅长从官方文档中提取准确的 API 定义、配置说明和使用指南。",
        evidence_instruction=(
            "从文档角度分析，重点提取：API 签名、配置参数、返回值说明、最佳实践示例。"
        ),
    ),
}


def _extract_evidences(
    sub_question: str,
    source_content: str,
    llm: BaseChatModel,
    profile: AgentProfile,
) -> list[dict]:
    """用 profile 的 system_prompt + evidence_instruction 从 source content 中抽取 evidence 列表。"""
    prompt = f"""{profile.system_prompt}

{profile.evidence_instruction}

当前研究问题：
{sub_question}

资料内容：
{source_content}

请从资料中抽取可以支持研究报告的 evidence。

要求：
1. 只抽取与当前问题相关的内容。
2. 不要编造资料中不存在的信息。
3. 每条 evidence 包含 claim、quote、confidence。
4. 如果资料无关，返回空列表。
5. 只输出 JSON。

JSON 格式：
{{
  "evidences": [
    {{
      "claim": "...",
      "quote": "...",
      "confidence": 0.85
    }}
  ]
}}"""
    messages = [SystemMessage(content=prompt)]
    response = llm.invoke(messages)
    raw = str(response.content) if hasattr(response, "content") else str(response)

    # 尝试提取 ```json ... ``` 代码块
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", raw, re.DOTALL)
    if match:
        raw = match.group(1).strip()

    try:
        data = json.loads(raw)
        return data.get("evidences", [])
    except json.JSONDecodeError:
        logger.warning("Failed to parse evidence JSON: %s", raw[:200])
        return []


def make_research_agent(llm: BaseChatModel):
    """创建 research_agent 节点（闭包注入 LLM）。

    从 state["agent_profile"] 读取 profile key，从 state["sub_question"] 读取搜索配置，
    用 profile 的 search_modifiers 增强搜索，最后用 profile 的 prompts 抽取 evidence。
    """

    def research_agent(state: AgentState) -> dict:
        profile_key = state.get("agent_profile", "blog")
        profile = AGENT_PROFILES.get(profile_key, AGENT_PROFILES["blog"])

        sub_question = state.get("sub_question")
        if sub_question is None:
            return {
                "status": "error",
                "errors": ["No sub_question found in state."],
            }

        all_sources: list[dict] = []
        all_evidences: list[dict] = []
        all_search_results: list[dict] = []

        queries = sub_question.get("search_queries", [])
        for query in queries[:2]:
            # 用 profile 的 search_modifiers 增强搜索查询
            modifiers = profile.search_modifiers[:2]
            enhanced_query = f"{query} {' '.join(modifiers)}" if modifiers else query

            results = search_web(enhanced_query, max_results=5)
            for r in results:
                source_id = str(uuid.uuid4())[:8]
                source_dict: dict[str, Any] = {
                    "id": source_id,
                    "title": r.title,
                    "url": r.url,
                    "snippet": r.snippet,
                    "content": None,
                    "source_type": profile_key,
                    "score": 0.5,
                    "source_agent": profile_key,
                }

                content = fetch_content(r.url)
                if content:
                    source_dict["content"] = content
                    evidences = _extract_evidences(
                        sub_question.get("question", ""),
                        content,
                        llm,
                        profile,
                    )
                    for ev in evidences:
                        ev["id"] = str(uuid.uuid4())[:8]
                        ev["source_id"] = source_id
                        ev["source_agent"] = profile_key
                        all_evidences.append(ev)

                all_sources.append(source_dict)
                all_search_results.append({
                    "query": query,
                    "url": r.url,
                    "title": r.title,
                })

        logger.info(
            "ResearchAgent[%s] done: %d sources, %d evidences",
            profile_key,
            len(all_sources),
            len(all_evidences),
        )

        return {
            "search_results": state.get("search_results", []) + all_search_results,
            "sources": state.get("sources", []) + all_sources,
            "evidences": state.get("evidences", []) + all_evidences,
            "agent_profile": profile_key,
        }

    return research_agent


# 模块级 fallback 入口（兼容 graph.py 直接导入）
def research_agent(state: AgentState) -> dict:
    """Backward-compatible entry point (uses default LLM from build_llm())."""
    from deepresearch.llm import build_llm

    llm = build_llm()
    return make_research_agent(llm)(state)
