# -*- coding: utf-8 -*-
"""
抽取模块同步检查（C 负责）

背景：A 维护的 notification_extractor.py 在仓库里有两份同源副本——
      src/notification_extractor.py（A 的工作目录）与 backend/notification_extractor.py（C 的后端依赖）。
      两份内容一旦分叉，前端看到的结构就可能和 A 定的不一样。

用法：
    python check_sync.py

输出「一致 ✅」说明没问题；若提示不一致，按提示把 A 的最新版同步到 backend/ 再跑 smoke_test.py 回归。
"""

import hashlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PAIRS = [
    ("notification_extractor.py", os.path.join(HERE, "notification_extractor.py"),
     os.path.join(HERE, "..", "src", "notification_extractor.py")),
    ("service.py", os.path.join(HERE, "service.py"),
     os.path.join(HERE, "..", "src", "service.py")),
]


def sha256(path: str) -> str:
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


print("=" * 64)
print("抽取模块同步检查（backend/ 与 src/ 是否一致）")
print("=" * 64)

bad = []
for name, backend_path, src_path in PAIRS:
    print("-" * 64)
    if not os.path.exists(src_path):
        print("⚠️  %s：src 版本不存在（%s），跳过" % (name, os.path.abspath(src_path)))
        continue
    if not os.path.exists(backend_path):
        print("❌ %s：backend 版本缺失（%s）" % (name, backend_path))
        bad.append(name)
        continue
    h1, h2 = sha256(backend_path), sha256(src_path)
    if h1 == h2:
        print("✅ %s 一致  (%s)" % (name, h1[:16]))
    else:
        print("❌ %s 不一致！" % name)
        print("     backend: %s" % h1)
        print("     src    : %s" % h2)
        print("     处理：把 src 的最新版复制到 backend，然后跑 python smoke_test.py 回归")
        bad.append(name)

print("=" * 64)
if bad:
    print("需要同步：%s" % "、".join(bad))
    sys.exit(1)
print("全部一致 ✅  A 更新文件后记得再跑一次本检查")