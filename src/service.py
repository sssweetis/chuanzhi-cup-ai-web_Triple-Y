# src/service.py
import logging
import json
import uuid
from typing import Dict, Any, List
from notification_extractor import LLMClient, MatterExtractor
from prompt import SYSTEM_PROMPT, QA_PROMPT

logger = logging.getLogger(__name__)
_extractor = None

def _get_extractor() -> MatterExtractor:
    global _extractor
    if _extractor is None:
        llm = LLMClient()
        _extractor = MatterExtractor(llm, SYSTEM_PROMPT)
        logger.info("MatterExtractor 初始化完成")
    return _extractor

def analyze_notification(notification_text: str) -> Dict[str, Any]:
    """初次解析：调大模型一次，生成基础清单"""
    if not notification_text or not notification_text.strip():
        return {"success": False, "data": None, "error": "通知内容不能为空"}

    try:
        extractor = _get_extractor()
        matter, err = extractor.process(notification_text)
        if err:
            return {"success": False, "data": None, "error": err}
        
        data = matter.to_dict()
        # 初次解析后，立即执行一次状态初始化
        data = recalculate_matter_status(data, user_materials=[], existing_todos=None)
        return {"success": True, "data": data, "error": None}
        
    except Exception as e:
        logger.exception("AI 解析异常")
        return {"success": False, "data": None, "error": f"解析异常: {str(e)}"}

def update_matter_status(matter_data: dict, user_materials: List[str] = None, existing_todos: List[dict] = None) -> Dict[str, Any]:
    """本地更新状态：纯代码推导，不请求大模型，秒级响应"""
    try:
        # 深拷贝，防止修改原对象
        data = json.loads(json.dumps(matter_data))
        data = recalculate_matter_status(data, user_materials, existing_todos)
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": f"状态更新异常: {str(e)}"}

def recalculate_matter_status(data: dict, user_materials: List[str] = None, existing_todos: List[dict] = None) -> dict:
    if user_materials is None: user_materials = []

    # 1. 检查时间预警
    if not data.get("warning_list"): 
        data["warning_list"] = []
    if not data.get("deadline") or not data["deadline"].get("due_at"):
        if not any(w.get("warning_type") == "missing_information" for w in data["warning_list"]):
            data["warning_list"].append({
                "warning_id": f"warn_{uuid.uuid4().hex[:6]}", 
                "warning_type": "missing_information",
                "severity": "high", 
                "message": "通知原文未提及明确的截止时间，请手动确认并设置"
            })

    # 2. 核对材料状态
    materials = data.get("materials", [])
    missing_items = []
    for mat in materials:
        mat_name = mat.get("material_name", "").strip()
        mat_type = mat.get("material_type", "required")
        is_have = any(u in mat_name or mat_name in u for u in user_materials)
        if is_have:
            mat["status"] = "prepared"
            mat["status_desc"] = "已准备"
        else:
            mat["status"] = "pending"
            mat["status_desc"] = "缺少"
            if mat_type == "required":
                missing_items.append({"material_id": mat.get("material_id"), "material_name": mat_name, "reason": "必填材料，尚未准备"})

    # 3. 步骤推导：基于 DAG 依赖图溯源
    steps = data.get("step_list", [])
    valid_steps = []
    delivery_keywords = ["提交", "发送", "交至", "上交", "参与", "上传", "打印", "打包"]
    condition_keywords = ["初审后", "通过后", "修改后", "合格后", "审核后", "二次", "最终"]
    
    step_dict = {s["step_id"]: s for s in steps if "step_id" in s}
    completed_step_ids = set()

    # 第一轮：找出因材料齐备而直接完成的步骤
    for step in steps:
        title = step.get("title", "").strip()
        if not title or title.startswith("执行步骤"): 
            continue
        
        valid_steps.append(step)
        
        # 交付类动作不自动打勾
        if any(k in title for k in delivery_keywords): 
            continue
            
        step_materials = step.get("materials", [])
        is_finished = False
        if step_materials:
            if all(next((m for m in materials if m["material_id"] == m_id), {"status": "pending"})["status"] == "prepared" for m_id in step_materials):
                is_finished = True
        elif user_materials and any(u in title for u in user_materials):
            is_finished = True
            
        if is_finished:
            completed_step_ids.add(step["step_id"])

    # 第二轮：基于 dependencies 向上溯源
    changed = True
    while changed:
        changed = False
        for step in valid_steps:
            step_id = step.get("step_id")
            if step_id in completed_step_ids:
                for dep in step.get("dependencies", []):
                    dep_id = dep.get("step_id") if isinstance(dep, dict) else dep
                    if dep_id and dep_id not in completed_step_ids and dep_id in step_dict:
                        completed_step_ids.add(dep_id)
                        changed = True

    # 应用最终步骤状态
    for step in valid_steps:
        step["status"] = "completed" if step.get("step_id") in completed_step_ids else "not_started"
            
    data["step_list"] = valid_steps

    # 4. 待办联动 (含前置条件阻断)
    todos = existing_todos if existing_todos is not None else data.get("todo_list", [])
    mat_name_to_obj = {m["material_name"]: m for m in materials}

    for i, todo in enumerate(todos):
        action = todo.get("action", "")
        
        is_delivery = any(k in action for k in ["打包", "发送", "提交", "交至", "上传"])
        is_condition_action = any(k in action for k in condition_keywords)
        
        if is_delivery:
            # 交付动作：必须所有材料 ready 才能完成
            if all(m["status"] == "prepared" for m in materials):
                todo["status"] = "completed"
            else:
                todo["status"] = "pending"
        elif is_condition_action:
            # 条件动作：寻找前置的“发送/提交”动作
            prev_delivery = next((t for t in todos[:i] if any(k in t.get("action", "") for k in ["发送", "提交"])), None)
            
            # 如果前置交付动作还没完成，锁定为 pending
            if prev_delivery and prev_delivery.get("status") != "completed":
                todo["status"] = "pending"
            else:
                # 前置动作做完了，再检查关联材料
                related_mat = next((m_name for m_name in mat_name_to_obj.keys() if m_name in action), "")
                if related_mat and mat_name_to_obj[related_mat]["status"] == "prepared":
                    todo["status"] = "completed"
        else:
            # 普通的准备动作
            related_mat = next((m_name for m_name in mat_name_to_obj.keys() if m_name in action or (action and action in m_name)), "")
            if related_mat and mat_name_to_obj[related_mat]["status"] == "prepared":
                todo["status"] = "completed"
            
            # 反向联动
            if existing_todos and todo.get("status") == "completed" and related_mat:
                mat_name_to_obj[related_mat]["status"] = "prepared"
                mat_name_to_obj[related_mat]["status_desc"] = "已准备"

    data["todo_list"] = todos
    data["missing_items"] = missing_items
    return data

def ask_question(matter_json: dict, raw_text: str, question: str) -> Dict[str, Any]:
    if not question or not question.strip(): 
        return {"success": False, "answer": "问题不能为空", "error": "问题不能为空"}
    try:
        extractor = _get_extractor()
        llm = extractor.llm
        
        matter_json_str = json.dumps(matter_json, ensure_ascii=False)
        prompt = QA_PROMPT.replace("{{MATTER_JSON}}", matter_json_str)
        prompt = prompt.replace("{{RAW_TEXT}}", raw_text)
        prompt = prompt.replace("{{USER_QUESTION}}", question)

        from openai import OpenAI
        client = OpenAI(api_key=llm.api_key, base_url=llm.base_url, timeout=llm.timeout)
        
        response = client.chat.completions.create(
            model=llm.model,
            messages=[
                {"role": "system", "content": "你是一个严谨的文档问答助手，只根据给定资料回答，绝不编造。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0, stream=True
        )
        
        answer = "".join(
            chunk.choices[0].delta.content 
            for chunk in response 
            if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content
        )
        return {"success": True, "answer": answer.strip(), "error": None}
    except Exception as e:
        return {"success": False, "answer": "系统异常，请稍后再试", "error": str(e)}