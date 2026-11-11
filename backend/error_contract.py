# -*- coding: utf-8 -*-
"""统一错误信封（C 侧，错误契约 v2）。"""
from contextvars import ContextVar
import uuid

_request_id = ContextVar("tripley_request_id", default="")


def new_request_id() -> str:
    return "req_" + uuid.uuid4().hex[:10]


def set_request_id(value: str):
    return _request_id.set(value or new_request_id())


def reset_request_id(token) -> None:
    _request_id.reset(token)


def current_request_id() -> str:
    return _request_id.get() or new_request_id()


def error_object(message, code="REQUEST_FAILED", stage="request",
                 retryable=False, retry_after=None, request_id=None) -> dict:
    payload = {
        "code": code,
        "message": str(message or "请求失败，请稍后重试"),
        "retryable": bool(retryable),
        "stage": stage,
        "request_id": request_id or current_request_id(),
    }
    if retry_after is not None:
        payload["retry_after"] = int(retry_after)
    return payload


def infer_error_meta(message: str, code=None, stage=None, retryable=False):
    """对入口校验的常见中文提示补上稳定的机器可读 code。"""
    text = str(message or "")
    if code and stage:
        return code, stage, retryable
    if "通知内容不能为空" in text:
        return "TEXT_EMPTY", "validation", False
    if "通知过长" in text:
        return "TEXT_TOO_LONG", "validation", False
    if "matter 必须" in text or "请提供已解析结果" in text or "请提供通知原文" in text:
        return "CHECK_INPUT", "check", False
    if "图片内容为空" in text:
        return "IMAGE_EMPTY", "upload", False
    if "图片不能超过" in text:
        return "IMAGE_TOO_LARGE", "upload", False
    if "仅支持 JPG" in text or "格式" in text and "图片" in text:
        return "IMAGE_TYPE", "validation", False
    if "PDF 内容为空" in text:
        return "PDF_EMPTY", "upload", False
    if "PDF 不能超过" in text:
        return "PDF_TOO_LARGE", "upload", False
    if "仅支持 PDF" in text:
        return "PDF_TYPE", "validation", False
    if "文件内容为空" in text:
        return "FILE_EMPTY", "upload", False
    if "文件不能超过" in text:
        return "FILE_TOO_LARGE", "upload", False
    if "仅支持 TXT / MD / PDF" in text:
        return "FILE_TYPE", "validation", False
    if "检索内容不能为空" in text:
        return "SEARCH_EMPTY", "validation", False
    if "问题不能为空" in text:
        return "ASK_EMPTY", "validation", False
    if "没有找到" in text:
        return "NOT_FOUND", "business", False
    if "没有可导出的" in text:
        return "EXPORT_EMPTY", "business", False
    return code or "REQUEST_FAILED", stage or "request", retryable
