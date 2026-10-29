# -*- coding: utf-8 -*-
"""双通知对比与存档（C 侧，10/28）。

两份通知各自保留文件名、原文和抽取结果；对比只读，不改写 A 产生的 Matter 字段。
"""
import json
import os
import re
import threading
import uuid
from datetime import datetime, timedelta, timezone

from date_tool import check_date

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
STORE_PATH = os.path.join(DATA_DIR, "comparisons.json")
_LOCK = threading.Lock()
TZ = timezone(timedelta(hours=8))
_PUNCT = re.compile(r"[\s，。；：、！？,.!?:;（）()\[\]【】《》<>\"'“”‘’\-]+")


def _norm(value) -> str:
    return _PUNCT.sub("", str(value or "")).lower()


def _record_key(session_id: str, comparison_id: str) -> str:
    return comparison_id if session_id == "default" else "%s:%s" % (session_id, comparison_id)


def _load() -> dict:
    if not os.path.exists(STORE_PATH):
        return {}
    try:
        with open(STORE_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save(data: dict) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = STORE_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, STORE_PATH)


def _owner(record: dict) -> str:
    return record.get("session_id") or "default"


def _named(items, key):
    result = {}
    for item in items or []:
        if not isinstance(item, dict):
            continue
        name = item.get(key)
        if name:
            result[_norm(name)] = name
    return result


def _deadline(matter: dict) -> dict:
    deadline = matter.get("deadline") or {}
    due_at = deadline.get("due_at") if isinstance(deadline, dict) else None
    info = None
    if due_at:
        try:
            info = check_date(due_at)
        except ValueError:
            info = None
    return {"due_at": due_at, "label": deadline.get("label") if isinstance(deadline, dict) else None,
            "date_info": info}




_REPLACEMENT_HINTS = ("取消", "不再", "改为", "替换", "不提交", "无需", "删除")


def _merge_incremental(right_matter: dict, left_matter: dict, right_text: str):
    """补充通知默认按增量处理；只有明确取消/替换时才让它覆盖原清单。"""
    if not right_text or any(hint in right_text for hint in _REPLACEMENT_HINTS):
        return right_matter
    merged = dict(right_matter or {})
    for field, name_key in (("materials", "material_name"), ("step_list", "title")):
        current = [x for x in (merged.get(field) or []) if isinstance(x, dict)]
        seen = {_norm(x.get(name_key)) for x in current if x.get(name_key)}
        for item in (left_matter or {}).get(field) or []:
            if not isinstance(item, dict) or not item.get(name_key):
                continue
            if _norm(item.get(name_key)) not in seen:
                current.append(item)
                seen.add(_norm(item.get(name_key)))
        if current:
            merged[field] = current
    return merged

def compare_matters(left: dict, right: dict, left_text: str = "", right_text: str = "") -> dict:
    # 补充通知经常只写“新增某项”，不会重复列出原通知已有材料。
    # 默认增量合并，避免把原有的报名表/成绩单误报成 only_left。
    right = _merge_incremental(right, left, right_text)
    left_deadline, right_deadline = _deadline(left), _deadline(right)
    left_materials = _named(left.get("materials"), "material_name")
    right_materials = _named(right.get("materials"), "material_name")
    left_steps = _named(left.get("step_list"), "title")
    right_steps = _named(right.get("step_list"), "title")

    left_mat_keys, right_mat_keys = set(left_materials), set(right_materials)
    left_step_keys, right_step_keys = set(left_steps), set(right_steps)
    deadline_changed = left_deadline.get("due_at") != right_deadline.get("due_at")

    return {
        "deadline": {
            "left": left_deadline,
            "right": right_deadline,
            "changed": deadline_changed,
        },
        "materials": {
            "common": [left_materials[k] for k in sorted(left_mat_keys & right_mat_keys)],
            "only_left": [left_materials[k] for k in sorted(left_mat_keys - right_mat_keys)],
            "only_right": [right_materials[k] for k in sorted(right_mat_keys - left_mat_keys)],
            "changed": bool(left_mat_keys ^ right_mat_keys),
        },
        "steps": {
            "common": [left_steps[k] for k in sorted(left_step_keys & right_step_keys)],
            "only_left": [left_steps[k] for k in sorted(left_step_keys - right_step_keys)],
            "only_right": [right_steps[k] for k in sorted(right_step_keys - left_step_keys)],
            "changed": bool(left_step_keys ^ right_step_keys),
        },
        "has_difference": deadline_changed or bool(left_mat_keys ^ right_mat_keys) or bool(left_step_keys ^ right_step_keys),
    }


def save_comparison(left: dict, right: dict, diff: dict, session_id: str = "default") -> dict:
    comparison_id = "cmp_" + uuid.uuid4().hex[:8]
    created_at = datetime.now(TZ).isoformat()
    record = {
        "comparison_id": comparison_id,
        "session_id": session_id or "default",
        "created_at": created_at,
        "left": left,
        "right": right,
        "diff": diff,
    }
    with _LOCK:
        data = _load()
        data[_record_key(record["session_id"], comparison_id)] = record
        _save(data)
    return record


def get_comparison(comparison_id: str, session_id: str = "default"):
    if not comparison_id:
        return None
    with _LOCK:
        record = _load().get(_record_key(session_id or "default", comparison_id))
    if not record or _owner(record) != (session_id or "default"):
        return None
    return record


def list_comparisons(session_id: str = "default") -> list:
    owner = session_id or "default"
    with _LOCK:
        data = _load()
    items = [r for r in data.values() if isinstance(r, dict) and _owner(r) == owner]
    items.sort(key=lambda r: r.get("created_at", ""), reverse=True)
    return [{"comparison_id": r.get("comparison_id"), "created_at": r.get("created_at"),
             "left_filename": (r.get("left") or {}).get("filename"),
             "right_filename": (r.get("right") or {}).get("filename"),
             "has_difference": bool((r.get("diff") or {}).get("has_difference"))}
            for r in items]


def delete_comparison(comparison_id: str, session_id: str = "default") -> bool:
    key = _record_key(session_id or "default", comparison_id)
    with _LOCK:
        data = _load()
        record = data.get(key)
        if not record or _owner(record) != (session_id or "default"):
            return False
        del data[key]
        _save(data)
    return True
