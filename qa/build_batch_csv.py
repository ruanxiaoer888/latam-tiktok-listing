# -*- coding: utf-8 -*-
r"""
批量：把 input\ 原始数据与 output\listing-<id>.txt 合成校验用 CSV。

用法：
  python build_batch_csv.py --input-root ..\input --listing-dir ..\output\批次20261020 --out ..\output\批次20261020\check.csv
"""
import argparse
import csv
import json
import sys
from pathlib import Path


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-root", required=True)
    ap.add_argument("--listing-dir", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    inroot = Path(args.input_root).resolve()
    ldir = Path(args.listing_dir).resolve()
    rows, missing = [], []

    for d in sorted(inroot.iterdir()):
        f = d / "input.json"
        if not f.exists() or d.name.startswith("_") or d.name in ("示例商品", "示例商品001"):
            continue
        data = json.loads(f.read_text(encoding="utf-8"))
        pid = data.get("product_id", d.name)
        listing = ldir / f"listing-{pid}.txt"
        if not listing.exists():
            missing.append(pid)
            continue
        lines = listing.read_text(encoding="utf-8").splitlines()
        while lines and not lines[0].strip():
            lines.pop(0)
        title = lines[0].strip()
        desc = "\n".join(lines[1:]).strip()
        rows.append([
            pid,
            title,
            desc,
            data.get("core_keyword", ""),
            data.get("category", ""),
            (data.get("price_source") or {}).get("amount", ""),
            str(d / "img"),
        ])

    out = Path(args.out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "标题", "描述", "核心词", "类目", "原价MXN", "图片目录"])
        w.writerows(rows)

    print(f"已写出 {len(rows)} 条 -> {out}")
    print("\n标题长度检查：")
    for r in rows:
        flag = "OK" if 60 <= len(r[1]) <= 80 else "!!"
        print(f"  [{flag}] {r[0]:12} {len(r[1]):3} chars | {r[1]}")
    if missing:
        print("缺 listing 的商品：" + "、".join(missing))


if __name__ == "__main__":
    main()
