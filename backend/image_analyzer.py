# -*- coding: utf-8 -*-
"""
图片解析（C 侧 10/23）：截图 →（团队视觉模型）→ 文字 → A 的 analyze_notification → Matter

A 提供的方案（2026-10-21 确认）：
    1. 图片 base64 → 视觉模型（gpt-4o / qwen-vl-max 等）提取纯文字
    2. 把文字交给 service.analyze_notification()
    3. 返回完整 Matter

与她的示例相比，这里做了两处适配：
    · import：`from service import analyze_notification`（backend 目录下直接可导入）
    · 返回：main.py 约定 `(matter, error)` 元组，而不是直接抛异常
另外：没有配置团队 Key 时返回明确提示，方便前端展示失败态。
"""

import base64
import logging
import os
from typing import Optional, Tuple

from service import analyze_notification

logger = logging.getLogger("image_analyzer")

IMAGE_MAX_BYTES = 5 * 1024 * 1024          # 5 MB
ALLOWED_IMAGE_TYPES = {
    "image/jpeg": "JPG",
    "image/png": "PNG",
    "image/webp": "WEBP",
}

VISION_PROMPT = "请精确提取图片中的通知文字，保持原有格式，不要任何解释。"
VISION_TIMEOUT = 90


def _vision_config():
    """团队视觉模型配置：TEAM_LLM_* 优先，其次回退到 LLM_*。"""
    api_key = (os.getenv("TEAM_LLM_API_KEY") or os.getenv("LLM_API_KEY") or "").strip()
    base_url = (os.getenv("TEAM_LLM_BASE_URL") or os.getenv("LLM_BASE_URL") or "").strip() or None
    model = (os.getenv("TEAM_LLM_MODEL") or "").strip() or os.getenv("LLM_MODEL") or "gpt-4o"
    return api_key, base_url, model


def analyze_image_bytes(raw: bytes, filename: str, content_type: str) -> Tuple[Optional[dict], Optional[str]]:
    """返回 (matter_dict | None, error | None)。"""
    api_key, base_url, model = _vision_config()
    if not api_key:
        return None, ("未配置 TEAM_LLM_API_KEY（团队视觉模型 Key），图片解析暂不可用；"
                      "请先粘贴文字通知，或把截图里的文字复制出来。")

    try:
        from openai import OpenAI

        b64 = base64.b64encode(raw).decode("utf-8")
        client = OpenAI(api_key=api_key, base_url=base_url, timeout=VISION_TIMEOUT)
        response = client.chat.completions.create(
            model=model,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": VISION_PROMPT},
                    {"type": "image_url",
                     "image_url": {"url": "data:%s;base64,%s" % (content_type, b64)}},
                ],
            }],
            temperature=0,
        )
        extracted_text = (response.choices[0].message.content or "").strip()
    except Exception as e:
        logger.exception("图片识别失败：%s", e)
        return None, "图片识别失败：%s" % e

    if len(extracted_text) < 10:
        return None, "图片中未识别到有效文字，请换一张更清晰的通知截图"

    logger.info("图片识别完成：%s chars=%d model=%s", filename, len(extracted_text), model)
    result = analyze_notification(extracted_text)
    if not result.get("success"):
        return None, result.get("error") or "图片内容解析失败"
    return result.get("data"), None