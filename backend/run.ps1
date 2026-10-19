# 启动后端服务（Windows PowerShell）—— 自动优先使用本目录的 .venv
$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

$port = if ($env:PORT) { $env:PORT } else { "8000" }
$py = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $py)) { $py = "python" }

Write-Host "启动通知抽取服务：0.0.0.0:$port  （Ctrl+C 停止）" -ForegroundColor Green
Write-Host "自检地址：http://127.0.0.1:$port/health"
& $py -m uvicorn main:app --reload --host 0.0.0.0 --port $port