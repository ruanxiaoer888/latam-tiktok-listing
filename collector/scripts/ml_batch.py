# -*- coding: utf-8 -*-
r"""ml_batch.py — 分批抓美客多商品页（item 级）→ _work/raw_<tag>.json

用法：
    # 待采清单由一个 JSON 文件给出：[{"sku":"AMU6000005","url":"https://articulo..."}]
    python scripts/ml_batch.py --items _work\pending.json --tag b01 --work <工作区>\collector\_work

要点（照做，别改）：
  - 必须在 mercadolibre.com.mx 页面上下文执行（同源才有 cookie）；用 --goto 让它先开首页
  - 单批 <= 24 个 URL，批间串行 + 停顿；并发是触发风控最快的方式
  - 只负责抓，不判性质、不重试；结果交给 build_input.py / gen_manifest.py 处理
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bridge  # noqa: E402

DEFAULT_WORK = os.path.join(os.path.dirname(HERE), "_work")
ORIGIN = "https://www.mercadolibre.com.mx/"
ML_EXTRACT = os.path.join(HERE, "ml_extract.js")


def load_items(path):
    data = json.load(open(path, encoding="utf-8"))
    if isinstance(data, dict):
        data = data.get("rows") or data.get("items") or []
    out = []
    for r in data:
        sku = (r.get("sku") or "").strip()
        url = (r.get("url") or r.get("link") or "").strip()
        if sku and url:
            out.append({"sku": sku, "url": url})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--items", required=True, help="待采清单 JSON（[{sku,url},...]）")
    ap.add_argument("--work", default=DEFAULT_WORK)
    ap.add_argument("--tag", default="b01", help="批次名，用于 raw_<tag>.json / raw_<tag>_NN.json")
    ap.add_argument("--batch", type=int, default=24, help="单批 URL 数（不要超过 24）")
    ap.add_argument("--pause", type=float, default=3.0, help="批间停顿秒数")
    ap.add_argument("--goto", default=ORIGIN, help="先导航到的同源页面（默认 ML 首页）")
    ap.add_argument("--no-init", action="store_true")
    ap.add_argument("--tag-field", action="store_true",
                    help="按批次编号分文件 raw_<tag>_01.json；默认合并成 raw_<tag>.json")
    args = ap.parse_args()

    os.makedirs(args.work, exist_ok=True)
    items = load_items(args.items)
    if not items:
        print("没有可采 URL（检查 --items 文件）")
        return 1
    batches = [items[i:i + args.batch] for i in range(0, len(items), args.batch)]
    print("待采 %d 个 → %d 批（每批 <= %d）" % (len(items), len(batches), args.batch))

    print("CLI:", bridge.version())
    if not args.no_init:
        out, rc = bridge.init()
        print("init:", out.splitlines()[-1] if out else rc)
    if args.goto:
        out, rc = bridge.goto(args.goto)
        print("goto:", (out or "").splitlines()[-1])

    extract = open(ML_EXTRACT, encoding="utf-8").read()
    merged = []
    for bi, batch in enumerate(batches, 1):
        tag = "%s_%02d" % (args.tag, bi) if args.tag_field else args.tag
        setup = "(() => { window.__URLS = %s; return btoa('ok'); })()" % json.dumps(batch, ensure_ascii=False)
        bridge.eval_js_source(setup)
        records = bridge.eval_js_returning_json(extract)
        for rec, src in zip(records, batch):
            rec.setdefault("sku", src["sku"])
            rec.setdefault("url", src["url"])
            merged.append(rec)

        ok = sum(1 for r in records if r.get("title"))
        blocked = {}
        err = []
        for r in records:
            if r.get("title"):
                continue
            if r.get("blocked"):
                blocked[r["blocked"]] = blocked.get(r["blocked"], 0) + 1
            else:
                err.append(r["sku"])
        print("[批 %d/%d] 取回 %d 条：成功 %d / 未取到 %d %s %s" % (
            bi, len(batches), len(records), ok, len(records) - ok,
            ("(拦截:%s)" % blocked) if blocked else "",
            ("(其他失败:%s)" % ",".join(err[:6])) if err else ""))

        if args.tag_field:
            path = os.path.join(args.work, "raw_%s.json" % tag)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(records, f, ensure_ascii=False, indent=1)
            print("  ->", path)
        if bi < len(batches) and args.pause:
            bridge.sleep(args.pause)

    if not args.tag_field:
        path = os.path.join(args.work, "raw_%s.json" % args.tag)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(merged, f, ensure_ascii=False, indent=1)
        print("合并 ->", path)

    wall = [r["sku"] for r in merged if r.get("blocked") == "wall" or r.get("blocked") == "empty"]
    if wall:
        print("!! 疑似风控拦截 %d 个：%s" % (len(wall), ", ".join(wall[:12])))
        print("!! 先按 references/03-风控与失效排查.md 换网络出口，再整批重采；不要就地重试")
    return 0


if __name__ == "__main__":
    sys.exit(main())