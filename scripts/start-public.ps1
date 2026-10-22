# 临时公网演示（cloudflared 隧道）
# 用法：先启动后端（8000 端口），再执行本脚本
#   powershell -ExecutionPolicy Bypass -File .\scripts\start-public.ps1
param([int]$Port = 8000)

$ErrorActionPreference = "Stop"
$cf = Get-Command cloudflared -ErrorAction SilentlyContinue
if (-not $cf) {
    Write-Host "未安装 cloudflared。" -ForegroundColor Yellow
    Write-Host "下载地址：https://github.com/cloudflare/cloudflared/releases/latest"
    Write-Host "（Windows 选 cloudflared-windows-amd64.exe，改名 cloudflared.exe 放到 PATH 里）"
    exit 1
}

Write-Host "请确认后端已在 http://127.0.0.1:$Port 运行（/health 可访问）..." -ForegroundColor Cyan
try {
    $h = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/health" -TimeoutSec 5
    Write-Host "后端状态：$($h | ConvertTo-Json -Compress)" -ForegroundColor Green
} catch {
    Write-Host "后端没起来，先启动它：" -ForegroundColor Red
    Write-Host "  cd backend; .\.venv\Scripts\python.exe -m uvicorn main:app --reload --host 0.0.0.0 --port $Port"
    exit 1
}

Write-Host ""
Write-Host "正在建立公网隧道，稍后会打印一个 https://xxxx.trycloudflare.com 地址" -ForegroundColor Cyan
Write-Host "拿到地址后：前端 .env.production 里把 VITE_API_BASE_URL 改成该地址 + /api 不加（只填域名）" -ForegroundColor Gray
cloudflared tunnel --url "http://127.0.0.1:$Port"