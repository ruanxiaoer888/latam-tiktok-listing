# -*- coding: utf-8 -*-
r"""
把 input/<SKU>/input.json 里的美客多原始信息压成「生成用摘要」。

只读，不改任何文件；输出到 output\_batch\digest.md。

用法：
  python qa\source_digest.py
"""
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT = ROOT / "input"
SKIP_DIRS = {"示例商品", "示例商品001"}

from build_facts import parse_package  # noqa: E402


def point_lines(desc, limit=5):
    """描述里编号段落的首句，作为卖点素材。"""
    out = []
    for line in (desc or "").splitlines():
        s = line.strip()
        m = re.match(r"^\d+[\.\)]\s*(.+)", s)
        if not m:
            continue
        t = re.split(r"(?<=[.!?])\s", m.group(1))[0]
        out.append(t[:150])
        if len(out) >= limit:
            break
    return out


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="美客多信息 -> 生成摘要")
    ap.add_argument("--input-root", default=str(DEFAULT_INPUT))
    ap.add_argument("--out", default=str(ROOT / "output" / "_batch" / "digest.md"))
    args = ap.parse_args()

    root = Path(args.input_root).resolve()
    dirs = [d for d in sorted(root.iterdir()) if (d / "input.json").exists()
            and d.name not in SKIP_DIRS and not d.name.startswith("_")]
    lines = ["# 美客多原始信息摘要（生成 Listing 的唯一参数来源）", ""]
    for d in dirs:
        data = json.loads((d / "input.json").read_text(encoding="utf-8"))
        pid = data.get("product_id", d.name)
        attrs = data.get("attributes_raw") or {}
        desc = data.get("description_raw") or ""
        price = (data.get("price_source") or {}).get("amount")
        lines += [f"## {pid} | {data.get('category', '')}", f"title: {data.get('title_raw', '')}"]
        if price:
            lines.append(f"price: {price} MXN")
        lines.append("attrs:")
        for k, v in attrs.items():
            lines.append(f"  {k}: {v}")
        pkg = parse_package(desc)
        if pkg:
            lines.append("package:")
            lines += [f"  - {x}" for x in pkg]
        pts = point_lines(desc)
        if pts:
            lines.append("desc_points:")
            lines += [f"  - {x}" for x in pts]
        lines.append("")
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"已写出 {len(dirs)} 个 SKU -> {out}")


if __name__ == "__main__":
    main()
