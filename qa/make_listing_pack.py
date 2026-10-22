# -*- coding: utf-8 -*-
r"""make_listing_pack.py — 把一个 SKU 的「生成 TikTok Listing 所需的全部材料」打成一个 md 文件。

输入（都已存在）：
    input\<SKU>\facts.json          事实卡（唯一事实源）
    input\<SKU>\item.json           只用来校验原文是否存在（不直接喂给模型）
    output\_batch\scene\<SKU>.md     场景卡（qa\build_scene.py 生成）

输出：
    output\_packs\<SKU>.md           一份可直接发给任意 Agent 的生成包
    output\_packs\_index.md          --all 时的索引

用法（仓库根目录）：
    python qa\make_listing_pack.py --sku ABU6000014
    python qa\make_listing_pack.py --all            # 所有 status=verified 的 SKU
    python qa\make_listing_pack.py --all --out output\_packs_2

生成后：把 output\_packs\<SKU>.md 发给 Agent，产出 output\批次YYYYMMDD\listing-<SKU>.txt，
再跑 python qa\run_batch.py --input-root input --listing-dir output\批次YYYYMMDD --site MX。
"""
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INPUT = ROOT / "input"
SCENE = ROOT / "output" / "_batch" / "scene"
BATCH = ROOT / "output" / "批次20261022-v2"
OUT = ROOT / "output" / "_packs"

CAT_PACK = {
    "五金工具": "01-五金工具.md",
    "汽车摩托": "02-汽车摩托.md",
    "家居建材": "03-家居建材.md",
    "运动户外": "04-运动户外.md",
    "宠物用品": "05-宠物用品.md",
    "厨房用品": "06-厨房用品.md",
    "家电": "07-家电.md",
    "时尚配件": "08-时尚配件.md",
    "服装": "09-服装.md",
}
# 范本：同/近类目、已通过校验的成稿。学结构，不抄参数。
EXAMPLES = {
    "五金工具": ["AMU0000003", "ABU5000000"],
    "汽车摩托": ["ATVMX09400", "25011401"],
    "家电": ["AHR6C50002", "ATVMX16200"],
    "运动户外": ["ME260117"],
    "服装": [],
}

RULES = """## 2. 硬规则（违反即返工）

- 标题：60–80 字符（**汽车摩托 80–120**）；`para` 用途词尽量进前 30 字符；核心词片段齐全；品牌放句尾；只放一个可验证规格；禁 Emoji/促销词/价格。
- 首行（钩子）：≤60 字符，必须出现**产品名词** + 具体场景/痛点；问句比例不超过一半；禁 `alta calidad` / `perfecto para` 这类空泛开场。
- 卖点：4–5 条。第一条讲最痛的利益、不许以参数开头；第 4 条写**差异化**（铜芯电机 / 6 档 / 含替换碳刷 / 双头…）；至少一条**决策信息**（哪种耗材用在哪一步、含不含、要不要另买）。
- 规格：`📋 Especificaciones Técnicas:` 逐行；参数只取事实卡；facts 没有而场景卡原文有明确数值的可写；**电压一律以 facts 为准**；没出处不写。
- 包装：`📦 Contenido del Paquete:` 按 facts.package.included 逐件（`x1` 格式）；`not_included` 非空必须写 **NO incluidas**。
- FAQ：`💡 Preguntas Frecuentes (FAQ):` 固定 3 条：兼容/适用 → 含什么/怎么用 → 隐藏成本（耗材、配件、保养）。高价品可加第 4 条「¿Por qué cuesta más que otros?」。
- 颜色：facts.raw_attributes.Color 有值就在规格区加 `- Color: X`；没有就不写。
- 语言：es-MX；禁中文/葡语/英文混排。
- 禁用：`Compra protegida`、`envío gratis`、`entrega inmediata`、`pago contra entrega`、`solo por hoy`、`última pieza`、`100%`（材质语境除外）、绝对化、医疗宣称、站外导流、`NOM/INMETRO/ANATEL/UN38.3`（本批认证 missing）。
- 不写价格、不编赠品/保修/物流时效。
- CTA 一行：`Compra segura con pago dentro de TikTok Shop.` + 一句核对建议。
"""


def load_json(p):
    return json.load(open(p, encoding="utf-8-sig"))


def g(d, *path, default=None):
    cur = d
    for k in path:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur


def fmt(v, unit=""):
    if v in (None, "", []):
        return "-"
    if isinstance(v, list):
        return " / ".join(str(x) for x in v) if v else "-"
    return "%s%s" % (v, unit)


def facts_block(f):
    p = f.get("power") or {}
    s = f.get("size") or {}
    lines = [
        "| 字段 | 值 |",
        "|---|---|",
        "| SKU | %s |" % f.get("product_id"),
        "| 类目 | %s |" % (f.get("category") or "-"),
        "| 品牌 / 型号 | %s / %s |" % (g(f, "identity", "brand"), g(f, "identity", "model")),
        "| 原标题（美客多） | %s |" % (g(f, "identity", "title_raw") or "-"),
        "| 平台核心词 | %s |" % (g(f, "extras", "core_keyword") or "-"),
        "| 价格 MXN（后台字段，不写正文） | %s |" % (g(f, "site_profiles", "MX", "price") or "-"),
        "| 供电类型 | %s |" % (p.get("type") or "-"),
        "| 可写功率 | %s |" % (("%s W" % p.get("w")) if p.get("state_power") and p.get("w") else "不写"),
        "| 电压 / 电池电压 / 充电器电压 | %s / %s / %s |" % (
            fmt(p.get("voltage_v"), " V"), fmt(p.get("battery_v"), " V"), fmt(p.get("charger_v"), " V")),
        "| 尺寸（L/W/H/直径 cm） | %s / %s / %s / %s |" % (
            fmt(s.get("length_cm")), fmt(s.get("width_cm")), fmt(s.get("height_cm")), fmt(s.get("diameter_cm"))),
        "| 重量 kg | %s |" % fmt(f.get("weight_kg")),
        "| 承载/容量 | %s |" % fmt(f.get("capacity")),
        "| 件数 | %s |" % fmt(f.get("pieces")),
        "| 材质（依据） | %s（%s） |" % (fmt(f.get("material")), f.get("material_basis") or "-"),
        "| 兼容/适配 | %s |" % fmt(f.get("compatibility")),
        "| 功能点 | %s |" % fmt(f.get("features")),
        "| 使用场景（facts） | %s |" % fmt(f.get("usage")),
        "| 认证状态 | %s |" % g(f, "certification", "status"),
        "| 颜色属性 | %s |" % ((f.get("raw_attributes") or {}).get("Color") or "-"),
    ]
    specs = f.get("specs") or {}
    if specs:
        lines.append("| 其他规格 | %s |" % "; ".join("%s: %s" % (k, v) for k, v in specs.items()))
    pkg = (f.get("package") or {}).get("included") or []
    lines.append("| 包装清单（facts） | %s |" % ("; ".join(pkg) if pkg else "-"))
    ni = (f.get("package") or {}).get("not_included") or []
    lines.append("| 不含 | %s |" % ("; ".join(ni) if ni else "-"))
    warns = g(f, "gates", "warnings") or []
    if warns:
        lines.append("| 数据警告 | %s |" % "；".join(warns))
    return "\n".join(lines)


def build(sku, out_dir):
    facts_p = INPUT / sku / "facts.json"
    if not facts_p.exists():
        return None, "缺 facts.json"
    f = load_json(facts_p)
    if str(f.get("status")) != "verified":
        return None, "status=%s（只有 verified 可生成）" % f.get("status")
    if not (INPUT / sku / "item.json").exists():
        return None, "缺 item.json（没有原始描述，场景卡可能为空）"
    scene_p = SCENE / (sku + ".md")
    scene = scene_p.read_text(encoding="utf-8") if scene_p.exists() else "（无场景卡；先跑 python qa\\build_scene.py --only %s）" % sku
    cat = f.get("category") or ""
    cat_pack = ROOT / "skill" / "类目" / CAT_PACK.get(cat, "")
    cat_txt = cat_pack.read_text(encoding="utf-8") if cat_pack.exists() else "（该类目暂无类目包）"
    ex_txt = []
    for ex in EXAMPLES.get(cat, [])[:2]:
        p = BATCH / ("listing-%s.txt" % ex)
        if p.exists():
            ex_txt.append("### 范本 %s\n\n```\n%s\n```" % (ex, p.read_text(encoding="utf-8").strip()))
    ex_block = "\n\n".join(ex_txt) if ex_txt else "（同类目暂无范本，按规则写）"

    md = """# 生成包：{sku} · {cat} · TikTok Shop MX

> 把本文件整段发给 Agent，要求它只产出 `output\\批次YYYYMMDD\\listing-{sku}.txt`（标题第一行，正文按格式）。
> 事实只认第 3 节，场景只认第 4 节，写法按第 2 节；范本只学结构，不抄参数。

## 1. 任务

为 **{sku}** 写一条 TikTok Shop 墨西哥站（es-MX）商品 Listing：标题 + 描述（卖点 / 规格 / 包装 / FAQ / CTA）。
写完后自检：标题长度、首行 ≤60、⭐ 4–5 条、三段标题齐全、无中文/禁词。

{rules}

## 3. 事实卡（唯一事实源，参数只能取这里）

{facts}

> 口径：`可写功率 = 不写` 时全文不得出现瓦数；`认证状态 = missing` 时全文不得出现 NOM/INMETRO/ANATEL/UN38.3；缺失的字段不写、不猜。

## 4. 场景卡（原文依据，可改写语言，不可新增事实）

{scene}

## 5. 类目要点（{cat}）

{cat_pack}

## 6. 范本（学结构，不抄参数）

{examples}

## 7. 输出与验收

- 文件：`output\\批次YYYYMMDD\\listing-{sku}.txt`（UTF-8 无 BOM，标题第一行，段落空行）
- 自检：
```powershell
python -c "import sys;t=open(sys.argv[1],encoding='utf-8').read().splitlines();n=[x for x in t if x.strip()];print('title',len(t[0]),'hook',len(n[1]),'stars',sum(1 for x in t if x.startswith('⭐')),'chars',len(chr(10).join(t)))" output\\批次YYYYMMDD\\listing-{sku}.txt
```
- 批次校验：
```powershell
python qa\\run_batch.py --input-root input --listing-dir output\\批次YYYYMMDD --site MX
```
""".format(sku=sku, cat=cat, rules=RULES, facts=facts_block(f), scene=scene.strip(),
           cat_pack=cat_txt.strip(), examples=ex_block)
    p = out_dir / (sku + ".md")
    p.write_text(md, encoding="utf-8")
    return p, ""


def main():
    for s in (sys.stdout, sys.stderr):
        if hasattr(s, "reconfigure"):
            s.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--sku", default="", help="单个 SKU")
    ap.add_argument("--all", action="store_true", help="所有 verified SKU")
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)

    if args.sku:
        skus = [args.sku.strip()]
    elif args.all:
        skus = []
        for d in sorted(INPUT.iterdir()):
            if d.is_dir() and (d / "facts.json").exists():
                skus.append(d.name)
    else:
        ap.error("给 --sku 或 --all")

    ok, skipped = [], []
    for sku in skus:
        p, why = build(sku, out)
        if p:
            ok.append(p)
        else:
            skipped.append((sku, why))
    print("生成 %d 份 -> %s" % (len(ok), out))
    for s, w in skipped:
        print("  跳过 %-12s %s" % (s, w))
    if args.all:
        idx = ["# 生成包索引（%d 份）" % len(ok), "", "| SKU | 文件 |", "|---|---|"]
        for p in ok:
            idx.append("| %s | %s |" % (p.stem, p.name))
        (out / "_index.md").write_text("\n".join(idx) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
