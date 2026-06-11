# 简历包装文档

## 1. 中文项目描述

项目名称：DeepResearch Agent：基于 LangGraph 和 DeepSeek 的深度调研智能体

项目描述：

设计并实现一个面向复杂问题调研的 DeepResearch Agent，基于 LangGraph 构建 Plan → Research → Summary → Critique 的多阶段工作流，结合 LangChain 和 DeepSeek API 完成问题拆解、资料检索、证据整理、阶段总结、批判性检查和最终报告生成。

## 2. 中文简历要点

- 基于 LangGraph 实现 DeepResearch Agent 工作流编排，将复杂调研任务拆解为 Plan、Research、Summary、Critique 和 Final Report 多个节点，并通过条件路由实现 critique-driven 迭代。
- 基于 LangChain 封装 Prompt、LLM、Tool 和结构化输出解析，接入 DeepSeek API 作为默认模型，支持后续扩展 OpenAI、Ollama 等模型 Provider。
- 设计 AgentState、ResearchPlan、Source、Evidence、CritiqueResult 等结构化数据模型，实现中间状态可追踪和报告生成过程可解释。
- 实现搜索工具、资料抽取、证据抽取和 Markdown 报告生成模块，支持 CLI 一键运行完整研究流程。
- 设计 Critique 模块，从覆盖度、证据支持、来源质量和无依据断言等维度检查报告质量，并自动生成补充研究任务。

## 3. 英文简历要点

Project: DeepResearch Agent — LangGraph-based research agent powered by DeepSeek

- Built a DeepResearch Agent using LangGraph to orchestrate a Plan → Research → Summary → Critique → Final Report workflow for complex research tasks.
- Integrated LangChain with DeepSeek API through a provider-specific LLM adapter, enabling structured prompting, tool usage, and model-provider extensibility.
- Designed structured state models including AgentState, ResearchPlan, Source, Evidence, and CritiqueResult to make the research process traceable and explainable.
- Implemented search, content extraction, evidence extraction, critique-driven refinement, and Markdown report generation in a CLI-first workflow.
- Developed a critique module to evaluate coverage, evidence support, source quality, and unsupported claims, enabling iterative improvement of research outputs.

## 4. 面试讲法

这个项目不是简单调用搜索 API，而是把 Deep Research 抽象成一个可控的 Agent Workflow。

我使用 LangGraph 管理工作流状态和节点流转，把整个研究过程拆成 plan、research、summary、critique 和 final report。每个节点只负责一个阶段，所有中间产物都保存在 AgentState 中。Research 阶段负责搜索和证据抽取，Summary 阶段基于 evidence 生成阶段总结，Critique 阶段检查报告是否覆盖问题、证据是否充分、是否存在无依据断言。如果 critique 不通过，LangGraph 会通过条件路由回到 research 节点继续补充资料。最终系统输出 Markdown 报告，并保留 sources、evidence 和 critique 结果。

## 5. 面试追问准备

### Q1：为什么选择 LangGraph？

因为这个项目的核心不是单轮对话，而是多阶段、有状态、可循环的 Agent Workflow。LangGraph 能显式定义节点、边、条件路由和状态结构，比普通 Chain 更适合实现 Plan → Research → Summary → Critique 的流程。

### Q2：为什么要设计 Critique？

Deep Research 最大的问题是报告看似完整但可能证据不足。Critique 模块用于从覆盖度、证据支持、来源质量、逻辑完整性等维度检查当前总结，并决定是否继续研究，从而降低无证据断言和遗漏问题的风险。

### Q3：DeepSeek API 怎么接入？

v0 使用 `langchain-deepseek` 的 `ChatDeepSeek`，通过 `.env` 配置 `DEEPSEEK_API_KEY` 和模型名。业务节点不直接依赖具体模型，而是通过 `llm/factory.py` 创建 LLM 实例，方便后续切换 OpenAI、Ollama 或其他模型。
