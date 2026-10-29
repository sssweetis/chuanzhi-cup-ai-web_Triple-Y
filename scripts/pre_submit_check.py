# -*- coding: utf-8 -*-
"""提交前自检（评委提交版）：密钥 / 必交文件 / 大文件 / 说明占位"""
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SECRET_PATTERNS = [
    (re.compile(r"sk-[A-Za-z0-9]{16,}"), "疑似 API Key（sk- 开头）"),
    (re.compile(r"TEAM_LLM_API_KEY=\S+"), "TEAM_LLM_API_KEY 有值"),
    (re.compile(r"(?m)^LLM_API_KEY=\S+"), "LLM_API_KEY 有值"),
    (re.compile(r"ghp_[A-Za-z0-9]{20,}"), "疑似 GitHub Token"),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "疑似 AWS Key"),
    (re.compile(r"3468342816@qq\.com"), "个人邮箱"),
    (re.compile(r"3547251833@qq\.com"), "个人邮箱"),
]
REQUIRED = [
    "README.md", "LICENSE", "backend/main.py", "backend/requirements.txt",
    "backend/.env.example", "backend/smoke_test_hardening.py", "frontend/package.json",
    "scripts/build_tech_pdf.ps1",
    "docs/技术文档.md", "docs/技术文档.html", "docs/技术文档.pdf", "docs/演示视频脚本.md",
    "docs/部署说明.md", "docs/第三阶段测试用例.md",
]
LARGE_MB = 5


SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", "data", "dist", ".idea", ".vscode", ".pytest_cache"}


def git_files():
    """优先用 git ls-files；不可用时退化为目录遍历（跳过依赖/缓存/data）。"""
    try:
        out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
        files = [line for line in out.stdout.splitlines() if line]
        if files:
            return files
    except Exception:
        pass
    files = []
    for base, dirs, names in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for n in names:
            if n == ".env":          # 本地密钥文件不参与扫描（应被 gitignore）
                continue
            rel = os.path.relpath(os.path.join(base, n), ROOT).replace("\\", "/")
            files.append(rel)
    return files


def main():
    problems, warns = [], []
    files = git_files()
    print("=" * 66)
    print("提交前自检（仓库文件 %d 个）" % len(files))
    print("=" * 66)

    print("[1] 必交文件")
    for f in REQUIRED:
        if os.path.exists(os.path.join(ROOT, f)):
            print("  ✅", f)
        else:
            print("  ❌", f)
            problems.append("缺少文件：" + f)

    print("\n[2] 密钥 / 个人邮箱")
    hits = 0
    for f in files:
        path = os.path.join(ROOT, f)
        if not os.path.isfile(path) or os.path.getsize(path) > 2 * 1024 * 1024:
            continue
        if f == "scripts/pre_submit_check.py":
            continue
        try:
            text = open(path, encoding="utf-8", errors="ignore").read()
        except Exception:
            continue
        for pattern, desc in SECRET_PATTERNS:
            for m in pattern.finditer(text):
                found = m.group(0)
                if any(tok in found for tok in ("<", "xxx", "XXX", "在此", "your", "{", "…")):
                    continue          # 文档里的占位符，不是真实密钥
                print("  ⚠️ ", f, "→", desc, ":", found[:20])
                warns.append("%s: %s" % (f, desc))
                hits += 1
    if not hits:
        print("  ✅ 未发现密钥或个人邮箱")
    tracked_env = {f for f in files if f == ".env" or f.endswith("/.env")}
    if tracked_env:
        print("  ❌ .env 被 git 跟踪了！", tracked_env)
        problems.append(".env 被跟踪")
    else:
        print("  ✅ .env 未被跟踪（本地 .env 不计入）")

    print("\n[3] 大文件（>%dMB）" % LARGE_MB)
    big = []
    for f in files:
        path = os.path.join(ROOT, f)
        if os.path.isfile(path) and os.path.getsize(path) > LARGE_MB * 1024 * 1024:
            big.append((f, os.path.getsize(path) / 1024 / 1024))
    if big:
        for f, mb in sorted(big, key=lambda x: -x[1]):
            print("  ⚠️  %s  %.1f MB" % (f, mb))
        warns.append("存在大于 %dMB 的文件" % LARGE_MB)
    else:
        print("  ✅ 无")

    print("\n[4] 文档完整性")
    tech_doc = os.path.join(ROOT, "docs", "技术文档.md")
    if os.path.isfile(tech_doc):
        text = open(tech_doc, encoding="utf-8", errors="ignore").read()
        if any(mark in text for mark in ("<<<<<<<", "=======", ">>>>>>>")):
            print("  ❌ 技术文档仍有 Git 冲突标记")
            problems.append("技术文档存在冲突标记")
        if "TODO（A）" in text:
            print("  ⚠️  技术文档 4.1/4.2 仍有 A 侧 TODO")
            warns.append("技术文档 4.1/4.2 待 A 补完")

    print("\n[5] 提醒（需人工确认）")
    print("  · README「团队分工」是否写了真实姓名/GitHub 账号")
    print("  · docs/技术文档.md 的 4.1/4.2 已由 A 补完（检查最终 PDF 是否包含）")
    print("  · 演示视频是否已录（5–8 分钟、MP4、≥1080p）")
    print("  · 技术文档 PDF 是否已按最终版重新导出（当前 24 页，≤30 页）")

    print("\n" + "=" * 66)
    if problems:
        print("❌ 有 %d 个必须修复的问题" % len(problems))
        for p in problems:
            print("   -", p)
        return 1
    if warns:
        print("⚠️  有 %d 个提醒（不阻塞，但建议处理）" % len(warns))
        return 0
    print("✅ 提交前自检通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())