# V2.1 性能修复报告：去重卡死 & Context 溢出

> 日期: 2026-06-16  
> 分支: dev/v2.1  
> 关联模块: `evidence/dedup.py`, `evidence/cross_validate.py`, `prompts.py`, `nodes/*.py`

---

## 问题总览

| 问题 | 症状 | 严重度 |
|------|------|--------|
| Evidence 去重 O(n²) LLM 调用 | "一直在去重流程"，27 组 source 逐个对比 | 高 |
| Cross-validate O(n²) LLM 调用 | "卡死在交叉验证"，157 条 evidence 12K 次调用 | 致命 |
| Final/Critique prompt context 溢出 | `BadRequest 400: 1.86M > 1.05M tokens` | 致命 |
| 工作流日志缺失 | 不知道程序运行到哪个节点 | 中 |

---

## Round 1: 去重预算分配不均 + 冗余调用

### 根因

`_dedup_within_group()` 对每组内 evidence 做 O(n²) 两两 LLM 比较。第一个 >1 条 evidence 的 source 组直接消耗全部预算（n=5 时消耗 5~10 次调用），导致后续 21 组（91%）被跳过。

```text
dedup(23 组, budget=10) → 组1: 消耗 9 次 → 组2: 消耗 1 次 → 组3-23: 全部跳过 ❌
```

同时 `research.py`（旧版 research_node）和 `merge.py` 两处都调用 `deduplicate_evidences`，多 Agent 场景下重复执行。

### 修复

| 文件 | 变更 |
|------|------|
| [dedup.py](../../deepresearch/evidence/dedup.py#L106-L157) | 公平预算分配：多证据组每组分至少 1 次，剩余预算按剩余组数均分 |
| [config.py](../../deepresearch/config.py#L40) | `dedup_max_calls_per_run: 10 → 30` |
| [research.py](../../deepresearch/nodes/research.py#L124-L128) | 移除冗余 dedup 调用（已由 merge 节点统一负责） |
| [research_agent.py](../../deepresearch/nodes/research_agent.py#L161-L187) | `fetch_content` 失败时跳过空 source |
| [dedup.py](../../deepresearch/evidence/dedup.py#L60-L103) | 修正进度显示："最多 X 对" → 实际比较数 |

### 副作用

"公平分配"虽然每组至少 1 次比较（覆盖率 100%），但总 LLM 调用从 ~11 次增加到 **27+ 次**（27 组），反而更慢。

---

## Round 2: 批量去重替代逐对比较

### 根因

公平分配导致去重时间更长（27 次 LLM 调用），因为每组仍然用逐对（O(n²)）方式。需要将 "O(n²) 次 LLM 调用 → 每组 1 次批量调用"。

### 修复

重写 `_dedup_within_group`：从 N(N-1)/2 次逐对 LLM 调用 → **1 次批量 LLM 调用**。

```python
# 修复前：逐对比较
for i, ev_a in enumerate(evidences):
    for ev_b in evidences[i+1:]:
        if _are_duplicates(ev_a, ev_b, llm):  # 每次 1 个 LLM call
            remove(ev_b)

# 修复后：批量去重
prompt = "以下是同一来源的 N 条证据，找出重复条目返回 remove_ids"
response = llm.invoke(prompt)  # 1 次 LLM call
remove_ids = parse_json(response)["remove_ids"]
```

`deduplicate_evidences` 策略调整为：

- 按证据数量 **降序** 处理（大组优先，重复概率更高）
- `dedup_max_calls_per_run=15` 语义变更为 "最大处理组数"
- 超出预算的组直接保留全部 evidence

| 文件 | 变更 |
|------|------|
| [dedup.py](../../deepresearch/evidence/dedup.py) | 全面重写：`_BATCH_DEDUP_PROMPT` + `_dedup_within_group` 批量模式 |
| [config.py](../../deepresearch/config.py#L40) | `dedup_max_calls_per_run: 30 → 15`（语义变更：最大组数） |
| [test_evidence_dedup.py](../../tests/unit/test_evidence_dedup.py) | 适配批量 API，新增 3 个测试 |

### 效果

| 维度 | 修复前 | 修复后 |
|------|--------|--------|
| 5 evidence 组 | 5-10 次 LLM 调用 | **1 次** |
| 27 组总调用 | 27+ 次 | **≤15 次** |
| API 开销 | O(总evidence²) | O(组数) |

---

## Round 3: 交叉验证 O(n²) 卡死

### 根因

`cross_validate.py` 的 `_cluster_evidences()` 使用**和 dedup 完全相同的 O(n²) 逐对 LLM 比较**，但规模更大：

```
157 条 evidence × 156 / 2 = 12,246 次潜在 LLM 调用
```

每次调用 2 秒 ≈ **6.8 小时** — 用户看到的就是 "卡死"。

此外，`detect_conflicts` 对每个 multi-agent cluster 单独调用 LLM，也存在 O(clusters) 次调用问题。

### 修复

和 Round 2 同样的批量策略应用到交叉验证：

```python
# 修复前：O(n²) 逐对聚类
for i, ev_a in enumerate(evidences):
    for ev_b in evidences[i+1:]:
        if _are_same_claim(ev_a, ev_b, llm):  # 每次 1 个 LLM call
            cluster.append(ev_b)

# 修复后：1 次批量聚类 + top-50 上限
prompt = "将以下 N 条证据按语义聚类，返回 clusters"
response = llm.invoke(prompt)  # 1 次 LLM call
clusters = parse_json(response)["clusters"]
```

关键设计：

- **单次批量聚类**：1 次 API 调用替代 12K 次
- **top-50 上限**：取 confidence 最高的前 50 条 evidence 参与聚类
- **批量冲突检测**：所有 cluster 的冲突检测合并为 1 次 LLM 调用
- **Fail-safe**：LLM 故障时每条 evidence 独立成簇

| 文件 | 变更 |
|------|------|
| [cross_validate.py](../../deepresearch/evidence/cross_validate.py) | 全面重写：`_batch_cluster()` 替代 `_cluster_evidences()` + `_are_same_claim()` |
| [test_cross_validate.py](../../tests/unit/test_cross_validate.py) | 适配批量 API，新增 1 个测试 |

### 效果

| 维度 | 修复前 | 修复后 |
|------|--------|--------|
| 聚类 | 12K 次 LLM | **1 次** |
| 冲突检测 | N 次 LLM | **1 次** |
| 处理上限 | 无（卡死） | top-50 |

---

## Round 4: Final/Critique Prompt Context 溢出

### 根因

`sources` 列表中每个 source 包含完整的网页正文 (`content` 字段，由 trafilatura 提取)。`json.dumps(sources)` 将 40+ 个 source 的完整内容序列化后远超 1M tokens。

```
Error: 1864732 tokens requested > 1048565 tokens max
```

`final`、`critique`、`summary` 三个节点都会把 `sources + evidences` 序列化进 prompt，任何一个都可能触发溢出。

### 修复

在 [prompts.py](../../deepresearch/prompts.py) 增加两个安全函数：

```python
def _safe_sources(sources: list[dict]) -> list[dict]:
    """剥离 source.content 并限制数量，防止 prompt 超出 LLM context 限制。"""
    # 1. 移除 content 字段（完整网页正文）
    # 2. 上限 40 条

def _safe_evidences(evidences: list[dict]) -> list[dict]:
    """限制 evidence 数量，截断过长的 claim/quote。"""
    # 1. 上限 60 条
    # 2. claim > 500 字符截断
    # 3. quote > 300 字符截断
```

自动应用于 `build_summarizer_messages`、`build_critique_messages`、`build_finalizer_messages` 三个 prompt builder。

| 文件 | 变更 |
|------|------|
| [prompts.py](../../deepresearch/prompts.py) | 新增 `_safe_sources()` + `_safe_evidences()`；三个 builder 自动剥离 content |

### 效果

| 维度 | 修复前 | 修复后 |
|------|--------|--------|
| Final prompt | 1.86M tokens (400 error) | ~50K tokens |
| Critique prompt | 可能溢出 | ~80K tokens |
| Summary prompt | 可能溢出 | ~60K tokens |

---

## Round 5: 全流程日志补全

### 根因

用户无法判断程序运行到哪个节点。各节点日志不统一（混用 `print()` 和 `logger.info()`），缺少耗时统计。

### 修复

所有节点统一日志格式：

```
📋 Plan: 正在生成研究计划...           [plan] 开始: ... (0.0s)
📋 Plan: 完成 → 3 个子问题             [plan] 完成 (2.1s)

🔬 ResearchAgent[学术论文 Agent]: ...   [research_agent:paper] 开始: ...
   🔎 [学术论文 Agent] 搜索: ... → 5 条
   📄 [学术论文 Agent] url → 3 条证据
                                        [research_agent:paper] 完成 (4.2s)

🔗 Merge: 12 sources, 45 evidences      [merge] 开始: ...
   📋 URL 去重: 12 → 10 sources
   🔄 语义去重: 8 组
   🔬 交叉验证: 45 条批量聚类中...
   ✅ 交叉验证完成: 12/45 validated
🔗 Merge: 完成 → 10 sources (5.1s)     [merge] 完成 (5.1s)

📝 Summary: 正在生成...                  [summary] 开始: ...
📝 Summary: 完成 → 2500 字符 (2.0s)

🔍 Critique: 正在评审 (iteration 1)...  [critique] 开始: ...
🔍 Critique: 完成 → score=0.85

✅ Critique: 通过 → 最终报告            [route] → final
📄 Final: 正在生成...                    [final] 开始: ...
📄 Final: 完成 → 3500 字符 (1.5s)
```

| 文件 | 变更 |
|------|------|
| [plan.py](../../deepresearch/nodes/plan.py) | +开始/结束日志，+耗时 |
| [research_agent.py](../../deepresearch/nodes/research_agent.py) | +开始/结束日志，+搜索进度，+耗时 |
| [merge.py](../../deepresearch/nodes/merge.py) | +阶段日志，+URL去重统计，+耗时 |
| [summary.py](../../deepresearch/nodes/summary.py) | +耗时 |
| [critique.py](../../deepresearch/nodes/critique.py) | 统一日志格式 |
| [final.py](../../deepresearch/nodes/final.py) | +开始/结束日志，+citation 统计，+耗时 |
| [graph.py](../../deepresearch/graph.py) | 路由/fan-out 可见日志 |

---

## 总效果

### LLM 调用优化

| 阶段 | 修复前（最坏情况） | 修复后 |
|------|------------------|--------|
| Evidence Dedup | O(n²) 逐对 → 30+ 次 | 每组 1 次，上限 15 组 |
| Cross-Validate | O(n²) 逐对 → **12K+ 次** | **1 次**批量，上限 50 条 |
| Conflict Detect | O(clusters) 逐组 | **1 次**批量 |
| Final/Critique Prompt | 1.86M tokens (400) | ~50K tokens |
| **总计** | **12,000+ 次 / 6.8h** | **≤17 次 / ~30s** |

### 修改文件

```
deepresearch/
├── config.py                    # dedup_max_calls_per_run: 10→15
├── prompts.py                   # +_safe_sources/_safe_evidences
├── graph.py                     # +路由日志
├── evidence/
│   ├── dedup.py                 # 批量去重重写
│   └── cross_validate.py        # 批量聚类重写
└── nodes/
    ├── plan.py                  # +日志+耗时
    ├── research.py              # -冗余dedup
    ├── research_agent.py        # +日志+跳过空source
    ├── merge.py                 # +日志+耗时
    ├── summary.py               # +耗时
    ├── critique.py              # 统一格式
    └── final.py                 # +日志+耗时

tests/unit/
├── test_config.py               # 默认值适配
├── test_evidence_dedup.py       # 批量API适配 +3测试
├── test_cross_validate.py       # 批量API适配 +1测试
└── test_research_node.py        # 验证不再调用dedup
```

### 核心设计原则

1. **批量替代逐对**：O(n²) LLM 调用 → 1 次批量调用（dedup + cross-validate）
2. **上限保护**：所有 LLM prompt 前截断数据（top-N + 字段剥离）
3. **大组优先**：证据多的 source 组优先处理（重复概率更高）
4. **Fail-safe**：LLM 故障/无效 JSON 时保留所有数据
5. **可见性**：每个节点统一格式 [node] 开始/完成 + 耗时
