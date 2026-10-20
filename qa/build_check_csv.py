# -*- coding: utf-8 -*-
"""
把生成好的 listing 文本批量汇总成 check_listing.py 能读的 CSV。

用法：
  python build_check_csv.py <目录> [--out check.csv] [--keyword 词] [--category 类目] [--site MX]

规则：
  - 目录下每个 `listing-*.txt` / `listing-*.md` 视为一条
  - 第一行非空文本 = 标题，其余 = 描述
  - id 取文件名（去掉扩展名）
  - --keyword / --category 给同目录所有条目统一填（按行不同请改 CSV）
"""
import argparse
import csv
import sys
from pathlib import Path


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("dir")
    ap.add_argument("--out", default="check.csv")
    ap.add_argument("--keyword", default="")
    ap.add_argument("--category", default="")
    ap.add_argument("--site", default="MX")
    args = ap.parse_args()

    d = Path(args.dir).expanduser().resolve()
    if not d.is_dir():
        raise SystemExit(f"目录不存在：{d}")

    files = sorted([p for p in d.iterdir() if p.suffix.lower() in (".txt", ".md") and p.stem.startswith("listing")])
    if not files:
        raise SystemExit(f"{d} 下没有 listing-*.txt/md")

    rows = []
    for p in files:
        lines = p.read_text(encoding="utf-8").splitlines()
        while lines and not lines[0].strip():
            lines.pop(0)
        if not lines:
            continue
        title = lines[0].strip()
        desc = "\n".join(lines[1:]).strip()
        rows.append([p.stem, title, desc, args.keyword, args.category])

    out = Path(args.out)
    if not out.is_absolute():
        out = d / out
    with open(out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "标题", "描述", "核心词", "类目"])
        w.writerows(rows)
    print(f"已写出 {len(rows)} 条 -> {out}")


if __name__ == "__main__":
    main()
