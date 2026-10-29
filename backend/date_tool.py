# -*- coding: utf-8 -*-
"""日期核对工具（C 侧，10/30）：判断星期、距今、周末与常见法定节假日。"""
from datetime import date, datetime, timedelta, timezone

TZ = timezone(timedelta(hours=8))
WEEKDAYS = ("周一", "周二", "周三", "周四", "周五", "周六", "周日")

# 固定日期的法定休假日段（不包含每年可能调整的调休工作日）。
# 比赛演示用于提示风险，最终仍应以学校/单位当年通知为准。
FIXED_HOLIDAY_RANGES = (
    ((1, 1), (1, 1), "元旦"),
    ((5, 1), (5, 5), "劳动节"),
    ((10, 1), (10, 7), "国庆节"),
)


def _today() -> date:
    return datetime.now(TZ).date()


def parse_date(value: str) -> date:
    if value is None or not str(value).strip():
        raise ValueError("日期不能为空")
    raw = str(value).strip()
    normalized = raw.replace("/", "-").replace(".", "-")
    try:
        if "T" in normalized or " " in normalized:
            dt = datetime.fromisoformat(normalized.replace("Z", "+00:00"))
            if dt.tzinfo is not None:
                dt = dt.astimezone(TZ)
            return dt.date()
        return date.fromisoformat(normalized[:10])
    except (TypeError, ValueError):
        raise ValueError("日期格式应为 YYYY-MM-DD，例如 2026-11-02")


def _holiday_name(day: date):
    md = (day.month, day.day)
    for start, end, name in FIXED_HOLIDAY_RANGES:
        if start <= md <= end:
            return name
    return None


def check_date(value: str, today: date = None) -> dict:
    target = parse_date(value)
    base = today or _today()
    days_left = (target - base).days
    weekday_index = target.weekday()
    weekend = weekday_index >= 5
    holiday_name = _holiday_name(target)
    is_holiday = weekend or bool(holiday_name)

    if days_left < 0:
        deadline_label = "已过期 %d 天" % abs(days_left)
    elif days_left == 0:
        deadline_label = "今天到期"
    else:
        deadline_label = "还剩 %d 天" % days_left

    return {
        "date": target.isoformat(),
        "weekday": WEEKDAYS[weekday_index],
        "weekday_index": weekday_index + 1,
        "days_left": days_left,
        "deadline_label": deadline_label,
        "is_weekend": weekend,
        "is_holiday": is_holiday,
        "holiday_name": holiday_name,
        "is_workday": not is_holiday,
        "needs_manual_confirmation": is_holiday,
        "note": "周末/节假日遇到调休时，请以学校或单位当年通知为准。",
    }
