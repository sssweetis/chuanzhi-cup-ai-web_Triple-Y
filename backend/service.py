# src/service.py
import logging
import json
import uuid
import re
from typing import Dict, Any, List, Set
from notification_extractor import LLMClient, MatterExtractor
from prompt import SYSTEM_PROMPT, QA_PROMPT, UPDATE_PROMPT, IMAGE_CHECK_RULES

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


def _call_chat(llm, prompt_text: str, system_content: str, use_stream: bool = False) -> str:
    """统一的 LLM 调用，兼容部分 endpoint 不支持 response_format 的情况。"""
    from openai import OpenAI
    client = OpenAI(api_key=llm.api_key, base_url=llm.base_url, timeout=llm.timeout)
    msgs = [
        {"role": "system", "content": system_content},
        {"role": "user", "content": prompt_text},
    ]
    try:
        if use_stream:
            resp = client.chat.completions.create(
                model=llm.model, messages=msgs, temperature=0,
                stream=True, response_format={"type": "json_object"},
            )
            return "".join(
                c.choices[0].delta.content
                for c in resp if c.choices and c.choices[0].delta and c.choices[0].delta.content
            )
        else:
            resp = client.chat.completions.create(
                model=llm.model, messages=msgs, temperature=0,
                stream=False, response_format={"type": "json_object"},
            )
            return resp.choices[0].message.content
    except TypeError:
        # 部分第三方 endpoint 不支持 response_format，降级重试
        if use_stream:
            resp = client.chat.completions.create(
                model=llm.model, messages=msgs, temperature=0, stream=True
            )
            return "".join(
                c.choices[0].delta.content
                for c in resp if c.choices and c.choices[0].delta and c.choices[0].delta.content
            )
        else:
            resp = client.chat.completions.create(
                model=llm.model, messages=msgs, temperature=0, stream=False
            )
            return resp.choices[0].message.content


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

        content = _call_chat(llm, prompt, "你是一个严谨的状态更新引擎，只输出完整的 JSON。", use_stream=False)
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


def ask_question(matter_json: dict, raw_text: str, question: str) -> Dict[str, Any]:
    if not question or not question.strip():
        return {"success": False, "answer": "问题不能为空", "error": "问题不能为空"}
    try:
        extractor = _get_extractor()
        llm = extractor.llm
        prompt = (
            QA_PROMPT.replace("{{MATTER_JSON}}", json.dumps(matter_json, ensure_ascii=False))
            .replace("{{RAW_TEXT}}", raw_text)
            .replace("{{USER_QUESTION}}", question)
        )
        answer = _call_chat(llm, prompt, "你是一个严谨的文档问答助手。", use_stream=True)
        return {"success": True, "answer": answer.strip(), "error": None}
    except Exception as e:
        return {"success": False, "answer": "系统异常，请稍后再试", "error": str(e)}