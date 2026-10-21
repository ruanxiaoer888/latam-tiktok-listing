# -*- coding: utf-8 -*-
r"""gen_manifest.py — 增量规划(--plan) 与 采集清单生成

用法：
    # 1) 增量规划：只打印三类，不写文件（采集前先跑）
    python scripts/gen_manifest.py --plan

    # 2) 顺手把「待采 + 需补采」写成 ml_batch.py 能直接吃的清单
    python scripts/gen_manifest.py --plan --pending-out collector/_work/pending.json

    # 3) 生成采集清单（交付物之一）
    python scripts/gen_manifest.py --out "..\\采集清单.md" --zip ml-listing-input-108sku.zip

判据（照做，别改）：
  - 已采（跳过）：--input-root 下已有 <SKU>/input.json 的目录
  - 待采（新增）：飞书表里有链接、但没有目录的 SKU
  - 需补采：--work/build_report.json 里 status=failed 的 SKU（上次被拦/失效），
            或 --work/pending.json 里你手工追加的 SKU
  - 清单必须与实际目录一致：只统计 input/ 下真实存在的目录，不靠抓取日志凑数
"""
import argparse
import io
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
COLLECTOR = os.path.dirname(HERE)
REPO_FALLBACK = os.path.dirname(COLLECTOR)
DEFAULT_INPUT_ROOT = os.path.join(REPO_FALLBACK, "input")
DEFAULT_WORK = os.path.join(COLLECTOR, "_work")
DEFAULT_OUT = os.path.join(REPO_FALLBACK, "采集清单.md")

REQUIRED_INPUT_KEYS = ["product_id", "site", "category", "title_raw", "description_raw",
                       "attributes_raw", "images", "core_keyword", "price_source"]


# ---------------- 读盘 ----------------
def load_sheet(path):
    if not path or not os.path.exists(path):
        return None
    try:
        data = json.load(io.open(path, encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        print("!! 读不了清单 %s: %s" % (path, e))
        return None
    if isinstance(data, dict):
        rows = data.get("rows") or []
    else:
        rows = data
    out = []
    for r in rows:
        sku = (r.get("sku") or "").strip()
        if not sku:
            continue
        out.append({"sku": sku, "link": (r.get("link") or r.get("url") or "").strip(),
                    "ml_title": r.get("ml_title") or "", "note": r.get("note") or ""})
    return out


def scanned_dirs(input_root):
    """input/ 下真实存在的 SKU 目录（跳过 _ 开头与 README）。"""
    if not os.path.isdir(input_root):
        return []
    out = []
    for name in sorted(os.listdir(input_root)):
        d = os.path.join(input_root, name)
        if not os.path.isdir(d) or name.startswith("_"):
            continue
        out.append((name, d))
    return out


def read_sku(d):
    ip = os.path.join(d, "input.json")
    itp = os.path.join(d, "item.json")
    if not os.path.exists(ip) or not os.path.exists(itp):
        return None
    try:
        inp = json.load(io.open(ip, encoding="utf-8"))
        itm = json.load(io.open(itp, encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        return {"__broken": str(e)}
    imgs = itm.get("images") or []
    img_dir = os.path.join(d, "img")
    files = sorted(f for f in (os.listdir(img_dir) if os.path.isdir(img_dir) else []))
    desc = (itm.get("description") or {})
    cat = (itm.get("category") or {})
    return {
        "sku": inp.get("product_id") or itm.get("sku"),
        "data_level": inp.get("data_level") or itm.get("data_level") or "item",
        "title": itm.get("title") or inp.get("title_raw") or "",
        "category": cat.get("bucket_zh") or inp.get("category") or "",
        "shop": itm.get("shop_name") or inp.get("store_id") or "",
        "price": (inp.get("price_source") or {}).get("amount"),
        "images_declared": int(len(imgs)),
        "images_files": int(len(files)),
        "attrs": int(len(inp.get("attributes_raw") or (itm.get("attributes") or {}).get("flat") or {})),
        "desc_len": int(desc.get("char_count") if desc.get("char_count") is not None else len(desc.get("text") or "")),
        "collected_at": itm.get("collected_at") or "",
        "item_id": itm.get("item_id"),
        "status": itm.get("item_status") or "",
        "note": inp.get("note") or itm.get("note") or "",
        "dir": d,
    }


# ---------------- 增量规划 ----------------
def plan(args):
    sheet = load_sheet(args.sheet)
    collected = {name: read_sku(d) for name, d in scanned_dirs(args.input_root)}
    have = {k for k, v in collected.items() if v and not v.get("__broken")}

    # 先算「需补采」= 上次失败（build_report.json）或手工登记（pending.json），且当前无目录
    retry = []
    br = os.path.join(args.work, "build_report.json")
    if os.path.exists(br):
        try:
            rep = json.load(io.open(br, encoding="utf-8"))
            for rec in rep.get("records") or []:
                if rec.get("status") == "failed" and rec.get("sku") not in have:
                    retry.append({"sku": rec.get("sku"), "url": rec.get("url") or "",
                                  "why": rec.get("error") or ""})
        except Exception as e:  # noqa: BLE001
            print("!! 读不了 build_report.json: %s" % e)
    pend = os.path.join(args.work, "pending.json")
    if os.path.exists(pend):
        try:
            extra = json.load(io.open(pend, encoding="utf-8"))
            known = {r["sku"] for r in retry}
            for r in extra:
                sku = (r.get("sku") or "").strip()
                if sku and sku not in have and sku not in known:
                    retry.append({"sku": sku, "url": (r.get("url") or r.get("link") or "").strip(),
                                  "why": "pending.json 手工登记"})
        except Exception as e:  # noqa: BLE001
            print("!! 读不了 pending.json: %s" % e)

    # 补 URL：优先失败记录自带的，其次清单里的「商品链接」
    urls = {}
    if sheet is not None:
        urls.update({r["sku"]: r["link"] for r in sheet})
    retry = [r for r in retry if r.get("url") or urls.get(r["sku"])]
    for r in retry:
        r["url"] = r.get("url") or urls.get(r["sku"], "")

    # 待采（新增）= 清单里有链接、当前无目录、且不在需补采里
    rset = {r["sku"] for r in retry}
    todo = []
    if sheet is not None:
        for r in sheet:
            if r["link"] and r["sku"] not in have and r["sku"] not in rset:
                todo.append({"sku": r["sku"], "url": r["link"]})

    broken = [k for k, v in collected.items() if v and v.get("__broken")]
    print("input: %s" % args.input_root)
    print("清单: %s%s" % (args.sheet, "" if sheet is not None else "  (未找到，只按本地目录判断)"))
    print("")
    print("已采（跳过）  : %3d%s" % (len(have), "  " + ", ".join(sorted(have)[:8]) + " ..." if len(have) > 8 else ""))
    print("待采（新增）  : %3d%s" % (len(todo), "  " + ", ".join(r["sku"] for r in todo[:12]) if todo else ""))
    print("需补采（上次失败）: %3d%s" % (len(retry), "  " + ", ".join(r["sku"] for r in retry[:12]) if retry else ""))
    if broken:
        print("!! 目录缺件（input.json/item.json 不全）%d 个：%s" % (len(broken), ", ".join(broken[:12])))
    if sheet is not None:
        nolink = [r["sku"] for r in sheet if not r["link"]]
        if nolink:
            print("清单里无链接（不采）: %d 个：%s" % (len(nolink), ", ".join(nolink[:12])))

    if args.pending_out:
        pend_items = [{"sku": r["sku"], "url": r["url"]} for r in todo] + \
                     [{"sku": r["sku"], "url": r.get("url") or urls.get(r["sku"], "")} for r in retry]
        with io.open(args.pending_out, "w", encoding="utf-8") as f:
            json.dump(pend_items, f, ensure_ascii=False, indent=1)
        print("\n待采清单 -> %s（%d 个，可直接喂 ml_batch.py --items）" % (args.pending_out, len(pend_items)))
    print("\n下一步：只对「待采 + 需补采」跑 ml_batch.py；已采目录默认不覆盖。")
    return 0


# ---------------- 清单生成 ----------------
def esc(s):
    return str(s or "").replace("|", "\\|").replace("\n", " ").strip()


def money(v):
    if v is None:
        return None
    if isinstance(v, float) and v == int(v):
        return str(int(v))
    return ("%.2f" % v).rstrip("0").rstrip(".") if isinstance(v, float) else str(v)


def build_manifest(args):
    dirs = scanned_dirs(args.input_root)
    recs = [(name, read_sku(d)) for name, d in dirs]
    broken = [(n, r) for n, r in recs if r and r.get("__broken")]
    ok = [(n, r) for n, r in recs if r and not r.get("__broken")]
    items = [(n, r) for n, r in ok if r.get("data_level") == "item"]
    cats = [(n, r) for n, r in ok if r.get("data_level") != "item"]

    by_date = {}
    for n, r in ok:
        by_date.setdefault(r.get("collected_at") or "日期未记录", []).append((n, r))
    dates = sorted(by_date.keys(), reverse=True)

    t_sku = len(ok)
    t_img = sum(int(r["images_files"] or 0) for _, r in ok)
    t_attr = sum(int(r["attrs"] or 0) for _, r in ok)
    t_desc = sum(int(r["desc_len"] or 0) for _, r in ok)

    sheet = load_sheet(args.sheet)
    sheet_n = len(sheet) if sheet is not None else None
    have = {n for n, _ in ok}
    miss = []
    if sheet is not None:
        for r in sheet:
            if r["link"] and r["sku"] not in have:
                miss.append(r)

    br = os.path.join(args.work, "build_report.json")
    fails = {}
    if os.path.exists(br):
        try:
            for rec in (json.load(io.open(br, encoding="utf-8")).get("records") or []):
                if rec.get("status") == "failed":
                    fails[rec.get("sku")] = rec.get("error") or ""
        except Exception:  # noqa: BLE001
            pass

    L = []
    L.append("# 美客多 %d SKU Listing 采集清单" % t_sku)
    L.append("")
    L.append("- 生成时间：%s" % time.strftime("%Y-%m-%d %H:%M:%S"))
    if dates and dates != ["日期未记录"]:
        L.append("- 采集时间：%s ～ %s" % (min(d for d in dates if d != "日期未记录") or "-",
                                          max(dates)))
    if sheet_n is not None:
        L.append("- 数据来源：飞书多维表格「商品链接」列共 %d 条记录 -> 美客多商品页" % sheet_n)
    L.append("- 落盘目录：`%s`" % args.input_root)
    if args.zip:
        L.append("- 交付压缩包：`%s`" % args.zip)
    L.append("- 每个 SKU 目录结构：")
    L.append("")
    L.append("```")
    L.append("<SKU>\\")
    L.append("├─ input.json        管道入参（site/category/title_raw/description_raw/images/core_keyword/attributes_raw/price_source）")
    L.append("├─ item.json         完整采集明细（标题/价格/类目/规格属性分组/描述/图片清单+尺寸/卖家/状态）")
    L.append("└─ img\\              商品原图（最高分辨率原图，保留原始格式与尺寸，01.jpg 起顺序编号）")
    L.append("```")
    L.append("")
    L.append("## 汇总")
    L.append("")
    L.append("| 口径 | SKU | 原图 | 规格属性字段 | 描述字数 |")
    L.append("|---|---|---|---|---|")
    for d in dates:
        rs = by_date[d]
        L.append("| %s | %d | %d | %d | %d |" % (
            d, len(rs), sum(int(r["images_files"] or 0) for _, r in rs),
            sum(int(r["attrs"] or 0) for _, r in rs), sum(int(r["desc_len"] or 0) for _, r in rs)))
    L.append("| **合计已落盘** | **%d** | **%d** | **%d** | **%d** |" % (t_sku, t_img, t_attr, t_desc))
    if sheet_n is not None:
        L.append("| 未采到 | %d | — | — | — |" % len(miss))
    L.append("")
    if sheet_n is not None:
        L.append("飞书表共 %d 个 SKU：已落盘 %d 个，未采到 %d 个。" % (sheet_n, t_sku, len(miss)))
    if cats:
        L.append("其中 %s 的原 item 已被卖家停售，Mercado Libre 将链接重定向到同一商品的**目录产品页**，"
                 "这些 SKU 采到的是目录级数据（标题／描述／规格属性／全部原图可采；价格与卖家在停售状态下不可得），"
                 "已在 `input.json`／`item.json` 中以 `data_level: \"catalog\"`、`availability: \"OutOfStock\"` 标注。"
                 % "、".join("`%s`" % n for n, _ in cats))
    L.append("")

    for d in dates:
        L.append("## 明细（采集日期 %s）" % d)
        L.append("")
        L.append("| SKU | 商品标题 | 类目 | 店铺 | 价格(MXN) | 图片 | 属性 | 描述字数 |")
        L.append("|---|---|---|---|---|---|---|---|")
        for n, r in by_date[d]:
            price = money(r["price"])
            if price is None:
                price = "不可得（停售）" if r.get("data_level") != "item" else "—"
            L.append("| `%s` | %s | %s | %s | %s | %d | %d | %d |" % (
                n, esc(r["title"])[:90], esc(r["category"]) or "—",
                esc(r["shop"]) or "—", price, r["images_files"], r["attrs"], r["desc_len"]))
        L.append("")

    if miss:
        L.append("## 未采到 %d 个 SKU" % len(miss))
        L.append("")
        L.append("| SKU | 链接 | 性质 | 动作 |")
        L.append("|---|---|---|---|")
        for r in miss:
            why = fails.get(r["sku"], "")
            kind = "未知/未尝试"
            if "404" in why:
                kind = "404（商品已删除）"
            elif "类目浏览页" in why or "下架" in why:
                kind = "已下架/删除（重定向到类目浏览页）"
            elif "验证" in why or "拦截" in why:
                kind = "被风控拦截（换出口后重采）"
            elif why:
                kind = "抓取失败"
            action = "不重试，记缺口" if kind.startswith(("404", "已下架")) else "换住宅出口后重采"
            L.append("| `%s` | %s | %s | %s |" % (r["sku"], esc(r["link"])[:120], kind, action))
        L.append("")

    if broken:
        L.append("## 目录缺件（需修）")
        L.append("")
        for n, r in broken:
            L.append("- `%s`：%s" % (n, r.get("__broken")))
        L.append("")

    L.append("## 异常与说明")
    L.append("")
    L.append("1. **清单口径**：只统计 `input/` 下真实存在的 SKU 目录（跳过 `_` 开头），共 %d 个；"
             "与抓取日志不一致时以本清单为准。" % t_sku)
    if miss:
        L.append("2. **未采到 %d 个**：见上表——已下架／404 属美客多侧数据缺失，重试无意义；被风控拦截的换住宅出口后整批重采。" % len(miss))
    if cats:
        L.append("3. **目录级数据**：%s 的 `price_source.amount` 为 `null`、`store_id` 为空字符串，其余字段与 item 级一致，可直接用于 Listing 生成。"
                 % "、".join("`%s`" % n for n, _ in cats))
    L.append("4. **自动判定项**：`category`（中文类目）与 `core_keyword` 由类目路径与标题按脚本内规则判定，可事后核对。")
    L.append("5. **描述内容**：均为卖家原文（西班牙语），完整提取未截断、未翻译。")
    L.append("6. **图片**：均取美客多最高分辨率原图（`-OO` JPEG），保留原始格式与尺寸。")
    L.append("")

    text = "\n".join(L)
    out = os.path.abspath(args.out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with io.open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    print("清单 -> %s" % out)
    print("SKU %d / 原图 %d / 属性 %d / 描述 %d 字 / 未采到 %s" % (
        t_sku, t_img, t_attr, t_desc, len(miss) if sheet is not None else "n/a"))
    if broken:
        print("!! 目录缺件 %d 个：%s" % (len(broken), ", ".join(n for n, _ in broken)))
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-root", default=os.environ.get("MLP_INPUT_ROOT") or DEFAULT_INPUT_ROOT)
    ap.add_argument("--work", default=DEFAULT_WORK)
    ap.add_argument("--sheet", default=None, help="飞书清单 JSON（默认 <work>/_sheet_rows.json）")
    ap.add_argument("--out", default=DEFAULT_OUT, help="清单输出路径")
    ap.add_argument("--zip", default="", help="清单里写的交付包名（可选）")
    ap.add_argument("--plan", action="store_true", help="只打印增量三类，不生成清单")
    ap.add_argument("--pending-out", default=None, help="配合 --plan：把待采+需补采写成 ml_batch.py 用的 JSON")
    args = ap.parse_args()
    if not args.sheet:
        args.sheet = os.path.join(args.work, "_sheet_rows.json")
    os.makedirs(args.work, exist_ok=True)
    return plan(args) if args.plan else build_manifest(args)


if __name__ == "__main__":
    sys.exit(main())