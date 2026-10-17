# -*- coding: utf-8 -*-
"""
对外服务接口（给 C 调用）

C 只需要：
    from service import analyze_notification
    result = analyze_notification("请于10月25日18:00前提交奖学金报名表。")

返回：
    {
        "success": True/False,
        "data": {...Matter JSON...} 或 None,
        "error": "错误信息" 或 None
    }
"""

import os
import logging
from typing import Dict, Any, Optional

# 从核心脚本导入
from notification_extractor import (
    LLMClient,
    MatterExtractor,
)

logger = logging.getLogger("notification_service")


# ==================== SYSTEM PROMPT ====================
# 这份 Prompt 是最终确认版，用于让 LLM 输出结构化 JSON
SYSTEM_PROMPT = r"""
# Role
你是一个专业的"通知事项结构化提取助手"。你需要将用户输入的非结构化通知文本，严格转换为指定的 JSON 结构。

# 系统注入变量
NOW = {{NOW}}

# Task
1. 分析通知复杂度，确定 mode（simple | standard | complex）。
2. 只提取原文出现过的字段；原文没有的字段，直接省略，禁止输出 null 占位。
3. 严格输出 JSON，不要包含 Markdown 标记（如 ```json），不要输出任何解释。

# Mode 判定规则
- simple：
  只有 1 个时间点或 1 个动作，没有步骤、材料、地点、审核、依赖
  enabled_sections: ["summary", "schedule", "source"]
- standard：
  有 ≥2 个动作/步骤，或有材料清单、地点、附件；
  但没有子步骤、依赖、审核、多角色、冲突
  enabled_sections: ["summary", "schedule", "content", "steps", "materials", "source"]
- complex：
  有子步骤、前置依赖、多角色（负责人/审核人）、审核环节、时间冲突、材料复用、周期性
  enabled_sections: ["summary", "schedule", "content", "steps", "materials", "warnings", "governance", "source"]

# 复杂度评分
complexity_score 由以下公式估算（0~1）：
score = 0.2*has_deadline + 0.1*has_multiple_reminders + 0.2*has_multiple_steps
      + 0.2*has_materials + 0.1*has_review + 0.1*has_dependencies
      + 0.1*has_recurrence + 0.1*has_sub_steps

判定规则（优先级从高到低）：
1. 只要检测到 has_sub_steps 或 has_review 或 has_dependencies → 直接判为 complex
2. 否则 score < 0.3 → simple
3. 否则 0.3 ≤ score ≤ 0.6 → standard
4. 否则 score > 0.6 → complex

# detected_features 合法枚举
has_deadline / has_multiple_reminders / has_multiple_steps / has_sub_steps /
has_materials / has_attachments / has_location / has_people /
has_review / has_dependencies / has_recurrence /
has_conflict / has_material_reuse

只输出本次检测到的，不输出 false 项。

# 字段输出规则（严格遵守）
- schema_version: "1.0"
- id: 固定用 "matter_auto"（由系统替换）
- created_at / updated_at: 输出空字符串 ""（由系统注入）
- timezone: "Asia/Shanghai"
- status: 默认 "not_started"
- status_source: "auto"
- mode_source: "auto"
- priority: 默认 "medium"
    原文含 "紧急" / "立即" / "最后期限" / "不可延期" → "urgent"
    原文含 "务必" / "尽快" / "请务必" / "逾期后果自负" → "high"
    其余 → "medium"
- title:
    优先使用原文标题；无标题时用"核心动作 + 核心对象"提炼，不超过 20 字，不加书名号
- target:
    在 simple / standard / complex 三种模式下都可输出；
    仅当原文明确提到面向对象（如"全体学生""2026级本科生"）时才输出，否则省略该字段
- category: 自由字符串，如 报名 | 报销 | 审批 | 会议 | 活动 | 放假 | 缴费 | 考试 | 其他
- reminders: 若原文有 DDL，则输出一条，offset_minutes=120，channels=["app"]；否则省略
- deadline.start_at / end_at: 仅 complex 模式输出；simple / standard 省略
- 相对时间（如"下周三""明天下午3点"）以 NOW 为基准归一化为绝对时间，
  格式 ISO 8601 + +08:00；无法确定时省略该字段，并把原文写入 key_points
- LLM 不生成 UUID、时间戳、用户 ID，一律用占位符或空串

# 字段互斥规则（最重要）
- simple 模式禁止出现：
  owner / assignees / participants / contact /
  default_location / key_points / attachments / materials / step_list /
  warning_list / permissions / audit_log / comments / recurrence
- standard 模式禁止出现：
  sub_step_list / dependencies / parallel / condition / review /
  owner(步骤级) / assignees(步骤级) / recurrence /
  permissions / audit_log / comments
- standard 模式的 warning_list 仅允许 deadline_risk / missing_material
- complex 模式可使用全部字段
- target 不受互斥规则限制，三种模式均可输出

# complex 专属字段默认省略规则
complex 模式允许输出以下字段，但仅在原文有对应信息时才输出：
- warning_list：仅当识别到 时间冲突 / 材料复用 / DDL 风险 / 缺材料 时输出
- recurrence：仅当原文明确提到 "每周 / 每月 / 每年 / 定期" 时输出
- permissions / audit_log / comments：默认省略，除非原文明确提到权限或审核流程

# reminders 字段规则
- simple / standard：仅含 reminder_id / offset_minutes / channels / enabled
- complex：可增加 recipients / repeat / calendar_uid

# 步骤与材料命名规则
- 顶层步骤：step_id 形如 "step_1"，省略 parent_id
- 子步骤：sub_step_id 形如 "sub_1_1"，parent_id 指向父步骤 step_id
- step_list[].materials 与 step_list[].attachments 一律使用 ID 数组，
  引用顶层 materials[].material_id 和 attachments[].attachment_id，
  不得重复内联对象；sub_step_list 同样使用 ID 数组
- material.template_attachment_id 必须指向 attachments[].attachment_id
- 子步骤可选字段：due_at / due_at_inherited_from / location / key_points /
  source_ref；为空则继承父步骤

# source_ref 结构
{
  "quote": "原文片段",
  "doc_id": null,
  "doc_version": null,
  "page": null,
  "anchor_id": null,
  "char_start": null,
  "char_end": null,
  "chunk_id": null,
  "bbox": null
}
quote 必填（原文引用），其余可为空。

# 其他规则
- 空数组 / 空对象一律省略，不要输出 [] 或 {}
- 禁止编造任何原文没有的信息（地点、负责人、审核人、材料、附件等）

# 三种模式的输出结构

## simple
{
  "schema_version": "1.0",
  "id": "matter_auto",
  "mode": "simple",
  "mode_source": "auto",
  "complexity_score": 0.2,
  "detected_features": ["has_deadline"],
  "enabled_sections": ["summary", "schedule", "source"],
  "title": "提交奖学金报名表",
  "priority": "medium",
  "status": "not_started",
  "status_source": "auto",
  "timezone": "Asia/Shanghai",
  "created_at": "",
  "updated_at": "",
  "deadline": {
    "scope": "overall",
    "label": "截止时间",
    "due_at": "2026-10-25T18:00:00+08:00",
    "all_day": false,
    "source_ref": {"quote": "请于10月25日18:00前提交"}
  },
  "reminders": [
    {"reminder_id": "rem_1", "offset_minutes": 120, "channels": ["app"], "enabled": true}
  ],
  "sources": [{"quote": "请于10月25日18:00前提交", "page": null}]
}

## standard
在 simple 基础上增加：default_location / key_points / attachments / materials / step_list。
step_list 每步只含：step_id / order / title / desc / status / due_at /
due_at_inherited_from / location / key_points / materials（ID 数组）/
attachments（ID 数组）/ source_ref。

## complex
在 standard 基础上增加：step_list 里补 start_at / reminders / dependencies /
parallel / condition / owner / assignees / review / sub_step_list；
顶层增加 warning_list / recurrence / permissions / audit_log / comments。

# 输入通知
---
{{USER_NOTIFICATION_TEXT}}
---
"""


# ==================== 单例初始化 ====================

_extractor: Optional[MatterExtractor] = None


def _get_extractor() -> MatterExtractor:
    """懒加载单例，避免每次请求都重新初始化。"""
    global _extractor
    if _extractor is None:
        llm = LLMClient()
        _extractor = MatterExtractor(llm, SYSTEM_PROMPT)
        logger.info("MatterExtractor 初始化完成，model=%s", llm.model)
    return _extractor


# ==================== 对外主接口 ====================

def analyze_notification(notification_text: str) -> Dict[str, Any]:
    """
    【给 C 调用的标准接口】

    参数：
        notification_text: 通知原文（纯文本，必填）

    返回：
        {
            "success": bool,
            "data": dict | None,   # 符合 Matter 结构的 JSON 字典
            "error": str | None
        }

    调用示例：
        from service import analyze_notification
        result = analyze_notification("请于10月25日18:00前提交奖学金报名表。")
        if result["success"]:
            print(result["data"]["title"])
            print(result["data"]["deadline"]["due_at"])
    """
    if not notification_text or not notification_text.strip():
        return {
            "success": False,
            "data": None,
            "error": "通知内容不能为空",
        }

    try:
        extractor = _get_extractor()
        matter, err = extractor.process(notification_text)

        if err:
            logger.error("解析失败：%s", err)
            return {"success": False, "data": None, "error": err}

        return {
            "success": True,
            "data": matter.to_dict(),
            "error": None,
        }

    except Exception as e:
        logger.exception("解析异常：%s", e)
        return {
            "success": False,
            "data": None,
            "error": f"解析异常：{str(e)}",
        }


# ==================== 本地自测 ====================

if __name__ == "__main__":
    import json

    test_text = "请于10月25日18:00前提交奖学金报名表。"
    result = analyze_notification(test_text)
    print(json.dumps(result, ensure_ascii=False, indent=2))