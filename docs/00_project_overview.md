# DeepResearch Agent 项目概述

## 1. 项目定位

DeepResearch Agent 是一个面向复杂问题调研的智能体系统，采用：

```text
Plan → Research → Summary → Critique → Final Report
```

的多阶段工作流，自动完成问题拆解、资料检索、证据整理、阶段总结、批判性检查和最终报告生成。

本项目用于招聘展示，重点体现：

1. Agent 工作流设计能力
2. LangChain / LangGraph 工程实践能力
3. DeepSeek API 接入能力
4. 搜索工具与资料抽取能力
5. 结构化状态管理能力
6. 报告生成与自我 critique 能力

## 2. v0 项目目标

v0 不追求复杂多 Agent 系统，而是优先完成一个稳定闭环：

```text
用户输入研究问题
↓
Planner 生成研究计划
↓
Researcher 执行搜索和资料整理
↓
Summarizer 生成阶段总结
↓
Critic 检查问题
↓
根据 Critique 决定是否补充研究
↓
Finalizer 输出最终 Markdown 报告
```

## 3. v0 非目标

v0 暂时不做：

- 复杂前端
- 多用户系统
- 分布式任务调度
- 自研 Agent 框架
- 大规模网页爬虫
- 长时间后台任务
- 企业级权限系统

## 4. 项目亮点

本项目的核心亮点不是简单搜索，而是：

- 基于 LangGraph 的显式工作流编排
- 基于 LangChain 的模型、Prompt、Tool 组合
- 基于 DeepSeek API 的国产大模型接入
- 基于结构化 State 的 Agent 执行过程追踪
- 基于 Critique 的迭代改进机制
- 可输出带来源和证据的研究报告

## 5. 推荐 Demo 问题

```text
请调研目前 Deep Research Agent 的主流架构、代表性开源项目和工程实现难点，并给出我作为求职项目应该如何实现的建议。
```

## 6. 招聘展示重点

面试展示时，不要把项目讲成“调用搜索 API 生成报告”。应该强调：

1. 你将复杂调研任务抽象成了可控工作流。
2. 你使用 LangGraph 管理状态流转与条件路由。
3. 你使用 LangChain 统一模型调用、Prompt 编排、工具调用和结构化输出。
4. 你为 DeepSeek API 做了兼容封装。
5. 你设计了 Critique 节点，让系统具备自我检查和迭代修正能力。
6. 你保留了中间状态，使 Agent 执行过程可观察、可调试、可复盘。
