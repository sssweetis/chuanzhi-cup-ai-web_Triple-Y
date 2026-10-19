# -*- coding: utf-8 -*-
"""
用户情况核对 / 缺项核对（C 负责 · 对应 10/18 里程碑「增加用户情况核对」）

职责边界（重要）：
    · 只做「确定性比对」，不调用大模型、不修改 A 的抽取逻辑与任何字段命名
    · 输入 = A 的 Matter JSON（/api/analyze 的 data）+ 用户勾选状态 + 用户自述情况
    · 输出 = 还缺什么、什么需要用户去确认，供前端高亮展示

三类结果：
    1. missing_required / missing_optional / unchecked_unspecified
       材料清单 与 用户勾选 的差集（必交 / 可选 / 原文未明确是否必交）
    2. need_confirm
       原文没写清、需要用户向发布方确认的（例如没有识别到截止时间）
    3. profile_issues
       用户自述情况与原文要求的冲突（例如原文要视频，用户说没有）

    ⚠️ profile 的判定规则表（DEFAULT_PROFILE_CHECKS）是 C 侧的兜底实现。
       A 定稿核对规则后，只需要替换规则表或由前端传 profile_checks，不必改这里的代码结构。
"""

from typing import Any, Dict, List, Optional

# 视为「还没准备」的取值（字符串会去空格后比较，"" 也视为未准备）
NOT_READY_VALUES = (
    False, None, 0, "0", "", "false", "False", "no", "No", "NO",
    "无", "没有", "否", "未准备", "未办", "还没", "未完成",
)

# 用户自述字段 -> 缺项提示 的规则表（请求里的 profile_checks 可覆盖/扩展它）
DEFAULT_PROFILE_CHECKS: List[Dict[str, Any]] = [
    {
        "key": "has_video",
        "label": "视频材料",
        "keywords": ["视频"],
        "message": "原文要求提交视频，你说还没准备",
    },
    {
        "key": "has_photo",
        "label": "证件照",
        "keywords": ["证件照", "照片", "一寸", "二寸"],
        "message": "原文要求证件照，你说还没准备",
    },
    {
        "key": "has_recommendation",
        "label": "推荐信",
        "keywords": ["推荐信", "推荐表"],
        "message": "原文要求推荐信，你说还没准备",
    },
    {
        "key": "has_signature",
        "label": "签字 / 盖章",
        "keywords": ["签字", "签名", "盖章", "公章"],
        "message": "原文要求签字或盖章，你说还没办",
    },
]


def _norm(text: Any) -> str:
    """去掉所有空白字符，便于中文关键词匹配。"""
    return "".join(str(text or "").split())


def _not_ready(value: Any) -> bool:
    """判断用户自述的某个情况是否等于「还没准备」。"""
    if isinstance(value, str):
        return value.strip() in [str(v) for v in NOT_READY_VALUES] or value.strip() == ""
    for item in NOT_READY_VALUES:
        if isinstance(item, bool) and isinstance(value, bool) and item == value:
            return True
        if not isinstance(item, bool) and item is not None and value == item:
            return True
    return value is None


def _material_view(m: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "material_id": m.get("material_id"),
        "material_name": m.get("material_name") or m.get("name") or "未命名材料",
        "material_type": (m.get("material_type") or "unspecified"),
        "required_by_source": bool(m.get("required_by_source")),
    }


def _is_required(m: Dict[str, Any]) -> bool:
    if m.get("required_by_source"):
        return True
    return str(m.get("material_type") or "").strip().lower() == "required"


def build_corpus(matter: Dict[str, Any], notice_text: str = "") -> str:
    """把 Matter 里能体现「原文说过什么」的文字拼起来，用于关键词判断。"""
    parts: List[str] = [notice_text, matter.get("title"), matter.get("category"), matter.get("target")]
    for kp in matter.get("key_points") or []:
        parts.append(kp)
    for s in matter.get("sources") or []:
        if isinstance(s, dict):
            parts.append(s.get("quote"))
    deadline = matter.get("deadline")
    if isinstance(deadline, dict):
        parts.append((deadline.get("source_ref") or {}).get("quote"))
        parts.append(deadline.get("label"))
    for m in matter.get("materials") or []:
        if isinstance(m, dict):
            parts.append(m.get("material_name"))
            parts.append(m.get("material_desc"))
            parts.append((m.get("source_ref") or {}).get("quote"))
    for st in matter.get("step_list") or []:
        if isinstance(st, dict):
            parts.append(st.get("title"))
            parts.append(st.get("desc"))
    for kw in matter.get("warning_list") or []:
        if isinstance(kw, dict):
            parts.append(kw.get("message"))
    return _norm(" ".join(str(p) for p in parts if p))


def check_requirements(
    matter: Dict[str, Any],
    checked_material_ids: Optional[List[str]] = None,
    profile: Optional[Dict[str, Any]] = None,
    profile_checks: Optional[List[Dict[str, Any]]] = None,
    notice_text: str = "",
) -> Dict[str, Any]:
    """
    参数：
        matter                : /api/analyze 返回的 data（Matter JSON）
        checked_material_ids  : 用户勾选「已准备好」的材料 ID（也接受材料名，容错）
        profile               : 用户自述情况，如 {"has_video": false, "people_count": 3}
        profile_checks        : 自定义规则表（不传就用 DEFAULT_PROFILE_CHECKS）
        notice_text           : 通知原文（可选，用于关键词判断；传了更准）

    返回：缺项核对结果字典（可直接放在接口 data 里给前端）
    """
    matter = matter or {}
    materials = [m for m in (matter.get("materials") or []) if isinstance(m, dict)]
    checked_raw = {str(x).strip() for x in (checked_material_ids or []) if str(x).strip()}

    checked: List[Dict[str, Any]] = []
    missing_required: List[Dict[str, Any]] = []
    missing_optional: List[Dict[str, Any]] = []
    unchecked_unspecified: List[Dict[str, Any]] = []
    need_confirm: List[Dict[str, Any]] = []

    for m in materials:
        view = _material_view(m)
        is_checked = (str(view["material_id"]) in checked_raw) or (str(view["material_name"]) in checked_raw)
        if is_checked:
            checked.append(view)
        elif _is_required(m):
            missing_required.append(view)
        elif str(view["material_type"]).strip().lower() == "optional":
            missing_optional.append(view)
        else:
            unchecked_unspecified.append(view)
            need_confirm.append({
                "item": "材料「%s」是否必交" % view["material_name"],
                "reason": "原文没有明确这项材料是否必须提交，建议向发布方确认",
            })

    if not matter.get("deadline"):
        need_confirm.append({
            "item": "截止时间",
            "reason": "原文未识别到明确截止时间，建议向发布方确认",
        })

    # ---- 用户自述情况核对 ----
    rules = profile_checks if profile_checks else DEFAULT_PROFILE_CHECKS
    corpus = build_corpus(matter, notice_text)
    profile_issues: List[Dict[str, Any]] = []
    for rule in (rules or []):
        if not isinstance(rule, dict):
            continue
        key = str(rule.get("key") or "").strip()
        if not key or key not in (profile or {}):
            continue
        if not _not_ready((profile or {}).get(key)):
            continue
        keywords = [str(k) for k in (rule.get("keywords") or []) if str(k).strip()]
        hit = (not keywords) or any(_norm(k) in corpus for k in keywords)
        if hit:
            profile_issues.append({
                "key": key,
                "label": rule.get("label") or key,
                "message": rule.get("message") or ("原文相关要求：%s，你说还没准备" % (rule.get("label") or key)),
            })

    required_total = len(missing_required) + len(checked)
    ready_ratio = 1.0 if required_total == 0 else round(len(checked) / required_total, 3)
    ready = (not missing_required) and (not profile_issues)

    # ---- 一句话结论 ----
    if not materials and str(matter.get("mode") or "") == "simple":
        summary = "该通知未要求提交材料，无需核对清单"
    elif missing_required:
        names = "、".join(v["material_name"] for v in missing_required[:4])
        more = "" if len(missing_required) <= 4 else "…等 %d 项" % len(missing_required)
        summary = "还缺 %d 项必交材料：%s%s" % (len(missing_required), names, more)
        if profile_issues:
            summary += "；另有 %d 项自述情况与原文要求不符" % len(profile_issues)
    elif profile_issues:
        summary = "%d 项自述情况与原文要求不符：%s" % (
            len(profile_issues), "、".join(i["label"] for i in profile_issues[:4]))
    else:
        summary = "必交材料已齐全"
        if missing_optional:
            summary += "；另有 %d 项可选材料未勾选" % len(missing_optional)
        elif unchecked_unspecified:
            summary += "；有 %d 项材料原文未明确是否必交" % len(unchecked_unspecified)
    if need_confirm and not missing_required and "需要确认" not in summary:
        summary += "；%d 项信息需要确认" % len(need_confirm)

    return {
        "mode": matter.get("mode"),
        "required_total": required_total,
        "checked": checked,
        "missing_required": missing_required,
        "missing_optional": missing_optional,
        "unchecked_unspecified": unchecked_unspecified,
        "need_confirm": need_confirm,
        "profile_issues": profile_issues,
        "ready": ready,
        "ready_ratio": ready_ratio,
        "summary": summary,
    }