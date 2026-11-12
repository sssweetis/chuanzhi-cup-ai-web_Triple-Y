# -*- coding: utf-8 -*-
"""生成 A2 评测集（全部写在 D 盘 docs/eval-v2 下）。

不写 C 盘；图片使用系统字体只读，PDF 用 PyMuPDF 生成。
运行：python docs/eval-v2/generate_cases.py
"""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
import fitz

HERE = Path(__file__).resolve().parent
ASSETS = HERE / "assets"
ASSETS.mkdir(parents=True, exist_ok=True)


def _font(size=26):
    for p in (
        r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\simhei.ttf",
        r"C:\Windows\Fonts\simsun.ttc",
    ):
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            continue
    return ImageFont.load_default()


def make_image(name: str, title: str, lines: list[str]):
    img = Image.new("RGB", (1100, 720), "white")
    d = ImageDraw.Draw(img)
    font_title = _font(34)
    font_body = _font(25)
    d.rectangle([25, 25, 1075, 695], outline="#888", width=2)
    d.text((60, 60), title, fill="#111", font=font_title)
    y = 135
    for line in lines:
        d.text((60, y), line, fill="#222", font=font_body)
        y += 52
    img.save(ASSETS / name)


def make_pdf(name: str, title: str, lines: list[str]):
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    y = 70
    page.insert_text((60, y), title, fontsize=18, fontname="china-s")
    y += 35
    for line in lines:
        page.insert_textbox(fitz.Rect(60, y, 535, y + 55), line,
                            fontsize=12, fontname="china-s", lineheight=1.2)
        y += 52
    doc.save(ASSETS / name)
    doc.close()


TEXT_CASES = [
    {
        "id": "T01",
        "text": "请于2026年11月20日18:00前提交奖学金报名表和成绩单，逾期不再受理。",
        "expect": {"title": ["奖学金"], "deadline": "2026-11-20", "materials": ["报名表", "成绩单"], "min_steps": 1},
    },
    {
        "id": "T02",
        "text": "关于开展2026年社会实践活动的通知：请各团队于11月18日17:00前提交项目申报书、安全承诺书和成员名单。学院审核通过后，于11月25日前完成立项缴费。",
        "expect": {"title": ["社会实践"], "deadline": "2026-11-18", "materials": ["申报书", "安全承诺书", "成员名单"], "min_steps": 2},
    },
    {
        "id": "T03",
        "text": "2026年校园创新挑战赛报名：请于12月1日12:00前提交报名表、项目说明书和3分钟演示视频。大一学生还需提交高考成绩单；大二及以上学生提交上一学年成绩单。",
        "expect": {"title": ["创新", "挑战赛"], "deadline": "2026-12-01", "materials": ["报名表", "项目说明书", "视频"], "min_steps": 1},
    },
    {
        "id": "T04",
        "text": "请于11月30日前将身份证复印件交到学院办公室A203，联系人王老师。材料不齐者不予办理。",
        "expect": {"title": ["身份证", "材料"], "deadline": "2026-11-30", "materials": ["身份证"], "min_steps": 1},
    },
    {
        "id": "T05",
        "text": "关于国家助学金申请的通知：请于11月22日18:00前提交申请表、家庭经济困难证明和成绩单。获奖证书为选填材料，可一并提交。",
        "expect": {"title": ["助学金"], "deadline": "2026-11-22", "materials": ["申请表", "困难证明", "成绩单"], "min_steps": 1},
    },
    {
        "id": "T06",
        "text": "请于2026年12月5日17:00前提交社团活动立项表。审核通过后，于12月8日前到财务处缴纳场地费；未按时缴费视为放弃。",
        "expect": {"title": ["社团", "立项"], "deadline": "2026-12-05", "materials": ["立项表"], "min_steps": 2},
    },
    {
        "id": "T07",
        "text": "请于2026年11月28日18:00前提交报名表；学院初审通过后，于12月2日前提交纸质版材料，最后于12月5日前完成最终报名。",
        "expect": {"title": ["报名"], "deadline": "2026-12-05", "materials": ["报名表", "纸质版"], "min_steps": 3},
    },
    {
        "id": "T08",
        "text": "请于2026年12月10日17:00前提交项目总结报告和经费使用明细。逾期不候。",
        "expect": {"title": ["总结", "经费"], "deadline": "2026-12-10", "materials": ["总结报告", "经费"], "min_steps": 1},
    },
    {
        "id": "T09",
        "text": "请于2026年11月19日12:00前提交电子版报名表，文件命名为“姓名-学号-报名表”，发送至 student@example.com。",
        "expect": {"title": ["报名"], "deadline": "2026-11-19", "materials": ["报名表"], "min_steps": 1},
    },
    {
        "id": "T10",
        "text": "请于2026年12月15日前提交纸质版申请书、身份证复印件和两张一寸照片。材料交至行政楼302。",
        "expect": {"title": ["申请", "材料"], "deadline": "2026-12-15", "materials": ["申请", "身份证", "照片"], "min_steps": 1},
    },
]

IMAGE_CASES = [
    ("I01", "奖学金申请提醒", ["截止时间：2026年11月21日18:00", "提交材料：报名表、成绩单", "提交地点：学院办公室"]),
    ("I02", "社团活动报名", ["请于12月3日17:00前提交活动方案", "材料：活动方案、安全承诺书", "审核通过后缴费"]),
    ("I03", "证件办理通知", ["请于11月26日前提交身份证复印件", "地点：行政楼一楼", "联系人：李老师"]),
    ("I04", "竞赛材料提交", ["截止：2026年12月6日12:00", "材料：报名表、项目说明书、演示视频", "逾期不候"]),
]

PDF_CASES = [
    ("P01", "奖学金评审通知", ["请于2026年11月20日18:00前提交报名表、成绩单和身份证复印件。", "材料交至学院办公室A203。"]),
    ("P02", "社会实践立项通知", ["请于2026年11月24日17:00前提交项目申报书和安全承诺书。", "学院审核通过后，于11月28日前完成缴费。"]),
    ("P03", "竞赛报名通知", ["请于2026年12月2日12:00前提交报名表和项目说明书。", "演示视频为选填材料，时长不超过3分钟。"]),
]

ASSET_EXPECT = {
    "I01": {"title": ["奖学金"], "deadline": "2026-11-21", "materials": ["报名表", "成绩单"], "min_steps": 1},
    "I02": {"title": ["社团"], "deadline": "2026-12-03", "materials": ["活动方案", "安全承诺书"], "min_steps": 1},
    "I03": {"title": ["证件", "身份证"], "deadline": "2026-11-26", "materials": ["身份证"], "min_steps": 1},
    "I04": {"title": ["竞赛"], "deadline": "2026-12-06", "materials": ["报名表", "项目说明书", "视频"], "min_steps": 1},
    "P01": {"title": ["奖学金"], "deadline": "2026-11-20", "materials": ["报名表", "成绩单", "身份证"], "min_steps": 1},
    "P02": {"title": ["社会实践", "立项"], "deadline": "2026-11-24", "materials": ["申报书", "安全承诺书"], "min_steps": 1},
    "P03": {"title": ["竞赛", "报名"], "deadline": "2026-12-02", "materials": ["报名表", "项目说明书"], "min_steps": 1},
}

COMPARE_CASES = [
    {
        "id": "C01",
        "left": "请于2026年11月20日18:00前提交报名表和成绩单。",
        "right": "补充通知：截止时间改为2026年11月22日18:00，另需提交身份证复印件。以此为准。",
        "expect": {"deadline": "2026-11-22", "new_material": "身份证"},
    },
    {
        "id": "C02",
        "left": "请于2026年11月25日17:00前提交项目申报书。",
        "right": "补充通知：申报书提交时间延长至2026年11月28日17:00，其他要求不变。",
        "expect": {"deadline": "2026-11-28", "new_material": None},
    },
    {
        "id": "C03",
        "left": "请于2026年12月1日前提交报名表、成绩单和推荐信。",
        "right": "补充通知：推荐信不再要求提交；新增安全承诺书。截止时间不变。",
        "expect": {"deadline": "2026-12-01", "new_material": "安全承诺书"},
    },
]

RAG_DOCS = [
    {
        "doc_name": "奖学金通知",
        "text": "请于2026年11月20日18:00前提交报名表、成绩单和身份证复印件。推荐信为选填材料。材料交至学院办公室A203。",
    },
    {
        "doc_name": "视频要求",
        "text": "申请者还需提交一段不超过3分钟的介绍视频，格式为MP4，画面清晰，文件大小不超过100MB。",
    },
    {
        "doc_name": "缴费与审核",
        "text": "学院初审通过后缴纳报名费100元；缴费成功后打印准考证。审核未通过者无需缴费。",
    },
    {
        "doc_name": "安全承诺",
        "text": "社会实践团队须提交安全承诺书，并由指导老师签字；活动期间每日报备安全情况。",
    },
]

RAG_QUESTIONS = [
    ("R01", "视频有什么要求", "视频", False),
    ("R02", "材料交到哪里", "A203", False),
    ("R03", "报名费多少钱", "100", False),
    ("R04", "推荐信是必交吗", "选填", False),
    ("R05", "成绩单需要吗", "成绩单", False),
    ("R06", "审核通过后做什么", "缴费", False),
    ("R07", "安全承诺书谁签字", "指导老师", False),
    ("R08", "视频格式是什么", "MP4", False),
    ("R09", "活动期间要报备吗", "报备", False),
    ("R10", "准考证什么时候打印", "缴费", False),
    ("R11", "食堂几点开门", None, True),
    ("R12", "宿舍怎么申请", None, True),
    ("R13", "图书馆开放时间", None, True),
    ("R14", "校车路线", None, True),
    ("R15", "网络密码是多少", None, True),
]


def main():
    # 文本 case
    (HERE / "cases.json").write_text(json.dumps({
        "text_cases": TEXT_CASES,
        "image_cases": [
            {"id": i, "path": f"assets/{i}.png", "expect": ASSET_EXPECT[i]}
            for i, _title, _lines in IMAGE_CASES
        ],
        "pdf_cases": [
            {"id": i, "path": f"assets/{i}.pdf", "expect": ASSET_EXPECT[i]}
            for i, _title, _lines in PDF_CASES
        ],
        "compare_cases": COMPARE_CASES,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    (HERE / "rag_questions.json").write_text(json.dumps({
        "docs": RAG_DOCS,
        "questions": [{"id": i, "query": q, "expect": e, "out_of_scope": o}
                      for i, q, e, o in RAG_QUESTIONS],
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    for i, title, lines in IMAGE_CASES:
        make_image(f"{i}.png", title, lines)
    for i, title, lines in PDF_CASES:
        make_pdf(f"{i}.pdf", title, lines)

    print("generated", HERE / "cases.json")
    print("generated", HERE / "rag_questions.json")
    print("assets", len(list(ASSETS.iterdir())))


if __name__ == "__main__":
    main()
