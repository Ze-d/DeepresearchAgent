# 开发验证并提交脚本
# 用法：
#   .\scripts\dev-pr.ps1 -Message "feat: 实现 plan node"
#   .\scripts\dev-pr.ps1 -Message "fix: 修复搜索超时" -SkipMypy

param(
    [Parameter(Mandatory=$true, HelpMessage="提交信息")]
    [string]$Message,

    [Parameter(HelpMessage="跳过 mypy 类型检查")]
    [switch]$SkipMypy
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..

# ============================================================
# Step 1: 代码检查 (ruff)
# ============================================================
Write-Host "=== Step 1: ruff 代码检查 ===" -ForegroundColor Cyan
uv run ruff check .
if (-not $?) { throw "ruff 检查未通过，请修复后重试" }

# ============================================================
# Step 2: 类型检查 (mypy, 可选)
# ============================================================
if (-not $SkipMypy) {
    Write-Host "=== Step 2: mypy 类型检查 ===" -ForegroundColor Cyan
    uv run mypy deepresearch/
    if (-not $?) {
        Write-Warning "mypy 发现类型问题，建议修复（或使用 -SkipMypy 跳过）"
    }
}
else {
    Write-Host "=== Step 2: mypy 已跳过 ===" -ForegroundColor DarkGray
}

# ============================================================
# Step 3: 运行测试
# ============================================================
Write-Host "=== Step 3: pytest 测试 ===" -ForegroundColor Cyan
uv run pytest
if (-not $?) { throw "测试未通过，请修复后重试" }

# ============================================================
# Step 4: 提交变更
# ============================================================
Write-Host "=== Step 4: 提交 ===" -ForegroundColor Cyan
git add -A
git commit -m $Message
if (-not $?) { throw "提交失败（可能没有待提交的变更）" }

Write-Host "✅ 验证通过并已提交" -ForegroundColor Green
