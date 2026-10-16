<#
  一键提交并推送到 GitHub（传智杯 · Triple Y）
  ------------------------------------------------------------------
  仓库地址：https://github.com/sssweetis/chuanzhi-cup-ai-web_Triple-Y

  用法：在【本文件所在目录】打开 PowerShell，执行：
      powershell -ExecutionPolicy Bypass -File .\push-to-github.ps1

  可选参数：
      -NoPush      只做本地提交，不推送（先自己看看 git log）
      -UseHttps    直接用 HTTPS + 浏览器登录推送（跳过 SSH 配置）

  说明：
      · 按功能模块分多次提交，形成真实的开发记录（比赛要求「完整提交历史」）
      · .env / .venv / __pycache__ / .ssh / 官方 docx 都在 .gitignore 里，不会被上传
      · 优先走 SSH（本机 HTTPS 到 github.com:443 可能被网络阻断）
#>
param(
    [switch]$NoPush,
    [switch]$UseHttps
)

Set-Location -LiteralPath $PSScriptRoot
$ErrorActionPreference = "Continue"

$GhUser  = "sssweetis"
$GhRepo  = "chuanzhi-cup-ai-web_Triple-Y"
$SshUrl  = "git@github.com:$GhUser/$GhRepo.git"
$HttpUrl = "https://github.com/$GhUser/$GhRepo.git"
$WebUrl  = "https://github.com/$GhUser/$GhRepo"

function Info($m) { Write-Host "`n$m" -ForegroundColor Cyan }
function Ok($m)   { Write-Host "  [OK] $m" -ForegroundColor Green }
function Warn($m) { Write-Host "  [!]  $m" -ForegroundColor Yellow }
function Bad($m)  { Write-Host "  [X]  $m" -ForegroundColor Red }

# 静默执行 git，返回输出与退出码（避免 stderr 噪声把脚本打断）
function RunGit {
    param([string[]]$GitArgs)
    $out = (& git @GitArgs 2>&1 | Out-String).Trim()
    return @{ Out = $out; Code = $LASTEXITCODE }
}

function Commit-Group {
    param([string]$Message, [string[]]$Paths)
    $staged = @()
    foreach ($p in $Paths) {
        if (Test-Path -LiteralPath $p) { $staged += $p } else { Warn "跳过不存在的路径：$p" }
    }
    if (-not $staged) { return }
    $null = RunGit @("add", "--") + @($staged)
    $null = (& git add -- $staged 2>&1 | Out-String)
    $diff = RunGit @("diff", "--cached", "--quiet")
    if ($diff.Code -eq 0) { Warn "无变化，跳过：$Message"; return }
    $r = RunGit @("commit", "-q", "-m", $Message)
    if ($r.Code -eq 0) { Ok $Message } else { Bad "提交失败：$Message`n$($r.Out)" }
}

# ===================== 1. 环境检查 =====================
Info "===== 1/6 环境检查 ====="
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Bad "没找到 git，请先安装 Git for Windows：https://git-scm.com/download/win"
    exit 1
}
$gv = RunGit @("--version")
Ok $gv.Out

$name = (RunGit @("config", "user.name")).Out
$mail = (RunGit @("config", "user.email")).Out
if (-not $name) { $name = Read-Host "请输入 Git 提交用户名（拼音/英文）"; $null = RunGit @("config", "--global", "user.name", $name) }
if (-not $mail) { $mail = Read-Host "请输入 Git 提交邮箱"; $null = RunGit @("config", "--global", "user.email", $mail) }
Ok "提交身份：$name <$mail>"

# ===================== 2. 清理无用文件 =====================
Info "===== 2/6 清理无用文件 ====="
if (Test-Path -LiteralPath ".\.ssh") {
    Remove-Item -LiteralPath ".\.ssh" -Recurse -Force
    Ok "已删除项目里的 .ssh（私钥不应该放在项目目录）"
}
if (Test-Path -LiteralPath ".\.git") {
    if ((RunGit @("rev-parse", "--verify", "HEAD")).Code -ne 0) {
        Remove-Item -LiteralPath ".\.git" -Recurse -Force
        Ok "已删除空的 .git（准备重新初始化）"
    } else {
        Ok "已有提交历史，保留"
    }
}
foreach ($d in @("backend\__pycache__", "backend\.venv")) {
    if (Test-Path -LiteralPath $d) { Warn "$d 存在但是被 .gitignore 忽略，不会上传（可保留，不影响）" }
}

# ===================== 3. 初始化仓库 =====================
Info "===== 3/6 初始化 git 仓库 ====="
if (-not (Test-Path -LiteralPath ".\.git")) {
    $null = RunGit @("init", "-b", "main")
    Ok "git init -b main"
} else {
    Ok "仓库已存在，跳过 init"
}
$null = RunGit @("config", "core.autocrlf", "true")
$null = RunGit @("config", "core.quotepath", "false")
$null = RunGit @("config", "core.safecrlf", "false")

# ===================== 4. 分组提交 =====================
Info "===== 4/6 分组提交（形成真实开发记录）====="

Commit-Group -Message "chore: 初始化仓库，添加项目总说明与 .gitignore" -Paths @(
    "README.md", ".gitignore", "frontend\README.md"
)

Commit-Group -Message "feat(backend): 接入通知抽取服务模块（Prompt / 复杂度评分 / Matter 结构）" -Paths @(
    "backend\service.py", "backend\notification_extractor.py"
)

Commit-Group -Message "feat(backend): FastAPI 接口入口 —— CORS、参数校验、统一响应与 /health 自检" -Paths @(
    "backend\main.py"
)

Commit-Group -Message "chore(backend): 依赖清单、环境变量模板、密钥配置与一键启动脚本" -Paths @(
    "backend\requirements.txt", "backend\.env.example", "backend\.gitignore",
    "backend\run.ps1", "backend\run.sh", "backend\configure_env.ps1", "backend\configure_env.sh"
)

Commit-Group -Message "feat(backend): 环境自检、密钥连通性验证与接口回归脚本" -Paths @(
    "backend\check_env.py", "backend\test_llm.py", "backend\smoke_test.py"
)

Commit-Group -Message "feat(frontend): 提供前端接入包（api.js 封装与环境变量示例）" -Paths @(
    "backend\for-frontend"
)

Commit-Group -Message "docs: 补充比赛要求、接口契约与环境配置说明" -Paths @(
    "docs", "backend\README.md"
)

Commit-Group -Message "chore: 添加一键提交并推送到 GitHub 的脚本" -Paths @(
    "push-to-github.ps1"
)

Info "----- 提交历史 -----"
Write-Host (RunGit @("log", "--oneline", "--date=short", "--pretty=format:%h %ad %s")).Out
Info "----- 将上传的文件 -----"
$tracked = @((RunGit @("ls-files")).Out -split "`r?`n" | Where-Object { $_ })
$tracked | ForEach-Object { Write-Host "  $_" }
Write-Host ("  共 " + $tracked.Count + " 个文件") -ForegroundColor White

$leak = $tracked | Where-Object { $_ -match '(^|/)\.env$' -or $_ -match '\.venv' -or $_ -match '__pycache__' -or $_ -match '\.ssh/' -or $_ -match '\.docx$' }
if ($leak) {
    Bad "检测到不该上传的文件，已中止：$($leak -join ', ')"
    exit 1
}
Ok "确认无 .env / .venv / .ssh / docx 混入"

# ===================== 5. 推送 =====================
Info "===== 5/6 配置连接并推送 ====="
$remotes = @((RunGit @("remote")).Out -split "`r?`n" | Where-Object { $_ })
if ($remotes -contains "origin") { $null = RunGit @("remote", "remove", "origin") }

if ($NoPush) {
    $null = RunGit @("remote", "add", "origin", $SshUrl)
    Warn "已按 -NoPush 跳过推送。本地仓库已就绪，之后执行： git push -u origin main"
    exit 0
}

$useHttps = [bool]$UseHttps
if (-not $useHttps) {
    $keyPath = Join-Path $env:USERPROFILE ".ssh\id_ed25519"
    if (-not (Test-Path -LiteralPath $keyPath)) {
        New-Item -ItemType Directory -Force -Path (Split-Path $keyPath) | Out-Null
        ssh-keygen -t ed25519 -C $mail -f $keyPath -N '""' -q
        Ok "已生成 SSH 密钥：$keyPath"
    }
    $null = RunGit @("remote", "add", "origin", $SshUrl)
    $probe = (& ssh -T -o StrictHostKeyChecking=accept-new git@github.com 2>&1 | Out-String)
    if ($probe -match "successfully authenticated") {
        Ok "SSH 认证通过"
    } else {
        Write-Host ""
        Write-Host "  还需一步：把下面这行公钥加到 GitHub（只需做一次）" -ForegroundColor Yellow
        Write-Host "  1) 打开    https://github.com/settings/ssh/new" -ForegroundColor Yellow
        Write-Host "  2) Title 随便填（例如 my-laptop），Key type 选 Authentication Key" -ForegroundColor Yellow
        Write-Host "  3) 把下面这一整行粘进 Key 框，点 Add SSH key：" -ForegroundColor Yellow
        Write-Host ""
        Write-Host ("  " + (Get-Content -LiteralPath "$keyPath.pub" -Raw).Trim()) -ForegroundColor White
        Write-Host ""
        Write-Host "  4) 加到【你要用来推送的账号】下即可：团队账号最好；用个人账号也行，只要它对仓库有 Write 权限" -ForegroundColor Yellow
        Write-Host "     （同一把公钥只能属于一个 GitHub 账号，若已加到个人账号，先去 个人账号 Settings→SSH keys 删掉再加）" -ForegroundColor DarkGray
        Read-Host "  添加完成后按回车继续" | Out-Null
        $probe = (& ssh -T -o StrictHostKeyChecking=accept-new git@github.com 2>&1 | Out-String)
        if ($probe -match "successfully authenticated") { Ok "SSH 认证通过" }
        else { Warn "SSH 仍未通过，自动改用 HTTPS（浏览器登录）"; $useHttps = $true }
    }
}

if ($useHttps) {
    $null = RunGit @("remote", "add", "origin", $HttpUrl)
    Warn "改用 HTTPS 推送，会弹出浏览器让你登录 GitHub（登录 sssweetis 账号）"
}

# 远端若已有提交（例如 GitHub 自动生成的 README），先 rebase 上去
$fetch = RunGit @("fetch", "origin")
if ($fetch.Code -eq 0) {
    if ((RunGit @("rev-parse", "--verify", "origin/main")).Code -eq 0) {
        Ok "远端已有 main 分支，先 rebase 到远端之上"
        $rb = RunGit @("rebase", "origin/main")
        if ($rb.Code -ne 0) { Bad "rebase 有冲突，请手动处理后再执行 git push -u origin main`n$($rb.Out)"; exit 1 }
    }
}

$push = RunGit @("push", "-u", "origin", "main")
if ($push.Code -ne 0) {
    Bad "推送失败：`n$($push.Out)"
    Write-Host "  排查建议：" -ForegroundColor Yellow
    Write-Host "   · 确认公钥已加到【用来推送的那个账号】（团队账号或你的个人账号，需仓库 Write 权限）：https://github.com/settings/keys"
    Write-Host "   · 或改用 HTTPS：powershell -ExecutionPolicy Bypass -File .\push-to-github.ps1 -UseHttps"
    Write-Host "   · HTTPS 若提示连不上 github.com，说明网络被拦，开代理后重试"
    exit 1
}

# ===================== 6. 完成 =====================
Info "===== 6/6 完成 ====="
Ok "已推送到 $WebUrl"
Write-Host (RunGit @("log", "--oneline")).Out
Write-Host (RunGit @("status", "-sb")).Out
Warn "最后确认：仓库要设为 Public，或给评审账号开通访问权限（Settings → Collaborators / Manage visibility）"