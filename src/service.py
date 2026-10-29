# src/service.py
import copy
import logging
import json
import math
import uuid
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Set, Optional, Union
from notification_extractor import (
    LLMClient,
    MatterExtractor,
    DocumentChunk,
    extract_pdf_pages_and_text,
    chunk_document_text,
    chunk_document_pages,
    enforce_mode,
    enforce_enabled_sections,
    normalize_step_orders,
    TZ,
)
from prompt import (
    SYSTEM_PROMPT,
    QA_PROMPT,
    UPDATE_PROMPT,
    IMAGE_CHECK_RULES,
    RAG_QA_PROMPT,
    COMPARE_PROMPT,
    DATE_TOOL_SYSTEM_PROMPT,
)

logger = logging.getLogger(__name__)
_extractor = None


def _get_extractor() -> MatterExtractor:
    global _extractor
    if _extractor is None:
        llm = LLMClient()
        _extractor = MatterExtractor(llm, SYSTEM_PROMPT)
        logger.info("MatterExtractor 初始化完成")
    return _extractor


def _apply_mode_guards(data: dict) -> dict:
    """在服务层补 warning/日期/来源后，再按 mode 做一次字段互斥裁剪。

    MatterExtractor.process 内部已经裁剪过一次，但 service 后续会追加
    warning_list、confirmation_needed 等字段；如果不再裁一次，simple 模式
    会重新出现 warning_list 等禁止字段。
    """
    if not isinstance(data, dict):
        return data
    data = enforce_mode(data)
    data = enforce_enabled_sections(data)
    data = normalize_step_orders(data)
    return data


def _fix_todo_actions(data: dict):
    """统一的待办补齐引擎：为空的 action 通过关联字段兜底"""
    for todo in data.get("todo_list", []):
        if not todo.get("action") or not str(todo.get("action")).strip():
            # 1. 用 step_id 找
            if todo.get("step_id"):
                step_ref = next((s for s in data.get("step_list", []) if s.get("step_id") == todo["step_id"]), None)
                if step_ref and step_ref.get("title"):
                    todo["action"] = f"完成：{step_ref.get('title')}"

            # 2. 用 material_id 找
            if not todo.get("action") or not str(todo.get("action")).strip():
                if todo.get("material_id"):
                    mat_ref = next((m for m in data.get("materials", []) if m.get("material_id") == todo["material_id"]), None)
                    if mat_ref and mat_ref.get("material_name"):
                        todo["action"] = f"准备：{mat_ref.get('material_name')}"

            # 3. 用 source_ref.quote 兜底
            if not todo.get("action") or not str(todo.get("action")).strip():
                quote = todo.get("source_ref", {}).get("quote", "")
                if quote:
                    todo["action"] = f"完成：{quote[:10]}..."
                else:
                    todo["action"] = "待确认的操作项"


def _fix_step_titles(data: dict):
    """步骤标题兜底：title 为空时从 source_ref.quote 提炼动宾短语"""
    for step in data.get("step_list", []):
        title = (step.get("title") or "").strip()
        if title:
            continue
        quote = step.get("source_ref", {}).get("quote", "")
        if quote:
            # 抓取中文字符段（含字母数字），限 2~12 字
            m = re.search(r"[\u4e00-\u9fa5A-Za-z0-9]{2,12}", quote)
            step["title"] = m.group(0) if m else quote[:10]
        else:
            step["title"] = "待确认步骤"


def _merge_ai_output(original: dict, ai: dict) -> dict:
    """
    以 original 的稳定结构（ID、顺序、source_ref 等）为基准，
    只吸收 ai 对 status 相关字段的修改。
    即使大模型漏返回某个列表 / 改动了结构，也不会破坏原数据。
    """
    merged = json.loads(json.dumps(original))  # 深拷贝，保留原结构

    # 材料
    original_mats = {m.get("material_id"): m for m in merged.get("materials", []) if m.get("material_id")}
    for m in ai.get("materials", []):
        mid = m.get("material_id")
        if mid and mid in original_mats:
            tgt = original_mats[mid]
            if "status" in m:
                tgt["status"] = m["status"]
            if "status_desc" in m:
                tgt["status_desc"] = m["status_desc"]

    # 步骤
    original_steps = {s.get("step_id"): s for s in merged.get("step_list", []) if s.get("step_id")}
    for s in ai.get("step_list", []):
        sid = s.get("step_id")
        if sid and sid in original_steps:
            tgt = original_steps[sid]
            if "status" in s:
                tgt["status"] = s["status"]
            if "status_desc" in s:
                tgt["status_desc"] = s["status_desc"]

    # 待办
    original_todos = {t.get("todo_id"): t for t in merged.get("todo_list", []) if t.get("todo_id")}
    for t in ai.get("todo_list", []):
        tid = t.get("todo_id")
        if tid and tid in original_todos:
            tgt = original_todos[tid]
            if "status" in t:
                tgt["status"] = t["status"]
            if "status_desc" in t:
                tgt["status_desc"] = t["status_desc"]

    # 其他顶层可能被 AI 更新的字段
    for key in ("warning_list", "missing_items"):
        if key in ai and ai.get(key) is not None:
            merged[key] = ai[key]

    return merged


def _material_status_map(data: dict) -> dict:
    return {m.get("material_id"): m for m in data.get("materials", []) if m.get("material_id")}


def _sequential_backfill(data: dict):
    """顺序回填：找到已完成的步骤，沿其前置依赖把材料一起置为 prepared。"""
    steps = data.get("step_list", [])
    step_by_id = {}
    for s in steps:
        if s.get("step_id"):
            step_by_id[s["step_id"]] = s

    # 依赖关系：step_id -> 前置 step_id 列表
    deps = {}
    for s in steps:
        sid = s.get("step_id")
        if not sid:
            continue
        d = []
        for dep in s.get("dependencies", []) or []:
            did = dep.get("step_id") if isinstance(dep, dict) else dep
            if did:
                d.append(did)
        deps[sid] = d

    def mark_material(sid: str):
        """把属于该步骤（material_id 数组引用）的材料置 prepared"""
        st = step_by_id.get(sid)
        if not st:
            return
        for mid_ref in st.get("materials", []) or []:
            mid = mid_ref.get("material_id") if isinstance(mid_ref, dict) else mid_ref
            if mid is None:
                continue
            for mat in data.get("materials", []):
                if mat.get("material_id") == mid and mat.get("status") != "prepared":
                    mat["status"] = "prepared"
                    mat["status_desc"] = "顺序链前置，已备好"

    # 已完成步骤集合
    completed_sids = {s.get("step_id") for s in steps if s.get("status") == "completed"}

    # 顺序链：沿已完成的步骤，把所有前置依赖步骤的材料一并置 prepared
    for sid in list(completed_sids):
        stack = [sid]
        while stack:
            cur = stack.pop()
            mark_material(cur)
            for pid in deps.get(cur, []):
                mark_material(pid)
                stack.append(pid)


def _code_level_fallback(data: dict):
    """代码层兜底：非交付的步骤/待办，若其依赖材料已全部准备，则置为 completed。"""
    # 材料名 -> 状态
    name_to_status = {}
    id_to_status = {}
    for m in data.get("materials", []):
        name = m.get("material_name")
        if name:
            name_to_status[name] = m.get("status", "pending")
        if m.get("material_id"):
            id_to_status[m["material_id"]] = m.get("status", "pending")

    delivery_keywords = ["提交", "发送", "上交", "上传", "打包", "初审", "审核", "盖章"]

    def is_delivery(text: str) -> bool:
        return any(k in text for k in delivery_keywords)

    # ---------- 待办联动（按材料名匹配） ----------
    for todo in data.get("todo_list", []):
        action = str(todo.get("action", ""))
        if is_delivery(action):
            continue
        # 优先按 material_id，其次按材料名出现在 action 中
        mid = todo.get("material_id")
        if mid and mid in id_to_status and id_to_status[mid] == "prepared":
            todo["status"] = "completed"
            continue
        hit = [n for n in name_to_status if n and n in action]
        if hit and all(name_to_status[n] == "prepared" for n in hit):
            todo["status"] = "completed"

    # ---------- 步骤联动 ----------
    for step in data.get("step_list", []):
        title = str(step.get("title", ""))
        if is_delivery(title):
            continue
        step_mats = step.get("materials", []) or []
        if step_mats:
            # 按 ID 判断，任何给定材料的 ID 状态不是 prepared 就不绿
            all_prepared = True
            for mid_ref in step_mats:
                mid = mid_ref.get("material_id") if isinstance(mid_ref, dict) else mid_ref
                if id_to_status.get(mid) != "prepared":
                    all_prepared = False
                    break
            if all_prepared:
                step["status"] = "completed"
        else:
            hit = [n for n in name_to_status if n and n in title]
            if hit and all(name_to_status[n] == "prepared" for n in hit):
                step["status"] = "completed"


def _rebuild_missing_items(data: dict):
    """重建缺项清单：只保留必填且未准备好的材料"""
    missing_items = []
    for mat in data.get("materials", []):
        if mat.get("material_type") == "required" and mat.get("status") != "prepared":
            missing_items.append({
                "material_id": mat.get("material_id"),
                "material_name": mat.get("material_name"),
                "reason": "必填材料，尚未准备",
            })
    data["missing_items"] = missing_items


def analyze_notification(notification_text: str) -> Dict[str, Any]:
    if not notification_text or not notification_text.strip():
        return {"success": False, "data": None, "error": "通知内容不能为空"}

    try:
        extractor = _get_extractor()
        matter, err = extractor.process(notification_text)
        if err:
            return {"success": False, "data": None, "error": err}

        data = matter.to_dict()

        if not data.get("warning_list"):
            data["warning_list"] = []
        if not data.get("deadline") or not data["deadline"].get("due_at"):
            data["warning_list"].append({
                "warning_id": f"warn_{uuid.uuid4().hex[:6]}",
                "warning_type": "missing_information",
                "severity": "high",
                "message": "通知原文未提及明确的截止时间，请手动确认并设置",
            })

        _fix_todo_actions(data)
        _fix_step_titles(data)
        _rebuild_missing_items(data)
        data = _apply_mode_guards(data)

        return {"success": True, "data": data, "error": None}
    except Exception as e:
        logger.exception("AI 解析异常")
        return {"success": False, "data": None, "error": f"解析异常: {str(e)}"}

def analyze_notification_from_image(image_data_uri: str) -> Dict[str, Any]:
    """新增：截图分析入口（多模态）。返回结构与 analyze_notification 一致，附 confirmation_needed。
    image_data_uri: 形如 data:image/png;base64,.... 的图片 data URI
    """

    if not image_data_uri or not image_data_uri.strip():
        return {"success": False, "data": None, "error": "图片不能为空"}

    try:
        extractor = _get_extractor()
        llm = extractor.llm
        sys_raw = SYSTEM_PROMPT  # 复用你的系统提示词
        sys_total = sys_raw + IMAGE_CHECK_RULES  # 只新增，不改原有

        from openai import OpenAI
        client = OpenAI(api_key=llm.api_key, base_url=llm.base_url, timeout=llm.timeout)

        response = client.chat.completions.create(
            model=llm.model,
            messages=[
                {"role": "system", "content": sys_total},
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url",
                         "image_url": {"url": image_data_uri, "detail": "high"}},
                    ],
                },
            ],
            temperature=0,
            response_format={"type": "json_object"},
            stream=False,
        )
        content = response.choices[0].message.content
        data = json.loads(content)
        data["deadline"] = _normalize_deadline_value(data.get("deadline"))

        # ---------- 后端兜底：关键字段缺失时补一条 confirmation ----------
        confirmations = data.get("confirmation_needed") or []
        if not data.get("deadline") or not data.get("deadline", {}).get("due_at"):
            confirmations.append("未识别到明确的截止时间，请确认")

        # ---------- 复用原有补齐函数（新增，不删） ----------
        if not data.get("warning_list"):
            data["warning_list"] = []
        if not data.get("deadline") or not data["deadline"].get("due_at"):
            data["warning_list"].append({
                "warning_id": f"warn_{uuid.uuid4().hex[:6]}",
                "warning_type": "missing_information",
                "severity": "high",
                "message": "通知原文未提及明确的截止时间，请手动确认并设置",
            })
        _fix_todo_actions(data)
        _fix_step_titles(data)
        _rebuild_missing_items(data)
        data = _apply_mode_guards(data)

        data["confirmation_needed"] = confirmations
        return {"success": True, "data": data, "error": None, "source": "image"}

    except Exception as e:
        logger.exception("图片分析异常")
        return {"success": False, "data": None, "error": f"图片解析失败: {str(e)}"}


# ==================== 10.25：文字型 PDF 解析入口 ====================

def extract_text_from_pdf(pdf_source: Any, filename: str = "document.pdf") -> Dict[str, Any]:
    """
    10.25 任务：从 PDF 提取文字
    支持传入文件路径、bytes 或 file-like 流对象。
    """
    return extract_pdf_pages_and_text(pdf_source, filename=filename)


def analyze_notification_from_pdf(
    pdf_source: Any,
    filename: str = "document.pdf",
    extracted_text: Optional[str] = None
) -> Dict[str, Any]:
    """
    10.25 任务：接收文字型 PDF（或已提取出的文字），接入已有分析流程
    pdf_source: 可以是本地文件路径、bytes、file 对象，或已提取的纯文本
    extracted_text: 可选，如调用方已提取出文字则优先使用
    """
    pages = []
    total_pages = 0
    is_scanned = False
    doc_name = filename

    # 1. 提取文字：优先使用外部已提取的文字，否则从 PDF 提取
    if extracted_text and extracted_text.strip():
        text_to_analyze = extracted_text.strip()
    elif isinstance(pdf_source, str) and not (pdf_source.lower().endswith(".pdf") and os.path.exists(pdf_source)):
        # 直接传入了文本字符串
        text_to_analyze = pdf_source.strip()
    else:
        extract_res = extract_text_from_pdf(pdf_source, filename=filename)
        if not extract_res["success"]:
            return {"success": False, "data": None, "error": extract_res["error"]}

        text_to_analyze = extract_res.get("text", "")
        pages = extract_res.get("pages", [])
        total_pages = extract_res.get("total_pages", 0)
        is_scanned = extract_res.get("is_scanned", False)
        doc_name = extract_res.get("doc_name", filename)

    if not text_to_analyze or not text_to_analyze.strip():
        return {
            "success": False,
            "data": None,
            "error": "未能从 PDF 中提取到有效文字内容；若为扫描版或纯图片 PDF，请改用截图识别功能"
        }

    # 2. 接入已有分析流程
    analysis_res = analyze_notification(text_to_analyze)
    if not analysis_res.get("success"):
        return analysis_res

    data = analysis_res["data"]

    # 3. 补充 PDF 来源元数据与扫描件预警
    if is_scanned:
        data.setdefault("warning_list", []).append({
            "warning_id": f"warn_{uuid.uuid4().hex[:6]}",
            "warning_type": "scanned_pdf_risk",
            "severity": "medium",
            "message": "检测到该 PDF 提取出的文字较少，疑似图片扫描件，建议核对原文或改用截图识别",
        })

    # 为所有 source_ref 和 sources 注入来源文件名和页码
    doc_id = f"doc_{uuid.uuid4().hex[:6]}"
    for s in data.get("sources", []):
        if not s.get("doc_id"):
            s["doc_id"] = doc_id
        if not s.get("doc_version"):
            s["doc_version"] = doc_name

    data = _apply_mode_guards(data)
    return {
        "success": True,
        "data": data,
        "error": None,
        "source": "pdf",
        "doc_name": doc_name,
        "total_pages": total_pages,
        "pages": pages,
        "extracted_text": text_to_analyze,
    }


def _call_chat(
    llm,
    prompt_text: str,
    system_content: str,
    use_stream: bool = False,
    json_mode: bool = False,
) -> str:
    """统一的 LLM 调用，兼容部分 endpoint 不支持 response_format 的情况。"""
    from openai import OpenAI
    client = OpenAI(api_key=llm.api_key, base_url=llm.base_url, timeout=llm.timeout)
    msgs = [
        {"role": "system", "content": system_content},
        {"role": "user", "content": prompt_text},
    ]
    kwargs = {
        "model": llm.model,
        "messages": msgs,
        "temperature": 0,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    try:
        if use_stream:
            resp = client.chat.completions.create(stream=True, **kwargs)
            return "".join(
                c.choices[0].delta.content
                for c in resp if c.choices and c.choices[0].delta and c.choices[0].delta.content
            )
        else:
            resp = client.chat.completions.create(stream=False, **kwargs)
            return resp.choices[0].message.content
    except Exception as e:
        # 若第三方 endpoint 不支持 response_format 或报错要求含 json，降级去掉重试
        if "response_format" in str(e) or "json" in str(e).lower() or isinstance(e, TypeError):
            kwargs.pop("response_format", None)
            if use_stream:
                resp = client.chat.completions.create(stream=True, **kwargs)
                return "".join(
                    c.choices[0].delta.content
                    for c in resp if c.choices and c.choices[0].delta and c.choices[0].delta.content
                )
            else:
                resp = client.chat.completions.create(stream=False, **kwargs)
                return resp.choices[0].message.content
        raise


def update_matter_status_with_ai(matter_data: dict, raw_text: str, user_action: str) -> Dict[str, Any]:
    try:
        extractor = _get_extractor()
        llm = extractor.llm

        matter_json_str = json.dumps(matter_data, ensure_ascii=False)
        prompt = (
            UPDATE_PROMPT.replace("{{MATTER_JSON}}", matter_json_str)
            .replace("{{RAW_TEXT}}", raw_text)
            .replace("{{USER_ACTION}}", user_action)
        )

        content = _call_chat(llm, prompt, "你是一个严谨的状态更新引擎，只输出完整的 JSON。", use_stream=False, json_mode=True)
        ai_data = json.loads(content)

        # 以旧结构为基准合并，AI 漏字段也不丢数据
        updated_data = _merge_ai_output(matter_data, ai_data)

        # 兜底补齐空 action / 空 title
        _fix_todo_actions(updated_data)
        _fix_step_titles(updated_data)

        # 代码层安全兜底（只做"补勾"，不误勾交付类）
        _code_level_fallback(updated_data)

        # 顺序链回填：已完成的步骤沿依赖把前置材料置 prepared
        _sequential_backfill(updated_data)

        # 重建缺项清单
        _rebuild_missing_items(updated_data)
        updated_data = _apply_mode_guards(updated_data)

        return {"success": True, "data": updated_data, "error": None}

    except Exception as e:
        logger.exception("状态更新异常")
        return {"success": False, "data": matter_data, "error": f"状态更新失败: {str(e)}"}


# ==================== 10.26：片段划分与多材料检索功能 ====================

def split_into_chunks(
    text: str,
    doc_name: str = "通知原文",
    doc_id: str = "doc_1",
    page: Optional[int] = None,
    chunk_size: int = 250,
    overlap: int = 40,
) -> List[Dict[str, Any]]:
    """
    10.26 任务：将通知内容分成便于查找的片段，每个片段带编号与来源
    """
    chunks = chunk_document_text(
        text=text,
        doc_name=doc_name,
        doc_id=doc_id,
        page=page,
        chunk_size=chunk_size,
        overlap=overlap,
    )
    return [c.to_dict() for c in chunks]


class NotificationRetriever:
    """
    10.26 检索功能：给文件和片段编号，从几份材料中找出相关原文。
    支持多文档混合检索，打分结合词频覆盖度、连续字串匹配度与实体关键词加权。
    """
    def __init__(self, chunk_size: int = 250, overlap: int = 40):
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.chunks: List[DocumentChunk] = []

    def clear(self):
        self.chunks.clear()

    def add_document(
        self,
        text_or_pages: Union[str, List[Dict[str, Any]]],
        doc_name: str = "通知材料",
        doc_id: Optional[str] = None,
    ):
        doc_id = doc_id or f"doc_{len(self.chunks) + 1}"
        if isinstance(text_or_pages, list):
            new_chunks = chunk_document_pages(
                pages=text_or_pages,
                doc_name=doc_name,
                doc_id=doc_id,
                chunk_size=self.chunk_size,
                overlap=self.overlap,
            )
        else:
            new_chunks = chunk_document_text(
                text=str(text_or_pages),
                doc_name=doc_name,
                doc_id=doc_id,
                page=None,
                chunk_size=self.chunk_size,
                overlap=self.overlap,
            )
        self.chunks.extend(new_chunks)

    def add_documents(self, docs: List[Union[str, Dict[str, Any]]]):
        """
        支持传入多份材料：
        docs 元素可以是:
        - str: 纯文本
        - dict: {"text": "...", "doc_name": "...", "doc_id": "...", "pages": [...]}
        """
        for i, d in enumerate(docs):
            if isinstance(d, str):
                self.add_document(d, doc_name=f"材料_{i+1}", doc_id=f"doc_{i+1}")
            elif isinstance(d, dict):
                d_name = d.get("doc_name") or d.get("filename") or f"材料_{i+1}"
                d_id = d.get("doc_id") or f"doc_{i+1}"
                if d.get("pages"):
                    self.add_document(d["pages"], doc_name=d_name, doc_id=d_id)
                elif d.get("text"):
                    self.add_document(d["text"], doc_name=d_name, doc_id=d_id)

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        """中英混合分词（词组、中文字符与 2-gram）"""
        if not text:
            return []
        text = text.lower()
        words = re.findall(r"[a-z0-9_]+", text)
        chinese_chars = re.findall(r"[\u4e00-\u9fa5]", text)
        stop_words = set("的一是在有了和与及或这那每个到于把将按向以等从为被上中下前后的呢吧啊吗呀什么怎样如何哪些请需")
        filtered_chars = [c for c in chinese_chars if c not in stop_words]
        bigrams = [filtered_chars[i] + filtered_chars[i+1] for i in range(len(filtered_chars) - 1)]
        return words + filtered_chars + bigrams

    def search(
        self,
        query: str,
        top_k: int = 3,
        score_threshold: float = 0.10,
    ) -> List[Dict[str, Any]]:
        """
        从所有切分片段中检索与 query 最相关的 Top K 个片段
        """
        query_terms = self._tokenize(query)
        if not query_terms or not self.chunks:
            return []

        clean_q = re.sub(r"[^\w\u4e00-\u9fa5]", "", query.lower())
        scored_results = []

        for chunk in self.chunks:
            content = chunk.content
            c_lower = content.lower()
            matched_terms = [t for t in set(query_terms) if t in c_lower]
            if not matched_terms:
                continue

            # 词项加权（长度>1 的词项如双字词赋予更高权重）
            term_weight = sum(2.0 if len(t) > 1 else 0.8 for t in matched_terms)
            coverage = len(matched_terms) / max(1, len(set(query_terms)))

            # 连续字串匹配（LCS 相似度加分）
            clean_c = re.sub(r"[^\w\u4e00-\u9fa5]", "", c_lower)
            lcs_bonus = 0.0
            for span_len in (5, 4, 3, 2):
                found = False
                for start in range(len(clean_q) - span_len + 1):
                    sub = clean_q[start:start+span_len]
                    if sub in clean_c:
                        lcs_bonus += 0.35 * (span_len / 2.0)
                        found = True
                        break
                if found:
                    break

            final_score = round(min(1.0, 0.45 * coverage + 0.30 * (term_weight / (len(query_terms) + 2)) + 0.25 * min(1.0, lcs_bonus)), 4)

            if final_score >= score_threshold:
                c_dict = chunk.to_dict()
                c_dict["score"] = final_score
                c_dict["matched_terms"] = matched_terms[:6]
                scored_results.append(c_dict)

        scored_results.sort(key=lambda x: x["score"], reverse=True)
        return scored_results[:top_k]


def search_relevant_chunks(
    query: str,
    docs: Union[str, List[Union[str, Dict[str, Any]]]],
    top_k: int = 3,
    score_threshold: float = 0.10,
) -> List[Dict[str, Any]]:
    """
    10.26 快捷检索函数：从几份材料或单篇通知中找出相关原文片段
    """
    retriever = NotificationRetriever()
    if isinstance(docs, str):
        retriever.add_document(docs, doc_name="通知原文", doc_id="doc_1")
    elif isinstance(docs, list):
        retriever.add_documents(docs)
    return retriever.search(query, top_k=top_k, score_threshold=score_threshold)


# ==================== 10.27：先查材料再回答 (RAG 问答) ====================

def ask_question_with_rag(
    question: str,
    docs: Union[str, List[Union[str, Dict[str, Any]]]],
    matter_json: Optional[dict] = None,
    top_k: int = 3,
) -> Dict[str, Any]:
    """
    10.27 任务：接通“先查材料，再回答”；无依据时提示未找到。
    最低交付物要求：能回答材料内问题，回答附出处；材料外问题不乱答。
    """
    if not question or not question.strip():
        return {
            "success": False,
            "answer": "问题不能为空",
            "found_evidence": False,
            "evidence_chunks": [],
            "error": "问题不能为空",
        }

    # 1. 先查材料：通过 10.26 检索器在材料库中检索相关片段
    relevant_chunks = search_relevant_chunks(question, docs, top_k=top_k, score_threshold=0.10)

    # 若检索不到任何相关片段，直接判定无依据，绝不瞎编
    if not relevant_chunks:
        return {
            "success": True,
            "answer": f"【未找到依据】现有材料中未提及与“{question}”相关的内容或要求。",
            "found_evidence": False,
            "evidence_chunks": [],
            "error": None,
        }

    # 2. 组装片段出处与原文内容
    chunk_blocks = []
    for i, c in enumerate(relevant_chunks, 1):
        page_info = f" (第 {c['page']} 页)" if c.get("page") else ""
        chunk_blocks.append(
            f"【材料片段 {i}】\n"
            f"来源文件：{c['doc_name']}{page_info}\n"
            f"片段编号：{c['chunk_id']}\n"
            f"原文内容：“{c['content']}”"
        )
    retrieved_text = "\n\n".join(chunk_blocks)

    # 3. 再回答：严格基于检索片段回答，并在回答中注明出处
    try:
        extractor = _get_extractor()
        llm = extractor.llm
        matter_str = json.dumps(matter_json, ensure_ascii=False) if matter_json else "{}"

        prompt = (
            RAG_QA_PROMPT
            .replace("{{RETRIEVED_CHUNKS}}", retrieved_text)
            .replace("{{MATTER_JSON}}", matter_str)
            .replace("{{USER_QUESTION}}", question)
        )

        answer = _call_chat(
            llm=llm,
            prompt_text=prompt,
            system_content="你是一个严谨的材料检索与文档问答助手。必须先查材料再回答，回答必须附出处，无依据时明确提示未找到。",
            use_stream=False,
            json_mode=False,
        )
        answer = answer.strip()

        # 若模型按 JSON 包装输出，自动提取为易读文本
        if answer.startswith("{") and answer.endswith("}"):
            try:
                parsed_ans = json.loads(answer)
                if "answer" in parsed_ans:
                    val = parsed_ans["answer"]
                    if isinstance(val, list):
                        answer = "\n".join(str(item) for item in val)
                    else:
                        answer = str(val)
            except Exception:
                pass

        # 检查是否为无依据判定
        no_evidence_keywords = ["未找到依据", "未提及", "未找到相关", "没有提到", "未能找到", "无相关"]
        found = not any(kw in answer for kw in no_evidence_keywords)

        return {
            "success": True,
            "answer": answer,
            "found_evidence": found,
            "evidence_chunks": relevant_chunks,
            "error": None,
        }
    except Exception as e:
        err_msg = str(e)
        logger.exception("RAG 问答异常: %s", err_msg)
        if "quota" in err_msg.lower() or "额度不足" in err_msg:
            fallback_answer = "【检索已定位到相关原文（API 额度不足未能调用总结）】：\n"
            for i, c in enumerate(relevant_chunks, 1):
                page_info = f" (第 {c['page']} 页)" if c.get("page") else ""
                fallback_answer += f"\n{i}. 【出处：{c['doc_name']} - {c['chunk_id']}{page_info}】\n原文依据：“{c['content']}”\n"
            return {
                "success": True,
                "answer": fallback_answer.strip(),
                "found_evidence": True,
                "evidence_chunks": relevant_chunks,
                "error": "API 额度不足（insufficient_user_quota），已展示本地检索原文",
            }
        return {
            "success": False,
            "answer": "问答处理异常，请稍后重试",
            "found_evidence": False,
            "evidence_chunks": relevant_chunks,
            "error": err_msg,
        }


def ask_question(
    matter_json: dict,
    raw_text: str,
    question: str,
    docs: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    通用问答入口：全面升级为“先查材料，再回答”的 RAG 机制。
    向后兼容原有的 (matter_json, raw_text, question) 调用，同时支持传入多材料 docs。
    """
    target_docs = docs if docs else raw_text
    return ask_question_with_rag(
        question=question,
        docs=target_docs,
        matter_json=matter_json,
        top_k=3,
    )


# ==================== 10.29：补充通知对比 + 变更联动待办 ====================

# 补充通知里出现这些词，说明它明确覆盖原通知；
# 没有这些词时，改期 / 删材料一律要求用户确认，避免“默默改掉”用户清单。
_AUTHORITATIVE_PATTERNS = (
    "以此为准", "以本通知为准", "以补充通知为准", "以最新通知为准",
    "原通知作废", "替代原通知", "取代原通知", "本通知为最终版本",
    "如有冲突，以本通知为准", "如有不一致，以本通知为准",
)

# 只有明确写了这些词，才允许直接删除原材料/步骤。
_CANCEL_PATTERNS = (
    "取消", "不再要求", "无需提交", "不需要提交", "不需要", "删除",
    "不再提交", "不再提供", "免交", "无需提供",
)

# “推荐意见改为安全承诺书”这类明确替换，才允许把旧材料视为被替换。
_REPLACEMENT_PATTERNS = ("改为", "替换为", "改成", "替代为", "换成")

_WEEKDAY_CN = ("周一", "周二", "周三", "周四", "周五", "周六", "周日")


def _parse_datetime(value: Any, default_tz=timezone(timedelta(hours=8))) -> Optional[datetime]:
    """把 ISO / 常见中文日期字符串解析为带时区的 datetime。"""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value).strip().replace("Z", "+00:00")
        text = text.replace("年", "-").replace("月", "-").replace("日", " ")
        text = re.sub(r"\s+", " ", text).strip()
        dt = None
        for fmt in (
            None, "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d",
            "%Y/%m/%d %H:%M:%S", "%Y/%m/%d %H:%M", "%Y/%m/%d",
        ):
            try:
                dt = datetime.fromisoformat(text) if fmt is None else datetime.strptime(text, fmt)
                break
            except (ValueError, TypeError):
                continue
        if dt is None:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=default_tz)
    return dt.astimezone(default_tz)


def _coerce_deadline_datetime(value: Any) -> Optional[datetime]:
    """把 ISO 或“11月2日 17:00”这类中文日期统一成带时区的 datetime。"""
    dt = _parse_datetime(value)
    if dt:
        return dt
    text = str(value or "").strip()
    match = re.search(
        r"(?:(\d{4})\s*年)?\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日"
        r"(?:\s*(\d{1,2})\s*[:：]\s*(\d{1,2}))?",
        text,
    )
    if not match:
        return None
    year = int(match.group(1) or datetime.now(TZ).year)
    month, day = int(match.group(2)), int(match.group(3))
    hour = int(match.group(4) or 23)
    minute = int(match.group(5) or 59)
    try:
        return datetime(year, month, day, hour, minute, tzinfo=TZ)
    except ValueError:
        return None


def _normalize_deadline_value(value: Any) -> Any:
    """图片模型常返回中文日期字符串；统一成 Matter 需要的 deadline 对象。"""
    if isinstance(value, dict):
        result = copy.deepcopy(value)
        due = _coerce_deadline_datetime(result.get("due_at"))
        if due:
            result["due_at"] = due.isoformat()
        return result
    if isinstance(value, str) and value.strip():
        due = _coerce_deadline_datetime(value)
        if due:
            return {"scope": "overall", "label": "截止时间", "due_at": due.isoformat()}
    return value


def _format_datetime(dt: Optional[datetime]) -> str:
    if not dt:
        return ""
    return dt.strftime("%Y-%m-%d %H:%M")


def _format_due(value: Any) -> str:
    return _format_datetime(_parse_datetime(value)) or str(value or "")


def _norm_name(name: Any) -> str:
    """材料/步骤名称归一化：去书名号、括号注解、标点和空白，便于跨通知匹配。"""
    text = str(name or "").strip()
    text = re.sub(r"[（(][^（）()]*[）)]", "", text)      # 去掉“（附件1）”这类注解
    text = re.sub(r"[《》【】\[\]（）()]", "", text)
    text = re.sub(r"[\s：:，,。；;、·•\-—_]+", "", text)
    return text.lower()


def _material_name(material: Dict[str, Any]) -> str:
    return str(
        material.get("material_name")
        or material.get("name")
        or material.get("title")
        or "未命名材料"
    )


def _material_key(material: Dict[str, Any]) -> str:
    key = _norm_name(_material_name(material))
    return key or str(material.get("material_id") or "")


def _step_key(step: Dict[str, Any]) -> str:
    key = _norm_name(step.get("title"))
    return key or str(step.get("step_id") or "")


def _index_by_key(items: List[Dict[str, Any]], key_func) -> Dict[str, Dict[str, Any]]:
    result: Dict[str, Dict[str, Any]] = {}
    for i, item in enumerate(items or []):
        if not isinstance(item, dict):
            continue
        key = key_func(item)
        if key in result:
            key = f"{key}#{i}"
        result[key] = item
    return result


def _has_any(text: str, patterns) -> bool:
    return any(p in (text or "") for p in patterns)


def _mentioned_in(name: Any, text: str) -> bool:
    """材料/步骤名是否在补充通知原文里被明确提到（归一化后匹配）。"""
    normalized_name = _norm_name(name)
    normalized_text = _norm_name(text)
    return bool(normalized_name and normalized_name in normalized_text)


def _requirements_from_matter(matter: Dict[str, Any]) -> List[str]:
    """把 Matter 压缩成前端好展示的“要求列表”。"""
    matter = matter or {}
    requirements: List[str] = []
    due = (matter.get("deadline") or {}).get("due_at")
    if due:
        requirements.append(f"截止时间：{_format_due(due)}")
    for material in matter.get("materials") or []:
        if isinstance(material, dict):
            requirements.append(f"材料：{_material_name(material)}")
    for step in matter.get("step_list") or []:
        if isinstance(step, dict) and step.get("title"):
            requirements.append(f"步骤：{step.get('title')}")
    for point in matter.get("key_points") or []:
        if isinstance(point, str) and point.strip():
            requirements.append(f"要点：{point.strip()}")
    return requirements


def _build_notice_diff(
    original_matter: Dict[str, Any],
    supplement_matter: Dict[str, Any],
    original_text: str = "",
    supplement_text: str = "",
) -> Dict[str, Any]:
    """代码层对比：稳定、可解释，作为 LLM 对比的兜底与校验基线。"""
    original_matter = original_matter or {}
    supplement_matter = supplement_matter or {}

    authoritative = _has_any(supplement_text, _AUTHORITATIVE_PATTERNS)
    cancel_explicit = _has_any(supplement_text, _CANCEL_PATTERNS)
    replacement_explicit = _has_any(supplement_text, _REPLACEMENT_PATTERNS)
    # “补充通知/补充说明”默认是增量，不是完整替代；只有明确写“原通知作废/替代”才算全量替换。
    is_supplement = (
        "补充" in (supplement_text or "")
        or "补充" in str((supplement_matter or {}).get("title") or "")
    ) and not any(p in (supplement_text or "") for p in ("原通知作废", "替代原通知", "取代原通知"))

    old_deadline = copy.deepcopy(original_matter.get("deadline") or {})
    new_deadline = copy.deepcopy(supplement_matter.get("deadline") or {})
    old_due = old_deadline.get("due_at")
    new_due = new_deadline.get("due_at")
    # 补充通知没提截止时间 ≠ 取消截止时间：只有两边都给了时间且不同，才算改期。
    deadline_changed = bool(old_due and new_due and _format_due(old_due) != _format_due(new_due))

    old_materials = [m for m in (original_matter.get("materials") or []) if isinstance(m, dict)]
    new_materials = [m for m in (supplement_matter.get("materials") or []) if isinstance(m, dict)]
    old_map = _index_by_key(old_materials, _material_key)
    new_map = _index_by_key(new_materials, _material_key)

    added_material_keys = [k for k in new_map if k not in old_map]
    removed_material_keys = [k for k in old_map if k not in new_map]
    changed_material_keys = [
        k for k in new_map
        if k in old_map and (new_map[k].get("material_type") or "") != (old_map[k].get("material_type") or "")
    ]

    old_steps = [s for s in (original_matter.get("step_list") or []) if isinstance(s, dict)]
    new_steps = [s for s in (supplement_matter.get("step_list") or []) if isinstance(s, dict)]
    old_step_map = _index_by_key(old_steps, _step_key)
    new_step_map = _index_by_key(new_steps, _step_key)
    added_step_keys = [k for k in new_step_map if k not in old_step_map]
    removed_step_keys = [k for k in old_step_map if k not in new_step_map]

    changes: List[Dict[str, Any]] = []
    confirmations: List[str] = []

    def add_change(type_: str, field: str, text: str, old=None, new=None):
        item = {"type": type_, "field": field, "text": text}
        if old not in (None, "", [], {}):
            item["old"] = old
        if new not in (None, "", [], {}):
            item["new"] = new
        changes.append(item)

    # 1) 截止时间
    if deadline_changed:
        old_text = _format_due(old_due) or "未提及"
        new_text = _format_due(new_due) or "未提及"
        add_change(
            "changed", "deadline",
            f"截止时间由 {old_text} 变更为 {new_text}",
            old=old_text, new=new_text,
        )
        if old_due and new_due and not authoritative:
            confirmations.append(
                f"补充通知未明确说明是否替代原截止时间（原：{old_text}，新：{new_text}），"
                f"请确认以哪个为准。"
            )
    elif new_due and not old_due:
        add_change("added", "deadline", f"新增截止时间：{_format_due(new_due)}", new=_format_due(new_due))
    elif old_due and not new_due:
        add_change(
            "info", "deadline",
            f"补充通知未提及截止时间，保留原截止时间 {_format_due(old_due)}",
            old=_format_due(old_due),
        )

    # 2) 材料
    omitted_material_keys = [k for k in old_map if k not in new_map]
    if old_materials and not new_materials:
        # 补充通知可能只改时间，没有重复列材料；不能把“没重复”当成“全取消”。
        add_change("info", "material", "补充通知未重新列材料，保留原材料清单")
        removed_material_keys = []
    elif is_supplement and not cancel_explicit and not replacement_explicit:
        # 补充通知默认是增量：没重复提到的原材料继续适用，不能误报“删除”。
        removed_material_keys = []
        if omitted_material_keys:
            names = "、".join(_material_name(old_map[k]) for k in omitted_material_keys[:5])
            add_change("info", "material", f"补充通知未提及以下原材料，按继续适用处理：{names}")
    elif cancel_explicit or replacement_explicit:
        # 只有原文明确提到该材料，才把它视为取消/替换；避免“改一个材料”误删其他材料。
        removed_material_keys = [
            k for k in omitted_material_keys
            if _mentioned_in(_material_name(old_map[k]), supplement_text)
        ]
    else:
        removed_material_keys = omitted_material_keys
    for key in added_material_keys:
        material = new_map[key]
        add_change("added", "material", f"新增材料：{_material_name(material)}", new=_material_name(material))
    for key in removed_material_keys:
        material = old_map[key]
        add_change("removed", "material", f"不再出现材料：{_material_name(material)}", old=_material_name(material))
        if not cancel_explicit:
            confirmations.append(
                f"补充通知未明确说明是否取消材料《{_material_name(material)}》，"
                f"请确认是否还需要提交。"
            )
    for key in changed_material_keys:
        old_type = old_map[key].get("material_type") or "unspecified"
        new_type = new_map[key].get("material_type") or "unspecified"
        add_change(
            "changed", "material",
            f"材料《{_material_name(new_map[key])}》类型由 {old_type} 变为 {new_type}",
            old=old_type, new=new_type,
        )

    # 3) 步骤
    omitted_step_keys = [k for k in old_step_map if k not in new_step_map]
    if old_steps and not new_steps:
        add_change("info", "step", "补充通知未重新列步骤，保留原步骤")
        removed_step_keys = []
    elif is_supplement and not cancel_explicit and not replacement_explicit:
        removed_step_keys = []
        if omitted_step_keys:
            titles = "、".join(str(old_step_map[k].get("title") or "") for k in omitted_step_keys[:5])
            add_change("info", "step", f"补充通知未提及以下原步骤，按继续适用处理：{titles}")
    elif cancel_explicit or replacement_explicit:
        removed_step_keys = [
            k for k in omitted_step_keys
            if _mentioned_in(old_step_map[k].get("title"), supplement_text)
        ]
    else:
        removed_step_keys = omitted_step_keys
    for key in added_step_keys:
        step = new_step_map[key]
        add_change("added", "step", f"新增步骤：{step.get('title')}", new=step.get("title"))
    for key in removed_step_keys:
        step = old_step_map[key]
        add_change("removed", "step", f"删除步骤：{step.get('title')}", old=step.get("title"))
        if not cancel_explicit:
            confirmations.append(
                f"补充通知未明确说明是否取消步骤「{step.get('title')}」，请确认。"
            )

    # 4) 把变化映射到待办
    removed_material_ids = {
        str(old_map[k].get("material_id"))
        for k in removed_material_keys if old_map[k].get("material_id")
    }
    removed_material_names = [_material_name(old_map[k]) for k in removed_material_keys]
    removed_name_norms = {_norm_name(n) for n in removed_material_names}

    affected_todos: List[str] = []
    affected_details: List[Dict[str, Any]] = []
    preview_todos: List[Dict[str, Any]] = []
    used_todo_ids = {
        str(t.get("todo_id")) for t in (original_matter.get("todo_list") or []) if isinstance(t, dict)
    }

    for todo in (original_matter.get("todo_list") or []):
        if not isinstance(todo, dict):
            continue
        item = copy.deepcopy(todo)
        action = str(item.get("action") or "")
        mid = str(item.get("material_id") or "")
        hit_removed = bool(mid and mid in removed_material_ids) or any(
            n and n in _norm_name(action) for n in removed_name_norms
        )

        if hit_removed:
            reason = "补充通知中不再要求该材料/步骤"
            detail = {
                "todo_id": item.get("todo_id"),
                "action": action,
                "change": "remove",
                "reason": reason,
            }
            affected_details.append(detail)
            if cancel_explicit:
                affected_todos.append(f"删除待办：{action}（{reason}）")
                continue     # 明确取消，预览里直接不出现
            item["change"] = "remove"
            item["needs_confirmation"] = True
            affected_todos.append(f"需确认是否删除待办：{action}")
            preview_todos.append(item)
            continue

        if deadline_changed and new_due:
            item["due_at"] = new_due
            item["change"] = "update_deadline"
            detail = {
                "todo_id": item.get("todo_id"),
                "action": action,
                "change": "update_deadline",
                "old_due_at": old_due,
                "new_due_at": new_due,
            }
            affected_details.append(detail)
            affected_todos.append(
                f"更新截止：{action} → {_format_due(new_due)}"
            )
        else:
            item["change"] = "keep"
        preview_todos.append(item)

    # 5) 新增材料 → 自动生成待办
    for i, key in enumerate(added_material_keys, 1):
        material = new_map[key]
        name = _material_name(material)
        todo_id = f"todo_new_{i}"
        while todo_id in used_todo_ids:
            todo_id = f"{todo_id}_new"
        used_todo_ids.add(todo_id)
        action = f"准备{name}"
        new_todo = {
            "todo_id": todo_id,
            "action": action,
            "status": "pending",
            "material_id": material.get("material_id") or f"mat_new_{i}",
            "source_ref": material.get("source_ref") or {},
            "change": "add",
        }
        if deadline_changed and new_due:
            new_todo["due_at"] = new_due
        preview_todos.append(new_todo)
        affected_todos.append(f"新增待办：{action}")
        affected_details.append({
            "todo_id": todo_id,
            "action": action,
            "change": "add",
            "material_name": name,
        })

    # 去重但保持顺序
    confirmations = list(dict.fromkeys([c for c in confirmations if c]))
    affected_todos = list(dict.fromkeys(affected_todos))

    return {
        "old_requirements": _requirements_from_matter(original_matter),
        "new_requirements": _requirements_from_matter(supplement_matter),
        "changes": changes,
        "confirmation_needed": confirmations,
        "reasoning": (
            "补充通知明确说明以此为准，冲突按补充通知处理。"
            if authoritative else
            "补充通知未明确说明以此为准，涉及改期/删材料时保留用户确认。"
        ),
        "authoritative": authoritative,
        "old_deadline": old_deadline,
        "new_deadline": new_deadline,
        "added_materials": [new_map[k] for k in added_material_keys],
        "removed_materials": [old_map[k] for k in removed_material_keys],
        "changed_materials": [
            {"old": old_map[k], "new": new_map[k]} for k in changed_material_keys
        ],
        "added_steps": [new_step_map[k] for k in added_step_keys],
        "removed_steps": [old_step_map[k] for k in removed_step_keys],
        "affected_todos": affected_todos,
        "affected_todo_details": affected_details,
        "preview_todo_list": preview_todos,
        "requires_confirmation": bool(confirmations),
    }


def _compare_with_llm(
    original_text: str,
    supplement_text: str,
    rule_diff: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """有 Key 时用 LLM 补充语义差异；失败返回 None，由规则差异兜底。"""
    try:
        extractor = _get_extractor()
        llm = extractor.llm
        if not getattr(llm, "api_key", ""):
            return None
        prompt = (
            COMPARE_PROMPT
            .replace("{{ORIGINAL_TEXT}}", original_text or "")
            .replace("{{SUPPLEMENT_TEXT}}", supplement_text or "")
            .replace("{{RULE_DIFF}}", json.dumps(rule_diff, ensure_ascii=False))
        )
        content = _call_chat(
            llm=llm,
            prompt_text=prompt,
            system_content="你是严谨的补充通知对比引擎，只输出 JSON，禁止编造原文没有的信息。",
            use_stream=False,
            json_mode=True,
        )
        content = (content or "").strip()
        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?|```$", "", content, flags=re.MULTILINE).strip()
        parsed = json.loads(content)
        return parsed if isinstance(parsed, dict) else None
    except Exception as e:
        logger.warning("LLM 补充通知对比失败，使用规则差异兜底：%s", e)
        return None


def compare_notifications(
    original_text: str,
    supplement_text: str,
    original_matter: Optional[Dict[str, Any]] = None,
    supplement_matter: Optional[Dict[str, Any]] = None,
    use_llm: bool = True,
) -> Dict[str, Any]:
    """
    10.29 任务：比较原通知与补充通知，找出新增材料、改期或冲突，
    并把变化关联到用户已有的待办（affected_todos）。
    """
    if not original_matter:
        original_res = analyze_notification(original_text)
        if not original_res.get("success"):
            return {"success": False, "data": None, "error": f"原通知解析失败：{original_res.get('error')}"}
        original_matter = original_res["data"]
    if not supplement_matter:
        supplement_res = analyze_notification(supplement_text)
        if not supplement_res.get("success"):
            return {"success": False, "data": None, "error": f"补充通知解析失败：{supplement_res.get('error')}"}
        supplement_matter = supplement_res["data"]

    diff = _build_notice_diff(original_matter, supplement_matter, original_text, supplement_text)
    compare_mode = "rules"

    if use_llm:
        ai_diff = _compare_with_llm(original_text, supplement_text, diff)
        if isinstance(ai_diff, dict):
            seen = {(c.get("type"), c.get("text")) for c in diff["changes"] if isinstance(c, dict)}
            for change in ai_diff.get("changes") or []:
                if not isinstance(change, dict) or not change.get("text"):
                    continue
                key = (change.get("type"), change.get("text"))
                if key not in seen:
                    change["source"] = "llm"
                    diff["changes"].append(change)
                    seen.add(key)
            for item in ai_diff.get("confirmation_needed") or []:
                if item and str(item) not in diff["confirmation_needed"]:
                    diff["confirmation_needed"].append(str(item))
            if ai_diff.get("reasoning"):
                diff["reasoning"] = ai_diff["reasoning"]
            diff["requires_confirmation"] = bool(diff["confirmation_needed"])
            compare_mode = "llm+rules"

    return {
        "success": True,
        "data": {
            "original_matter": original_matter,
            "supplement_matter": supplement_matter,
            "diff": diff,
            "preview_todo_list": diff["preview_todo_list"],
            "requires_confirmation": diff["requires_confirmation"],
            "confirmation_needed": diff["confirmation_needed"],
            "compare_mode": compare_mode,
        },
        "error": None,
    }


def apply_notice_changes(
    original_matter: Dict[str, Any],
    diff: Dict[str, Any],
    confirmed: bool = False,
) -> Dict[str, Any]:
    """
    10.29 任务：用户确认后才更新清单；未确认时只返回预览与待确认项，
    并把修改前的 deadline / materials / todos 存进 change_log，支持回看。
    """
    diff = diff or {}
    requires_confirmation = bool(diff.get("requires_confirmation"))
    # 不管有没有歧义，保存前都必须由用户点一次“确认更新”；
    # requires_confirmation 只表示“还需要额外确认哪份有效”。
    if not confirmed:
        return {
            "success": True,
            "data": {
                "applied": False,
                "requires_user_confirmation": True,
                "requires_confirmation": requires_confirmation,
                "confirmation_needed": diff.get("confirmation_needed") or [],
                "diff": diff,
                "todo_list": diff.get("preview_todo_list") or [],
                "matter": copy.deepcopy(original_matter),
            },
            "error": None,
        }

    updated = copy.deepcopy(original_matter or {})
    updated_at = datetime.now(TZ).isoformat()
    before = {
        "deadline": copy.deepcopy(updated.get("deadline")),
        "materials": copy.deepcopy(updated.get("materials") or []),
        "step_list": copy.deepcopy(updated.get("step_list") or []),
        "todo_list": copy.deepcopy(updated.get("todo_list") or []),
    }

    # 1) 截止时间
    new_deadline = diff.get("new_deadline") or {}
    if new_deadline.get("due_at"):
        updated["deadline"] = copy.deepcopy(new_deadline)

    # 2) 材料
    removed_keys = {_material_key(m) for m in diff.get("removed_materials") or [] if isinstance(m, dict)}
    removed_ids = {str(m.get("material_id")) for m in diff.get("removed_materials") or [] if m.get("material_id")}
    materials = [
        m for m in (updated.get("materials") or [])
        if isinstance(m, dict)
        and _material_key(m) not in removed_keys
        and str(m.get("material_id") or "") not in removed_ids
    ]
    for material in diff.get("added_materials") or []:
        if isinstance(material, dict):
            new_material = copy.deepcopy(material)
            if not new_material.get("material_id"):
                new_material["material_id"] = f"mat_new_{len(materials) + 1}"
            materials.append(new_material)
    changed_by_key = {
        _material_key(item["new"]): item["new"]
        for item in (diff.get("changed_materials") or [])
        if isinstance(item, dict) and isinstance(item.get("new"), dict)
    }
    for i, material in enumerate(materials):
        key = _material_key(material)
        if key in changed_by_key:
            merged = copy.deepcopy(material)
            merged.update(changed_by_key[key])
            materials[i] = merged
    updated["materials"] = materials

    # 3) 步骤
    removed_step_keys = {_step_key(s) for s in diff.get("removed_steps") or [] if isinstance(s, dict)}
    steps = [
        s for s in (updated.get("step_list") or [])
        if isinstance(s, dict) and _step_key(s) not in removed_step_keys
    ]
    for step in diff.get("added_steps") or []:
        if isinstance(step, dict):
            steps.append(copy.deepcopy(step))
    updated["step_list"] = steps

    # 4) 待办：用 preview 覆盖，但清掉仅用于预览的标记
    preview = diff.get("preview_todo_list")
    if isinstance(preview, list):
        todos = []
        for todo in preview:
            if not isinstance(todo, dict):
                continue
            if todo.get("change") == "remove":
                continue      # 用户确认后，被取消材料的待办才真正删除
            item = copy.deepcopy(todo)
            for key in ("change", "needs_confirmation", "reason"):
                item.pop(key, None)
            todos.append(item)
        updated["todo_list"] = todos

    updated["updated_at"] = updated_at
    updated["change_log"] = {
        "applied_at": updated_at,
        "confirmed": True,
        "source": "supplement",
        "before": before,
        "summary": diff.get("changes") or [],
        "confirmation_needed": diff.get("confirmation_needed") or [],
    }

    return {
        "success": True,
        "data": {
            "applied": True,
            "requires_user_confirmation": False,
            "requires_confirmation": False,
            "matter": updated,
            "todo_list": updated.get("todo_list") or [],
            "change_log": updated["change_log"],
            "diff": diff,
        },
        "error": None,
    }


def update_from_supplement(
    original_text: str,
    supplement_text: str,
    original_matter: Optional[Dict[str, Any]] = None,
    supplement_matter: Optional[Dict[str, Any]] = None,
    confirmed: bool = False,
    use_llm: bool = True,
) -> Dict[str, Any]:
    """10.29 一站式入口：对比 → 生成受影响待办 → 用户确认后应用。"""
    compared = compare_notifications(
        original_text=original_text,
        supplement_text=supplement_text,
        original_matter=original_matter,
        supplement_matter=supplement_matter,
        use_llm=use_llm,
    )
    if not compared.get("success"):
        return compared

    data = compared["data"]
    applied = apply_notice_changes(
        data["original_matter"],
        data["diff"],
        confirmed=confirmed,
    )
    if not applied.get("success"):
        return applied

    merged = {
        "diff": data["diff"],
        "compare_mode": data["compare_mode"],
        "supplement_matter": data["supplement_matter"],
        **applied["data"],
    }
    return {"success": True, "data": merged, "error": None}


# ==================== 10.30：日期核对工具（Function Calling） ====================

DATE_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "check_date",
        "description": "核对截止时间是否已过、距今还有多久、是否周末，并给出建议完成时间",
        "parameters": {
            "type": "object",
            "properties": {
                "due_at": {
                    "type": "string",
                    "description": "截止时间，ISO 8601 格式，例如 2026-11-08T18:00:00+08:00",
                },
                "now": {
                    "type": "string",
                    "description": "当前时间，可省略；省略时使用服务器当前时间",
                },
            },
            "required": ["due_at"],
        },
    },
}


def check_date(due_at: Any, now: Any = None) -> Dict[str, Any]:
    """
    10.30 日期核对工具本体：不依赖大模型、不联网，输入截止时间即可核对。
    C 侧后续可以把它单独暴露成 /api/check-date；A 侧先保证 AI 能真实调用。
    """
    due = _parse_datetime(due_at)
    if not due:
        return {
            "success": False,
            "error": f"无法识别的截止时间：{due_at}",
            "due_at": str(due_at or ""),
        }

    now_dt = _parse_datetime(now) if now else datetime.now(TZ)
    if not now_dt:
        now_dt = datetime.now(TZ)

    delta = due - now_dt
    total_seconds = delta.total_seconds()
    is_expired = total_seconds < 0
    days_left = max(0, int(total_seconds // 86400))
    hours_left = max(0, int(total_seconds // 3600))
    weekday = _WEEKDAY_CN[due.weekday()]
    is_weekend = due.weekday() >= 5

    if is_expired or hours_left < 24:
        risk_level = "high"
    elif days_left < 3:
        risk_level = "medium"
    else:
        risk_level = "low"

    # 建议完成时间：默认提前 2 天；遇到周末就往前挪到最近的工作日 18:00。
    suggested_finish = None
    if not is_expired:
        suggested_finish = due - timedelta(days=2)
        while suggested_finish.weekday() >= 5:
            suggested_finish -= timedelta(days=1)
        suggested_finish = suggested_finish.replace(hour=18, minute=0, second=0, microsecond=0)
        if suggested_finish <= now_dt:
            suggested_finish = now_dt + timedelta(hours=2)

    if is_expired:
        overdue_days = abs(int(total_seconds // 86400))
        suggestion = (
            f"截止时间已过 {overdue_days} 天，请先联系对方确认是否还能补交，"
            f"再决定是否继续准备。"
        )
    elif is_weekend:
        suggestion = (
            f"截止日 {due.strftime('%m月%d日')} 是{weekday}，"
            f"建议在 {suggested_finish.strftime('%m月%d日')}（{_WEEKDAY_CN[suggested_finish.weekday()]}）"
            f"18:00 前提交，避免周末无人审核。"
        )
    elif days_left < 1:
        suggestion = "距截止不足 1 天，建议今天完成并提交，不要再等。"
    else:
        suggestion = (
            f"距截止还有 {days_left} 天，建议最晚 "
            f"{suggested_finish.strftime('%m月%d日')}（{_WEEKDAY_CN[suggested_finish.weekday()]}）"
            f"18:00 前完成并提交。"
        )

    return {
        "success": True,
        "due_at": _format_datetime(due),
        "now": _format_datetime(now_dt),
        "days_left": days_left,
        "hours_left": hours_left,
        "is_expired": is_expired,
        "weekday": weekday,
        "is_weekend": is_weekend,
        "risk_level": risk_level,
        "suggested_finish_at": _format_datetime(suggested_finish) if suggested_finish else "",
        "suggestion": suggestion,
        "checks": [
            f"截止时间：{_format_datetime(due)}",
            f"当前时间：{_format_datetime(now_dt)}",
            f"剩余：{days_left} 天（约 {hours_left} 小时）",
            f"星期：{weekday}（{'周末' if is_weekend else '工作日'}）",
        ],
        "error": None,
        "tool": "check_date",
        "tool_version": "1.0",
    }


def _apply_date_result(
    matter: Dict[str, Any],
    trace: List[Dict[str, Any]],
    result: Dict[str, Any],
    extra_suggestions: Optional[List[str]] = None,
    mode: str = "local",
) -> Dict[str, Any]:
    """把工具返回结果写回 Matter，并生成可展示的建议与风险提示。"""
    matter = copy.deepcopy(matter or {})
    matter["date_check"] = result
    matter["tool_trace"] = trace

    suggestions: List[str] = []
    if result.get("success"):
        suggestions.append(result.get("suggestion") or "")
        if result.get("risk_level") == "high" and not result.get("is_expired"):
            suggestions.append("风险较高：建议把该事项设为最高优先级，今天就处理。")
        if result.get("is_expired"):
            suggestions.append("如果对方允许补交，建议今天先提交已有材料，再补缺项。")
        if result.get("days_left", 0) >= 2:
            suggestions.append("建议在截止前 2 天再核对一次材料，避免遗漏。")
    for item in extra_suggestions or []:
        if item and item not in suggestions:
            suggestions.append(item)

    existing = [s for s in (matter.get("suggestions") or []) if isinstance(s, str)]
    for item in suggestions:
        if item and item not in existing:
            existing.append(item)
    matter["suggestions"] = existing

    # 日期风险写进 warning_list，前端已有预警面板可直接展示
    warnings = [
        w for w in (matter.get("warning_list") or [])
        if isinstance(w, dict) and w.get("warning_type") != "date_risk"
    ]
    if result.get("success") and result.get("risk_level") in ("high", "medium"):
        deadline_source = (matter.get("deadline") or {}).get("source_ref") or {}
        if not isinstance(deadline_source, dict):
            deadline_source = {}
        warnings.append({
            "warning_id": f"warn_date_{uuid.uuid4().hex[:6]}",
            "warning_type": "date_risk",
            "severity": "high" if result.get("risk_level") == "high" else "medium",
            "message": result.get("suggestion") or "截止时间较紧，请尽快处理",
            "source_ref": {"quote": deadline_source.get("quote", "")},
        })
    matter["warning_list"] = warnings
    matter = _apply_mode_guards(matter)

    return {
        "success": True,
        "data": matter,
        "tool_calls": trace,
        "mode": mode,
        "error": None,
    }


def _execute_date_tool(name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    if name != "check_date":
        return {"success": False, "error": f"未知工具：{name}"}
    allowed = {k: v for k, v in (arguments or {}).items() if k in ("due_at", "now")}
    return check_date(**allowed)


def _llm_date_tool_loop(
    matter: Dict[str, Any],
    llm,
    now: Any = None,
    client=None,
) -> Dict[str, Any]:
    """真实 Function Calling 循环：模型发起 check_date → 本地执行 → 模型总结。

    client 仅用于测试注入；生产环境不传，内部再创建 OpenAI 客户端。
    """
    if client is None:
        from openai import OpenAI
        client = OpenAI(api_key=llm.api_key, base_url=llm.base_url, timeout=llm.timeout)
    due = (matter.get("deadline") or {}).get("due_at")
    messages = [
        {"role": "system", "content": DATE_TOOL_SYSTEM_PROMPT.replace("{{NOW}}", _format_datetime(_parse_datetime(now) or datetime.now(TZ)))},
        {
            "role": "user",
            "content": "当前清单如下，请核对截止时间并给出建议：\n" + json.dumps(matter, ensure_ascii=False),
        },
    ]

    first = client.chat.completions.create(
        model=llm.model,
        messages=messages,
        tools=[DATE_TOOL_SCHEMA],
        tool_choice="auto",
        temperature=0,
    )
    message = first.choices[0].message
    tool_calls = getattr(message, "tool_calls", None) or []
    trace: List[Dict[str, Any]] = []
    local_result = None

    if tool_calls:
        assistant_tool_calls = []
        for call in tool_calls:
            name = call.function.name
            try:
                args = json.loads(call.function.arguments or "{}")
            except Exception:
                args = {"due_at": due}
            assistant_tool_calls.append({
                "id": call.id,
                "type": "function",
                "function": {"name": name, "arguments": call.function.arguments or "{}"},
            })
            result = _execute_date_tool(name, args)
            if name == "check_date" and result.get("success"):
                local_result = result
            trace.append({
                "step": len(trace) + 1,
                "tool": name,
                "call_id": call.id,
                "arguments": args,
                "result": result,
            })
        messages.append({
            "role": "assistant",
            "content": getattr(message, "content", "") or "",
            "tool_calls": assistant_tool_calls,
        })
        for item in trace:
            messages.append({
                "role": "tool",
                "tool_call_id": item["call_id"],
                "content": json.dumps(item["result"], ensure_ascii=False),
            })
        second = client.chat.completions.create(
            model=llm.model,
            messages=messages,
            temperature=0,
        )
        content = (second.choices[0].message.content or "").strip()
    else:
        content = (getattr(message, "content", "") or "").strip()

    if local_result is None:
        local_result = check_date(due, now)
        trace.append({
            "step": len(trace) + 1,
            "tool": "check_date",
            "arguments": {"due_at": due, "now": now},
            "result": local_result,
        })

    extra_suggestions: List[str] = []
    if content:
        text = re.sub(r"^```(?:json)?|```$", "", content, flags=re.MULTILINE).strip()
        try:
            parsed = json.loads(text)
            extra_suggestions = [str(s) for s in (parsed.get("suggestions") or []) if s]
        except Exception:
            extra_suggestions = [line.strip(" -") for line in text.splitlines() if line.strip()]

    return _apply_date_result(
        matter,
        trace,
        local_result,
        extra_suggestions=extra_suggestions,
        mode="llm" if tool_calls else "llm_no_tool_call",
    )


def run_date_check_tool_loop(
    matter_data: Dict[str, Any],
    now: Any = None,
    use_llm: bool = True,
) -> Dict[str, Any]:
    """
    10.30 任务：让 AI 在需要时调用日期核对工具，并用返回结果生成建议。
    无 Key 时走同一套工具调用轨迹（真实执行 check_date），只是不做模型总结；
    配好 Key 后自动切换为 LLM Function Calling。
    """
    matter = copy.deepcopy(matter_data or {})
    due = (matter.get("deadline") or {}).get("due_at")

    if not due:
        matter["date_check"] = {
            "success": False,
            "error": "清单中没有截止时间，未调用 check_date",
        }
        matter["tool_trace"] = []
        matter["suggestions"] = list(matter.get("suggestions") or []) + [
            "通知里没有明确截止时间，请手动补充后再核对。"
        ]
        return {
            "success": True,
            "data": matter,
            "tool_calls": [],
            "mode": "skipped",
            "error": None,
        }

    if use_llm:
        try:
            extractor = _get_extractor()
            llm = extractor.llm
            if getattr(llm, "api_key", ""):
                return _llm_date_tool_loop(matter, llm, now=now)
        except Exception as e:
            logger.warning("LLM 日期工具调用失败，回退本地工具：%s", e)

    result = check_date(due, now)
    trace = [{
        "step": 1,
        "tool": "check_date",
        "arguments": {"due_at": due, "now": now},
        "result": result,
    }]
    return _apply_date_result(matter, trace, result, mode="local")