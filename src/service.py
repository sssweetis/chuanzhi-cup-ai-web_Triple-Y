# src/service.py
import logging
import json
import uuid
import os
import re
from typing import Dict, Any, List, Set, Optional, Union
from notification_extractor import (
    LLMClient,
    MatterExtractor,
    DocumentChunk,
    extract_pdf_pages_and_text,
    chunk_document_text,
    chunk_document_pages,
)
from prompt import SYSTEM_PROMPT, QA_PROMPT, UPDATE_PROMPT, IMAGE_CHECK_RULES, RAG_QA_PROMPT

logger = logging.getLogger(__name__)
_extractor = None


def _get_extractor() -> MatterExtractor:
    global _extractor
    if _extractor is None:
        llm = LLMClient()
        _extractor = MatterExtractor(llm, SYSTEM_PROMPT)
        logger.info("MatterExtractor 初始化完成")
    return _extractor


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