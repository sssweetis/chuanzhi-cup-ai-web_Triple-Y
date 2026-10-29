<#
  从剪贴板读取团队 Key，并调用 configure_env.ps1 写入 backend/.env。
  用法：
    1) 只复制 Key 本身到剪贴板
    2) powershell -ExecutionPolicy Bypass -File .\configure_env_from_clipboard.ps1
#>
param(
  [string]$BaseUrl = "https://api.deepseek.com/v1",
  [string]$Model = "deepseek-chat"
)

$ErrorActionPreference = 'Stop'
$key = (Get-Clipboard -Raw).Trim()
if (-not $key) { throw '剪贴板为空，请先复制团队 Key。' }
if ($key.Length -lt 20) { throw "剪贴板内容只有 $($key.Length) 个字符，看起来不是完整 Key。" }
if ($key -match '\s') { throw 'Key 中包含空格或换行，请只复制 Key 本身。' }

& (Join-Path $PSScriptRoot 'configure_env.ps1') -ApiKey $key -BaseUrl $BaseUrl -Model $Model -Port 8000
Remove-Variable key
