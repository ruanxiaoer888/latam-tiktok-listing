# -*- coding: utf-8 -*-
r"""
人工核验后批量置 verified（只对硬门槛齐全、无 blocked 的 SKU 生效）。

用法：
  python qa\verify_facts.py ABU5000000 ABU6000008 --by "运营-张三"
  python qa\verify_facts.py ABU5000000 --by "运营-张三" --dry-run
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT = ROOT / "input"

from check_facts import load_json, load_schema, requirements, missing_of, SKIP_DIRS  # noqa: E402


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="批量把 facts 置为 verified")
    ap.add_argument("ids", nargs="+", help="product_id 列表")
    ap.add_argument("--by", required=True, help="核验人")
    ap.add_argument("--input-root", default=str(DEFAULT_INPUT))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    root = Path(args.input_root).resolve()
    ok, refused = [], []
    for pid in args.ids:
        p = root / pid / "facts.json"
        if not p.exists():
            refused.append((pid, "facts.json 不存在"))
            continue
        f = load_json(p)
        if f.get("status") == "quarantined":
            refused.append((pid, "已隔离，先删掉 overrides.json 里的 quarantine 再核验"))
            continue
        schema = load_schema(f.get("category", ""))
        if schema is None:
            refused.append((pid, f"类目 schema 未登记：{f.get('category') or '<空>'}，先补 kb\\_schemas\\"))
            continue
        missing = missing_of(f, requirements(f, schema))
        blocks = (f.get("gates") or {}).get("hard_blocks") or []
        if blocks:
            refused.append((pid, f"有硬伤：{'；'.join(blocks)}"))
            continue
        if missing:
            refused.append((pid, f"硬缺：{'、'.join(missing)}"))
            continue
        f["status"] = "verified"
        f["_meta"]["verified_by"] = args.by
        f["_meta"]["verified_at"] = datetime.now().isoformat(timespec="seconds")
        if not args.dry_run:
            p.write_text(json.dumps(f, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        ok.append(pid)

    print(f"{'[dry-run] ' if args.dry_run else ''}置 verified：{len(ok)} 个" + (f"（{'、'.join(ok)}）" if ok else ""))
    for pid, why in refused:
        print(f"  拒绝 {pid}：{why}")
    if refused:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
