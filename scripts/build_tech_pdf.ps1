# 将 docs/技术文档.md 重新生成 HTML 和可提交 PDF（C 侧工具）
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root 'backend\.venv\Scripts\python.exe'
if (-not (Test-Path $Python)) { $Python = 'python' }

& $Python (Join-Path $PSScriptRoot 'build_tech_doc.py')
if ($LASTEXITCODE -ne 0) { throw '生成技术文档 HTML 失败' }

$Html = Join-Path $Root 'docs\技术文档.html'
$Pdf = Join-Path $Root 'docs\技术文档.pdf'
$Candidates = @(
  'C:\Program Files\Google\Chrome\Application\chrome.exe',
  'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
  'C:\Program Files\Microsoft\Edge\Application\msedge.exe'
)
$Browser = $Candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $Browser) { throw '未找到 Chrome/Edge，无法自动导出 PDF' }

$Profile = Join-Path $env:TEMP 'tripley_techdoc_pdf_profile'
$FileUrl = 'file:///' + ($Html -replace '\\', '/')
& $Browser --headless=new --disable-gpu --no-sandbox --allow-file-access-from-files --user-data-dir="$Profile" --print-to-pdf="$Pdf" $FileUrl 2>$null
if (-not (Test-Path $Pdf)) { throw 'PDF 未生成，请打开 HTML 后手动打印为 PDF' }
$Item = Get-Item $Pdf
Write-Host ("PDF 已生成：{0}（{1:N0} KB）" -f $Item.FullName, ($Item.Length / 1KB))
