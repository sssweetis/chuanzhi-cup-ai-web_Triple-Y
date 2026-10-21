# -*- coding: utf-8 -*-
"""
要求 ↔ 原文的对应关系（C 侧，10/22「点击一条要求，能看到支持它的原文」）

    find_evidence(matter, target_type, target_id)  → 单条依据
    build_evidence_index(matter)                   → 全部可查看的条目

规则（与 A 的口径一致）：
    · 有 source_ref.quote → 原文依据，is_suggestion=false
    · 没有 quote          → 标明"系统建议，原文未直接给出依据"，is_suggestion=true
"""

TARGET_TYPES = ("material", "step", "todo", "attachment", "deadline", "warning", "key_point")


def _quote(ref):
    if isinstance(ref, dict):
        q = ref.get("quote")
        return q if isinstance(q, str) and q.strip() else None
    return None


def _material_items(matter):
    for m in matter.get("materials") or []:
        if isinstance(m, dict):
            yield m.get("material_id"), m.get("material_name") or "未命名材料", m.get("source_ref")


def _step_items(matter):
    for s in matter.get("step_list") or []:
        if isinstance(s, dict):
            yield s.get("step_id"), s.get("title") or "未命名步骤", s.get("source_ref")
            for sub in s.get("sub_step_list") or []:
                if isinstance(sub, dict):
                    yield sub.get("sub_step_id"), sub.get("title") or "未命名子步骤", sub.get("source_ref")


def _todo_items(matter):
    for t in matter.get("todo_list") or []:
        if isinstance(t, dict):
            yield t.get("todo_id"), t.get("action") or "待办", t.get("source_ref")


def _attachment_items(matter):
    for a in matter.get("attachments") or []:
        if isinstance(a, dict):
            yield a.get("attachment_id"), a.get("attachment_name") or "附件", a.get("source_ref")


def _deadline_items(matter):
    d = matter.get("deadline")
    if isinstance(d, dict):
        yield "overall", d.get("label") or "截止时间", d.get("source_ref")


def _warning_items(matter):
    for w in matter.get("warning_list") or []:
        if isinstance(w, dict):
            yield w.get("warning_id"), w.get("message") or w.get("warning_type") or "预警", w.get("source_ref")


def _key_point_items(matter):
    for i, kp in enumerate(matter.get("key_points") or []):
        if isinstance(kp, dict):
            yield i, kp.get("text") or kp.get("content") or "要点", kp.get("source_ref")
        else:
            yield i, str(kp), None          # 纯字符串要点没有单独溯源 → 视为建议


_COLLECTORS = {
    "material": _material_items,
    "step": _step_items,
    "todo": _todo_items,
    "attachment": _attachment_items,
    "deadline": _deadline_items,
    "warning": _warning_items,
    "key_point": _key_point_items,
}


def build_evidence_index(matter):
    matter = matter or {}
    items = []
    for target_type, collector in _COLLECTORS.items():
        for target_id, title, ref in collector(matter):
            quote = _quote(ref)
            items.append({
                "target_type": target_type,
                "target_id": target_id,
                "title": title,
                "quote": quote,
                "source_ref": ref if quote else None,
                "is_suggestion": not bool(quote),
                "note": None if quote else "该条为系统建议，原文未直接给出依据",
            })
    return items


def find_evidence(matter, target_type, target_id):
    for item in build_evidence_index(matter):
        if item["target_type"] == target_type and str(item["target_id"]) == str(target_id):
            return {"found": True, **item}
    return {
        "found": False, "target_type": target_type, "target_id": target_id,
        "title": None, "quote": None, "source_ref": None,
        "is_suggestion": False, "note": "未找到该条目",
    }