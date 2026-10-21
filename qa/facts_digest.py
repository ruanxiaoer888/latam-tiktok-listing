# -*- coding: utf-8 -*-
r"""
生成「生成用事实摘要」：只从 facts.json 取字段，压缩成每 SKU 约 14 行，供 Agent 批量写 Listing 时读。
不替代 facts.json（口径冲突时以 facts.json 为准）；不做任何推断。

用法：
  python qa\facts_digest.py                      # 只输出 DRAFT-OK / READY
  python qa\facts_digest.py --out output\_batch\facts_digest.md
  python qa\facts_digest.py --status draft       # 指定状态
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INPUT = ROOT / "input"
OUT = ROOT / "output" / "_batch" / "facts_digest.md"

from check_facts import load_json, load_schema, requirements, missing_of  # noqa: E402


def g(f, *path, default=None):
    cur = f
    for p in path:
        if not isinstance(cur, dict) or p not in cur:
            return default
        cur = cur[p]
    return cur


def join(v):
    if not v:
        return "-"
    if isinstance(v, list):
        return " / ".join(str(x) for x in v)
    return str(v)


def num(v, unit=""):
    if v is None or v == "":
        return "-"
    return f"{v}{unit}"


def size_str(f):
    s = f.get("size") or {}
    parts = []
    if s.get("length_cm"):
        parts.append(f"L{s['length_cm']}")
    if s.get("width_cm"):
        parts.append(f"A{s['width_cm']}")
    if s.get("height_cm"):
        parts.append(f"H{s['height_cm']}")
    if s.get("diameter_cm"):
        parts.append(f"D{s['diameter_cm']}")
    raw = join(s.get("raw"))
    txt = " x ".join(parts) if parts else "-"
    return f"{txt} cm（原文：{raw}）" if raw != "-" else txt


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-root", default=str(INPUT))
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--only", default="", help="只输出指定 SKU，逗号分隔")
    ap.add_argument("--include-pending", action="store_true", help="同时输出 PENDING（硬缺项）")
    args = ap.parse_args()

    root = Path(args.input_root).resolve()
    only = [x.strip() for x in args.only.split(",") if x.strip()]

    rows, skipped = [], []
    for d in sorted(root.iterdir()):
        if not d.is_dir() or not (d / "facts.json").exists():
            continue
        if only and d.name not in only:
            continue
        f = load_json(d / "facts.json")
        status = f.get("status", "draft")
        if status in ("quarantined", "blocked"):
            skipped.append((d.name, status))
            continue
        schema = load_schema(f.get("category", ""))
        missing = missing_of(f, requirements(f, schema))
        blocks = g(f, "gates", "hard_blocks", default=[]) or []
        if (missing or blocks) and not args.include_pending:
            skipped.append((d.name, "未过门禁：" + "、".join(missing or blocks)))
            continue
        rows.append(f)

    lines = []
    lines.append("# 生成用事实摘要（来源：input/<SKU>/facts.json）")
    lines.append("")
    lines.append(f"- 可生成条目：{len(rows)}")
    lines.append(f"- 已排除：{len(skipped)}（隔离/阻断/硬缺）")
    lines.append("- 口径：缺的写「-」，正文里不写、不猜；`state_power=false` 时禁止写瓦数；"
                 "`certification.status=missing` 时禁止出现 NOM/INMETRO/ANATEL/UN38.3 字样")
    lines.append("")
    for f in rows:
        p = f.get("power") or {}
        cert = f.get("certification") or {}
        mx = g(f, "site_profiles", "MX", default={}) or {}
        lines.append(f"## {f.get('product_id')} · {f.get('category')} · {f.get('status')}")
        lines.append(f"- 品牌：{g(f,'identity','brand')}　型号：{g(f,'identity','model')}")
        lines.append(f"- 原标题：{g(f,'identity','title_raw')}")
        ck = g(f, "extras", "core_keyword", default="") or "-"
        lines.append(f"- 平台核心词（标题必须覆盖其实词）：{ck}")
        lines.append(f"- 供电：{p.get('type')}　可写功率：{num(p.get('w'),'W') if p.get('state_power') else '不写'}　"
                     f"电压：{num(p.get('voltage_v'),'V')}　电池：{num(p.get('battery_v'),'V')}　"
                     f"充电器：{num(p.get('charger_v'),'V')}")
        lines.append(f"- 尺寸：{size_str(f)}　重量：{num(f.get('weight_kg'),'kg')}　"
                     f"承载/容量：{f.get('capacity') or '-'}　件数：{num(f.get('pieces'))}")
        lines.append(f"- 材质：{join(f.get('material'))}（依据 {f.get('material_basis') or '-'}）")
        lines.append(f"- 包装清单：{join(g(f,'package','included'))}　不含：{join(g(f,'package','not_included'))}")
        lines.append(f"- 兼容/适配：{join(f.get('compatibility'))}")
        lines.append(f"- 功能点：{join(f.get('features'))}")
        lines.append(f"- 使用场景：{join(f.get('usage'))}")
        lines.append(f"- 认证：{cert.get('status')}　价格：{num(mx.get('price'),' MXN')}　图片：{len(f.get('images') or [])} 张")
        w = g(f, "gates", "warnings", default=[]) or []
        if w:
            lines.append(f"- 注意：{'；'.join(w)}")
        lines.append("")

    if skipped:
        lines.append("## 已排除清单")
        for pid, why in skipped:
            lines.append(f"- {pid}：{why}")
        lines.append("")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"可生成 {len(rows)} 个，排除 {len(skipped)} 个 -> {out}")


if __name__ == "__main__":
    main()
