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
- Test logging module in isolation (handler creation, level propagation, test-mode detection)

## Test Modules

| Module | Test File | Coverage |
|--------|-----------|----------|
| `logging` | `tests/unit/test_logging.py` | setup, levels, handlers, test-mode, file output, third-party suppression |
