<#
  修复「推送时 rebase 冲突」并完成首次上传（传智杯 · Triple_Y）
  ------------------------------------------------------------------
  冲突原因：
      远端仓库已经有队友推的内容（README.md、.gitignore、src/、docs/01~03、samples/），
      本地 C 的后端工作在另一条"无关历史"上，两边都有 README.md / .gitignore → rebase 必然冲突。
  本脚本做法：
      1) 先把本地未提交的改动提交（rebase/merge 都要求工作区干净）
      2) 用 merge（允许无关历史）代替 rebase，冲突文件一律采用【远端团队版】
         → 队友的 README.md 和 .gitignore 保留，本地新增的 backend/ 等目录也全部带上
      3) 提交本地改动，并在缺失时补充 .gitignore 规则
      4) 推送到 GitHub
  用法：powershell -ExecutionPolicy Bypass -File .\fix-git-merge.ps1
#>
Set-Location -LiteralPath $PSScriptRoot
$ErrorActionPreference = "Continue"

function Info($m) { Write-Host "`n$m" -ForegroundColor Cyan }
function Ok($m)   { Write-Host "  [OK] $m" -ForegroundColor Green }
function Warn($m) { Write-Host "  [!]  $m" -ForegroundColor Yellow }
function Bad($m)  { Write-Host "  [X]  $m" -ForegroundColor Red }
function RunGit {
    param([string[]]$GitArgs)
    $o = (& git @GitArgs 2>&1 | Out-String).Trim()
    return @{ Out = $o; Code = $LASTEXITCODE }
}

Info "===== 1/5 保护检查 ====="
if ((RunGit @("rev-parse", "--is-inside-work-tree")).Code -ne 0) { Bad "当前目录不是 git 仓库"; exit 1 }
$url = RunGit @("remote", "get-url", "origin")
if ($url.Code -ne 0) { Bad "没有 origin 远端，请先跑 push-to-github.ps1"; exit 1 }
Ok "远端：$($url.Out)"
Ok "当前分支：$((RunGit @('rev-parse','--abbrev-ref','HEAD')).Out)"

Info "===== 2/5 提交本地未提交的改动 ====="
if ((RunGit @("status", "--porcelain")).Out -eq "") {
    Ok "工作区已干净，无需提交"
} else {
    $null = RunGit @("add", "--", "backend/main.py", "backend/requirement_checker.py", "backend/smoke_test_check.py", "backend/check_sync.py")
    if ((RunGit @("diff", "--cached", "--quiet")).Code -ne 0) {
        $c1 = RunGit @("commit", "-q", "-m", "feat(backend): 新增 /api/check 用户情况核对接口与自测脚本（10/18 里程碑）")
        if ($c1.Code -eq 0) { Ok "已提交后端新功能（/api/check）" } else { Bad "提交失败：$($c1.Out)"; exit 1 }
    }
    $null = RunGit @("add", "-A")
    if ((RunGit @("diff", "--cached", "--quiet")).Code -ne 0) {
        $c2 = RunGit @("commit", "-q", "-m", "docs: 更新接口契约、后端文档与依赖清单；平台示例文案中性化")
        if ($c2.Code -eq 0) { Ok "已提交文档与依赖整理" } else { Bad "提交失败：$($c2.Out)"; exit 1 }
    }
}

Info "===== 3/5 合并远端内容（冲突以团队版为准）====="
$null = RunGit @("fetch", "origin")
if ((RunGit @("rev-parse", "--verify", "origin/main")).Code -ne 0) {
    Warn "远端还没有 main 分支，跳过合并，直接推送"
} else {
    $m = RunGit @("merge", "origin/main", "--allow-unrelated-histories", "-X", "theirs", "--no-edit")
    if ($m.Code -ne 0) {
        $un = @((RunGit @("diff", "--name-only", "--diff-filter=U")).Out -split "`r?`n" | Where-Object { $_ })
        if ($un.Count -gt 0) {
            Warn "有 $($un.Count) 个冲突文件，采用远端（团队）版本：$($un -join ', ')"
            foreach ($f in $un) {
                $null = RunGit @("checkout", "--theirs", "--", $f)
                $null = RunGit @("add", "--", $f)
            }
            $cm = RunGit @("commit", "--no-edit")
            if ($cm.Code -ne 0) { Bad "合并提交失败：$($cm.Out)"; exit 1 }
        } else {
            Bad "merge 失败：$($m.Out)"
            Write-Host "  可手动执行： git merge origin/main --allow-unrelated-histories" -ForegroundColor Yellow
            exit 1
        }
    }
    Ok "已合并远端内容"
}

Info "===== 4/5 补充 .gitignore（缺失时）====="
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
$giAppendPath = Join-Path $PSScriptRoot "tools\gitignore-append.txt"

if (Test-Path -LiteralPath $giAppendPath) {
    $giPath = Join-Path $PSScriptRoot ".gitignore"
    $gi = [System.IO.File]::ReadAllText($giPath, [System.Text.Encoding]::UTF8)
    if ($gi -notmatch "\.env\.local") {
        [System.IO.File]::AppendAllText($giPath, [System.IO.File]::ReadAllText($giAppendPath, [System.Text.Encoding]::UTF8), $utf8NoBom)
        Ok "已补充 .gitignore（.env.local / .ssh/ / node_modules / docx 等）"
    } else { Ok ".gitignore 已包含这些规则，跳过" }
} else { Warn "找不到 tools\gitignore-append.txt，跳过 .gitignore 补充" }

$null = RunGit @("add", "-A")
if ((RunGit @("diff", "--cached", "--quiet")).Code -eq 0) {
    Ok "没有新改动需要提交"
} else {
    $c3 = RunGit @("commit", "-q", "-m", "docs: 更新接口契约、后端文档与依赖清单；清理 README 冗余章节")
    if ($c3.Code -eq 0) { Ok "已提交文档改动" } else { Bad "提交失败：$($c3.Out)"; exit 1 }
}

Info "===== 5/5 推送到 GitHub ====="
$null = RunGit @("fetch", "origin")
if ((RunGit @("rev-parse", "--verify", "origin/main")).Code -eq 0) {
    if ((RunGit @("merge-base", "--is-ancestor", "origin/main", "HEAD")).Code -ne 0) {
        Bad "本地还没包含远端最新提交，直接推会被拒绝。请先执行： git merge origin/main --allow-unrelated-histories"
        exit 1
    }
}
$p = RunGit @("push", "-u", "origin", "main")
if ($p.Code -ne 0) {
    Bad "推送失败：`n$($p.Out)"
    Write-Host "  排查：确认 SSH 公钥已加到你的 GitHub 账号，且你对该仓库有 Write 权限" -ForegroundColor Yellow
    exit 1
}
Ok "推送成功"

Info "----- 提交历史（最近 8 条）-----"
Write-Host (RunGit @("log", "--oneline", "-8")).Out
Info "----- 确认 README 状态 -----"
$head = (RunGit @("show", "HEAD:README.md")).Out
if ($head -match "不漏办") { Ok "团队 README（不漏办 · 智能办事清单助手）完好保留" } else { Warn "README 首行异常，请打开确认" }
if ($head -match "十八、后端服务") { Warn "README 里仍有『十八、后端服务』章节，请检查" } else { Ok "已确认 README 中不存在多余的后端章节" }
Info "----- 工作区状态 -----"
Write-Host (RunGit @("status", "-sb")).Out
Write-Host ""
Write-Host "仓库地址：https://github.com/sssweetis/chuanzhi-cup-ai-web_Triple-Y" -ForegroundColor Cyan