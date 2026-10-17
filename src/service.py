# src/service.py
import logging
import json
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
    """原有的解析接口，保持不变"""
    if not notification_text or not notification_text.strip():
        return {"success": False, "data": None, "error": "通知内容不能为空"}

    try:
        extractor = _get_extractor()
        matter, err = extractor.process(notification_text)
        if err:
            return {"success": False, "data": None, "error": err}
        return {"success": True, "data": matter.to_dict(), "error": None}
    except Exception as e:
        logger.exception("AI 解析异常")
        return {"success": False, "data": None, "error": f"解析异常: {str(e)}"}

# ==================== 新增：智能问答接口 ====================

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

        # 直接调用大模型（由于不需要强校验 JSON 格式，可以直接用 OpenAI 客户端）
        from openai import OpenAI
        client = OpenAI(api_key=llm.api_key, base_url=llm.base_url, timeout=llm.timeout)
        
        response = client.chat.completions.create(
            model=llm.model,
            messages=[
                {"role": "system", "content": "你是一个严谨的文档问答助手，只根据给定资料回答，绝不编造。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0,
            stream=True # 同样开启流式防超时
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