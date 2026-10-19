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

def analyze_notification(notification_text: str, user_materials: List[str] = None) -> Dict[str, Any]:
    """
    解析通知接口，包含精确的线性推导逻辑
    """
    if not notification_text or not notification_text.strip():
        return {"success": False, "data": None, "error": "通知内容不能为空"}

    try:
        extractor = _get_extractor()
        matter, err = extractor.process(notification_text)
        if err:
            return {"success": False, "data": None, "error": err}
        
        data = matter.to_dict()
        
        # ====== 缺失信息与状态核对 ======
        if "warning_list" not in data or not data["warning_list"]:
            data["warning_list"] = []
            
        # 1. 检查时间是否缺失（绝不猜测日期，强制提醒用户手动确认）
        if not data.get("deadline") or not data["deadline"].get("due_at"):
            data["warning_list"].append({
                "warning_id": f"warn_{uuid.uuid4().hex[:6]}",
                "warning_type": "missing_information",
                "mode_scope": "complex",
                "severity": "high",
                "message": "通知原文未提及明确的截止时间，请手动确认并设置"
            })
            
        # 2. 核对材料状态 (已准备、缺少、需要确认)
        materials = data.get("materials", [])
        missing_items = []
        
        for mat in materials:
            mat_name = mat.get("material_name", "").strip()
            mat_type = mat.get("material_type", "required")
            
            if not mat_name or mat_name == "未命名材料":
                mat["status"] = "need_confirm"
                mat["status_desc"] = "系统无法确认材料名称"
                missing_items.append({
                    "material_id": mat.get("material_id"),
                    "material_name": "未命名材料",
                    "reason": "名称模糊，需人工确认"
                })
            elif user_materials is not None:
                # 模糊匹配用户勾选的材料
                is_have = any(u in mat_name or mat_name in u for u in user_materials)
                if is_have:
                    mat["status"] = "prepared"
                    mat["status_desc"] = "已准备"
                else:
                    mat["status"] = "pending"
                    mat["status_desc"] = "缺少"
                    if mat_type == "required":
                        missing_items.append({
                            "material_id": mat.get("material_id"),
                            "material_name": mat_name,
                            "reason": "必填材料，尚未准备"
                        })
            else:
                # 如果用户还没勾选，默认都是待准备状态
                mat["status"] = "pending"
                mat["status_desc"] = "待准备"

        # ====== 3. 核心升级：线性推导逻辑 ======
        steps = data.get("step_list", [])
        
        # 定义不能自动打勾的“交付/行动类”关键词，必须由用户手动确认完成
        delivery_keywords = ["提交", "发送", "交至", "上交", "参与", "上传", "打印", "盖章"]
        
        completed_indices = []

        for idx, step in enumerate(steps):
            step_title = step.get("title", "")
            step_materials = step.get("materials", [])
            
            # 如果是交付动作，不管材料有没有，都视为未完成
            if any(k in step_title for k in delivery_keywords):
                continue
                
            # 检查材料绑定或标题匹配
            is_finished = False
            if step_materials:
                all_prepared = True
                for m_id in step_materials:
                    m_obj = next((m for m in materials if m["material_id"] == m_id), None)
                    if m_obj and m_obj["status"] != "prepared":
                        all_prepared = False
                        break
                if all_prepared:
                    is_finished = True
            else:
                if user_materials:
                    if any(u in step_title for u in user_materials):
                        is_finished = True
            
            if is_finished:
                completed_indices.append(idx)

        # 顺序推导：只要第 N 步完成了，排在它前面的 0 到 N-1 步必须也打勾
        max_completed_idx = max(completed_indices) if completed_indices else -1

        for idx, step in enumerate(steps):
            # 如果排在前面的，或者当前步骤本身被判定完成，就标为已完成
            if idx <= max_completed_idx:
                step["status"] = "completed"
            else:
                step["status"] = "not_started"

        # ==========================================

        data["missing_items"] = missing_items
        return {"success": True, "data": data, "error": None}
        
    except Exception as e:
        logger.exception("AI 解析异常")
        return {"success": False, "data": None, "error": f"解析异常: {str(e)}"}


# ==================== 智能问答接口 ====================

def ask_question(matter_json: dict, raw_text: str, question: str) -> Dict[str, Any]:
    """
    基于当前的 JSON 和原文，回答用户的问题（防幻觉）
    """
    if not question or not question.strip():
        return {"success": False, "answer": "问题不能为空", "error": "问题不能为空"}

    try:
        extractor = _get_extractor()
        llm = extractor.llm
        
        # 组装 QA Prompt
        matter_json_str = json.dumps(matter_json, ensure_ascii=False)
        prompt = QA_PROMPT.replace("{{MATTER_JSON}}", matter_json_str)
        prompt = prompt.replace("{{RAW_TEXT}}", raw_text)
        prompt = prompt.replace("{{USER_QUESTION}}", question)

        # 直接调用大模型（开启 stream=True 防超时）
        from openai import OpenAI
        client = OpenAI(api_key=llm.api_key, base_url=llm.base_url, timeout=llm.timeout)
        
        response = client.chat.completions.create(
            model=llm.model,
            messages=[
                {"role": "system", "content": "你是一个严谨的文档问答助手，只根据给定资料回答，绝不编造。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0,
            stream=True
        )
        
        # 拼接流式回答
        answer = ""
        for chunk in response:
            if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                answer += chunk.choices[0].delta.content
                
        return {"success": True, "answer": answer.strip(), "error": None}
        
    except Exception as e:
        logger.exception("问答异常")
        return {"success": False, "answer": "系统异常，请稍后再试", "error": str(e)}