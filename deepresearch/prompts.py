# deepresearch/prompts.py
import json

from langchain_core.messages import SystemMessage


def build_planner_messages(user_query: str) -> list[SystemMessage]:
    """构建 Planner Prompt。"""
    text = f"""你是一个研究规划 Agent。

用户问题：
{user_query}

任务：
请将用户问题拆解为可执行的研究计划。

要求：
1. 生成 research_goal。
2. 拆解为 3-6 个 sub_questions。
3. 每个 sub_question 给出 2-4 个 search_queries。
4. 给出 expected_sections。
5. 给出 success_criteria。
6. 只输出 JSON，不要输出解释。

JSON 格式：
{{
  "research_goal": "...",
  "sub_questions": [
    {{
      "id": "q1",
      "question": "...",
      "priority": 1,
      "search_queries": ["...", "..."]
    }}
  ],
  "expected_sections": ["..."],
  "success_criteria": ["..."]
}}"""
    return [SystemMessage(content=text)]


def build_researcher_messages(sub_question: str, source_content: str) -> list[SystemMessage]:
    """构建 Researcher Evidence 抽取 Prompt。"""
    text = f"""你是一个研究资料分析 Agent。

当前研究问题：
{sub_question}

资料内容：
{source_content}

任务：
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
    return [SystemMessage(content=text)]


def build_summarizer_messages(
    user_query: str,
    research_plan: dict,
    evidences: list[dict],
) -> list[SystemMessage]:
    """构建 Summary Prompt。"""
    text = f"""你是一个研究总结 Agent。

用户问题：
{user_query}

研究计划：
{json.dumps(research_plan, ensure_ascii=False, indent=2)}

证据列表：
{json.dumps(evidences, ensure_ascii=False, indent=2)}

任务：
生成阶段性研究总结。

要求：
1. 按照研究计划组织内容。
2. 每个关键结论都要基于 evidence。
3. 标记证据不足的地方。
4. 不要生成最终报告。
5. 输出中文 Markdown。
6. 对每个关键结论使用 [来源: 简短标题](URL) 格式标注引用。
   URL 必须严格来自 evidence 对应的 source url，不得编造。"""
    return [SystemMessage(content=text)]


def build_critique_messages(
    user_query: str,
    draft_summary: str,
    sources: list[dict],
    evidences: list[dict],
    prev_critique: dict | None = None,
) -> list[SystemMessage]:
    """构建增强版 Critique Prompt（v1: 三维度评分 + fix rate 追踪）。"""
    prev_section = ""
    if prev_critique:
        prev_issues = json.dumps(prev_critique.get("issues", []), ensure_ascii=False, indent=2)
        prev_section = f"""
上一轮 Critique 结果：
评分: {prev_critique.get('overall_score', 'N/A')}
Issues: {prev_issues}

请评估上一轮 issue 的修复情况。"""

    text = f"""你是一个严格的研究审稿 Agent。

用户问题：
{user_query}

当前总结：
{draft_summary}

来源：
{json.dumps(sources, ensure_ascii=False, indent=2)}

证据：
{json.dumps(evidences, ensure_ascii=False, indent=2)}
{prev_section}

任务：
从以下三个维度独立评分（每个维度 0-1，≥0.7 为通过）：

1. **fact_check（事实核查）**: 每个断言是否有 evidence 支撑？是否存在无来源的主观判断或编造？
2. **logic_coherence（逻辑一致性）**: 论证链是否自洽？不同部分的结论是否有矛盾？
3. **coverage（覆盖度）**: 是否回答了研究计划的所有子问题？是否有明显遗漏？

只输出 JSON：

{{
  "pass": false,
  "overall_score": 0.65,
  "dimensions": {{
    "fact_check": {{"score": 0.8, "issues": [], "status": "pass"}},
    "logic_coherence": {{"score": 0.6, "issues": ["发现矛盾"], "status": "fail"}},
    "coverage": {{"score": 0.55, "issues": ["遗漏子问题"], "status": "fail"}}
  }},
  "issues": [
    {{
      "type": "insufficient_evidence",
      "severity": "high",
      "description": "...",
      "suggested_action": "..."
    }}
  ],
  "new_search_queries": ["...", "..."]
}}"""
    return [SystemMessage(content=text)]


def build_finalizer_messages(
    user_query: str,
    draft_summary: str,
    critique_result: dict,
    sources: list[dict],
) -> list[SystemMessage]:
    """构建 Finalizer Prompt。"""
    text = f"""你是一个专业技术报告写作 Agent。

用户问题：
{user_query}

研究总结：
{draft_summary}

Critique 结果：
{json.dumps(critique_result, ensure_ascii=False, indent=2)}

来源：
{json.dumps(sources, ensure_ascii=False, indent=2)}

任务：
生成最终中文 Markdown 报告。

报告结构：
1. 摘要
2. 研究背景
3. 主要发现
4. 技术分析
5. 对比表
6. 工程建议
7. 局限性
8. 参考来源

要求：
1. 结论清晰。
2. 不要夸大证据。
3. 对证据不足的部分要说明。
4. 保留参考来源列表。
5. 使用 [来源: 简短标题](URL) 格式标注每个关键发现的来源。
6. 在报告末尾列出所有引用的参考文献。"""
    return [SystemMessage(content=text)]
