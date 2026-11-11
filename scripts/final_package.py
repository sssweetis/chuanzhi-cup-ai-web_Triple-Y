# -*- coding: utf-8 -*-
"""生成提交用 ZIP，排除密钥、依赖、缓存和大测试文件。"""
import os
import zipfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT.parent / ("Triple_Y_submission_" + datetime.now().strftime("%Y%m%d_%H%M") + ".zip")
SKIP_DIRS = {".git", ".venv", "node_modules", "__pycache__", "data", "dist", ".pytest_cache"}
SKIP_FILES = {".env", ".env.local", ".env.development"}
LARGE_SKIP = {str(ROOT / "src" / "测试通知.pdf")}

with zipfile.ZipFile(OUT, "w", compression=zipfile.ZIP_DEFLATED) as zf:
    for base, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in files:
            path = Path(base) / name
            rel = path.relative_to(ROOT)
            if name in SKIP_FILES or str(path) in LARGE_SKIP:
                continue
            zf.write(path, rel)

size_mb = OUT.stat().st_size / 1024 / 1024
print("ZIP:", OUT)
print("大小: %.1f MB" % size_mb)
if size_mb >= 100:
    raise SystemExit("ZIP 超过 100MB，请先清理大型素材")
