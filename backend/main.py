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

from fastapi import FastAPI, File, Request, UploadFile  # noqa: E402
from fastapi.exceptions import RequestValidationError  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from service import analyze_notification  # noqa: E402
from requirement_checker import check_requirements  # noqa: E402
from mock_extractor import mock_extract  # noqa: E402
from prepare_list import build_prepare_list, save_prepare_list, load_prepare_list  # noqa: E402
from image_analyzer import ALLOWED_IMAGE_TYPES, IMAGE_MAX_BYTES, analyze_image_bytes  # noqa: E402
from evidence import build_evidence_index, find_evidence, TARGET_TYPES  # noqa: E402

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

def _mock_matter(notification_text: str) -> Optional[dict]:
    """无 Key 时按输入内容生成 Matter（离线关键词 Mock，见 mock_extractor.py）。

    与之前"从 samples/ 里挑固定示例"不同：标题、截止时间、材料、步骤都来自用户输入，
    所以演示时不会出现"输入网络安全、结果却是奖学金"的串数据现象。
    """
    try:
        return mock_extract(notification_text)
    except Exception as e:
        logger.warning("离线 Mock 生成失败：%s", e)
        return None


def _analyze_with_fallback(text: str) -> dict:
    """先走 A 的真实抽取；无 Key 且 LLM_ENABLE_MOCK=1 时直接返回示例 Matter。

    注意：A 的新版模块在没有 Key 时会抛 RuntimeError（并在日志里打一整段 traceback）。
    演示时那段红字容易被误认为故障，所以这里先判断"确实没 Key"，直接走兜底，
    不去触发异常；只有"有 Key 但调用失败"时才让 A 的代码走它自己的错误路径。
    """
    if LLM_ENABLE_MOCK and not (os.getenv("LLM_API_KEY") or "").strip():
        mock = _mock_matter(text)
        if mock:
            logger.info("LLM_API_KEY 未配置，按 Mock 模式返回示例 Matter（内容虚构，结构真实）")
            return {"success": True, "data": mock, "error": None}

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


# ==================== 10/21：准备清单（生成 / 保存 / 读取）====================

class PrepareListRequest(BaseModel):
    matter: Optional[dict] = None
    text: Optional[str] = None
    checked_material_ids: Optional[List[str]] = None


class SavePrepareListRequest(BaseModel):
    matter_id: str
    todo_list: List[dict]
    checked_material_ids: Optional[List[str]] = None


def _matter_from_request(matter, text):
    """matter 优先；没有就用 text 现场解析（含 Mock 兜底）。"""
    if isinstance(matter, dict) and matter:
        return matter, None
    notice_text = (text or "").strip()
    if not notice_text:
        return None, _fail("请提供已解析结果（matter）或通知原文（text）")
    if 0 < MAX_TEXT_LENGTH < len(notice_text):
        return None, _fail(f"通知过长，当前{len(notice_text)}字符，上限{MAX_TEXT_LENGTH}")
    result = _analyze_with_fallback(notice_text)
    if not result.get("success"):
        return None, result
    return result.get("data"), None


@app.post("/api/prepare-list", response_model=AnalyzeResponse)
def prepare_list(req: PrepareListRequest):
    """生成准备清单：缺项材料 + 逐条待办（不调用大模型）。"""
    matter, error = _matter_from_request(req.matter, req.text)
    if error:
        return error
    try:
        data = build_prepare_list(matter, req.checked_material_ids)
    except Exception as e:
        logger.exception("生成准备清单失败：%s", e)
        return _fail(f"生成准备清单失败：{e}")
    return {"success": True, "data": data, "error": None}


@app.post("/api/prepare-list/save", response_model=AnalyzeResponse)
def save_prepare_list_endpoint(req: SavePrepareListRequest):
    """保存（修改后的）准备清单，刷新/换浏览器可恢复。"""
    try:
        record = save_prepare_list(req.matter_id, req.todo_list, req.checked_material_ids)
    except ValueError as e:
        return _fail(str(e))
    except Exception as e:
        logger.exception("保存准备清单失败：%s", e)
        return _fail(f"保存准备清单失败：{e}")
    return {"success": True, "data": record, "error": None}


@app.get("/api/prepare-list/{matter_id}", response_model=AnalyzeResponse)
def get_prepare_list(matter_id: str):
    """读取上次保存的准备清单。"""
    record = load_prepare_list(matter_id)
    if not record:
        return _fail("没有找到保存的准备清单")
    return {"success": True, "data": record, "error": None}


# ==================== 10/23：图片解析（截图 → Matter）====================

@app.get("/api/analyze-image/limits")
def analyze_image_limits():
    """前端启动时读一次，用同一套限制做提示（避免前后端文案不一致）。"""
    return {
        "success": True,
        "data": {
            "field": "image",
            "content_type": "multipart/form-data",
            "max_files": 1,
            "max_bytes": IMAGE_MAX_BYTES,
            "max_mb": round(IMAGE_MAX_BYTES / 1024 / 1024, 1),
            "formats": list(ALLOWED_IMAGE_TYPES.values()),
        },
        "error": None,
    }


@app.post("/api/analyze-image", response_model=AnalyzeResponse)
async def analyze_image(image: UploadFile = File(...)):
    """截图 → Matter。字段名 image，multipart/form-data，返回与 /api/analyze 相同的信封。"""
    ctype = (image.content_type or "").lower().split(";")[0].strip()
    if ctype not in ALLOWED_IMAGE_TYPES:
        return _fail("仅支持 JPG / PNG / WEBP 格式（收到：%s）" % (ctype or "未知"))

    raw = await image.read(IMAGE_MAX_BYTES + 1)
    if not raw:
        return _fail("图片内容为空，请重新选择")
    if len(raw) > IMAGE_MAX_BYTES:
        return _fail("图片不能超过 5 MB（当前 %.1f MB）" % (len(raw) / 1024 / 1024))

    try:
        matter, err = analyze_image_bytes(raw, image.filename or "image", ctype)
    except Exception as e:
        logger.exception("图片解析异常：%s", e)
        return _fail(f"图片解析异常：{e}")

    if err:
        return _fail(err)
    if not isinstance(matter, dict) or not matter:
        return _fail("图片解析失败：结果为空")
    return {"success": True, "data": matter, "error": None}


# ==================== 10/22：查看依据（要求 → 原文）====================

class EvidenceRequest(BaseModel):
    matter: Optional[dict] = None
    target_type: Optional[str] = None
    target_id: Optional[str] = None


class EvidenceIndexRequest(BaseModel):
    matter: Optional[dict] = None


@app.post("/api/evidence", response_model=AnalyzeResponse)
def evidence(req: EvidenceRequest):
    """点一条要求（材料/步骤/待办/附件/截止/预警/要点），返回支持它的原文片段。"""
    if not isinstance(req.matter, dict) or not req.matter:
        return _fail("请提供已解析结果（matter）")
    if not req.target_type or req.target_id is None:
        return _fail("请提供 target_type 与 target_id")
    if req.target_type not in TARGET_TYPES:
        return _fail("target_type 不支持：%s（可选：%s）" % (req.target_type, " / ".join(TARGET_TYPES)))
    return {"success": True, "data": find_evidence(req.matter, req.target_type, req.target_id), "error": None}


@app.post("/api/evidence/index", response_model=AnalyzeResponse)
def evidence_index(req: EvidenceIndexRequest):
    """一次性返回所有条目的依据（前端可预取，用于给每条要求挂「查看依据」）。"""
    if not isinstance(req.matter, dict) or not req.matter:
        return _fail("请提供已解析结果（matter）")
    items = build_evidence_index(req.matter)
    return {
        "success": True,
        "data": {"items": items, "total": len(items),
                 "suggestion_count": sum(1 for i in items if i["is_suggestion"])},
        "error": None,
    }


# ==================== 统一错误兜底 ====================

@app.exception_handler(RequestValidationError)
async def on_validation_error(request: Request, exc: RequestValidationError):
    """请求体不是合法 JSON / 字段类型不对时，也返回统一契约，而不是 FastAPI 默认的 422。"""
    logger.warning("请求体校验失败：%s", exc.errors())
    return JSONResponse(status_code=200, content=_fail(
        '请求体格式错误：请检查字段与类型（JSON: text / matter，multipart: image）'))


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