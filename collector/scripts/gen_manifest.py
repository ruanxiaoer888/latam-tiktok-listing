# -*- coding: utf-8 -*-
r"""gen_manifest.py — 增量规划(--plan) 与 采集清单生成（缺件显式化版）

用法：
    # 1) 增量规划：打印完整性 + 待采/需补采，不写文件
    python scripts/gen_manifest.py --plan
    python scripts/gen_manifest.py --plan --allow-incomplete   # 缺件也放行

    # 2) 顺手把「待采 + 需补采」写成 ml_batch.py 能直接吃的清单
    python scripts/gen_manifest.py --plan --pending-out collector/_work/pending.json

    # 3) 生成采集清单（交付物之一）
    python scripts/gen_manifest.py --out output/_batch/采集清单-自动.md --zip ml-listing-input-17sku.zip

三类目录（不再静默跳过）：
  - 完整     input.json + item.json + img\ 齐全，JSON 都能解析 → 可交付、可生成
  - 只有 facts  目录里只有 facts.json / img_manifest.csv，没有 raw
                （input.json / item.json / img\ 被 .gitignore 排除，换机没搬 U 盘就会这样）
  - 损坏     facts.json 或 raw JSON 解析失败；或 raw 不全（只有其中一个文件 / 缺 img\）

退出码：
  0 = 全部完整
  1 = 存在「只有 facts」或「损坏」（加 --allow-incomplete 放行，仍打印警告）

判据（照做，别改）：
  - 已采（跳过）：只有「完整」目录才计入
  - 待采（新增）：飞书表里有链接、但没有完整目录的 SKU
  - 需补采：--work/build_report.json 里 status=failed 的 SKU（上次被拦/失效），
            或 --work/pending.json 里你手工追加的 SKU
  - 清单必须与实际目录一致：只统计 input/ 下真实存在的目录，不靠抓取日志凑数
  - 清单正文只列「完整」SKU；完整性计数写在开头，全部目录的状态单独成表
"""
import argparse
import io
import json
import os
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

STATE_COMPLETE = "complete"
STATE_FACTS_ONLY = "facts_only"
STATE_BROKEN = "broken"
STATE_LABEL = {
    STATE_COMPLETE: "完整",
    STATE_FACTS_ONLY: "只有 facts",
    STATE_BROKEN: "损坏",
}


# ---------------- 读盘 ----------------
def load_json(path):
    # utf-8-sig：人工用记事本改过的 facts.json 可能带 BOM，不该被当成「损坏」
    with io.open(path, encoding="utf-8-sig") as f:
        return json.load(f)


def load_sheet(path):
    if not path or not os.path.exists(path):
        return None
    try:
        data = load_json(path)
    except Exception as e:  # noqa: BLE001
        print("!! 读不了清单 %s: %s" % (path, e))
        return None
    rows = data.get("rows") or [] if isinstance(data, dict) else data
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


def classify_dir(name, d):
    """把一个 SKU 目录归到 完整 / 只有 facts / 损坏，绝不静默跳过。"""
    rec = {"sku": name, "dir": d, "state": STATE_COMPLETE, "reason": "",
           "facts": None, "raw": None, "has_facts": False, "img_files": 0}
    ip = os.path.join(d, "input.json")
    itp = os.path.join(d, "item.json")
    fp = os.path.join(d, "facts.json")
    img_dir = os.path.join(d, "img")
    files = sorted(f for f in (os.listdir(img_dir) if os.path.isdir(img_dir) else []))
    rec["img_files"] = len(files)

    if os.path.exists(fp):
        rec["has_facts"] = True
        try:
            rec["facts"] = load_json(fp)
        except Exception as e:  # noqa: BLE001
            rec["state"] = STATE_BROKEN
            rec["reason"] = "facts.json JSON 解析失败：%s" % e
            return rec

    has_ip, has_itp = os.path.exists(ip), os.path.exists(itp)
    errors, inp, itm = [], None, None
    if has_ip:
        try:
            inp = load_json(ip)
        except Exception as e:  # noqa: BLE001
            errors.append("input.json 解析失败：%s" % e)
    if has_itp:
        try:
            itm = load_json(itp)
        except Exception as e:  # noqa: BLE001
            errors.append("item.json 解析失败：%s" % e)
    if errors:
        rec["state"] = STATE_BROKEN
        rec["reason"] = "；".join(errors)
        return rec

    if not has_ip and not has_itp:
        rec["state"] = STATE_FACTS_ONLY
        if rec["has_facts"]:
            rec["reason"] = "只有 facts.json（缺 input.json / item.json / img\\）"
        else:
            rec["reason"] = "空目录（无 raw、无 facts.json）"
        return rec

    if not has_ip or not has_itp:
        rec["state"] = STATE_BROKEN
        rec["reason"] = "raw 不全：缺 %s" % ("input.json" if not has_ip else "item.json")
        return rec

    declared = len(inp.get("images") or [])
    if declared > 0 and not files:
        rec["state"] = STATE_BROKEN
        rec["reason"] = "缺 img\\：input.json 声明 %d 张，实际 0 张" % declared
        return rec

    imgs = itm.get("images") or []
    desc = itm.get("description") or {}
    cat = itm.get("category") or {}
    rec["raw"] = {
        "sku": name,
        "data_level": inp.get("data_level") or itm.get("data_level") or "item",
        "title": itm.get("title") or inp.get("title_raw") or "",
        "category": cat.get("bucket_zh") or inp.get("category") or "",
        "shop": itm.get("shop_name") or inp.get("store_id") or "",
        "price": (inp.get("price_source") or {}).get("amount"),
        "images_declared": int(declared),
        "images_files": int(len(files)),
        "attrs": int(len(inp.get("attributes_raw") or (itm.get("attributes") or {}).get("flat") or {})),
        "desc_len": int(desc.get("char_count") if desc.get("char_count") is not None
                        else len(desc.get("text") or "")),
        "collected_at": itm.get("collected_at") or "",
        "item_id": itm.get("item_id"),
        "status": itm.get("item_status") or "",
        "note": inp.get("note") or itm.get("note") or "",
    }
    return rec


def scan_input(input_root):
    return [classify_dir(name, d) for name, d in scanned_dirs(input_root)]


def split_by_state(scan):
    complete = [r for r in scan if r["state"] == STATE_COMPLETE]
    facts_only = [r for r in scan if r["state"] == STATE_FACTS_ONLY]
    broken = [r for r in scan if r["state"] == STATE_BROKEN]
    return complete, facts_only, broken


def short_list(recs, limit=20):
    names = [r["sku"] for r in recs]
    if len(names) <= limit:
        return ", ".join(names)
    return ", ".join(names[:limit]) + " … 共 %d 个" % len(names)


def print_incomplete_details(facts_only, broken, limit=20):
    if facts_only:
        print("  只有 facts（缺 raw，不能生成/交付）：%d 个" % len(facts_only))
        for r in facts_only[:limit]:
            print("    - %-14s %s" % (r["sku"], r["reason"]))
        if len(facts_only) > limit:
            print("    … 共 %d 个" % len(facts_only))
    if broken:
        print("  损坏（需修）：%d 个" % len(broken))
        for r in broken[:limit]:
            print("    - %-14s %s" % (r["sku"], r["reason"]))
        if len(broken) > limit:
            print("    … 共 %d 个" % len(broken))


# ---------------- 增量规划 ----------------
def plan(args, scan, facts_only, broken):
    sheet = load_sheet(args.sheet)
    have = {r["sku"] for r in scan if r["state"] == STATE_COMPLETE}

    # 先算「需补采」= 上次失败（build_report.json）或手工登记（pending.json），且当前无完整目录
    retry = []
    br = os.path.join(args.work, "build_report.json")
    if os.path.exists(br):
        try:
            rep = load_json(br)
            for rec in rep.get("records") or []:
                if rec.get("status") == "failed" and rec.get("sku") not in have:
                    retry.append({"sku": rec.get("sku"), "url": rec.get("url") or "",
                                  "why": rec.get("error") or ""})
        except Exception as e:  # noqa: BLE001
            print("!! 读不了 build_report.json: %s" % e)
    pend = os.path.join(args.work, "pending.json")
    if os.path.exists(pend):
        try:
            extra = load_json(pend)
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

    # 待采（新增）= 清单里有链接、当前没有「完整」目录、且不在需补采里
    rset = {r["sku"] for r in retry}
    todo = []
    if sheet is not None:
        for r in sheet:
            if r["link"] and r["sku"] not in have and r["sku"] not in rset:
                todo.append({"sku": r["sku"], "url": r["link"]})

    print("input: %s" % args.input_root)
    print("清单: %s%s" % (args.sheet, "" if sheet is not None else "  (未找到，只按本地目录判断)"))
    print("")
    print("完整性: 完整 %d / 只有 facts %d / 损坏 %d（共 %d 个 SKU 目录）" % (
        len(scan) - len(facts_only) - len(broken), len(facts_only), len(broken), len(scan)))
    print("已采（完整）  : %3d%s" % (len(have), "  " + short_list(
        [r for r in scan if r["state"] == STATE_COMPLETE]) if have else ""))
    print_incomplete_details(facts_only, broken)
    print("待采（新增）  : %3d%s" % (len(todo), "  " + ", ".join(r["sku"] for r in todo[:12]) if todo else ""))
    print("需补采（上次失败）: %3d%s" % (len(retry), "  " + ", ".join(r["sku"] for r in retry[:12]) if retry else ""))
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


def build_status_table(scan):
    L = ["| SKU | 状态 | 类目 | 标题 | facts状态 | 采集日期 | 图片(实际/声明) | 属性 | 描述字数 | 说明 |",
         "|---|---|---|---|---|---|---|---|---|---|"]
    for r in scan:
        facts = r.get("facts") or {}
        if r["state"] == STATE_COMPLETE:
            raw = r["raw"]
            cat = raw["category"] or facts.get("category") or "—"
            title = raw["title"]
            fstatus = facts.get("status") or "—"
            date = raw["collected_at"] or "—"
            img = "%d/%d" % (raw["images_files"], raw["images_declared"])
            attrs = str(raw["attrs"])
            desc = str(raw["desc_len"])
            note = raw["note"] or ""
        else:
            cat = facts.get("category") or "—"
            title = ((facts.get("identity") or {}).get("title_raw") or "")
            fstatus = facts.get("status") or ("无 facts" if not r["has_facts"] else "—")
            date = "—"
            fimg = len(facts.get("images") or [])
            img = ("%d（事实卡）" % fimg) if r["has_facts"] else "—"
            attrs = str(len(facts.get("raw_attributes") or {})) if r["has_facts"] else "—"
            desc = "—"
            note = r["reason"]
        L.append("| `%s` | %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
            r["sku"], STATE_LABEL[r["state"]], esc(cat) or "—", esc(title)[:60] or "—",
            esc(fstatus) or "—", date, img, attrs, desc, esc(note)))
    return L


def build_manifest(args, scan, facts_only, broken):
    complete = [r for r in scan if r["state"] == STATE_COMPLETE]
    cats = [r for r in complete if r["raw"]["data_level"] != "item"]

    by_date = {}
    for r in complete:
        d = r["raw"]["collected_at"] or "日期未记录"
        by_date.setdefault(d, []).append(r)
    dates = sorted(by_date.keys(), reverse=True)
    real_dates = [d for d in dates if d != "日期未记录"]

    t_img = sum(int(r["raw"]["images_files"] or 0) for r in complete)
    t_attr = sum(int(r["raw"]["attrs"] or 0) for r in complete)
    t_desc = sum(int(r["raw"]["desc_len"] or 0) for r in complete)

    sheet = load_sheet(args.sheet)
    sheet_n = len(sheet) if sheet is not None else None
    have = {r["sku"] for r in complete}
    miss = []
    if sheet is not None:
        for r in sheet:
            if r["link"] and r["sku"] not in have:
                miss.append(r)

    br = os.path.join(args.work, "build_report.json")
    fails = {}
    if os.path.exists(br):
        try:
            for rec in (load_json(br).get("records") or []):
                if rec.get("status") == "failed":
                    fails[rec.get("sku")] = rec.get("error") or ""
        except Exception:  # noqa: BLE001
            pass

    L = []
    L.append("# 美客多 Listing 采集清单（自动生成）")
    L.append("")
    L.append("- 生成时间：%s" % time.strftime("%Y-%m-%d %H:%M:%S"))
    L.append("- 生成脚本：`collector\\scripts\\gen_manifest.py --out`（可重跑，勿手改）")
    if real_dates:
        L.append("- 采集时间：%s ～ %s" % (min(real_dates), max(real_dates)))
    if sheet_n is not None:
        L.append("- 数据来源：飞书多维表格「商品链接」列共 %d 条记录 -> 美客多商品页" % sheet_n)
    # 落盘目录不要写死盘符：仓库内的路径显示为相对路径，换机器也能照抄
    shown_root = args.input_root
    try:
        repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        rel = os.path.relpath(os.path.abspath(args.input_root), repo_root)
        if not rel.startswith(".."):
            shown_root = rel.replace("\\", "/")
    except Exception:
        pass
    L.append("- 落盘目录：`%s`（%d 个 SKU 目录，跳过 `_` 开头）" % (
        shown_root, len(scan)))
    if args.zip:
        L.append("- 交付压缩包：`%s`" % args.zip)
    L.append("- **完整性口径**：完整 %d / 只有 facts %d / 损坏 %d" % (
        len(complete), len(facts_only), len(broken)))
    L.append("")
    if facts_only or broken:
        L.append("> ⚠ 有 %d 个目录只有 facts.json、缺 `input.json` / `item.json` / `img\\`，另有 %d 个损坏。"
                 % (len(facts_only), len(broken)))
        L.append("> 这些目录只保留事实卡主本，**不能用于重新生成 Listing，也不计入交付包**；")
        L.append("> 需从家里机器用 U 盘/网盘补齐 `input\\<SKU>\\` 的 raw 文件（见 `采集怎么用.md`）。")
        L.append("")
    L.append("- 每个完整 SKU 目录结构：")
    L.append("")
    L.append("```")
    L.append("<SKU>\\")
    L.append("├─ input.json        管道入参（site/category/title_raw/description_raw/images/core_keyword/attributes_raw/price_source）")
    L.append("├─ item.json         完整采集明细（标题/价格/类目/规格属性分组/描述/图片清单+尺寸/卖家/状态）")
    L.append("├─ facts.json        事实卡（qa\\build_facts.py 生成，知识库主本）")
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
            d, len(rs), sum(int(r["raw"]["images_files"] or 0) for r in rs),
            sum(int(r["raw"]["attrs"] or 0) for r in rs), sum(int(r["raw"]["desc_len"] or 0) for r in rs)))
    L.append("| **完整合计（可交付）** | **%d** | **%d** | **%d** | **%d** |" % (
        len(complete), t_img, t_attr, t_desc))
    L.append("| 只有 facts（缺 raw，不计入交付） | %d | — | — | — |" % len(facts_only))
    L.append("| 损坏（需修） | %d | — | — | — |" % len(broken))
    L.append("| **目录合计** | **%d** | — | — | — |" % len(scan))
    if sheet_n is not None:
        L.append("| 未采到 | %d | — | — | — |" % len(miss))
    L.append("")
    if sheet_n is not None:
        L.append("飞书表共 %d 个 SKU：已落盘（完整）%d 个，未采到 %d 个。" % (sheet_n, len(complete), len(miss)))
    if cats:
        L.append("其中 %s 的原 item 已被卖家停售，Mercado Libre 将链接重定向到同一商品的**目录产品页**，"
                 "这些 SKU 采到的是目录级数据（标题／描述／规格属性／全部原图可采；价格与卖家在停售状态下不可得），"
                 "已在 `input.json`／`item.json` 中以 `data_level: \"catalog\"`、`availability: \"OutOfStock\"` 标注。"
                 % "、".join("`%s`" % r["sku"] for r in cats))
    L.append("")

    if complete:
        L.append("## 明细（只列完整 SKU）")
        L.append("")
        for d in dates:
            L.append("### 采集日期 %s（%d 个）" % (d, len(by_date[d])))
            L.append("")
            L.append("| SKU | 商品标题 | 类目 | 店铺 | 价格(MXN) | 图片 | 属性 | 描述字数 |")
            L.append("|---|---|---|---|---|---|---|---|")
            for r in by_date[d]:
                raw = r["raw"]
                price = money(raw["price"])
                if price is None:
                    price = "不可得（停售）" if raw.get("data_level") != "item" else "—"
                L.append("| `%s` | %s | %s | %s | %s | %d | %d | %d |" % (
                    r["sku"], esc(raw["title"])[:90], esc(raw["category"]) or "—",
                    esc(raw["shop"]) or "—", price, raw["images_files"], raw["attrs"], raw["desc_len"]))
            L.append("")
    else:
        L.append("## 明细")
        L.append("")
        L.append("_当前没有任何「完整」目录（raw 齐全），因此没有可交付明细。_")
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

    L.append("## 全部 SKU 状态表（%d 个目录）" % len(scan))
    L.append("")
    L.extend(build_status_table(scan))
    L.append("")

    L.append("## 异常与说明")
    L.append("")
    notes = []
    notes.append("**完整性口径**：`完整 %d / 只有 facts %d / 损坏 %d`，共 %d 个目录；"
                 "只有「完整」目录计入明细与交付，缺失项逐条列在上面状态表。" % (
                     len(complete), len(facts_only), len(broken), len(scan)))
    if facts_only:
        notes.append("**只有 facts 的 %d 个**：raw 数据（`input.json`、`item.json`、`img\\`）不进 git，"
                     "换机后需要从原采集机用 U 盘/网盘搬回；补齐前这些 SKU 不能重新生成 Listing。" % len(facts_only))
    if broken:
        notes.append("**损坏 %d 个**：JSON 解析失败或 raw 不全，逐条原因见状态表「说明」列，需修复后重跑。" % len(broken))
    if miss:
        notes.append("**未采到 %d 个**：见上表——已下架／404 属美客多侧数据缺失，重试无意义；被风控拦截的换住宅出口后整批重采。" % len(miss))
    if cats:
        notes.append("**目录级数据**：%s 的 `price_source.amount` 为 `null`、`store_id` 为空字符串，其余字段与 item 级一致，可直接用于 Listing 生成。"
                     % "、".join("`%s`" % r["sku"] for r in cats))
    notes.append("**自动判定项**：`category`（中文类目）与 `core_keyword` 由类目路径与标题按脚本内规则判定，可事后核对。")
    notes.append("**描述内容**：均为卖家原文（西班牙语），完整提取未截断、未翻译。")
    notes.append("**图片**：均取美客多最高分辨率原图（`-OO` JPEG），保留原始格式与尺寸。")
    for i, note in enumerate(notes, 1):
        L.append("%d. %s" % (i, note))
    L.append("")

    text = "\n".join(L)
    out = os.path.abspath(args.out)
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with io.open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    print("清单 -> %s" % out)
    print("完整 %d / 只有 facts %d / 损坏 %d / 目录合计 %d" % (
        len(complete), len(facts_only), len(broken), len(scan)))
    print("SKU %d / 原图 %d / 属性 %d / 描述 %d 字 / 未采到 %s" % (
        len(complete), t_img, t_attr, t_desc, len(miss) if sheet is not None else "n/a"))
    return 0


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-root", default=os.environ.get("MLP_INPUT_ROOT") or DEFAULT_INPUT_ROOT)
    ap.add_argument("--work", default=DEFAULT_WORK)
    ap.add_argument("--sheet", default=None, help="飞书清单 JSON（默认 <work>/_sheet_rows.json）")
    ap.add_argument("--out", default=DEFAULT_OUT, help="清单输出路径")
    ap.add_argument("--zip", default="", help="清单里写的交付包名（可选）")
    ap.add_argument("--plan", action="store_true", help="只打印完整性 + 增量三类，不生成清单")
    ap.add_argument("--pending-out", default=None, help="配合 --plan：把待采+需补采写成 ml_batch.py 用的 JSON")
    ap.add_argument("--allow-incomplete", action="store_true",
                    help="存在「只有 facts」/「损坏」时也返回 0（仍打印警告）")
    args = ap.parse_args()
    if not args.sheet:
        args.sheet = os.path.join(args.work, "_sheet_rows.json")
    os.makedirs(args.work, exist_ok=True)

    scan = scan_input(args.input_root)
    if not scan:
        print("!! %s 下没有 SKU 目录" % args.input_root)
        return 2
    complete, facts_only, broken = split_by_state(scan)

    if args.plan:
        rc = plan(args, scan, facts_only, broken)
    else:
        rc = build_manifest(args, scan, facts_only, broken)
    if rc != 0:
        return rc

    if facts_only or broken:
        summary = "只有 facts %d 个、损坏 %d 个（%d 个完整 / 共 %d 个目录）" % (
            len(facts_only), len(broken), len(complete), len(scan))
        if args.allow_incomplete:
            print("\n[WARN] --allow-incomplete：存在缺件/损坏：%s；已放行，交付与生成只使用「完整」SKU。" % summary)
            return 0
        print("\n[FAIL] 存在缺件/损坏：%s" % summary)
        print("[HINT] 补齐 input/<SKU>/ 的 raw 文件，或加 --allow-incomplete 明确放行。")
        return 1
    print("\n[OK] 全部 %d 个 SKU 目录完整（raw 齐全）。" % len(scan))
    return 0


if __name__ == "__main__":
    sys.exit(main())
