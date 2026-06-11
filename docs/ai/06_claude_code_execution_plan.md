# Claude Code 执行计划

## 1. 执行原则

不要一次性实现整个项目。

Claude Code 应该按阶段完成，每个阶段都要能运行、能测试、能提交。

## 2. 第一阶段：项目骨架

目标：

1. 创建 Python 项目结构
2. 配置 uv
3. 配置 ruff
4. 配置 pytest
5. 创建 Typer CLI
6. 创建 LangGraph 最小工作流
7. 使用 mock node 跑通完整流程

验收命令：

```bash
uv run pytest
uv run deepresearch --help
uv run deepresearch run "测试问题"
```

## 3. 第二阶段：DeepSeek 接入

目标：

1. 添加 `langchain-deepseek`
2. 创建 `llm/factory.py`
3. 从 `.env` 读取 `DEEPSEEK_API_KEY`
4. 实现 DeepSeek 调用测试
5. 保留 mock LLM 作为测试模式

验收命令：

```bash
uv run deepresearch llm-test
```

## 4. 第三阶段：Planner

目标：

1. 实现 Planner Prompt
2. 使用 DeepSeek 生成 ResearchPlan
3. 使用 Pydantic 校验输出
4. 如果 JSON 解析失败，进行 fallback 修复

验收命令：

```bash
uv run deepresearch plan "调研 Deep Research Agent"
```

## 5. 第四阶段：Researcher

目标：

1. 添加搜索工具
2. 支持 DuckDuckGo fallback
3. 支持 Tavily 可选
4. 保存 sources
5. 初步抽取 evidence

验收命令：

```bash
uv run deepresearch research "调研 LangGraph 的应用"
```

## 6. 第五阶段：Summary + Critique

目标：

1. 实现 summary_node
2. 实现 critique_node
3. 实现 route_after_critique
4. 支持最多 2 轮研究循环

验收命令：

```bash
uv run deepresearch run "调研 Deep Research Agent 的架构"
```

## 7. 第六阶段：Final Report

目标：

1. 生成 Markdown 报告
2. 保存中间文件
3. 保存最终报告
4. README 添加 demo

验收命令：

```bash
uv run deepresearch run "调研 Deep Research Agent 的架构" --output outputs/demo.md
```

## 8. 给 Claude Code 的第一条指令

```text
请先阅读 docs/00_project_overview.md、docs/01_v0_technical_route.md、docs/02_langgraph_architecture.md、docs/03_deepseek_compatibility.md 和 CLAUDE.md。

第一阶段只完成项目骨架，不要实现完整业务逻辑。

具体任务：
1. 使用 uv 初始化 Python 项目；
2. 创建 src/deepresearch 目录结构；
3. 添加 Typer CLI；
4. 添加 LangGraph 最小 StateGraph；
5. 实现 plan、research、summary、critique、final 五个 mock node；
6. 让 deepresearch run "测试问题" 可以跑完整流程；
7. 添加 pytest 测试；
8. 确保 uv run pytest 通过。

完成后请说明：
1. 修改了哪些文件；
2. 如何运行；
3. 测试结果；
4. 下一阶段建议做什么。
```
