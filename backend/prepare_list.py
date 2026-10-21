# -*- coding: utf-8 -*-
"""
准备清单（C 侧 10/21）：生成 + 本地存档

    build_prepare_list(matter, checked_ids)  → 缺项 + 待办（不调模型）
    save_prepare_list(matter_id, todo_list)  → 写 backend/data/prepare_lists.json
    load_prepare_list(matter_id)             → 读回

文件存储：演示够用、零依赖、换浏览器/重开服务都能恢复；生产可替换数据库，接口不变。
"""
import json
import os
import threading
from datetime import datetime, timedelta, timezone

from mock_extractor import MATERIAL_TODO

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
STORE_PATH = os.path.join(DATA_DIR, "prepare_lists.json")
_LOCK = threading.Lock()
TZ = timezone(timedelta(hours=8))


def _action_for(material):
    name = material.get("material_name") or "材料"
    action = MATERIAL_TODO.get(name, "准备%s并检查是否符合要求" % name)
    if material.get("material_type") == "optional":
        action = "（选填）" + action
    return action


def build_prepare_list(matter, checked_material_ids=None):
    matter = matter or {}
    checked = {str(x) for x in (checked_material_ids or [])}
    materials = [m for m in (matter.get("materials") or []) if isinstance(m, dict)]

    missing_items, ready_items = [], []
    for m in materials:
        mid = str(m.get("material_id") or "")
        name = m.get("material_name") or "未命名材料"
        is_checked = (mid and mid in checked) or (name in checked)
        item = {
            "material_id": m.get("material_id"),
            "material_name": name,
            "material_type": m.get("material_type") or "unspecified",
        }
        if is_checked:
            ready_items.append(item)
        elif (m.get("material_type") or "required") == "optional":
            continue
        else:
            missing_items.append(item)

    todos = []
    for t in (matter.get("todo_list") or []):
        if not isinstance(t, dict) or not t.get("action"):
            continue
        item = {
            "todo_id": t.get("todo_id") or "todo_%d" % (len(todos) + 1),
            "action": t["action"],
            "status": t.get("status") or "pending",
            "source_ref": t.get("source_ref") or {},
        }
        for key in ("depends_on", "step_id", "material_id"):   # A 新版 todo 的可选字段
            if t.get(key):
                item[key] = t[key]
        todos.append(item)
    if not todos:
        for m in missing_items:
            todos.append({
                "todo_id": "todo_%d" % (len(todos) + 1),
                "action": _action_for(m),
                "status": "pending",
                "source_ref": {},
            })

    if not materials:
        summary = "该通知未要求提交材料，无需准备清单"
    elif missing_items:
        summary = "还有 %d 项材料要准备：%s" % (
            len(missing_items), "、".join(i["material_name"] for i in missing_items[:4]))
    else:
        summary = "材料已齐全，可以按清单逐项确认"

    return {
        "matter_id": matter.get("id"),
        "title": matter.get("title"),
        "todo_list": todos,
        "missing_items": missing_items,
        "ready_items": ready_items,
        "summary": summary,
    }


def save_prepare_list(matter_id, todo_list, checked_material_ids=None):
    if not matter_id:
        raise ValueError("matter_id 不能为空")
    if not isinstance(todo_list, list):
        raise ValueError("todo_list 必须是数组")

    with _LOCK:
        os.makedirs(DATA_DIR, exist_ok=True)
        data = {}
        if os.path.exists(STORE_PATH):
            try:
                with open(STORE_PATH, encoding="utf-8") as f:
                    data = json.load(f)
                if not isinstance(data, dict):
                    data = {}
            except Exception:
                data = {}
        record = {
            "matter_id": matter_id,
            "todo_list": todo_list,
            "checked_material_ids": list(checked_material_ids or []),
            "saved_at": datetime.now(TZ).isoformat(),
        }
        data[matter_id] = record
        tmp = STORE_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, STORE_PATH)
    return record


def load_prepare_list(matter_id):
    if not matter_id or not os.path.exists(STORE_PATH):
        return None
    try:
        with open(STORE_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return data.get(matter_id) if isinstance(data, dict) else None
    except Exception:
        return None