# -*- coding: utf-8 -*-
"""
图片解析接入点（C 侧，对应 10/23「截图分析」）

链路：前端 multipart 上传 image → main.py 校验大小/格式 → 本函数交给 A 的 OCR / 多模态解析
     → 返回 {success, data: Matter, error} 统一信封。

A 提供图片解析函数后，只需要替换 analyze_image_bytes 的实现（保持签名不变），
main.py 与前端契约都不用改。
"""

import logging

logger = logging.getLogger("image_analyzer")

IMAGE_MAX_BYTES = 5 * 1024 * 1024          # 5 MB
ALLOWED_IMAGE_TYPES = {
    "image/jpeg": "JPG",
    "image/png": "PNG",
    "image/webp": "WEBP",
}


def analyze_image_bytes(raw: bytes, filename: str, content_type: str):
    """解析一张图片。

    返回 (matter_dict | None, error_str | None)。
    当前（10/21）为接入前的占位实现：给前端明确的、可展示的错误文案。
    """
    logger.info("收到图片：name=%s type=%s size=%.1fKB", filename, content_type, len(raw) / 1024)
    # TODO(10/23)：接入 A 的图片解析（OCR / 多模态），例如：
    #   text = a_ocr(raw)                 # 图片 → 文字
    #   return a_analyze(text)            # 文字 → Matter
    return None, ("图片解析能力正在接入（OCR / 多模态，10/23 上线）；"
                  "当前请先粘贴文字通知，或使用页面上的示例。")