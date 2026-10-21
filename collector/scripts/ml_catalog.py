# -*- coding: utf-8 -*-
r"""ml_catalog.py — 抓「目录产品页」（原 item 已下架时 ML 的重定向落点）

用法：
    python scripts/ml_catalog.py --items _work\catalog.json --work <工作区>\collector\_work

做法：逐个 goto 到该 SKU 的链接（ML 会自动重定向到目录产品页）→ 读页面里的
__NORDIC_RENDERING_CTX__（catalog_extract.js）。串行，不并发。
产出：<work>/raw_catalog.json（记录带 data_level=catalog / availability=OutOfStock）
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bridge  # noqa: E402

DEFAULT_WORK = os.path.join(os.path.dirname(HERE), "_work")
CAT_JS = os.path.join(HERE, "catalog_extract.js")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--items", required=True, help="[{sku,url},...] JSON")
    ap.add_argument("--work", default=DEFAULT_WORK)
    ap.add_argument("--out", default=None, help="默认 <work>/raw_catalog.json")
    ap.add_argument("--no-init", action="store_true")
    args = ap.parse_args()

    os.makedirs(args.work, exist_ok=True)
    data = json.load(open(args.items, encoding="utf-8"))
    if isinstance(data, dict):
        data = data.get("items") or data.get("rows") or []
    items = [{"sku": r["sku"], "url": r.get("url") or r.get("link")} for r in data if r.get("sku")]

    print("CLI:", bridge.version())
    if not args.no_init:
        out, rc = bridge.init()
        print("init:", out.splitlines()[-1] if out else rc)

    extract = open(CAT_JS, encoding="utf-8").read()
    out_records = []
    for i, it in enumerate(items, 1):
        try:
            bridge.goto(it["url"])
            rec = bridge.eval_js_returning_json(extract)
        except bridge.BridgeError as e:
            rec = {"error": str(e)}
        rec["sku"] = it["sku"]
        rec["url"] = it["url"]
        rec.setdefault("data_level", "catalog")
        rec.setdefault("availability", "OutOfStock")
        if rec.get("error"):
            print("[%d/%d] %-12s 失败: %s" % (i, len(items), it["sku"], rec["error"][:80]))
        else:
            print("[%d/%d] %-12s pics=%-2s attrs=%-3s desc=%-5s %s" % (
                i, len(items), it["sku"], rec.get("pic_count"),
                len(rec.get("attributes_raw") or {}),
                len(rec.get("description_text") or ""),
                rec.get("catalog_id") or ""))
        out_records.append(rec)

    path = args.out or os.path.join(args.work, "raw_catalog.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out_records, f, ensure_ascii=False, indent=1)
    print("-> %s（%d 条）" % (path, len(out_records)))


if __name__ == "__main__":
    main()