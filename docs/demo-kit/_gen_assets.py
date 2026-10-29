# -*- coding: utf-8 -*-
"""生成演示用截图与文字型 PDF"""
import os
from PIL import Image, ImageDraw, ImageFont

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)))
TEXT = "通知：请于11月2日17:00前提交报名表和成绩单，交至行政楼305。"

def font_path(size):
    for p in (r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\simhei.ttf", r"C:\Windows\Fonts\simsun.ttc"):
        if os.path.exists(p):
            return ImageFont.truetype(p, size), p
    return ImageFont.load_default(), None

font, used = font_path(40)
img = Image.new("RGB", (1400, 240), "white")
d = ImageDraw.Draw(img)
d.rectangle([20, 20, 1380, 220], outline="#dddddd")
d.text((45, 90), TEXT, font=font, fill="black")
img.save(os.path.join(OUT, "04-通知截图.png"))
print("截图已生成，字体:", used)

# 文字型 PDF（中文）
try:
    from reportlab.pdfgen import canvas
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib.pagesizes import A4

    used_ttf = None
    for idx, p in enumerate((r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\simhei.ttf")):
        try:
            pdfmetrics.registerFont(TTFont("CNFont", p))
            used_ttf = p
            break
        except Exception as e:
            print("注册字体失败:", p, e)
    if not used_ttf:
        raise RuntimeError("没有可用的中文字体")

    path = os.path.join(OUT, "05-文字型通知.pdf")
    c = canvas.Canvas(path, pagesize=A4)
    c.setFont("CNFont", 14)
    lines = [
        "关于开展2026年度校级奖学金申报工作的通知",
        "",
        "各位同学：",
        "请于11月10日18:00前提交《奖学金申请表》（附件1）、成绩单和",
        "身份证复印件，交至行政楼302办公室，需本人签字。",
        "学院将于11月12日至11月14日完成材料审核。",
    ]
    y = 760
    for line in lines:
        c.drawString(60, y, line)
        y -= 26
    c.save()
    print("PDF 已生成，字体:", used_ttf)
except Exception as e:
    print("PDF 生成失败:", e)