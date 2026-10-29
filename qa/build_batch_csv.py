# -*- coding: utf-8 -*-
r"""
批量：把 input\ 原始数据与批次成稿合成校验用 CSV。

认两种成稿布局（优先扁平，再 SKU 文件夹）：
  <batch>\listing-<id>.txt                 旧布局
  <batch>\<id>\标题.txt + 描述.txt         新布局（交付文件夹即源稿）

标题长度只做「提示」，不阻断；区间从 qa\denylist.json 统一读取（qa\_limits.py），
汽配类目自动用更宽的 autoparts 区间。

用法：
  python build_batch_csv.py --input-root ..\input --listing-dir ..\output\批次20261020 --out ..\output\_smoke\...\check.csv
  python build_batch_csv.py ... --site BR
"""
import argparse
import csv
import json
import sys
from pathlib import Path

from _limits import title_ok, title_range


def load_listing(ldir, pid):
    """返回 (title, desc)；没有成稿返回 None。"""
    flat = ldir / f"listing-{pid}.txt"
    if flat.exists():
        lines = flat.read_text(encoding="utf-8").splitlines()
        while lines and not lines[0].strip():
            lines.pop(0)
        return lines[0].strip(), "\n".join(lines[1:]).strip()
    t = ldir / pid / "标题.txt"
    d = ldir / pid / "描述.txt"
    if t.exists() and d.exists():
        return t.read_text(encoding="utf-8").strip(), d.read_text(encoding="utf-8").strip()
    return None


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-root", required=True)
    ap.add_argument("--listing-dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--site", default="MX", choices=["MX", "BR"], help="站点；标题建议区间按站点/类目取")
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
        got = load_listing(ldir, pid)
        if got is None:
            missing.append(pid)
            continue
        title, desc = got
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
    lo, hi = title_range(args.site)
    print(f"\n标题长度检查（{args.site} 建议 {lo}–{hi}；汽配用更宽区间）：")
    for r in rows:
        ok = title_ok(args.site, r[1], r[4])
        print(f"  [{'OK' if ok else '!!'}] {r[0]:12} {len(r[1]):3} chars | {r[1]}")
    if missing:
        print("缺成稿的商品：" + "、".join(missing))


if __name__ == "__main__":
    main()
