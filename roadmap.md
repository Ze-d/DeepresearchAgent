# Roadmap

## v0：CLI MVP ✅

**状态:** 已完成

- LangGraph 工作流（Plan → Research → Summary → Critique → Final）
- DeepSeek API 接入
- CLI 可运行（`deepresearch run "query"`）
- Markdown 报告输出
- 本地 outputs 保存中间文件（plan / sources / evidences / critique / final_report）
- TDD 测试覆盖（unit + integration）

## v1：研究质量 + 工程基础设施 ✅

**状态:** 已完成

- Evidence 语义去重（DeepSeek API 批处理）
- Source 权威度多信号评分（域名/类型/时效/丰富度）
- Citation 管理（内联引用提取 + 参考文献格式化）
- Critique 三维评分（事实核查/逻辑一致性/覆盖度）
- Fix rate 追踪（迭代间质量对比）
- Checkpoint 持久化（SqliteSaver + JSON 快照）
- Streaming 输出（Rich Live + stream_mode）
- Observability（LangChain Callback + Token/延迟/错误统计）
- CLI 增强（resume / checkpoints 命令、--stream 选项）

## v2：Web 应用化

**状态:** 设计中

- FastAPI 后端（任务 CRUD API）
- SSE 事件流（node 级别进度推送）
- Vue 3 + Vite 前端
  - 任务提交表单
  - 实时进度面板
  - 来源表 + 证据列表
  - Critique 三维度仪表盘
  - Markdown 最终报告（含 citation 上标）
- CLI `serve` 命令（一键启动）
- CLI 与 API 共享 `build_graph()` 核心代码

## v2.1：多 Agent 并发研究

**状态:** 规划中

- Paper Research Agent（arXiv / 学术来源）
- GitHub Research Agent（代码仓库）
- Blog Research Agent（技术博客）
- Official Docs Agent（官方文档）
- 多来源并发研究 + 结果合并
- 人工审核节点（human-in-the-loop）

## v3：本地知识库 + MCP 集成

**状态:** 规划中

- 本地 PDF / Markdown 知识库
- RAG 检索增强
- GitHub MCP 工具
- Zotero / arXiv / 文件系统工具
- 多模型 Provider（OpenAI / Ollama 等）

## v4：生产级增强

**状态:** 规划中

- Docker 容器化部署
- 任务优先级队列（Redis）
- 生产数据库（PostgreSQL）
- 用户认证（JWT）
- 多用户隔离
- 项目管理（研究案例归档）

## v5：招聘展示增强

**状态:** 规划中

- 项目架构图（SVG）
- 完整 Demo Report（多 case）
- README 截图和 GIF
- Benchmark case 对比
- 简历项目描述和面试问答集
