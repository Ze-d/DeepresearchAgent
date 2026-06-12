# Workflows

## ci.yml — Automated Verification

**Trigger:** push to non-main branches, PR to main

```
Push / PR
  ↓
Python 3.11 + 3.12 matrix
  ↓
uv sync --dev
  ↓
ruff check ── mypy ── pytest ── deepresearch --help
```

| Check | Command | Strict |
|-------|---------|--------|
| Lint | `uv run ruff check .` | Must pass |
| Type | `uv run mypy deepresearch/` | Advisory |
| Unit | `uv run pytest` | Must pass |
| Smoke | `uv run deepresearch --help` | Must pass |

All four checks appear as status checks on the PR — merge is blocked if any strict check fails.

## scripts/dev-pr.ps1 — 本地验证并提交

```powershell
.\scripts\dev-pr.ps1 -Message "feat: 实现 plan node"
.\scripts\dev-pr.ps1 -Message "fix: 修复超时" -SkipMypy
```

四步顺序执行（不包含建分支和提 PR，由开发者自行操作）：

| Step | 操作 | 失败行为 |
|------|------|---------|
| Verify | `ruff check` | 终止 |
| Verify | `mypy`（可选跳过） | 警告 |
| Verify | `pytest` | 终止 |
| Commit | `git add -A` + `git commit` | 终止 |

## Manual Flow (alternative)

```bash
# 1. Create branch
git checkout -b feat/my-feature

# 2. Develop (TDD)
# ... write test → fail → implement → pass → refactor ...

# 3. Verify
uv run ruff check .
uv run mypy deepresearch/
uv run pytest

# 4. Commit
git add -A
git commit -m "feat: add my feature"

# 5. Push + PR
git push -u origin feat/my-feature
gh pr create --base main --title "feat: add my feature" --body "..."
```

## PR Checklist Template

```markdown
## Changes
- [Describe changes]

## Verification
- [ ] `uv run pytest` passes
- [ ] `uv run ruff check .` passes
- [ ] `uv run mypy deepresearch/` clean
- [ ] `uv run deepresearch --help` works
```
