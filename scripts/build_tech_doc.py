# -*- coding: utf-8 -*-
"""把 docs/技术文档.md 转成可打印的 HTML（浏览器 Ctrl+P → 另存为 PDF）"""
import io
import os

import markdown

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "docs", "技术文档.md")
OUT = os.path.join(ROOT, "docs", "技术文档.html")

text = io.open(SRC, encoding="utf-8").read()
body = markdown.markdown(text, extensions=["tables", "fenced_code", "sane_lists"])

HTML = """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>通知抽取助手 · 技术文档（Triple Y）</title>
<style>
  @page { size: A4; margin: 18mm 16mm; }
  body { font-family: "Microsoft YaHei", "PingFang SC", "Noto Sans CJK SC", sans-serif;
         font-size: 10.5pt; line-height: 1.75; color: #222; max-width: 180mm; margin: 0 auto; padding: 10mm 0; }
  h1 { font-size: 22pt; text-align: center; margin: 0 0 6mm; letter-spacing: 1px; }
  h2 { font-size: 15pt; border-bottom: 1px solid #c9c9c9; padding-bottom: 2mm; margin-top: 9mm; page-break-after: avoid; }
  h3 { font-size: 12.5pt; margin-top: 6mm; page-break-after: avoid; }
  p { margin: 2.5mm 0; text-align: justify; }
  table { border-collapse: collapse; width: 100%; font-size: 9.5pt; margin: 3mm 0; page-break-inside: avoid; }
  th, td { border: 1px solid #b9b9b9; padding: 2mm 2.5mm; vertical-align: top; }
  th { background: #f2f2f2; }
  pre { background: #f6f8fa; border: 1px solid #e1e4e8; padding: 3mm; font-size: 9pt;
        white-space: pre-wrap; word-break: break-all; page-break-inside: avoid; }
  code { background: #f2f4f7; padding: .2mm 1mm; border-radius: 2px; }
  blockquote { border-left: 3px solid #999; margin: 3mm 0; padding: 1mm 0 1mm 4mm; color: #555; background: #fafafa; }
  ul, ol { padding-left: 6mm; }
  .toolbar { position: fixed; top: 10px; right: 10px; }
  .toolbar button { padding: 8px 14px; font-size: 13px; cursor: pointer; }
  @media print { .toolbar { display: none; } body { max-width: none; padding: 0; } }
</style>
</head>
<body>
<div class="toolbar"><button onclick="window.print()">打印 / 另存为 PDF</button></div>
__BODY__
</body>
</html>
"""

io.open(OUT, "w", encoding="utf-8", newline="\n").write(HTML.replace("__BODY__", body))
print("已生成：", OUT)
print("段落数：", len(body.split("\n")))