# -*- coding: utf-8 -*-
"""
离线 Mock 抽取（C 侧）：无 Key 时按【用户输入】用关键词 + 正则生成 Matter，
结构与 A 的输出对齐；确定性输出，不调用模型、不产生费用。
用于演示/联调，保证"输入什么就大致出什么"，而不是固定示例。
"""
import re
import uuid
from datetime import datetime, timedelta, timezone

TZ = timezone(timedelta(hours=8))

MATERIAL_RULES = [
    ("报名表", ("报名表",)),
    ("申报表", ("申报表", "申请表")),
    ("成绩单", ("成绩单",)),
    ("身份证复印件", ("身份证",)),
    ("作品演示视频", ("视频",)),
    ("项目说明文档", ("说明文档", "说明书", "PPT", "ppt", "演示文稿")),
    ("指导老师推荐意见", ("推荐意见", "推荐信", "推荐表")),
    ("作品原创性声明", ("原创性声明", "承诺书")),
    ("个人基本信息表", ("基本信息表", "信息表")),
    ("宣传海报设计图", ("海报",)),
    ("获奖证明", ("获奖", "证书")),
]
OPTIONAL_HINTS = ("选填", "可选", "如有", "非必须", "非必需", "自愿")
ACTION_RE = re.compile(r"(提交|发送|交至|上交|上传|报名(?!表)|填写|审核|审批|缴费|打印|答辩|"
                       r"签字|盖章|准备|参加|领取|确认|登录)")
CONDITION_HINTS = ("通过的项目", "通过后", "才能", "须先", "之后", "前置",
                   "取消资格", "后果自负", "未按时")
FILLER_PREFIX = ("大家", "请大家", "欢迎", "谢谢", "请各位", "各位同学", "同时请")
DEADLINE_HINTS = re.compile(r"(截止|前|提交|交至|发送|上传|报名(?!表)|打印)")
URGENT_WORDS = ("紧急", "立即", "最后期限", "不可延期")
HIGH_WORDS = ("务必", "尽快", "逾期")
LOCATION_RE = re.compile(r"(行政楼|办公楼|教学楼|实验楼|图书馆|会议室|报告厅|校区|\d+\s*室)")
DATE_RE = re.compile(r"(?:(\d{4})\s*年)?\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日"
                     r"(?:\s*(?:上午|下午|晚上)?\s*(\d{1,2})\s*[:：]\s*(\d{2}))?")
SECTIONS = {
    "simple": ["summary", "schedule", "source"],
    "standard": ["summary", "schedule", "content", "steps", "materials", "source"],
    "complex": ["summary", "schedule", "content", "steps", "materials", "warnings", "governance", "source"],
}


def _sentences(text):
    return [s.strip() for s in re.split(r"[。；;\n]", text) if s.strip()]


def _clauses(text):
    return [c.strip() for c in re.split(r"[，,、。；;\n]", text) if c.strip()]


def _sentence_at(text, pos):
    start = 0
    for m in re.finditer(r"[。；;\n]", text):
        if m.start() >= pos:
            return text[start:m.start()]
        start = m.end()
    return text[start:]


def _deadline(text):
    """选截止时间：优先"强截止语句"（截止/前/提交/交至/上交）里最早的日期；
    没有强提示时取全文最晚的日期（流程类通知通常以最后一步为整体截止）。"""
    now = datetime.now(TZ)
    years = re.findall(r"(20\d{2})\s*年", text)
    strong, all_items = [], []
    for m in DATE_RE.finditer(text):
        year, month, day, hour, minute = m.groups()
        y = int(year) if year else (int(years[0]) if years else now.year)
        try:
            dt = datetime(y, int(month), int(day),
                          int(hour) if hour else 23, int(minute) if minute else 59, tzinfo=TZ)
        except ValueError:
            continue
        if not year and not years and (now - dt).days > 30:
            try:
                dt = dt.replace(year=y + 1)
            except ValueError:
                pass
        sent = _sentence_at(text, m.start())
        item = (dt, m.group(0))
        all_items.append(item)
        if re.search(r"(截止|前|提交|交至|上交)", sent):
            strong.append(item)
    if strong:
        return min(strong, key=lambda x: x[0])
    if all_items:
        return max(all_items, key=lambda x: x[0])
    return None, ""


def _materials(text):
    out, seen = [], set()
    sents = _sentences(text)
    for name, keys in MATERIAL_RULES:
        hit = next((s for s in sents if any(k in s for k in keys)), None)
        if not hit or name in seen:
            continue
        seen.add(name)
        optional = any(k in hit for k in OPTIONAL_HINTS)
        out.append({
            "material_id": "mat_%d" % (len(out) + 1),
            "material_name": name,
            "material_type": "optional" if optional else "required",
            "required_by_source": not optional,
            "status": "pending",
            "status_desc": "未准备",
            "source_ref": {"quote": hit[:80]},
        })
    return out


def _steps(text, materials):
    keys_of = dict(MATERIAL_RULES)
    steps = []
    for clause in _clauses(text):
        if len(clause) < 4 or clause.startswith(FILLER_PREFIX) or "踊跃" in clause:
            continue
        if any(k in clause for k in CONDITION_HINTS):
            continue
        if not ACTION_RE.search(clause):
            continue
        title = clause
        title = re.sub(r"^[^：:]{2,24}[：:]", "", title)          # 去掉 "xx流程：" 前缀
        changed = True
        while changed:                      # 反复剥离，处理"各团队须于…"这种叠加前缀
            changed = False
            for prefix in ("请", "须", "需", "于", "各队", "各团队", "各位同学", "本次", "另外", "同时"):
                if title.startswith(prefix):
                    title = title[len(prefix):]
                    changed = True
        title = title.strip(" 《》：:，,")[:26]
        title = re.sub(r"(须于|需于|于)$", "", title).strip()
        if not title:
            continue
        if any(title in s["title"] or s["title"] in title for s in steps):   # 去重
            continue
        ids = [m["material_id"] for m in materials
               if any(k in clause for k in keys_of.get(m["material_name"], ()))]
        step = {
            "step_id": "step_%d" % (len(steps) + 1),
            "order": len(steps) + 1,
            "title": title,
            "status": "not_started",
            "source_ref": {"quote": clause[:80]},
        }
        if ids:
            step["materials"] = ids
        steps.append(step)
        if len(steps) >= 6:
            break
    return steps


def _title(text):
    s = (_sentences(text) or ["通知事项"])[0].strip()
    m = re.search(r"关于(.+?)(?:的通知|通知)", s)
    if m:
        t = re.sub(r"^(开展|举办|组织)", "", m.group(1)).strip()
        if t:
            return t[:20]
    if "：" in s:
        head = s.split("：")[0].strip()
        if 2 <= len(head) <= 14:
            return head
    if "前" in s:
        tail = s.split("前", 1)[1].strip(" ，,：:")
        if len(tail) >= 4:
            return tail[:20]
    return s[:20]


def _priority(text):
    if any(w in text for w in URGENT_WORDS):
        return "urgent"
    if any(w in text for w in HIGH_WORDS):
        return "high"
    return "medium"


def _mode(text, deadline, materials, steps):
    f = []
    if deadline:
        f.append("has_deadline")
    if len(materials) >= 2 or "材料" in text:
        f.append("has_materials")
    if len(steps) >= 2:
        f.append("has_multiple_steps")
    if LOCATION_RE.search(text):
        f.append("has_location")
    if any(w in text for w in ("审核", "审批", "答辩", "复审", "初审")):
        f.append("has_review")
    if any(w in text for w in ("通过后", "之后", "才能", "须先", "前置")):
        f.append("has_dependencies")
    if "附件" in text:
        f.append("has_attachments")
    if any(w in text for w in ("老师", "负责人", "学院", "团队")):
        f.append("has_people")
    score = round(0.2 * ("has_deadline" in f) + 0.2 * ("has_multiple_steps" in f)
                  + 0.2 * ("has_materials" in f) + 0.1 * ("has_review" in f)
                  + 0.1 * ("has_dependencies" in f), 3)
    if ("has_review" in f) or ("has_dependencies" in f):
        return "complex", score, f
    if score < 0.3:
        return "simple", score, f
    if score <= 0.6:
        return "standard", score, f
    return "complex", score, f


def mock_extract(text: str) -> dict:
    source = (text or "").strip()
    deadline, phrase = _deadline(source)
    materials = _materials(source)
    steps = _steps(source, materials)
    mode, score, features = _mode(source, deadline, materials, steps)
    now = datetime.now(TZ).isoformat()

    data = {
        "schema_version": "1.0",
        "id": "matter_mock_" + uuid.uuid4().hex[:8],
        "mode": mode,
        "mode_source": "mock",
        "mock": True,
        "complexity_score": score,
        "detected_features": features,
        "enabled_sections": SECTIONS[mode],
        "title": _title(source),
        "priority": _priority(source),
        "status": "not_started",
        "status_source": "auto",
        "timezone": "Asia/Shanghai",
        "created_at": now,
        "updated_at": now,
        "sources": [{"quote": source[:160]}],
    }
    if deadline:
        data["deadline"] = {
            "scope": "overall", "label": "截止时间", "due_at": deadline.isoformat(),
            "all_day": not bool(re.search(r"\d{1,2}\s*[:：]\s*\d{2}", phrase)),
            "source_ref": {"quote": phrase},
        }
        data["reminders"] = [{"reminder_id": "rem_1", "offset_minutes": 120,
                              "channels": ["app"], "enabled": True}]
    if mode != "simple":
        if materials:
            data["materials"] = materials
        if steps:
            data["step_list"] = steps
        loc = LOCATION_RE.search(source)
        if loc:
            data["default_location"] = {"name": loc.group(1)}
    if mode == "complex" and not deadline:
        data["warning_list"] = [{
            "warning_id": "warn_" + uuid.uuid4().hex[:6],
            "warning_type": "missing_information", "severity": "high",
            "message": "通知原文未提及明确的截止时间，请手动确认",
        }]
    return data