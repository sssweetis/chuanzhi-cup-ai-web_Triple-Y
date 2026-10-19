<#
  交互式配置后端环境变量（C 负责 · 协助配置密钥）

  用法：
    powershell -ExecutionPolicy Bypass -File .\configure_env.ps1
    powershell -ExecutionPolicy Bypass -File .\configure_env.ps1 -ApiKey "<你的APIKey>" -BaseUrl "https://你的平台接口地址/v1" -Model "<模型名>" -Port 8000

  说明：
    · 密钥只写到本地 .env（已被 .gitignore 忽略），不会进 Git、不会打印完整内容
    · 配了 Key 后默认把 LLM_ENABLE_MOCK 置 0（走真实模型）；加 -KeepMock 可保留「失败降级到 mock」
    · 改完必须重启服务，然后看 /health 的 mode 字段
#>
param(
    [string]$ApiKey = "",
    [string]$BaseUrl = "",
    [string]$Model = "",
    [int]$Port = 0,
    [switch]$KeepMock
)

$ErrorActionPreference = "Stop"
$envPath = Join-Path $PSScriptRoot ".env"

$map = @{}
if (Test-Path -LiteralPath $envPath) {
    Get-Content -LiteralPath $envPath -Encoding UTF8 | ForEach-Object {
        if ($_ -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=(.*)$') { $map[$Matches[1]] = $Matches[2].Trim() }
    }
}
function Cur($k, $d) { if ($map.ContainsKey($k) -and $map[$k]) { $map[$k] } else { $d } }

Write-Host ""
Write-Host "===== 通知抽取服务 · 环境变量配置（直接回车 = 保持当前值）=====" -ForegroundColor Cyan

# ---- API Key（隐藏输入）----
if (-not $ApiKey) {
    $now = Cur "LLM_API_KEY" ""
    $hint = if ($now) { "（当前 $($now.Substring(0, [Math]::Min(6, $now.Length)))…，直接回车保持不变）" } else { "（留空 = 不配 Key，走 Mock）" }
    $sec = Read-Host -Prompt "LLM_API_KEY $hint" -AsSecureString
    $ApiKey = [System.Net.NetworkCredential]::new("", $sec).Password
}
if ($ApiKey) { $map["LLM_API_KEY"] = $ApiKey.Trim() }

# ---- Base URL / 模型 ----
if (-not $BaseUrl) {
    $d = Cur "LLM_BASE_URL" "https://api.openai.com/v1"
    $in = Read-Host -Prompt "LLM_BASE_URL（当前 $d）"
    $BaseUrl = if ($in) { $in } else { if ($map.ContainsKey("LLM_BASE_URL")) { $map["LLM_BASE_URL"] } else { "" } }
}
if ($BaseUrl) { $map["LLM_BASE_URL"] = $BaseUrl.Trim() }

if (-not $Model) {
    $d = Cur "LLM_MODEL" "gpt-4o"
    $in = Read-Host -Prompt "LLM_MODEL（当前 $d）"
    $Model = if ($in) { $in } else { if ($map.ContainsKey("LLM_MODEL")) { $map["LLM_MODEL"] } else { "" } }
}
if ($Model) { $map["LLM_MODEL"] = $Model.Trim() }

# ---- 端口 ----
if ($Port -le 0) {
    $d = Cur "PORT" "8000"
    $in = Read-Host -Prompt "PORT（当前 $d）"
    if ($in) { $Port = [int]$in }
}
if ($Port -gt 0) { $map["PORT"] = "$Port" }

# ---- Mock 开关：有 Key 默认走真实 ----
if ($map["LLM_API_KEY"]) {
    $map["LLM_ENABLE_MOCK"] = if ($KeepMock) { "1" } else { "0" }
    $modeInfo = if ($KeepMock) { "real 优先，调用失败时降级 mock" } else { "real（真实大模型）" }
} else {
    $map["LLM_ENABLE_MOCK"] = "1"
    $modeInfo = "mock（返回虚构 Matter 数据，用于前端联调）"
}

# ---- 写回 .env（UTF-8 无 BOM）----
$lines = @(
    "# 由 configure_env.ps1 生成/更新 —— 含密钥，已在 .gitignore 中忽略，不要提交"
    "LLM_ENABLE_MOCK=$($map['LLM_ENABLE_MOCK'])"
    "LLM_API_KEY=$($map['LLM_API_KEY'])"
    "PORT=$(Cur 'PORT' '8000')"
)
if ($map["LLM_BASE_URL"]) { $lines += "LLM_BASE_URL=$($map['LLM_BASE_URL'])" }
if ($map["LLM_MODEL"]) { $lines += "LLM_MODEL=$($map['LLM_MODEL'])" }
if ($map["MAX_TEXT_LENGTH"]) { $lines += "MAX_TEXT_LENGTH=$($map['MAX_TEXT_LENGTH'])" }

[System.IO.File]::WriteAllText($envPath, ($lines -join "`r`n") + "`r`n", (New-Object System.Text.UTF8Encoding($false)))

$key = $map["LLM_API_KEY"]
$masked = if ($key) { $key.Substring(0, [Math]::Min(6, $key.Length)) + "…" } else { "(空)" }
Write-Host ""
Write-Host "已写入：$envPath" -ForegroundColor Green
Write-Host "  LLM_API_KEY     = $masked"
Write-Host "  LLM_BASE_URL    = $(Cur 'LLM_BASE_URL' 'https://api.openai.com/v1')"
Write-Host "  LLM_MODEL       = $(Cur 'LLM_MODEL' 'gpt-4o')"
Write-Host "  PORT            = $(Cur 'PORT' '8000')"
Write-Host "  运行模式        = $modeInfo"
Write-Host ""
Write-Host "下一步：" -ForegroundColor Cyan
Write-Host "  1) 重启服务：powershell -ExecutionPolicy Bypass -File .\run.ps1"
Write-Host "  2) 验证密钥：python test_llm.py"
Write-Host "  3) 看模式：  http://127.0.0.1:$(Cur 'PORT' '8000')/health  → mode 应为 real/mock"