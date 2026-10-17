# src/service.py
import logging
from typing import Dict, Any
from notification_extractor import LLMClient, MatterExtractor
from prompt import SYSTEM_PROMPT

logger = logging.getLogger(__name__)

# 全局单例，避免每次请求都重新初始化
_extractor = None

def _get_extractor() -> MatterExtractor:
    global _extractor
    if _extractor is None:
        llm = LLMClient()
        _extractor = MatterExtractor(llm, SYSTEM_PROMPT)
        logger.info("MatterExtractor 初始化完成，准备就绪")
    return _extractor

def analyze_notification(notification_text: str) -> Dict[str, Any]:
    """
    对外统一接口（供 C 的后端调用）
    输入: 纯文本通知
    输出: {"success": bool, "data": dict | None, "error": str | None}
    """
    if not notification_text or not notification_text.strip():
        return {"success": False, "data": None, "error": "通知内容不能为空"}

    try:
        extractor = _get_extractor()
        matter, err = extractor.process(notification_text)
        
        if err:
            return {"success": False, "data": None, "error": err}
            
        return {
            "success": True,
            "data": matter.to_dict(),
            "error": None
        }
    except Exception as e:
        logger.exception("AI 解析异常")
        return {"success": False, "data": None, "error": f"解析异常: {str(e)}"}