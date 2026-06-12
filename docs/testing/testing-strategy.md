# Testing Strategy

## Layers

| Layer | Tool | Scope |
|-------|------|-------|
| Unit | pytest | Single function/class, no I/O |
| Integration | pytest | Multi-module, mock LLM |

## Principles

- Test each LangGraph node in isolation
- Mock DeepSeek API calls
- Test state transitions
- Test output formatting
