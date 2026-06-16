# Documentation

## Roadmap

- [Roadmap](../roadmap.md) — 版本路线图

## Specs (按版本)

- [v0 MVP](specs/v0-mvp.md) — CLI + LangGraph + DeepSeek 完整闭环
- [v1 Quality & Infra](specs/v1-quality-and-infra.md) — 研究质量 + 工程基础设施增强
- [v2 Web Application](specs/v2-web-application.md) — FastAPI + Vue 3 + SSE 实时可视化
- [v2 Web Plan](specs/v2-web-application-plan.md) — v2 实施计划（Phase 17–22）
- [v2.1 Multi-Agent Design](superpowers/specs/2026-06-15-v2.1-multi-agent-design.md) — 多 Agent 并发研究设计文档
- [v2.1 Tradeoff Analysis](superpowers/specs/2026-06-15-v2.1-tradeoff-analysis.md) — 方案选型与权衡分析
- [v2.1 Implementation Plan](superpowers/plans/2026-06-15-v2.1-implementation.md) — v2.1 实施计划（Task 21–23）
- [v2.1 HITL Completion](specs/v2.1-hitl-completion.md) — HITL 完整实现计划（interrupt/resume 对接、Server/CLI 双模式）

## Architecture (架构设计)

- [Architecture Overview](architecture/overview.md) — 项目定位、技术栈、模块边界、源码结构
- [LangGraph Workflow](architecture/langgraph-workflow.md) — StateGraph 设计、节点划分、条件路由
- [V2.1 Multi-Agent Architecture](architecture/v2.1-multi-agent.md) — Send API 扇出、Merge 流水线、HITL 审核
- [State Schema](architecture/state-schema.md) — Pydantic 数据模型与 AgentState 类型定义
- [DeepSeek Integration](architecture/deepseek-integration.md) — DeepSeek API 接入方案与 LLM Factory

## Design (设计文档)

- [Technical Route](design/technical-route.md) — 技术选型、最小闭环、v0 工作流
- [Prompts](design/prompts.md) — 五个阶段的 Prompt 模板
- [Resume Packaging](design/resume-packaging.md) — 简历描述、英文要点、面试讲法

## Testing (测试)

- [Testing Strategy](testing/testing-strategy.md) — 测试分层与原则
- [TDD Guide](testing/tdd-guide.md) — TDD 开发流程
- [Test Data](testing/test-data.md) — 测试数据规范

## Workflows (CI/CD)

- [Workflows Overview](workflows/README.md) — CI 流水线、本地验证脚本、PR 模板

## AI (AI 协作)

- [Coding Rules](ai/coding-rules.md) — 编码规范 + 审查清单
- [Context Map](ai/context-map.md) — 关键文件和文档的上下文地图
