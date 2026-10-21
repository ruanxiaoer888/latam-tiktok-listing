# -*- coding: utf-8 -*-
r"""read_sheet.py — 读飞书多维表格「商品链接」清单 → _work/_sheet_rows.json

用法（在技能目录下执行；--url 换成你的表）：
    python scripts/read_sheet.py --work <工作区>\collector\_work
    python scripts/read_sheet.py --url "https://xxx.feishu.cn/base/<app_token>?table=<table>&view=<view>"

前置：浏览器里已登录飞书（未登录会拿到 ERR:no_table）。
产出：<work>/_sheet_rows.json，结构见 references/01-飞书表读取.md
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bridge  # noqa: E402

DEFAULT_URL = ("https://mcny0kyorde8.feishu.cn/base/Nqxob1DmsalyjHs2E8YcSqaxnTe"
               "?table=tbl4wXgSNkfMYD1f&view=vewkZbJc3v")
DEFAULT_WORK = os.path.join(os.path.dirname(HERE), "_work")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default=DEFAULT_URL, help="多维表格 URL（默认当前在用的那张表）")
    ap.add_argument("--work", default=DEFAULT_WORK, help="中间目录，默认 <技能>/collector/_work")
    ap.add_argument("--js", default=os.path.join(HERE, "feishu_read.js"))
    ap.add_argument("--no-init", action="store_true", help="跳过 init（浏览器通道已在用）")
    args = ap.parse_args()

    os.makedirs(args.work, exist_ok=True)
    print("CLI:", bridge.version())
    if not args.no_init:
        out, rc = bridge.init()
        print("init:", out.splitlines()[-1] if out else rc)
    out, rc = bridge.goto(args.url)
    print("goto:", (out or "").splitlines()[-1])

    data = bridge.eval_js_file_json(args.js)
    out_path = os.path.join(args.work, "_sheet_rows.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)

    rows = data.get("rows") or []
    with_link = sum(1 for r in rows if r.get("link"))
    print("记录数: %d / 有链接: %d" % (len(rows), with_link))
    if data.get("missing_fields"):
        print("!! 缺少列: %s（脚本按列名取数，请核对表结构）" % data["missing_fields"])
    blank = [r["sku"] or "(空SKU)" for r in rows if not r.get("link")]
    if blank:
        print("无链接的行（%d）: %s" % (len(blank), ", ".join(blank[:20])))
    print("-> %s" % out_path)


if __name__ == "__main__":
    main()