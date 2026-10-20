# -*- coding: utf-8 -*-
"""
把一批 input.json 汇总成一个 markdown 文件，方便一次性通读后批量生成。

用法：
  python collect_inputs.py <input_root> [--out _batch_input.md] [--exclude 示例商品,示例商品001]
"""
import argparse
import json
import sys
from pathlib import Path


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--out", default="_batch_input.md")
    ap.add_argument("--exclude", default="示例商品,示例商品001")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    skip = {s.strip() for s in args.exclude.split(",") if s.strip()}
    dirs = sorted([p for p in root.iterdir()
                   if p.is_dir() and (p / "input.json").exists()
                   and p.name not in skip and not p.name.startswith("_")])

    parts = []
    for d in dirs:
        data = json.loads((d / "input.json").read_text(encoding="utf-8"))
        imgs = list((d / "img").glob("*")) if (d / "img").exists() else []
        parts.append(f"## {data.get('product_id', d.name)}")
        parts.append("")
        parts.append(f"- 来源站点：{data.get('site')}　类目：{data.get('category')}")
        parts.append(f"- 核心词：{data.get('core_keyword', '')}")
        price = data.get("price_source") or {}
        parts.append(f"- 原价：{price.get('amount')} {price.get('currency')}")
        parts.append(f"- 图片数：{len(imgs)}")
        parts.append(f"- 原标题：{data.get('title_raw', '')}")
        parts.append("")
        parts.append("### 原始属性")
        attrs = data.get("attributes_raw") or {}
        for k, v in attrs.items():
            parts.append(f"- {k}: {v}")
        parts.append("")
        parts.append("### 原始描述")
        parts.append(data.get("description_raw", "").strip())
        parts.append("")
        parts.append("---")
        parts.append("")

    out = Path(args.out)
    if not out.is_absolute():
        out = Path.cwd() / out
    out.write_text("\n".join(parts), encoding="utf-8")
    print(f"汇总 {len(dirs)} 个商品 -> {out}")
    print("商品：" + "、".join(d.name for d in dirs))


if __name__ == "__main__":
    main()
