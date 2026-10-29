# -*- coding: utf-8 -*-
r"""
生成「生成用事实摘要」：只从 facts.json 取字段，压缩成每 SKU 约 14 行，供 Agent 批量写 Listing 时读。
不替代 facts.json（口径冲突时以 facts.json 为准）；不做任何推断。

用法：
  python qa\facts_digest.py                          # 默认只输出 status=verified 的 SKU
  python qa\facts_digest.py --status draft           # 指定状态（逗号分隔可多选，如 draft,verified）
  python qa\facts_digest.py --status all             # 不限状态（隔离/阻断仍默认排除，见下）
  python qa\facts_digest.py --out output\_batch\facts_digest.md
  python qa\facts_digest.py --include-pending        # 连硬缺项未过的也输出（仅调试）

口径：
  - 默认 --status verified：不再把 draft 当可生成素材输出；
  - quarantined / blocked 默认永不输出；要排查可显式 --status quarantined（或 blocked）；
  - 同一 product_id 只输出一次，重复项剔除并计数；
  - 末尾/开头统计：每个 status 各多少条、排除多少（按状态拆分）、去重多少。

退出码：0 正常；2 目录不存在。
"""
import argparse
import sys
from collections import Counter
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


def fact_lines(f):
    """单个 facts.json → 生成用事实块（facts_digest 与 scripts/render_prompt.py 共用）。"""
    p = f.get("power") or {}
    cert = f.get("certification") or {}
    mx = g(f, "site_profiles", "MX", default={}) or {}
    ck = g(f, "extras", "core_keyword", default="") or "-"
    out = [
        f"## {f.get('product_id')} · {f.get('category')} · {f.get('status')}",
        f"- 品牌：{g(f,'identity','brand')}　型号：{g(f,'identity','model')}",
        f"- 原标题：{g(f,'identity','title_raw')}",
        f"- 平台核心词（标题必须覆盖其实词）：{ck}",
        f"- 供电：{p.get('type')}　可写功率：{num(p.get('w'),'W') if p.get('state_power') else '不写'}　"
        f"电压：{num(p.get('voltage_v'),'V')}　电池：{num(p.get('battery_v'),'V')}　"
        f"充电器：{num(p.get('charger_v'),'V')}",
        f"- 尺寸：{size_str(f)}　重量：{num(f.get('weight_kg'),'kg')}　"
        f"承载/容量：{f.get('capacity') or '-'}　件数：{num(f.get('pieces'))}",
        f"- 材质：{join(f.get('material'))}（依据 {f.get('material_basis') or '-'}）",
        f"- 包装清单：{join(g(f,'package','included'))}　不含：{join(g(f,'package','not_included'))}",
        f"- 兼容/适配：{join(f.get('compatibility'))}",
        f"- 功能点：{join(f.get('features'))}",
        f"- 使用场景：{join(f.get('usage'))}",
        f"- 认证：{cert.get('status')}　价格：{num(mx.get('price'),' MXN')}　图片：{len(f.get('images') or [])} 张",
    ]
    w = g(f, "gates", "warnings", default=[]) or []
    if w:
        out.append(f"- 注意：{'；'.join(w)}")
    return out


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="生成用事实摘要（默认只输出 verified）")
    ap.add_argument("--input-root", default=str(INPUT))
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--only", default="", help="只输出指定 SKU，逗号分隔")
    ap.add_argument("--status", default="verified",
                    help="输出哪些 facts 状态：verified（默认）/ draft / quarantined / blocked / all；可逗号分隔")
    ap.add_argument("--include-pending", action="store_true", help="连硬缺项未过的也输出（调试用）")
    args = ap.parse_args()

    root = Path(args.input_root).resolve()
    if not root.is_dir():
        print(f"[ERROR] 目录不存在：{root}", file=sys.stderr)
        return 2
    only = [x.strip() for x in args.only.split(",") if x.strip()]
    want = [s.strip().lower() for s in args.status.split(",") if s.strip()] or ["verified"]
    all_mode = "all" in want
    explicit = set(want) - {"all"}

    rows, skipped, dups = [], [], 0
    seen = set()
    for d in sorted(root.iterdir()):
        if not d.is_dir() or not (d / "facts.json").exists():
            continue
        if only and d.name not in only:
            continue
        f = load_json(d / "facts.json")
        pid = f.get("product_id") or d.name
        status = str(f.get("status") or "draft").lower()
        if pid in seen:  # 同一 product_id 只输出一次
            dups += 1
            skipped.append((pid, status, "重复 product_id（已去重）"))
            continue
        seen.add(pid)
        if status in ("quarantined", "blocked") and status not in explicit:
            skipped.append((pid, status, f"status={status}（不进生成集）"))
            continue
        if not all_mode and status not in want:
            skipped.append((pid, status, f"status={status}（不在 --status={args.status} 范围）"))
            continue
        schema = load_schema(f.get("category", ""))
        if schema is None:
            skipped.append((pid, status, f"类目 schema 未登记：{f.get('category') or '<空>'}"))
            continue
        missing = missing_of(f, requirements(f, schema))
        blocks = g(f, "gates", "hard_blocks", default=[]) or []
        if (missing or blocks) and not args.include_pending:
            skipped.append((pid, status, "未过门禁：" + "、".join(missing or blocks)))
            continue
        rows.append(f)

    out_status = Counter(str(f.get("status") or "draft") for f in rows)
    excl_status = Counter(st for _, st, _ in skipped)
    status_line = " / ".join(f"{k}={v}" for k, v in sorted(out_status.items())) or "无"
    excl_line = " / ".join(f"{k}={v}" for k, v in sorted(excl_status.items())) or "无"

    lines = []
    lines.append("# 生成用事实摘要（来源：input/<SKU>/facts.json）")
    lines.append("")
    lines.append(f"- 可生成条目：{len(rows)}（按状态：{status_line}）")
    lines.append(f"- 已排除：{len(skipped)}（按状态：{excl_line}）")
    lines.append(f"- 去重：重复 product_id 剔除 {dups} 个")
    lines.append("- 口径：缺的写「-」，正文里不写、不猜；`state_power=false` 时禁止写瓦数；"
                 "`certification.status=missing` 时禁止出现 NOM/INMETRO/ANATEL/UN38.3 字样")
    lines.append("")
    for f in rows:
        lines.extend(fact_lines(f))
        lines.append("")

    if skipped:
        lines.append("## 已排除清单")
        for pid, st, why in skipped:
            lines.append(f"- {pid}（{st}）：{why}")
        lines.append("")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"可生成 {len(rows)} 个（按状态：{status_line}）；排除 {len(skipped)} 个（按状态：{excl_line}）；"
          f"重复 product_id 去重 {dups} 个 -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
