# -*- coding: utf-8 -*-
r"""build_input.py — 把抓取记录落成 input/<SKU>/{input.json, item.json, img/}

用法：
    python scripts/build_input.py --raw <work>\raw_b01.json [--raw <work>\raw_catalog.json] \
        [--input-root <工作区>\input] [--work <工作区>\collector\_work] \
        [--only SKU1,SKU2] [--force] [--proxy 127.0.0.1:7890]

行为（照做，别改）：
  - 已存在且含 input.json 的目录默认**跳过**（增量采集的铁律），--force 才重建
  - 图片取最高分辨率原图 url_original，保留原始格式与尺寸，命名 01.jpg / 02.jpg …
  - 风控拦截(wall/empty)、404、已下架(delisted) 的记录**不建目录**，只写进 build_report.json
  - 目录级(catalog) 记录写 data_level/availability/catalog_product_id/note
  - 结果汇总写 <work>/build_report.json（供 gen_manifest.py --plan 判「需补采」）
"""
import argparse
import json
import os
import re
import shutil
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_FALLBACK = os.path.dirname(os.path.dirname(HERE))
DEFAULT_INPUT_ROOT = os.path.join(REPO_FALLBACK, "input")
DEFAULT_WORK = os.path.join(os.path.dirname(HERE), "_work")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36")

# ---------------- 自动判定：中文类目 / core_keyword ----------------
ACC = str.maketrans("áéíóúüñÁÉÍÓÚÑ", "aeiouunAEIOUN")


def norm(s):
    return (s or "").translate(ACC).lower()


def bucket(path):
    p = path or ""
    if ("Accesorios para Veh" in p) or ("Acc. para Motos" in p) or ("Refacciones Autos" in p):
        return "汽车摩托"
    if "Deportes y Fitness" in p:
        return "运动户外"
    if ("Electrodom" in p) or ("Iluminaci" in p) or ("Aspiradoras" in p):
        return "家电"
    if ("muebles" in norm(p)) or ("hogar" in norm(p)) or ("Cocina" in p):
        return "家居建材"
    return "五金工具"


RULES = [
    (r"porto power", "porto power hidraulico"),
    (r"opresor.{0,10}(piston|caliper)", "opresor de piston caliper"),
    (r"medidor de presion", "medidor de presion de combustible"),
    (r"prensa de junta", "kit prensa de junta esferica"),
    (r"candado|alarma motoci", "candado de disco moto"),
    (r"^bateria|bateria repuesto", "bateria de repuesto taladro 21v"),
    (r"aspiradora", "aspiradora industrial"),
    (r"hidrolavadora", "hidrolavadora electrica"),
    (r"mezcladora", "mezcladora de pintura electrica"),
    (r"termofusor", "termofusor kit"),
    (r"gatos? hidraulico|gato de botella", "gato hidraulico"),
    (r"motosierra", "motosierra electrica inalambrica"),
    (r"sopladora|soplador|ventilador turbo", "sopladora de aire inalambrica"),
    (r"ventilador", "ventilador portatil recargable"),
    (r"esmeriladora|esmeril|amoladora", "esmeriladora angular inalambrica"),
    (r"rotomartillo", "rotomartillo cincelador"),
    (r"lijadora", "lijadora orbital electrica"),
    (r"pulidora", "pulidora para autos"),
    (r"llave.{0,14}impacto|pistola.{0,14}impacto|matraca|llave de 3/4", "llave de impacto inalambrica"),
    (r"taladro|atornillador", "kit taladro atornillador inalambrico"),
    (r"pistola electrica|pistola de calor", "pistola de calor electrica"),
    (r"soldador|cautin", "kit de soldador electrico"),
    (r"lampara|linterna|reflector|farol", "lampara led recargable"),
    (r"juego de dados|kits? de herramientas|juego de herramientas|machuelos", "juego de herramientas"),
    (r"brocas", "juego de brocas para metal"),
    (r"chaleco", "chaleco reflectante"),
    (r"vibrador.{0,20}azulejo|remodelador", "vibrador de azulejo"),
]

PATHRULES = [
    (r"sopladora", "sopladora de aire inalambrica"),
    (r"gatos?", "gato hidraulico"),
    (r"motosierra", "motosierra electrica inalambrica"),
]


def keyword(title, path=""):
    t = norm(title)
    for pat, kw in RULES:
        if re.search(pat, t):
            return kw
    p = norm(path)
    for pat, kw in PATHRULES:
        if re.search(pat, p):
            return kw
    return ""


# ---------------- 图片下载 ----------------
def dl(url, dest, proxy=None, tries=3, timeout=60):
    if os.path.exists(dest) and os.path.getsize(dest) > 800:
        return True, "cached"
    if not url:
        return False, "no url"
    opener = urllib.request.build_opener()
    if proxy:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler(
            {"http": "http://" + proxy, "https": "http://" + proxy}))
    req = urllib.request.Request(url, headers={
        "User-Agent": UA, "Referer": "https://www.mercadolibre.com.mx/"})
    last = ""
    for _ in range(tries):
        try:
            with opener.open(req, timeout=timeout) as r:
                data = r.read()
            if len(data) > 800:
                with open(dest, "wb") as f:
                    f.write(data)
                return True, ""
            last = "too small (%d bytes)" % len(data)
        except Exception as e:  # noqa: BLE001
            last = str(e)
        time.sleep(1.5)
    return False, last


# ---------------- 记录规范化 ----------------
def bc_cats(bc):
    if isinstance(bc, dict) and bc.get("categories"):
        return [c.get("label", {}).get("text") for c in bc["categories"] if c.get("label")]
    return []


def normalize(rec, sku):
    """把 ml_extract.js / catalog_extract.js 的记录统一成一种形状。"""
    is_catalog = ("nordic_id" in rec or "catalog_id" in rec) and not rec.get("item_id")
    if is_catalog:
        nid = rec.get("nordic_id") or rec.get("catalog_id")
        return {
            "sku": sku, "data_level": "catalog", "url": rec.get("catalog_url") or rec.get("url"),
            "resolved_url": rec.get("catalog_url") or rec.get("url"),
            "item_id": None, "catalog_product_id": nid,
            "canonical_url": rec.get("canonical_url"),
            "title": rec.get("title"), "subtitle": rec.get("subtitle"), "reviews": rec.get("reviews"),
            "price": rec.get("price"), "category_id": None, "category_path": None,
            "breadcrumb_cats": bc_cats(rec.get("breadcrumb")),
            "item_status": "out_of_stock", "item_condition": None, "listing_type_id": None,
            "seller_id": None, "shop_name": "", "seller_data": rec.get("seller_data"),
            "status_message": rec.get("unavailable_text") or "Este producto no está disponible",
            "spec_groups": rec.get("spec_groups") or [], "highlighted_kv": rec.get("highlighted_kv") or [],
            "attributes_raw": rec.get("attributes_raw") or {},
            "description_title": rec.get("description_title"), "description_text": rec.get("description_text"),
            "pictures": rec.get("pictures") or [], "variations": [], "availability": "OutOfStock",
            "note": rec.get("note") or "原 item 已被卖家停售，ML 重定向至同一商品的目录产品页；价格/卖家在停售状态下不可得",
        }
    sd = rec.get("seller_data") or ""
    m = re.search(r'"shop_name"\s*:\s*"([^"]+)"', sd)
    return {
        "sku": sku, "data_level": rec.get("data_level") or "item", "url": rec.get("url"),
        "resolved_url": rec.get("resolved_url") or rec.get("url"),
        "item_id": rec.get("item_id"), "catalog_product_id": None,
        "canonical_url": rec.get("canonical_url"),
        "title": rec.get("title"), "subtitle": rec.get("subtitle"), "reviews": rec.get("reviews"),
        "price": rec.get("price"), "category_id": rec.get("category_id"),
        "category_path": rec.get("category_path"), "breadcrumb_cats": bc_cats(rec.get("breadcrumb")),
        "item_status": rec.get("item_status"), "item_condition": rec.get("item_condition"),
        "listing_type_id": rec.get("listing_type_id"), "seller_id": rec.get("seller_id"),
        "shop_name": m.group(1) if m else "", "seller_data": rec.get("seller_data"),
        "status_message": rec.get("status_message"),
        "spec_groups": rec.get("spec_groups") or [], "highlighted_kv": rec.get("highlighted_kv") or [],
        "attributes_raw": rec.get("attributes_raw") or {},
        "description_title": rec.get("description_title"), "description_text": rec.get("description_text"),
        "pictures": rec.get("pictures") or [], "variations": rec.get("variations") or [],
        "availability": rec.get("availability"), "note": rec.get("note") or "",
    }


def failure_reason(rec):
    b = rec.get("blocked")
    if b == "wall":
        return "Mercado Libre 安全验证（验证码墙）——网络出口被拦，换住宅出口后整批重采"
    if b == "empty":
        return "页面无商品数据（疑似验证码墙/壳页）——先按 03-风控与失效排查.md 判性质"
    if b == "404":
        return "链接 404（商品疑似已删除）"
    if b == "delisted":
        return "链接被重定向到类目浏览页（商品已下架/删除）"
    return rec.get("error") or "未取到商品数据"


# ---------------- 建目录 ----------------
def build_one(r, input_root, work, proxy, force):
    sku = r["sku"]
    d = os.path.join(input_root, sku)
    ip = os.path.join(d, "input.json")
    if os.path.exists(ip) and not force:
        return {"sku": sku, "dir": d, "status": "skipped", "note": "目录已存在（增量采集不覆盖）"}
    if not r.get("title"):
        return {"sku": sku, "dir": d, "status": "failed", "error": failure_reason(r)}

    path = " > ".join(r.get("category_path") or [])
    cat = bucket(" > ".join((r.get("breadcrumb_cats") or []) + [path]))
    kw = keyword(r.get("title"), cat)
    shop = r.get("shop_name") or ""
    imgd = os.path.join(d, "img")
    os.makedirs(imgd, exist_ok=True)

    pics = r.get("pictures") or []
    metas = []

    def worker(i, p):
        fn = "%02d.jpg" % i
        dest = os.path.join(imgd, fn)
        good, err = dl(p.get("url_original"), dest, proxy=proxy)
        meta = {"index": i, "file": "./img/" + fn, "url_original": p.get("url_original"),
                "page_width": p.get("width"), "page_height": p.get("height")}
        if good:
            meta["bytes"] = os.path.getsize(dest)
            try:
                from PIL import Image
                with Image.open(dest) as im:
                    meta["format"] = im.format
                    meta["width"], meta["height"] = im.size
            except Exception as e:  # noqa: BLE001
                if "PIL" not in str(e):
                    meta["pillow_error"] = str(e)
        else:
            meta["error"] = "download:" + err
        return i, meta

    ok = 0
    if pics:
        with ThreadPoolExecutor(max_workers=4) as ex:
            for _i, meta in ex.map(lambda a: worker(*a), list(enumerate(pics, 1))):
                metas.append(meta)
                if "error" not in meta:
                    ok += 1

    _pr = r.get("price")
    if isinstance(_pr, dict):
        price_val = _pr.get("value")
    elif isinstance(_pr, (int, float)):
        price_val = _pr
    else:
        price_val = None
    input_json = {
        "product_id": sku,
        "source": "mercadolibre",
        "source_url": r.get("resolved_url") or r.get("url"),
        "site": "MX",
        "category": cat,
        "title_raw": r.get("title"),
        "description_raw": r.get("description_text"),
        "price_source": {"currency": "MXN", "amount": price_val},
        "attributes_raw": r.get("attributes_raw") or {},
        "variations": [],
        "images": [m["file"] for m in metas],
        "store_id": shop,
        "core_keyword": kw,
    }
    if r.get("data_level") != "item":
        input_json["data_level"] = r["data_level"]
        input_json["availability"] = r.get("availability")
        input_json["catalog_product_id"] = r.get("catalog_product_id")
        input_json["note"] = r.get("note")

    desc = r.get("description_text") or ""
    item_json = {
        "sku": sku, "item_id": r.get("item_id"), "site": "MX", "source": "mercadolibre",
        "source_url": r.get("resolved_url") or r.get("url"),
        "canonical_url": r.get("canonical_url"),
        "title": r.get("title"), "subtitle": r.get("subtitle"), "price": r.get("price"),
        "category": {"bucket_zh": cat, "ml_category_id": r.get("category_id"),
                     "ml_category_path": r.get("category_path"),
                     "ml_breadcrumb": r.get("breadcrumb_cats")},
        "attributes": {"groups": r.get("spec_groups") or [],
                       "flat": r.get("attributes_raw") or {},
                       "highlighted": r.get("highlighted_kv") or []},
        "description": {"title": r.get("description_title"), "text": desc, "char_count": len(desc)},
        "images": metas, "reviews": r.get("reviews"), "seller_id": r.get("seller_id"),
        "shop_name": shop, "seller_data": r.get("seller_data"),
        "item_status": r.get("item_status"), "item_condition": r.get("item_condition"),
        "listing_type_id": r.get("listing_type_id"), "status_message": r.get("status_message"),
        "core_keyword": kw, "store_id": shop,
        "collected_at": time.strftime("%Y-%m-%d"),
    }
    if r.get("data_level") != "item":
        item_json["data_level"] = r["data_level"]
        item_json["availability"] = r.get("availability")
        item_json["catalog_product_id"] = r.get("catalog_product_id")
        item_json["note"] = r.get("note")

    with open(ip, "w", encoding="utf-8") as f:
        json.dump(input_json, f, ensure_ascii=False, indent=2)
    with open(os.path.join(d, "item.json"), "w", encoding="utf-8") as f:
        json.dump(item_json, f, ensure_ascii=False, indent=2)

    rep = {"sku": sku, "dir": d, "status": "ok", "data_level": r.get("data_level"),
           "shop_name": shop, "seller_id": r.get("seller_id"), "category": cat,
           "images_ok": ok, "images_total": len(pics), "attrs": len(r.get("attributes_raw") or {}),
           "desc_len": len(desc), "core_keyword": kw, "item_id": r.get("item_id"),
           "catalog_product_id": r.get("catalog_product_id"), "item_status": r.get("item_status"),
           "status_message": r.get("status_message"), "price": price_val}
    print("%-12s %-16s %-6s [%s] imgs %2d/%2d attrs %3d desc %5d kw=%s" % (
        sku, shop or "-", cat, r.get("data_level"), ok, len(pics),
        len(r.get("attributes_raw") or {}), len(desc), kw or "<EMPTY>"), flush=True)
    return rep


def load_records(paths):
    recs = []
    for p in paths:
        data = json.load(open(p, encoding="utf-8"))
        if isinstance(data, dict):
            data = [data]
        for r in data:
            sku = (r.get("sku") or "").strip()
            if sku:
                recs.append((sku, r))
    return recs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", action="append", required=True, help="抓取结果 JSON（可多次传）")
    ap.add_argument("--input-root", default=os.environ.get("MLP_INPUT_ROOT") or DEFAULT_INPUT_ROOT)
    ap.add_argument("--work", default=DEFAULT_WORK)
    ap.add_argument("--only", default="", help="只处理这些 SKU（逗号分隔）")
    ap.add_argument("--force", action="store_true", help="覆盖已存在的 SKU 目录（默认跳过）")
    ap.add_argument("--proxy", default=None, help="图片下载走代理，如 127.0.0.1:7890")
    args = ap.parse_args()

    os.makedirs(args.work, exist_ok=True)
    recs = load_records(args.raw)
    only = set(s.strip() for s in args.only.split(",") if s.strip())
    report = []
    for sku, r in recs:
        if only and sku not in only:
            continue
        report.append(build_one(normalize(r, sku), args.input_root, args.work, args.proxy, args.force))

    out = os.path.join(args.work, "build_report.json")
    payload = {"generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
               "input_root": args.input_root, "records": report}
    with open(out, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)

    ok = [r for r in report if r["status"] == "ok"]
    skip = [r for r in report if r["status"] == "skipped"]
    bad = [r for r in report if r["status"] == "failed"]
    print("\n落盘 %d / 跳过 %d / 未取到 %d   -> %s" % (len(ok), len(skip), len(bad), out))
    for r in bad:
        print("  未取到 %-12s %s" % (r["sku"], (r.get("error") or "")[:80]))
    return 0


if __name__ == "__main__":
    sys.exit(main())