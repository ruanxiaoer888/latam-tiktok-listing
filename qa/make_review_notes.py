# -*- coding: utf-8 -*-
r"""
批次辅助：把事实卡里的「待确认点」整理成两份交付物，不做任何推断。

1. review_notes.json  —— 给 make_batch_xlsx 用，{SKU: 中文备注}
   来源：gates.warnings + 软缺字段 + 认证状态
2. 待补数据清单.md    —— 给运营补资料的清单（硬缺 / 隔离 / 阻断）

用法：
  python qa\make_review_notes.py --out-dir output\批次20261022
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INPUT = ROOT / "input"

from check_facts import load_json, load_schema, requirements, missing_of  # noqa: E402


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-root", default=str(INPUT))
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()

    root = Path(args.input_root).resolve()
    outdir = Path(args.out_dir).resolve()
    outdir.mkdir(parents=True, exist_ok=True)

    notes = {}
    rows = []
    for d in sorted(root.iterdir()):
        p = d / "facts.json"
        if not p.exists():
            continue
        f = load_json(p)
        pid = f.get("product_id", d.name)
        status = f.get("status", "draft")
        schema = load_schema(f.get("category", ""))
        missing = missing_of(f, requirements(f, schema))
        blocks = (f.get("gates") or {}).get("hard_blocks") or []
        warns = (f.get("gates") or {}).get("warnings") or []
        quarantine = (f.get("_meta") or {}).get("quarantine") or {}

        if status == "verified" and not missing and not blocks:
            parts = []
            parts.extend(w for w in warns if "不在 Listing 中使用" not in w)
            if not f.get("weight_kg"):
                parts.append("缺整机重量")
            if not (f.get("material") or []):
                parts.append("缺材质")
            if not f.get("size") or all(
                not (f.get("size") or {}).get(k) for k in ("length_cm", "width_cm", "height_cm")
            ):
                parts.append("缺尺寸")
            notes[pid] = "；".join(parts) + "。" if parts else ""
            continue

        rows.append({
            "sku": pid,
            "category": f.get("category", ""),
            "status": status,
            "reason": "隔离" if status == "quarantined" else ("阻断" if status == "blocked" else "硬缺"),
            "missing": "、".join(missing) or "-",
            "blocks": "；".join(blocks) or "-",
            "quarantine": quarantine.get("reason", "") or "-",
        })

    (outdir / "review_notes.json").write_text(
        json.dumps(notes, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = ["# 待补数据清单（本批未生成）", ""]
    lines.append(f"- 未生成条目：{len(rows)}")
    lines.append("- 补法：把缺的字段补进 `input/<SKU>/overrides.json` 的 `set`，再跑 "
                 "`python qa\\build_facts.py --only <SKU> --force` + `python qa\\verify_facts.py <SKU> --by \"<你的名字>\"`")
    lines.append("")
    lines.append("| SKU | 类目 | 类型 | 缺什么 | 说明 |")
    lines.append("|---|---|---|---|---|")
    for r in rows:
        why = r["missing"] if r["reason"] != "隔离" else "—"
        note = r["blocks"] if r["blocks"] != "-" else r["quarantine"]
        lines.append(f"| {r['sku']} | {r['category']} | {r['reason']} | {why} | {note} |")
    lines.append("")
    (outdir / "待补数据清单.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"review_notes: {len(notes)} 个；待补：{len(rows)} 个 -> {outdir}")


if __name__ == "__main__":
    main()
