# -*- coding: utf-8 -*-
"""给卖点（⭐ 行）之间补空行：避免 Markdown 把连续行合并成文字墙。"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
FILES = [
    ROOT / "output" / "批次_20261021" / "Listing初稿.md",
    ROOT / "output" / "样例" / "ABU5000000-Listing.md",
]

for p in FILES:
    lines = p.read_text(encoding="utf-8").splitlines()
    out = []
    for i, ln in enumerate(lines):
        out.append(ln)
        if ln.startswith("⭐") and i + 1 < len(lines) and lines[i + 1].strip():
            out.append("")
    p.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"已处理 {p.name}：卖点 {sum(1 for x in lines if x.startswith('⭐'))} 条")
