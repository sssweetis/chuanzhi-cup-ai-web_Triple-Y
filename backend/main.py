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

import json
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

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

from service import analyze_notification  # noqa: E402
from requirement_checker import check_requirements  # noqa: E402

logger = logging.getLogger("main")

# ==================== 配置 ====================

# 无 Key 时是否返回示例 Matter（A 的抽取模块本身已不带 mock，这里由入口层兜底）
LLM_ENABLE_MOCK = (os.getenv("LLM_ENABLE_MOCK") or "0").strip() == "1"

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


# ==================== 无 Key 时的演示兜底 ====================

_MOCK_HINTS = {
    "complex": ("流程", "审核", "依赖", "子步骤", "缴费", "准考证", "答辩", "负责人", "学院"),
    "standard": ("材料", "附件", "成绩单", "复印件", "地点", "盖章", "签字", "行政楼", "办公室"),
}


def _mock_matter(notification_text: str) -> Optional[dict]:
    """从仓库自带的 samples/ 里挑一份示例 Matter（内容虚构、结构真实）。

    A 的新版抽取模块无 Key 时会直接报错；为了让前端在没有 Key 时也能联调，
    这里用 samples/simple|standard|complex.json 作为兜底。
    """
    text = notification_text or ""
    mode = "simple"
    for name in ("complex", "standard"):
        if any(k in text for k in _MOCK_HINTS[name]):
            mode = name
            break

    parent = Path(__file__).resolve().parent
    for path in (parent.parent / "samples" / (mode + ".json"), parent / "samples" / (mode + ".json")):
        if not path.exists():
            continue
        try:
            with path.open(encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue
        now = datetime.now(timezone(timedelta(hours=8))).isoformat()
        data["id"] = "matter_mock_" + uuid.uuid4().hex[:8]
        data["created_at"] = now
        data["updated_at"] = now
        data["mode"] = mode
        data["mode_source"] = "mock"
        return data
    return None


def _analyze_with_fallback(text: str) -> dict:
    """先走 A 的真实抽取；无 Key 且 LLM_ENABLE_MOCK=1 时退回示例 Matter。"""
    result = analyze_notification(text)
    if (not result.get("success") and LLM_ENABLE_MOCK
            and "LLM_API_KEY" in str(result.get("error") or "")):
        mock = _mock_matter(text)
        if mock:
            logger.warning("未配置 LLM_API_KEY，返回示例 Matter 兜底（仅供前端联调）")
            return {"success": True, "data": mock, "error": None}
    return result


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
    return _analyze_with_fallback(text)


# ==================== 10/18：用户情况核对（缺项核对）====================

class CheckRequest(BaseModel):
    """
    用户情况核对请求，三种用法：
      1) 传 matter（上次 /api/analyze 的 data）+ 勾选状态 → 不跑模型，最快
      2) 传 text（通知原文）+ 勾选状态 → 服务端先抽取一次再核对
      3) 再传 profile（用户自述，如 {"has_video": false}）→ 核对自述与原文要求是否冲突
    """

    matter: Optional[dict] = None
    text: Optional[str] = None
    checked_material_ids: Optional[List[str]] = None
    profile: Optional[Dict[str, Any]] = None
    profile_checks: Optional[List[dict]] = None


@app.post("/api/check", response_model=AnalyzeResponse)
def check(req: CheckRequest):
    """
    输入：{ "matter": {...} 或 "text": "通知原文", "checked_material_ids": [...], "profile": {...} }
    输出：{ "success": true, "data": { "matter": {...}, "missing_required": [...], "summary": "..." }, "error": null }

    纯规则比对，不调用大模型；不修改 /api/analyze 的字段命名与结构。
    """
    matter = req.matter
    notice_text = (req.text or "").strip()

    if matter is None:
        if not notice_text:
            return _fail("请提供通知原文（text）或已解析结果（matter）")
        if 0 < MAX_TEXT_LENGTH < len(notice_text):
            return _fail(f"通知过长，当前{len(notice_text)}字符，上限{MAX_TEXT_LENGTH}")
        result = _analyze_with_fallback(notice_text)
        if not result.get("success"):
            return result
        matter = result.get("data")

    if not isinstance(matter, dict) or not matter:
        return _fail("matter 必须是 /api/analyze 返回的 data 对象")

    try:
        detail = check_requirements(
            matter,
            checked_material_ids=req.checked_material_ids,
            profile=req.profile,
            profile_checks=req.profile_checks,
            notice_text=notice_text,
        )
    except Exception as e:  # 兜底：核对出错也不影响前端拿到原始 matter
        logger.exception("核对异常：%s", e)
        return _fail(f"核对异常：{e}")

    return {"success": True, "data": {"matter": matter, **detail}, "error": None}


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