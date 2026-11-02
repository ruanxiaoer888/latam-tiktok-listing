# -*- coding: utf-8 -*-
"""只读对比：mercadolibre 抓取目录 vs 流水线 input 目录。"""
import json
from pathlib import Path

SRC = Path(r"D:\Michael\DumateProjects\mercadolibre")
INPUT = Path(r"D:\Michael\DSHProjects\listing-pipeline\input")
FIELDS = [
    "ratings.score", "ratings.reviews_count", "seller.store_name",
    "shipping.free_shipping", "shipping.returns", "certifications",
    "variants", "package_contents", "key_features", "usage_scenarios",
    "target_audience", "specs", "images",
]


def get(obj, path):
    cur = obj
    for p in path.split("."):
        if not isinstance(cur, dict) or p not in cur:
            return None
        cur = cur[p]
    return cur


def filled(v):
    return v not in (None, "", [], {})


dirs = sorted([d for d in SRC.iterdir() if d.is_dir()])
existing = {d.name for d in INPUT.iterdir() if d.is_dir() and not d.name.startswith("_")}
mapped, news, no_img, bad = [], [], 0, []
counts = {f: 0 for f in FIELDS}
img_total = 0
for d in dirs:
    info_p = d / "info.json"
    if not info_p.exists():
        bad.append(f"{d.name}: 缺 info.json")
        continue
    try:
        info = json.loads(info_p.read_text(encoding="utf-8"))
    except Exception as e:
        bad.append(f"{d.name}: info.json 解析失败 {e}")
        continue
    sku = info.get("sku") or d.name.split("-MLM-")[0]
    if sku in existing:
        mapped.append(sku)
    else:
        news.append(sku)
    for f in FIELDS:
        if filled(get(info, f)):
            counts[f] += 1
    imgs = list(d.glob("image_*.jpg"))
    img_total += len(imgs)
    if not imgs:
        no_img += 1

print(f"抓取目录：{len(dirs)} 个")
print(f"已有 input/<SKU>：{len(set(mapped))} 个 -> {sorted(set(mapped))}")
print(f"新 SKU（input 里没有）：{len(set(news))} 个，前 10：{sorted(set(news))[:10]}")
print(f"无 image_*.jpg 的目录：{no_img} 个")
print(f"平均图片数：{img_total / max(len(dirs), 1):.1f}")
print("字段非空率：")
for f in FIELDS:
    print(f"  {f:<28} {counts[f]:>3}/{len(dirs)}")
if bad:
    print("异常：")
    for b in bad[:10]:
        print("  " + b)
