# DeepSeek API 兼容设计

## 1. 默认模型

v0 默认使用 DeepSeek API。

推荐模型：

```env
DEEPSEEK_MODEL=deepseek-chat
```

可选：

```env
DEEPSEEK_MODEL=deepseek-reasoner
```

## 2. 推荐接入方式

优先使用：

```bash
uv add langchain-deepseek
```

代码：

```python
from langchain_deepseek import ChatDeepSeek

llm = ChatDeepSeek(
    model="deepseek-chat",
    temperature=0,
    max_retries=2,
)
```

## 3. 环境变量

`.env.example`：

```env
DEEPSEEK_API_KEY=your_deepseek_api_key
DEEPSEEK_MODEL=deepseek-chat

SEARCH_PROVIDER=duckduckgo
TAVILY_API_KEY=

MAX_ITERATIONS=2
MAX_SEARCH_RESULTS=5
OUTPUT_DIR=outputs
```

## 4. 为什么不优先使用 ChatOpenAI base_url

DeepSeek API 虽然兼容 OpenAI API 格式，但在 LangChain 中，v0 推荐使用 `ChatDeepSeek`。

原因：

1. LangChain 已经提供 DeepSeek provider-specific integration
2. 避免第三方字段兼容问题
3. 方便后续切换 `deepseek-chat` / `deepseek-reasoner`
4. 代码语义更清晰
5. 简历中可以明确写“接入 DeepSeek API”

## 5. LLM Factory 设计

不要在业务节点里直接创建模型。

推荐封装：

```python
from langchain_deepseek import ChatDeepSeek

from deepresearch.config import settings


def build_llm():
    return ChatDeepSeek(
        model=settings.deepseek_model,
        temperature=settings.temperature,
        max_retries=settings.max_retries,
    )
```

节点里使用：

```python
llm = build_llm()
response = llm.invoke(messages)
```

## 6. 后续兼容其他模型

预留 Provider Adapter：

```python
def build_llm(provider: str = "deepseek"):
    if provider == "deepseek":
        return ChatDeepSeek(...)
    if provider == "openai":
        return ChatOpenAI(...)
    if provider == "ollama":
        return ChatOllama(...)
    raise ValueError(f"Unsupported provider: {provider}")
```

v0 只实现 DeepSeek 即可。
