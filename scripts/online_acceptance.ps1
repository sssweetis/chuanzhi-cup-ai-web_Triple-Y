param(
  [Parameter(Mandatory = $true)][string]$BaseUrl,
  [string]$Output = ''
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root 'backend\.venv\Scripts\python.exe'
if (-not (Test-Path $Python)) { $Python = 'python' }
$env:PYTHONIOENCODING = 'utf-8'
if (-not $Output) {
  $Output = Join-Path $Root ('docs\线上验收-' + (Get-Date -Format 'yyyyMMdd-HHmm') + '.log')
}

$Tests = @(
  'smoke_test.py',
  'smoke_test_check.py',
  'smoke_test_prepare.py',
  'smoke_test_evidence.py',
  'smoke_test_image.py',
  'smoke_test_pdf.py',
  'smoke_test_files.py',
  'smoke_test_acceptance.py',
  'smoke_test_hardening.py',
  'preflight.py'
)

Set-Content -LiteralPath $Output -Encoding utf8 -Value @(
  ('线上验收：' + $BaseUrl),
  ('时间：' + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss')),
  ('=' * 72)
)

Write-Host ('线上验收目标：' + $BaseUrl)
Write-Host ('日志：' + $Output)
foreach ($test in $Tests) {
  Write-Host ''
  Write-Host ('===== ' + $test + ' =====')
  Add-Content -LiteralPath $Output -Encoding utf8 -Value ''
  Add-Content -LiteralPath $Output -Encoding utf8 -Value ('===== ' + $test + ' =====')
  & $Python (Join-Path $Root ('backend\' + $test)) $BaseUrl 2>&1 | Tee-Object -FilePath $Output -Append
  if ($LASTEXITCODE -ne 0) {
    Add-Content -LiteralPath $Output -Encoding utf8 -Value ('FAILED: ' + $test)
    throw ($test + ' 未通过，详见 ' + $Output)
  }
}
Add-Content -LiteralPath $Output -Encoding utf8 -Value 'ALL PASSED'
Write-Host ''
Write-Host ('全部通过，记录已保存：' + $Output)
