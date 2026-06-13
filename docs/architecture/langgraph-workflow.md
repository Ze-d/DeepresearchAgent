# LangGraph 架构设计

## 1. 架构原则

v0 使用 LangGraph 构建显式状态图。

核心原则：

1. 每个节点只负责一个明确阶段
2. 所有中间结果都写入 AgentState
3. 节点之间只通过 State 通信
4. Critique 后通过条件路由决定下一步
5. 保留后续 checkpoint / streaming 扩展能力

## 2. AgentState 设计

```python
from typing import TypedDict, List, Dict, Any, Optional

class AgentState(TypedDict):
    user_query: str

    research_plan: Optional[Dict[str, Any]]
    search_results: List[Dict[str, Any]]
    sources: List[Dict[str, Any]]
    evidences: List[Dict[str, Any]]

    draft_summary: Optional[str]
    critique_result: Optional[Dict[str, Any]]
    final_report: Optional[str]

    iteration: int
    max_iterations: int
    status: str
    errors: List[str]
```

## 3. 节点划分

### 3.1 plan_node

职责：

- 理解用户问题
- 拆解研究子问题
- 生成搜索计划
- 生成报告结构

输入：

```python
state["user_query"]
```

输出：

```python
state["research_plan"]
```

### 3.2 research_node

职责：

- 读取 research_plan
- 执行搜索
- 抽取来源
- 抽取 evidence

输出：

```python
state["sources"]
state["evidences"]
state["search_results"]
```

### 3.3 summary_node

职责：

- 根据 evidence 生成阶段总结
- 标记证据不足的部分
- 生成 draft report

输出：

```python
state["draft_summary"]
```

### 3.4 critique_node

职责：

- 检查 draft summary
- 判断是否回答用户问题
- 判断证据是否足够
- 判断是否需要继续 research

输出：

```python
state["critique_result"]
state["iteration"]
```

### 3.5 final_node

职责：

- 生成最终 Markdown 报告
- 添加 sources
- 添加局限性说明

输出：

```python
state["final_report"]
```

## 4. 条件路由

```python
def route_after_critique(state: AgentState) -> str:
    critique = state.get("critique_result") or {}
    iteration = state.get("iteration", 0)
    max_iterations = state.get("max_iterations", 2)

    if critique.get("pass") is True:
        return "final"

    if iteration >= max_iterations:
        return "final"

    return "research"
```

## 5. LangGraph 伪代码

```python
from langgraph.graph import StateGraph, START, END

graph = StateGraph(AgentState)

graph.add_node("plan", plan_node)
graph.add_node("research", research_node)
graph.add_node("summary", summary_node)
graph.add_node("critique", critique_node)
graph.add_node("final", final_node)

graph.add_edge(START, "plan")
graph.add_edge("plan", "research")
graph.add_edge("research", "summary")
graph.add_edge("summary", "critique")

graph.add_conditional_edges(
    "critique",
    route_after_critique,
    {
        "research": "research",
        "final": "final",
    },
)

graph.add_edge("final", END)

app = graph.compile()
```

## 6. v0 与后续扩展

v0：

- 单图
- 单线程
- CLI 运行
- 文件保存中间结果

v1：

- 增加 checkpoint
- 增加 streaming
- 增加 FastAPI
- 增加 LangSmith tracing

v2：

- 多 Research Agent
- 人工审核节点
- 本地知识库 RAG
- MCP 工具接入
