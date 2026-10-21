#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
商品数据质量哨兵 v1.0（口径一致性检查）

和 qa/check_facts.py 分工：
  - check_facts.py          按 schema 查「必填/完整度/门禁」，产出 kb/_index/完整度报告.md
  - check_facts_quality.py  查「字段之间对不对」（本文件）：品牌/型号冲突、电压口径、
                            功率物理可能性、单位、价格币种、属性键值错位

用法：
  python check_facts_quality.py --input-root ..\\input
  python check_facts_quality.py --input-root ..\\input --strict   # 有 P0 时退出码 3
  python check_facts_quality.py --demo                            # 自检

不做的事：不修改 facts.json、不猜参数、不判认证真伪（认证走 check_certificates.py）。
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import unicodedata
from datetime import date
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

BASE = Path(__file__).resolve().parent
DEFAULT_INPUT = BASE.parent / "input"
DEFAULT_OUTDIR = BASE / "报告"

SEV_ORDER = {"P0": 0, "P1": 1, "P2": 2}
SEV_LABEL = {"P0": "阻断", "P1": "核实", "P2": "提示"}
PLACEHOLDERS = {"", "待确认", "tbd", "n/a", "na", "none", "null", "-"}


def norm_text(s) -> str:
    if s is None:
        return ""
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def is_placeholder(v) -> bool:
    return norm_text(v) in PLACEHOLDERS or "待确认" in str(v)


def find_key(d: dict, *names):
    if not isinstance(d, dict):
        return None, None
    for k, v in d.items():
        nk = norm_text(k)
        for n in names:
            if nk == norm_text(n):
                return k, v
    return None, None


def parse_number(v):
    if v is None:
        return None, ""
    s = str(v).strip().lower().replace(",", "")
    m = re.search(r"(\d+(?:\.\d+)?)", s)
    if not m:
        return None, ""
    rest = s[m.end():].strip()
    unit = rest.split(" ")[0] if rest else ""
    return float(m.group(1)), unit


def parse_watt(v):
    num, unit = parse_number(v)
    if num is None:
        return None
    return num * 1000 if unit.startswith("kw") else num


def parse_volt(v):
    num, unit = parse_number(v)
    if num is None or not unit.startswith("v"):
        return None
    return num


def add(findings, sku, cid, sev, title, evidence, advice, field=""):
    findings.append({
        "sku": sku, "cid": cid, "sev": sev, "title": title,
        "evidence": evidence, "advice": advice, "field": field,
    })


def check_one(d: dict, findings: list):
    sku = d.get("product_id") or d.get("_dir") or "?"
    power = d.get("power") or {}
    ident = d.get("identity") or {}
    raw = d.get("raw_attributes") or {}
    specs = d.get("specs") or {}
    sites = d.get("site_profiles") or {}
    ptype = (power.get("type") or "").strip().lower()

    battery_v = power.get("battery_v")
    charger_v = power.get("charger_v")
    device_v = power.get("device_v")
    listing_v = power.get("listing_voltage_v")

    # ---------- 品牌 / 型号冲突 ----------
    raw_brand = find_key(raw, "Marca", "Brand")[1]
    raw_model = find_key(raw, "Modelo", "Model")[1]
    aliases = [norm_text(a) for a in (ident.get("brand_aliases") or [])]
    brand, model = ident.get("brand"), ident.get("model")

    # 美客多 Marca/Modelo 两字段互换：Marca 填的是型号、Modelo 填的是品牌。
    # 这种是上游属性错位，identity 已按标题校正（见 input/<SKU>/overrides.json），
    # 不能再报 P0 品牌冲突，否则该 SKU 补齐其它缺项后永远过不了 --strict。
    # 注意：model 常被回填成品牌（缺型号属性时），brand==model 属正常兜底，不算互换。
    _has_conflict = (
        (not is_placeholder(brand) and not is_placeholder(raw_brand)
         and norm_text(brand) != norm_text(raw_brand))
        or (not is_placeholder(model) and not is_placeholder(raw_model)
            and norm_text(model) != norm_text(raw_model))
    )
    crossed = (
        _has_conflict
        and norm_text(brand) != norm_text(model)
        and (
            (not is_placeholder(model) and not is_placeholder(raw_brand)
             and norm_text(raw_brand) == norm_text(model))
            or (not is_placeholder(brand) and not is_placeholder(raw_model)
                and norm_text(raw_model) == norm_text(brand))
        )
    )
    if crossed:
        add(findings, sku, "FQ-P1-BRAND-MODEL-SWAP", "P1", "品牌/型号字段互换",
            f"raw.Marca={raw_brand!r} / raw.Modelo={raw_model!r} 与 identity 交叉相同"
            f"（brand={brand!r} model={model!r}）",
            "已按标题/override 校正，不用改 facts；要根治请让采购核对美客多属性",
            "identity.brand")
    else:
        if not is_placeholder(brand) and not is_placeholder(raw_brand):
            nb, nrb = norm_text(brand), norm_text(raw_brand)
            # 同公司并列品牌（identity.brand_aliases）不算冲突
            if nb != nrb and nrb not in aliases:
                add(findings, sku, "FQ-P0-BRAND-CONFLICT", "P0", "品牌冲突",
                    f"identity.brand={brand!r} vs raw.Marca={raw_brand!r}",
                    "先确认到底是哪个品牌，别猜", "identity.brand")

        if not is_placeholder(model) and not is_placeholder(raw_model):
            if norm_text(model) != norm_text(raw_model):
                add(findings, sku, "FQ-P1-MODEL-CONFLICT", "P1", "型号不一致",
                    f"identity.model={model!r} vs raw.Modelo={raw_model!r}",
                    "型号影响证书覆盖范围，需核对", "identity.model")

    # ---------- 电压口径 ----------
    if ptype == "battery":
        if battery_v is None and listing_v is None:
            add(findings, sku, "FQ-P0-BATT-NOV", "P0", "电池工具没有电池电压",
                "battery_v / listing_voltage_v 都为空", "补电池电压（如 21V）", "power.battery_v")

        if listing_v is not None and charger_v is not None and float(listing_v) == float(charger_v):
            add(findings, sku, "FQ-P0-VOLT-CHARGER", "P0", "把充电器电压当工具电压",
                f"listing_voltage_v={listing_v:g} 与 charger_v={charger_v:g} 相同",
                "电池工具写电池电压；充电器电压只能写“Cargador: 127V”", "power.listing_voltage_v")

        vals = {}
        for label, v in (("battery_v", battery_v), ("device_v", device_v), ("listing_voltage_v", listing_v)):
            if v is not None:
                vals[label] = float(v)
        rv = parse_volt(find_key(raw, "Voltaje", "Voltage")[1])
        if rv is not None and not (charger_v is not None and float(rv) == float(charger_v)):
            vals["raw.Voltaje"] = float(rv)
        if len(vals) >= 2 and max(vals.values()) - min(vals.values()) > 2:
            add(findings, sku, "FQ-P1-VOLT-CONFLICT", "P1", "电压口径冲突",
                " / ".join(f"{k}={v:g}V" for k, v in vals.items()),
                "确认电池平台电压，统一写同一个数", "power.*_v")

    # ---------- 功率物理一致性 ----------
    effective_w = power.get("w") or power.get("claimed_w")
    if effective_w:
        effective_w = float(effective_w)
        vref = None
        if ptype == "corded":
            vref = listing_v or power.get("voltage_v") or 127
        elif ptype == "battery":
            vref = battery_v or listing_v
        current = (effective_w / float(vref)) if vref else None

        if ptype == "corded" and current:
            if current > 27:
                add(findings, sku, "FQ-P0-POWER-IMPOSSIBLE", "P0", "功率物理不可能",
                    f"{effective_w:g}W / {float(vref):g}V ≈ {current:.1f}A，超过家用回路上限",
                    "核实铭牌；多半是把峰值/等效功率当额定值", "power.w / power.claimed_w")
            elif current > 16:
                add(findings, sku, "FQ-P1-POWER-CIRCUIT", "P1", "电流偏高（需专用回路）",
                    f"{effective_w:g}W / {float(vref):g}V ≈ {current:.1f}A",
                    "确认是否可用；Listing 不要强调瓦数", "power.w")
        if ptype == "battery" and effective_w > 600:
            add(findings, sku, "FQ-P1-POWER-BATT", "P1", "电池工具功率偏高",
                f"标称 {effective_w:g}W" + (f"，隐含 {current:.1f}A" if current else ""),
                "多为等效/峰值；按 state_power 决定是否写进文案", "power.claimed_w")

    raw_w = parse_watt(find_key(raw, "Potencia", "Power")[1])
    if raw_w is not None and effective_w:
        if abs(raw_w - float(effective_w)) > max(50, 0.1 * float(effective_w)):
            add(findings, sku, "FQ-P1-POWER-MISMATCH", "P1", "功率字段与属性不一致",
                f"字段={effective_w:g}W vs 属性={raw_w:g}W", "以铭牌为准，统一口径", "raw.Potencia")

    # ---------- 单位异常 ----------
    cap = str(d.get("capacity") or "")
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*ah\b", cap.lower())
    if m and float(m.group(1).replace(",", "")) > 100:
        add(findings, sku, "FQ-P1-UNIT-AH", "P1", "容量单位疑似写错",
            f"capacity={cap!r}（>100Ah 更像 mAh）", "1500Ah → 1500mAh", "capacity")

    weight = d.get("weight_kg")
    if weight is not None and float(weight) > 100:
        add(findings, sku, "FQ-P1-UNIT-WEIGHT", "P1", "重量单位疑似写错",
            f"weight_kg={weight}（>100kg 更像克）", "核对单位", "weight_kg")

    for k, v in list(specs.items()) + list(raw.items()):
        if "dba" in str(v).lower() and (parse_number(v)[0] or 0) > 110:
            add(findings, sku, "FQ-P1-NOISE", "P1", "噪音值异常",
                f"{k}={v}", "核实是否 dBA；>110 多为峰值或单位错", f"specs[{k}]")

    # ---------- 属性键值错位 ----------
    for k, v in raw.items():
        nk, vs = norm_text(k), str(v).lower()
        if "frecuencia" in nk and re.search(r"\d\s*w\b", vs):
            add(findings, sku, "FQ-P2-KEY-MISMATCH", "P2", "属性键值疑似错位",
                f"{k}={v}（键是频率，值是功率）", "导出时可能列错位，核对源表", f"raw[{k}]")
        if "potencia" in nk and re.search(r"\d\s*v\b", vs) and not re.search(r"\d\s*w\b", vs):
            add(findings, sku, "FQ-P2-KEY-MISMATCH", "P2", "属性键值疑似错位",
                f"{k}={v}（键是功率，值是电压）", "核对源表", f"raw[{k}]")

    # ---------- 价格 / 币种 ----------
    expect = {"MX": "MXN", "BR": "BRL"}
    for site, prof in sites.items():
        prof = prof or {}
        if not prof.get("price"):
            add(findings, sku, "FQ-P1-PRICE", "P1", f"{site} 缺价格",
                f"site_profiles.{site}.price 为空", "补价格后再生成", f"site_profiles.{site}.price")
        cur = prof.get("currency")
        if cur and expect.get(site) and str(cur).upper() != expect[site]:
            add(findings, sku, "FQ-P1-CURRENCY", "P1", "币种与站点不符",
                f"{site} 币种={cur}，应为 {expect[site]}", "改成站点币种", f"site_profiles.{site}.currency")

    # ---------- P2 提示 ----------
    if (d.get("material_basis") or "") == "description":
        add(findings, sku, "FQ-P2-MATERIAL", "P2", "材质来自描述推断",
            f"material={d.get('material')}", "人工核实后再写进规格", "material")

    title = str(ident.get("title_raw") or "")
    if re.search(r"\d+\s*(in|pulgadas?)\b", title, re.I) and not re.search(r"\d+\s*(cm|mm)\b", title, re.I):
        add(findings, sku, "FQ-P2-IMPERIAL", "P2", "标题含英制单位",
            title[:60], "生成时换算成 cm/mm（12in → 30.48cm）", "identity.title_raw")


def load_facts(input_root: Path):
    out = []
    if not input_root.exists():
        return out
    for f in sorted(input_root.glob("*/facts.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except Exception as e:  # noqa: BLE001
            print(f"[WARN] 读不了 {f}: {e}", file=sys.stderr)
            continue
        d["_dir"] = f.parent.name
        out.append(d)
    return out


def evaluate(facts_list):
    findings = []
    for d in facts_list:
        start = len(findings)
        check_one(d, findings)
        # 已隔离 SKU（移出生成集）保留问题记录，但不参与阻断判定
        if (d.get("status") or "").strip().lower() == "quarantined":
            for f in findings[start:]:
                f["quarantined"] = True
    # 去重：同一 SKU + 同一检查 + 同一证据只报一次（specs 与 raw 常重复）
    seen, uniq = set(), []
    for f in findings:
        key = (f["sku"], f["cid"], f["evidence"])
        if key in seen:
            continue
        seen.add(key)
        uniq.append(f)
    uniq.sort(key=lambda x: (SEV_ORDER[x["sev"]], x["sku"], x["cid"]))
    return uniq


def print_report(findings, strict):
    quarantined = [f for f in findings if f.get("quarantined")]
    active = [f for f in findings if not f.get("quarantined")]
    p0 = [f for f in active if f["sev"] == "P0"]
    p1 = [f for f in active if f["sev"] == "P1"]
    p2 = [f for f in active if f["sev"] == "P2"]
    tail = f"  |  已隔离（不阻断）={len(quarantined)}" if quarantined else ""
    print(f"\n数据质量哨兵（口径一致性）  |  P0={len(p0)}  P1={len(p1)}  P2={len(p2)}{tail}")
    print("=" * 100)
    for label, group in (("P0 阻断", p0), ("P1 需核实", p1), ("P2 提示", p2),
                         ("已隔离·仅提示（不进生成集，不参与阻断）", quarantined)):
        if not group:
            continue
        print(f"\n[{label}]")
        for f in group:
            print(f"  {f['sku']:<13}{f['cid']:<24}{f['title']}")
            print(f"     证据：{f['evidence']}")
            print(f"     建议：{f['advice']}")
    if p0:
        print(f"\n结论：{len(p0)} 条阻断项，修完再生成。" + ("（--strict，退出码 3）" if strict else "（未加 --strict，退出码 0）"))
    elif quarantined:
        print(f"\n结论：没有阻断项（{len(quarantined)} 条属于已隔离 SKU，不参与阻断）。")
    else:
        print("\n结论：没有阻断项。")


def write_csv(findings, out_path: Path):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["SKU", "检查ID", "级别", "问题", "证据", "建议", "字段", "隔离"])
        for x in findings:
            w.writerow([x["sku"], x["cid"], x["sev"], x["title"], x["evidence"], x["advice"],
                        x["field"], "隔离" if x.get("quarantined") else ""])
    return out_path


def demo() -> int:
    def mk(pid, **kw):
        d = {"product_id": pid, "category": "五金工具",
             "identity": {"brand": "Atverce", "model": "M1", "title_raw": "Taladro 20V"},
             "power": {"type": "corded", "listing_voltage_v": 127, "claimed_w": 850},
             "package": {"included": ["Taladro *1"]},
             "raw_attributes": {"Marca": "Atverce", "Modelo": "M1", "Potencia": "850 W", "Voltaje": "127V"},
             "site_profiles": {"MX": {"price": 100, "currency": "MXN"}}}
        for k, v in kw.items():
            if k in ("brand", "model"):
                d["identity"][k] = v
            elif k in ("ptype", "battery_v", "charger_v", "device_v", "listing_v", "w"):
                mp = {"ptype": "type", "listing_v": "listing_voltage_v"}
                d["power"][mp.get(k, k)] = v
            elif k == "raw":
                d["raw_attributes"].update(v)
        return d

    cases = [
        ("P0-功率不可能", mk("A", w=6800), "FQ-P0-POWER-IMPOSSIBLE"),
        ("P0-品牌冲突", mk("B", raw={"Marca": "Fanny"}), "FQ-P0-BRAND-CONFLICT"),
        ("P0-充电器电压当工具电压", mk("C", ptype="battery", battery_v=21, charger_v=127, listing_v=127), "FQ-P0-VOLT-CHARGER"),
        ("P1-电池功率偏高", mk("D", ptype="battery", battery_v=21, w=1500), "FQ-P1-POWER-BATT"),
        ("P1-电压口径冲突", mk("E", ptype="battery", battery_v=18, device_v=21, listing_v=18), "FQ-P1-VOLT-CONFLICT"),
        ("P1-单位写错", mk("F", **{"capacity": "1500Ah"}), "FQ-P1-UNIT-AH"),
    ]
    ok = True
    for name, d, cid in cases:
        if name.endswith("单位写错"):
            d["capacity"] = "1500Ah"
        got = {f["cid"] for f in evaluate([d])}
        hit = cid in got
        print(("[OK ] " if hit else "[FAIL] ") + name + " -> " + (cid if hit else f"未命中（实际：{sorted(got)}）"))
        ok = ok and hit
    print("\n自检结果：" + ("通过" if ok else "失败"))
    return 0 if ok else 2


def main() -> int:
    ap = argparse.ArgumentParser(description="商品数据质量哨兵 v1.0（口径一致性）")
    ap.add_argument("--input-root", default=str(DEFAULT_INPUT))
    ap.add_argument("--strict", action="store_true", help="有 P0 时退出码 3")
    ap.add_argument("--outdir", default=str(DEFAULT_OUTDIR))
    ap.add_argument("--demo", action="store_true")
    args = ap.parse_args()

    if args.demo:
        return demo()

    facts_list = load_facts(Path(args.input_root))
    if not facts_list:
        print(f"[ERROR] {args.input_root} 下没有 facts.json", file=sys.stderr)
        return 2
    findings = evaluate(facts_list)
    print_report(findings, args.strict)
    out = Path(args.outdir) / date.today().strftime("%Y%m%d") / "数据质量检查.csv"
    write_csv(findings, out)
    print(f"\n明细已写入：{out}")
    p0 = [f for f in findings if f["sev"] == "P0" and not f.get("quarantined")]
    return 3 if (args.strict and p0) else 0


if __name__ == "__main__":
    sys.exit(main())
