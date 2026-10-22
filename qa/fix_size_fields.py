# -*- coding: utf-8 -*-
r"""
一次性回填：把 facts.json 里不可信的尺寸字段置 null（默认 dry-run）。

规则与 qa/check_facts_quality.py 的 FQ-P0-SIZE-IMPLAUSIBLE 完全一致（直接复用
size_field_issues，避免两套口径漂移）：
  - 任一边 >150 cm 或 <1 cm；
  - 取自 rpm / r/min / Nm / kg / W / V 等非尺寸单位（如「3200 RPM」写成 3200 cm）；
  - mm 数值未 ÷10 直接写成 cm（如「210 * 190 * 125mm」写成 210/190/125）。

用法：
  python qa\fix_size_fields.py                       # 默认 dry-run，只打印清单，不写文件
  python qa\fix_size_fields.py --apply               # 真正写回 facts.json
  python qa\fix_size_fields.py --input-root input --apply

--apply 只写这几处，不动 status / 其它字段：
  - size.<field> = null；
  - _meta.size_fix = {at, by, fields:{field:{old, reasons}}}（时间 + 原值 + 原因）；
  - gates.warnings 追加「尺寸不可信，已置空：…」（已存在则不重复）。

再次运行 dry-run 应为 0 个 SKU（幂等）。

退出码：0 正常（dry-run / apply 均为 0）；2 参数或目录错误。
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent
ROOT = BASE.parent
DEFAULT_INPUT = ROOT / "input"

# 同目录复用质量哨兵的尺寸规则（python qa\fix_size_fields.py 时 sys.path[0] = qa）
sys.path.insert(0, str(BASE))
from check_facts_quality import SIZE_FIELDS, SIZE_MAX_CM, SIZE_MIN_CM, size_field_issues  # noqa: E402,F401


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="把 facts.json 里不可信的尺寸字段置 null")
    ap.add_argument("--input-root", default=str(DEFAULT_INPUT),
                    help="商品目录（含 */facts.json），默认 input")
    ap.add_argument("--apply", action="store_true",
                    help="真正写回 facts.json；不加时只 dry-run 打印清单")
    args = ap.parse_args()

    root = Path(args.input_root).resolve()
    if not root.is_dir():
        print(f"[ERROR] 目录不存在：{root}", file=sys.stderr)
        return 2

    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"尺寸回填（{mode}）口径：{SIZE_MIN_CM:g}–{SIZE_MAX_CM:g} cm；非尺寸单位；mm 未 ÷10")
    fixed_sku = fixed_fields = 0
    for f in sorted(root.glob("*/facts.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8-sig"))
        except Exception as e:  # noqa: BLE001
            print(f"[WARN] 读不了 {f}: {e}", file=sys.stderr)
            continue
        pid = d.get("product_id") or f.parent.name
        issues = size_field_issues(d)
        if not issues:
            continue
        fixed_sku += 1
        fixed_fields += len(issues)
        print(f"\n[{mode}] {pid}  ({d.get('status') or 'draft'})")
        for it in issues:
            print(f"    {it['field']}={it['value']:g} -> null | {'；'.join(it['reasons'])}")
            if it["evidence"]:
                print(f"        原文：{it['evidence'][:100]}")
        if not args.apply:
            continue

        size = d.setdefault("size", {})
        meta = d.setdefault("_meta", {})
        rec = meta.setdefault("size_fix", {})
        rec["at"] = datetime.now().isoformat(timespec="seconds")
        rec["by"] = "qa/fix_size_fields.py"
        rec_fields = rec.setdefault("fields", {})
        warns = d.setdefault("gates", {}).setdefault("warnings", [])
        for it in issues:
            size[it["field"]] = None
            rec_fields[it["field"]] = {"old": it["value"], "reasons": it["reasons"]}
            msg = f"尺寸不可信，已置空：{it['field']}={it['value']:g}（{'；'.join(it['reasons'])}）"
            if msg not in warns:
                warns.append(msg)
        # 只写回本文件，保持 build_facts 的 JSON 风格（ensure_ascii=False, indent=2, 末尾换行）
        f.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    verb = "修复" if args.apply else "将修复"
    tail = "" if args.apply else "（dry-run，未写文件；确认后加 --apply）"
    print(f"\n{verb} {fixed_sku} 个 SKU / {fixed_fields} 个字段{tail}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
