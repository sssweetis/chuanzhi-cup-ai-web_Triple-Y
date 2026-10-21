# src/service.py
import logging
import json
import uuid
from typing import Dict, Any, List, Set
from notification_extractor import LLMClient, MatterExtractor
from prompt import SYSTEM_PROMPT, QA_PROMPT, UPDATE_PROMPT

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
    """初次解析"""
    if not notification_text or not notification_text.strip():
        return {"success": False, "data": None, "error": "通知内容不能为空"}

    try:
        extractor = _get_extractor()
        matter, err = extractor.process(notification_text)
        if err:
            return {"success": False, "data": None, "error": err}

        data = matter.to_dict()
        
        # 初始化状态
        if not data.get("warning_list"): data["warning_list"] = []
        if not data.get("deadline") or not data["deadline"].get("due_at"):
            data["warning_list"].append({
                "warning_id": f"warn_{uuid.uuid4().hex[:6]}", "warning_type": "missing_information",
                "severity": "high", "message": "通知原文未提及明确的截止时间，请手动确认并设置"
            })

        # 提取缺失项
        missing_items = []
        for mat in data.get("materials", []):
            if mat.get("material_type") == "required":
                missing_items.append({"material_id": mat.get("material_id"), "material_name": mat.get("material_name"), "reason": "必填材料，尚未准备"})
        data["missing_items"] = missing_items
        
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        logger.exception("AI 解析异常")
        return {"success": False, "data": None, "error": f"解析异常: {str(e)}"}

def update_matter_status_with_ai(matter_data: dict, raw_text: str, user_action: str) -> Dict[str, Any]:
    """
    调用大模型，根据用户操作重新推演最新状态
    """
    try:
        extractor = _get_extractor()
        llm = extractor.llm
        
        matter_json_str = json.dumps(matter_data, ensure_ascii=False)
        prompt = UPDATE_PROMPT.replace("{{MATTER_JSON}}", matter_json_str)
        prompt = prompt.replace("{{RAW_TEXT}}", raw_text)
        prompt = prompt.replace("{{USER_ACTION}}", user_action)

        from openai import OpenAI
        client = OpenAI(api_key=llm.api_key, base_url=llm.base_url, timeout=llm.timeout)
        
        # 为了追求极高的准确度，状态推演关掉流式
        response = client.chat.completions.create(
            model=llm.model,
            messages=[
                {"role": "system", "content": "你是一个严谨的状态更新引擎，只输出完整的 JSON。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0,
            response_format={"type": "json_object"},
            stream=False 
        )
        
        raw_text_resp = response.choices[0].message.content
        updated_data = json.loads(raw_text_resp)
        
        # 如果大模型失忆把基础字段弄丢了，用原有的兜底
        if "materials" not in updated_data:
             updated_data = matter_data

        # 重新计算 missing_items
        missing_items = []
        for mat in updated_data.get("materials", []):
            if mat.get("material_type") == "required" and mat.get("status") != "prepared":
                missing_items.append({"material_id": mat.get("material_id"), "material_name": mat.get("material_name"), "reason": "必填材料，尚未准备"})
        updated_data["missing_items"] = missing_items

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
        prompt = QA_PROMPT.replace("{{MATTER_JSON}}", json.dumps(matter_json, ensure_ascii=False)).replace("{{RAW_TEXT}}", raw_text).replace("{{USER_QUESTION}}", question)
        from openai import OpenAI
        client = OpenAI(api_key=llm.api_key, base_url=llm.base_url, timeout=llm.timeout)
        response = client.chat.completions.create(
            model=llm.model,
            messages=[{"role": "system", "content": "你是一个严谨的文档问答助手。"}, {"role": "user", "content": prompt}],
            temperature=0, stream=True
        )
        answer = "".join(chunk.choices[0].delta.content for chunk in response if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content)
        return {"success": True, "answer": answer.strip(), "error": None}
    except Exception as e:
        return {"success": False, "answer": "系统异常，请稍后再试", "error": str(e)}