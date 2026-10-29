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


def _grade_level(profile):
    profile = profile or {}
    for key in ("grade", "grade_level", "student_type", "year"):
        value = str(profile.get(key) or "").strip().lower()
        if not value:
            continue
        if "大一" in value or "freshman" in value or value in ("1", "一"):
            return 1
        if "大二" in value or "sophomore" in value or value in ("2", "二"):
            return 2
        if "大三" in value or "junior" in value or value in ("3", "三"):
            return 3
        if "大四" in value or "senior" in value or value in ("4", "四"):
            return 4
        if "研究生" in value or "硕士" in value or "博士" in value or "graduate" in value:
            return 5
    return None


def _condition_status(condition, profile):
    text = "".join(str(condition or "").split())
    if not text:
        return True
    level = _grade_level(profile)
    if level is None:
        return None
    if "大一" in text or "新生" in text:
        return level == 1
    if "大二" in text or "及以上" in text:
        return level >= 2
    return None


def build_prepare_list(matter, checked_material_ids=None, profile=None):
    matter = matter or {}
    checked = {str(x) for x in (checked_material_ids or [])}
    materials = [m for m in (matter.get("materials") or []) if isinstance(m, dict)]

    missing_items, ready_items, need_confirm = [], [], []
    for m in materials:
        mid = str(m.get("material_id") or "")
        name = m.get("material_name") or "未命名材料"
        is_checked = (mid and mid in checked) or (name in checked)
        item = {
            "material_id": m.get("material_id"),
            "material_name": name,
            "material_type": m.get("material_type") or "unspecified",
            "condition": m.get("condition"),
        }
        condition_status = _condition_status(m.get("condition"), profile)
        if condition_status is False:
            continue
        if condition_status is None and not is_checked:
            need_confirm.append(item)
            continue
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

    # 用勾选状态联动待办：绑定材料已勾选 → completed；依赖全部完成 → 解除 blocked
    done_ids = set()
    for t in todos:
        mid = str(t.get("material_id") or "")
        if mid and (mid in checked or (t.get("action") or "") in checked):
            t["status"] = "completed"
            done_ids.add(t.get("todo_id"))
    for t in todos:
        deps = t.get("depends_on") or []
        if t.get("status") == "blocked" and deps:
            all_done = all((d in done_ids) or any(x.get("todo_id") == d and x.get("status") == "completed" for x in todos) for d in deps)
            if all_done:
                t["status"] = "pending"

    if not materials:
        summary = "该通知未要求提交材料，无需准备清单"
    elif missing_items:
        summary = "还有 %d 项材料要准备：%s" % (
            len(missing_items), "、".join(i["material_name"] for i in missing_items[:4]))
        if need_confirm:
            summary += "；另有 %d 项条件材料需确认年级" % len(need_confirm)
    elif need_confirm:
        summary = "有 %d 项条件材料需确认年级：%s" % (
            len(need_confirm), "、".join(i["material_name"] for i in need_confirm[:4]))
    else:
        summary = "材料已齐全，可以按清单逐项确认"

    return {
        "matter_id": matter.get("id"),
        "title": matter.get("title"),
        "todo_list": todos,
        "missing_items": missing_items,
        "ready_items": ready_items,
        "need_confirm": need_confirm,
        "summary": summary,
    }


def _key(session_id, matter_id):
    return matter_id if (session_id or "default") == "default" else "%s:%s" % (session_id, matter_id)


def _load_all():
    if not os.path.exists(STORE_PATH):
        return {}
    try:
        with open(STORE_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _write_all(data):
    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = STORE_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, STORE_PATH)


def save_prepare_list(matter_id, todo_list, checked_material_ids=None, session_id="default", title=None):
    """保存当前版本，并把修改前版本写入 history（最多保留最近 5 版）。"""
    if not matter_id:
        raise ValueError("matter_id 不能为空")
    if not isinstance(todo_list, list):
        raise ValueError("todo_list 必须是数组")

    owner = session_id or "default"
    with _LOCK:
        data = _load_all()
        key = _key(owner, matter_id)
        old = data.get(key) or {}
        history = list(old.get("history") or [])
        previous_todo_list = []
        if old:
            previous_todo_list = list(old.get("todo_list") or [])
            history.append({
                "version": old.get("version", len(history) + 1),
                "todo_list": previous_todo_list,
                "checked_material_ids": list(old.get("checked_material_ids") or []),
                "saved_at": old.get("saved_at"),
            })
            history = history[-5:]
        version = int(old.get("version") or 0) + 1
        record = {
            "matter_id": matter_id,
            "session_id": owner,
            "title": old.get("title") or title,
            "todo_list": todo_list,
            "previous_todo_list": previous_todo_list,
            "history": history,
            "version": version,
            "checked_material_ids": list(checked_material_ids or []),
            "saved_at": datetime.now(TZ).isoformat(),
        }
        data[key] = record
        _write_all(data)
    return record


def load_prepare_list(matter_id, session_id="default"):
    if not matter_id:
        return None
    owner = session_id or "default"
    try:
        with open(STORE_PATH, encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    record = data.get(_key(owner, matter_id))
    if not record or (record.get("session_id") or "default") != owner:
        return None
    return record


def load_prepare_list_history(matter_id, session_id="default"):
    record = load_prepare_list(matter_id, session_id)
    if not record:
        return None
    return {
        "matter_id": matter_id,
        "version": record.get("version", 1),
        "saved_at": record.get("saved_at"),
        "previous_todo_list": record.get("previous_todo_list") or [],
        "history": record.get("history") or [],
    }


def load_latest_prepare_list(session_id="default"):
    """返回当前会话最近保存的一份清单，供 /api/export 无 matter_id 时使用。"""
    owner = session_id or "default"
    try:
        with open(STORE_PATH, encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    records = [r for r in data.values() if isinstance(r, dict)
               and (r.get("session_id") or "default") == owner]
    if not records:
        return None
    return max(records, key=lambda r: r.get("saved_at") or "")


def delete_prepare_list(matter_id, session_id="default"):
    if not matter_id:
        return False
    owner = session_id or "default"
    with _LOCK:
        data = _load_all()
        key = _key(owner, matter_id)
        record = data.get(key)
        if not record or (record.get("session_id") or "default") != owner:
            return False
        del data[key]
        _write_all(data)
    return True
