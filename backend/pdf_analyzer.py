# -*- coding: utf-8 -*-
"""
PDF 文字提取（C 侧，10/25「实现文字型 PDF 内容提取」）

支持范围：**文字型 PDF**（能复制出文字的那种）。
扫描版 / 图片型 PDF 提取不到文字 → 明确提示改用截图或粘贴文字（对应 10/23 的图片方案）。
"""

import io
import logging

from pypdf import PdfReader

logger = logging.getLogger("pdf_analyzer")

PDF_MAX_BYTES = 10 * 1024 * 1024      # 10 MB
PDF_MAX_PAGES = 30
PDF_MAX_CHARS = 20000                 # 送给抽取层的上限，超出截断


def extract_pdf_text(raw: bytes):
    """返回 (text | None, meta | None, error | None)。"""
    try:
        reader = PdfReader(io.BytesIO(raw))
    except Exception as e:
        return None, None, "PDF 读取失败：文件可能已损坏（%s）" % type(e).__name__

    if getattr(reader, "is_encrypted", False):
        try:
            if not reader.decrypt(""):
                return None, None, "PDF 已加密，请先解除密码后再上传"
        except Exception:
            return None, None, "PDF 已加密，请先解除密码后再上传"

    pages = len(reader.pages)
    if pages > PDF_MAX_PAGES:
        return None, {"pages": pages}, "PDF 页数过多（%d 页），当前最多支持 %d 页" % (pages, PDF_MAX_PAGES)

    chunks = []
    for page in reader.pages:
        try:
            chunks.append(page.extract_text() or "")
        except Exception:
            chunks.append("")
    text = "\n".join(chunks).strip()
    if len(text) < 20:
        return None, {"pages": pages, "chars": len(text)}, (
            "未从 PDF 中提取到文字：这可能是扫描版 / 图片型 PDF。"
            "请改用清晰截图（图片解析）或直接粘贴文字。")

    truncated = False
    if len(text) > PDF_MAX_CHARS:
        text = text[:PDF_MAX_CHARS]
        truncated = True
    meta = {"pages": pages, "chars": len(text), "truncated": truncated}
    logger.info("PDF 提取完成：pages=%d chars=%d truncated=%s", pages, len(text), truncated)
    return text, meta, None