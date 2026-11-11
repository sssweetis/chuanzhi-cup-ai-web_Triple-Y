# -*- coding: utf-8 -*-
"""日志脱敏：不在日志中打印 Key，也不打印过长的模型原文输出。"""
import logging
import re

_KEY_RE = re.compile(r"(sk-[A-Za-z0-9_-]{8,})")


class RedactFilter(logging.Filter):
    def filter(self, record):
        try:
            message = record.getMessage()
        except Exception:
            return True
        message = _KEY_RE.sub("sk-***", message)
        if len(message) > 1200:
            message = message[:1200] + "...[truncated]"
        record.msg = message
        record.args = ()
        return True


def install():
    filt = RedactFilter()
    for name in ("main", "notification_extractor", "service", "image_analyzer", "pdf_analyzer"):
        logging.getLogger(name).addFilter(filt)
