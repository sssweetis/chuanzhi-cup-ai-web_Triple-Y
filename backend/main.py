# -*- coding: utf-8 -*-
"""
C 的后端入口（FastAPI）—— 通知抽取服务

启动（三选一）：
    python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
    bash run.sh          # macOS / Linux / Git Bash
    powershell run.ps1   # Windows

接口契约（不得修改）：
    GET  /health      → {"status": "ok", "mode": "mock" | "real"}
    POST /api/analyze
         请求：{"text": "通知原文"}
         响应：{"success": true/false, "data": {...} | null, "error": string | null}

说明：
    - 抽取逻辑（复杂度评分、模式判定、字段结构）全部在 service.py / notification_extractor.py，
      本文件只做「入口参数校验 + 统一响应 + 跨域 + 服务自检」，不改动 A 的字段命名与数据结构。
    - 所有 /api/analyze 的响应都是 HTTP 200 + 统一契约（包括参数错误），
      前端 B 只需判断 body.success，不用再处理 422 的 detail 结构。
"""

import logging
import os
from typing import Optional

from dotenv import load_dotenv

# ⚠️ 必须在 import service 之前加载 .env：
#    notification_extractor 在「导入时」就读取 LLM_ENABLE_MOCK，
#    如果放到后面加载，.env 里的 LLM_ENABLE_MOCK=1 会失效。
load_dotenv()

from fastapi import FastAPI, Request  # noqa: E402
from fastapi.exceptions import RequestValidationError  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from notification_extractor import LLM_ENABLE_MOCK  # noqa: E402
from service import analyze_notification  # noqa: E402

logger = logging.getLogger("main")

# ==================== 配置 ====================

DEFAULT_MAX_TEXT_LENGTH = 3000


def _read_max_text_length() -> int:
    """文本长度上限，默认 3000 字符；可用环境变量 MAX_TEXT_LENGTH 覆盖，0 或负数表示不限制。"""
    raw = (os.getenv("MAX_TEXT_LENGTH") or "").strip()
    if not raw:
        return DEFAULT_MAX_TEXT_LENGTH
    try:
        return int(raw)
    except ValueError:
        logger.warning("MAX_TEXT_LENGTH=%r 不是整数，已回退为 %d", raw, DEFAULT_MAX_TEXT_LENGTH)
        return DEFAULT_MAX_TEXT_LENGTH


MAX_TEXT_LENGTH = _read_max_text_length()

API_KEY = (os.getenv("LLM_API_KEY") or "").strip()


def runtime_mode() -> str:
    """当前运行模式：配了 Key → real；没 Key 且开了 Mock → mock。"""
    if API_KEY:
        return "real"
    return "mock" if LLM_ENABLE_MOCK else "real"


if runtime_mode() == "mock":
    logger.warning("当前模式：mock（未配置 LLM_API_KEY）—— 返回的是虚构 Matter 数据，仅用于前端联调")
elif not API_KEY:
    logger.warning("当前模式：real，但没有 LLM_API_KEY —— 真实解析会失败，请配置 Key 或设置 LLM_ENABLE_MOCK=1")
else:
    logger.info("当前模式：real，model=%s", os.getenv("LLM_MODEL", "gpt-4o"))

# ==================== FastAPI 应用 ====================

app = FastAPI(
    title="通知抽取服务",
    description="校园通知原文 → 结构化 Matter JSON（截止时间 / 材料清单 / 步骤）",
    version="1.0.0",
)

# CORS：允许所有来源，方便 B 在 http://localhost:5173 直接跨域调用。
# 注意：allow_credentials 必须为 False，才能与 allow_origins=["*"] 同时生效。
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================== 请求 / 响应模型 ====================

class AnalyzeRequest(BaseModel):
    text: Optional[str] = None


class AnalyzeResponse(BaseModel):
    success: bool
    data: Optional[dict] = None
    error: Optional[str] = None


def _fail(error: str) -> dict:
    """统一失败响应。"""
    return {"success": False, "data": None, "error": error}


# ==================== 接口 ====================

@app.get("/")
def index():
    """浏览器直接打开时给个提示，便于演示。"""
    return {
        "service": "通知抽取服务",
        "mode": runtime_mode(),
        "endpoints": ["GET /health", "POST /api/analyze", "GET /docs"],
    }


@app.get("/health")
def health():
    """服务自检：status 固定 ok，mode 表示当前走 mock 还是真实大模型。"""
    return {"status": "ok", "mode": runtime_mode()}


@app.post("/api/analyze", response_model=AnalyzeResponse)
def analyze(req: AnalyzeRequest):
    """
    输入：{ "text": "通知原文" }
    输出：{ "success": true, "data": {...Matter JSON...}, "error": null }
    """
    text = req.text

    # 1) 空文本校验
    if text is None or not text.strip():
        return _fail("通知内容不能为空")

    # 2) 超长文本保护
    if 0 < MAX_TEXT_LENGTH < len(text):
        return _fail(f"通知过长，当前{len(text)}字符，上限{MAX_TEXT_LENGTH}")

    # 3) 交给 A 的抽取服务（不改动其内部逻辑）
    return analyze_notification(text)


# ==================== 统一错误兜底 ====================

@app.exception_handler(RequestValidationError)
async def on_validation_error(request: Request, exc: RequestValidationError):
    """请求体不是合法 JSON / 字段类型不对时，也返回统一契约，而不是 FastAPI 默认的 422。"""
    logger.warning("请求体校验失败：%s", exc.errors())
    return JSONResponse(status_code=200, content=_fail('请求体格式错误，应为 {"text": "通知原文"}'))


@app.exception_handler(Exception)
async def on_unhandled_error(request: Request, exc: Exception):
    """兜底：任何未捕获异常都转成统一契约，避免前端拿到 500 堆栈。"""
    logger.exception("服务内部异常：%s", exc)
    return JSONResponse(status_code=200, content=_fail(f"服务内部异常：{exc}"))


# ==================== 本地直接运行 ====================

if __name__ == "__main__":
    import uvicorn

    port = int((os.getenv("PORT") or "8000").strip() or "8000")
    logger.info("启动服务：mode=%s，max_text_length=%s，port=%s", runtime_mode(), MAX_TEXT_LENGTH, port)
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)