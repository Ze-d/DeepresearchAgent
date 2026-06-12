# State 与数据结构设计

## 1. ResearchPlan

```python
from pydantic import BaseModel
from typing import List

class SubQuestion(BaseModel):
    id: str
    question: str
    priority: int
    search_queries: List[str]

class ResearchPlan(BaseModel):
    research_goal: str
    sub_questions: List[SubQuestion]
    expected_sections: List[str]
    success_criteria: List[str]
```

## 2. Source

```python
class Source(BaseModel):
    id: str
    title: str
    url: str
    snippet: str | None = None
    content: str | None = None
    source_type: str = "unknown"
    score: float = 0.0
```

## 3. Evidence

```python
class Evidence(BaseModel):
    id: str
    source_id: str
    claim: str
    quote: str | None = None
    confidence: float = 0.0
```

## 4. CritiqueResult

```python
class CritiqueIssue(BaseModel):
    type: str
    severity: str
    description: str
    suggested_action: str

class CritiqueResult(BaseModel):
    pass_: bool
    score: float
    issues: list[CritiqueIssue]
    new_search_queries: list[str]
```

## 5. FinalReport

```python
class FinalReport(BaseModel):
    title: str
    markdown: str
    sources: list[Source]
    limitations: list[str]
```

## 6. AgentState

```python
from typing import TypedDict

class AgentState(TypedDict):
    user_query: str
    research_plan: dict | None
    search_results: list[dict]
    sources: list[dict]
    evidences: list[dict]
    draft_summary: str | None
    critique_result: dict | None
    final_report: str | None
    iteration: int
    max_iterations: int
    status: str
    errors: list[str]
```

## 7. 文件输出 Schema

建议每次运行生成一个 session 目录：

```text
outputs/session_20260610_001/
├── plan.json
├── search_results.json
├── sources.json
├── evidences.json
├── draft_summary.md
├── critique.json
└── final_report.md
```
