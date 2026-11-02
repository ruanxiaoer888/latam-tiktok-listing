# -*- coding: utf-8 -*-
"""把 Listing初稿.md 拆成 check_listing.py 可读的 CSV（临时工具）。"""
import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SRC = ROOT / "output" / "批次_20261021" / "Listing初稿.md"
OUT = ROOT / "output" / "_batch" / "listings.csv"

text = SRC.read_text(encoding="utf-8")
parts = re.split(r"^## ([A-Z0-9]+) · .*$", text, flags=re.M)
rows = []
for i in range(1, len(parts), 2):
    pid, body = parts[i], parts[i + 1]
    m = re.search(r"^### 标题\s*\n(.+)$", body, flags=re.M)
    d = re.search(r"^### 描述\s*\n(.*?)^### 参数溯源", body, flags=re.M | re.S)
    if not (m and d):
        print(f"跳过 {pid}：缺标题或描述")
        continue
    rows.append({"id": pid, "标题": m.group(1).strip(), "描述": d.group(1).strip()})

with open(OUT, "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["id", "标题", "描述"])
    w.writeheader()
    w.writerows(rows)

print(f"{len(rows)} 条 -> {OUT}")
for r in rows:
    print(f"  {r['id']}  title={len(r['标题'])}c")
