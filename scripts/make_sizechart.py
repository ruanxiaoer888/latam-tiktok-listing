# -*- coding: utf-8 -*-
"""生成一张干净的西语尺码表 PNG（给 TikTok 尺码表识别用）。"""
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path

OUT = Path(r"D:\Michael\DSHProjects\listing-pipeline\output\批次20261022-AXNJC\尺码表-AXNJCPS300.png")
W, H = 1500, 940
img = Image.new("RGB", (W, H), "white")
d = ImageDraw.Draw(img)

FONT_DIR = Path(r"C:\Windows\Fonts")
f_title = ImageFont.truetype(str(FONT_DIR / "arialbd.ttf"), 46)
f_head = ImageFont.truetype(str(FONT_DIR / "arialbd.ttf"), 26)
f_cell = ImageFont.truetype(str(FONT_DIR / "arial.ttf"), 30)
f_note = ImageFont.truetype(str(FONT_DIR / "arial.ttf"), 24)

rows = [
    ("S", "92", "37", "57", "79"),
    ("M", "96", "38", "58", "80"),
    ("L", "100", "39", "59", "81"),
    ("XL", "104", "40", "60", "82"),
    ("2XL", "108", "41", "61", "83"),
]
headers = ["Talla", "Contorno de\npecho (cm)", "Ancho de\nhombros (cm)", "Largo de\nmanga (cm)", "Largo de la\nprenda (cm)"]
col_w = [180, 330, 320, 300, 320]
row_h = 92
head_h = 100
x0 = (W - sum(col_w)) // 2
y0 = 110


def center(text, box, font, fill="black"):
    x1, y1, x2, y2 = box
    lines = text.split("\n")
    heights = [d.textbbox((0, 0), ln, font=font)[3] for ln in lines]
    total = sum(heights) + (len(lines) - 1) * 8
    y = y1 + (y2 - y1 - total) / 2
    for ln, h in zip(lines, heights):
        tw = d.textbbox((0, 0), ln, font=font)[2]
        d.text((x1 + (x2 - x1 - tw) / 2, y), ln, font=font, fill=fill)
        y += h + 8


d.text(((W - d.textbbox((0, 0), "Guía de medidas", font=f_title)[2]) / 2, 28), "Guía de medidas", font=f_title, fill="black")

# 表头
x = x0
for text, cw in zip(headers, col_w):
    d.rectangle([x, y0, x + cw, y0 + head_h], outline="black", width=3, fill="#eeeeee")
    center(text, (x, y0, x + cw, y0 + head_h), f_head)
    x += cw

# 数据行
for i, row in enumerate(rows):
    y1 = y0 + head_h + i * row_h
    x = x0
    for text, cw in zip(row, col_w):
        d.rectangle([x, y1, x + cw, y1 + row_h], outline="black", width=2)
        center(text, (x, y1, x + cw, y1 + row_h), f_cell)
        x += cw

note = "Medidas en centímetros. Margen de error: 1-2 cm."
d.text(((W - d.textbbox((0, 0), note, font=f_note)[2]) / 2, y0 + head_h + len(rows) * row_h + 30), note, font=f_note, fill="#444444")

img.save(OUT, "PNG")
print(f"已生成：{OUT}")
