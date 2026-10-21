# -*- coding: utf-8 -*-
r"""
知识库索引：把 15 份 facts.json 汇总成 kb\_index\products.csv（一行一个 SKU）。

用法：
  python qa\index_kb.py
  python qa\index_kb.py --out kb\_index\products.csv
"""
import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT = ROOT / "input"
INDEX_DIR = ROOT / "kb" / "_index"
SKIP_DIRS = {"示例商品", "示例商品001"}

# 同目录导入（python qa\index_kb.py 时 sys.path[0] = qa）
from check_facts import load_json, load_schema, requirements, recommended_fields, missing_of  # noqa: E402


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="生成知识库索引 products.csv")
    ap.add_argument("--input-root", default=str(DEFAULT_INPUT))
    ap.add_argument("--out", default=str(INDEX_DIR / "products.csv"))
    args = ap.parse_args()

    root = Path(args.input_root).resolve()
    dirs = [d for d in sorted(root.iterdir()) if (d / "facts.json").exists()
            and d.name not in SKIP_DIRS and not d.name.startswith("_")]
    if not dirs:
        raise SystemExit("没有 facts.json，先运行 python qa\\build_facts.py")

    rows = []
    for d in dirs:
        f = load_json(d / "facts.json")
        schema = load_schema(f.get("category", ""))
        if schema is None:
            print(f"[!] 跳过 {d.name}：类目 schema 未登记（{f.get('category') or '<空>'}）",
                  file=sys.stderr)
            continue
        reqs = requirements(f, schema)
        missing = missing_of(f, reqs)
        soft = missing_of(f, recommended_fields(f, schema))
        if not (f.get("power") or {}).get("state_power"):
            soft = [m for m in soft if not str(m).startswith("可写功率")]
        power = f.get("power") or {}
        mx = (f.get("site_profiles") or {}).get("MX") or {}
        rows.append({
            "product_id": f.get("product_id", d.name),
            "category": f.get("category", ""),
            "brand": (f.get("identity") or {}).get("brand", ""),
            "status": f.get("status", "draft"),
            "required_filled": len(reqs) - len(missing),
            "required_total": len(reqs),
            "missing": "；".join(missing),
            "recommended_missing": "；".join(soft),
            "images": len(f.get("images") or []),
            "power_type": power.get("type", ""),
            "power_w": power.get("w") or "",
            "claimed_w": power.get("claimed_w") or "",
            "state_power": "yes" if power.get("state_power") else "no",
            "price_mxn": mx.get("price", ""),
            "hard_blocks": "；".join((f.get("gates") or {}).get("hard_blocks") or []),
            "built_at": (f.get("_meta") or {}).get("built_at", ""),
        })

    out = Path(args.out)
    if not out.is_absolute():
        out = ROOT / out
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    ok = sum(1 for r in rows if r["status"] != "quarantined" and r["required_filled"] >= r["required_total"])
    active = [r for r in rows if r["status"] != "quarantined"]
    print(f"已写出 {len(rows)} 行 -> {out}")
    print(f"生成候选（排除隔离）：{len(active)} 个；必填齐全：{ok} / {len(active)}；平均完整度 "
          f"{sum(r['required_filled'] / max(r['required_total'], 1) for r in active) / max(len(active), 1) * 100:.0f}%")
    if len(rows) != len(active):
        print(f"已隔离：{len(rows) - len(active)} 个（不参与生成，见 facts.json _meta.quarantine）")


if __name__ == "__main__":
    main()
