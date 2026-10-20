# -*- coding: utf-8 -*-
r"""
ML 属性 → TikTok Shop 属性槽位 映射器（v1.0）

用法：
  python map_attributes.py --input-root ..\input --out ..\output\批次20261020\属性映射.xlsx

输出：一张表，每行一个商品，列为 TikTok 后台可填的"语义槽位"，
      并列出源数据冲突/风险（电压口径、虚标功率、品牌不一致等）。

设计原则：
  1. 只做"翻译 + 校验"，不生成文案；文案仍由 Listing 生成环节负责
  2. 电池工具：电池电压 ≠ 充电器电压，绝不把 127V 写成产品电压
  3. 冲突不猜：多个不同值同时出现 → 全部列出，交人工决定
"""
import argparse
import json
import re
import sys
from pathlib import Path

BATTERY_HINT = re.compile(r"inal[aá]mbric|bater[ií]a|litio|li-ion", re.I)
NOISE = ["mercado libre", "mercado pago", "envío gratis", "envio gratis", "http"]
SKIP_DIRS = {"示例商品", "示例商品001"}


def num(s):
    """从字符串里抽第一个数字（支持 1,500 / 6.8 / 110V - 127V）"""
    if s is None:
        return None
    m = re.search(r"(\d+(?:[.,]\d+)?)", str(s).replace(" ", ""))
    if not m:
        return None
    return float(m.group(1).replace(",", "."))


def volts(s):
    """抽出所有电压值（大小写都认，21v 也算）"""
    if s is None:
        return []
    return [float(x.replace(",", ".")) for x in re.findall(r"(\d{2,3}(?:[.,]\d+)?)\s*V\b", str(s), re.I)]


def norm_voltage(v):
    """墨西哥家用电压归一：110/115/120 → 127"""
    if v is None:
        return None
    if 100 <= v <= 120:
        return 127.0
    return v


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-root", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    try:
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Font, PatternFill
    except ImportError:
        raise SystemExit("需要 openpyxl，用带 openpyxl 的 Python 运行")

    rows = []
    for d in sorted(Path(args.input_root).resolve().iterdir()):
        f = d / "input.json"
        if not f.exists() or d.name.startswith("_") or d.name in SKIP_DIRS:
            continue
        data = json.loads(f.read_text(encoding="utf-8"))
        attrs = data.get("attributes_raw") or {}
        title = data.get("title_raw", "")
        desc = data.get("description_raw", "")
        body = f"{title}\n{desc}"
        warn = []

        # ---------- 产品类型 / 是否电池驱动 ----------
        power_type = attrs.get("Tipo de alimentación", "")
        is_battery = bool(BATTERY_HINT.search(title) or BATTERY_HINT.search(str(power_type))
                          or "batería" in str(attrs.get("Incluye batería", "")).lower())

        # ---------- 电压 ----------
        v_battery, v_charger, v_nominal = None, None, None
        if is_battery:
            vb_vals = volts(attrs.get("Voltaje de la batería"))
            for k in ("Voltaje", "Voltaje nominal"):
                for v in volts(attrs.get(k)):
                    if 12 <= v <= 60:
                        vb_vals.append(v)
            for v in volts(title):
                if 12 <= v <= 60:
                    vb_vals.append(v)
            # 描述里的"Voltaje de la batería: 21V" / "batería de 21V"
            for m in re.finditer(r"voltaje\s+de\s+la\s+bater[ií]a\s*[:：]?\s*(\d{2,3})\s*V", desc, re.I):
                vb_vals.append(float(m.group(1)))
            for m in re.finditer(r"bater[ií]a\s+de\s+(\d{2,3})\s*V", desc, re.I):
                vb_vals.append(float(m.group(1)))
            vb_vals = sorted(set(vb_vals))
            if len(vb_vals) > 1:
                warn.append(f"电池电压多值冲突：{vb_vals}")
            v_battery = vb_vals[-1] if vb_vals else None
            # 充电器/额定输入
            for v in volts(attrs.get("Voltaje")):
                if 100 <= v <= 240:
                    v_charger = norm_voltage(v)
            if v_charger is None:
                v_charger = 127.0
                warn.append("充电器输入电压未提供，按 MX 127V 处理，需核实")
            if not v_battery:
                warn.append("未找到电池电压（电池工具必须写清，如 21V）")
        else:
            vv = volts(attrs.get("Voltaje")) or volts(attrs.get("Voltaje nominal"))
            if vv:
                raw = vv[0]
                v_nominal = norm_voltage(raw)
                if raw != v_nominal:
                    warn.append(f"源数据写 {raw:g}V，墨西哥应规范为 {v_nominal:g}V")
            # 描述里的电压若与属性不同
            dv = sorted(set(volts(desc)))
            if v_nominal and dv and int(v_nominal) not in [int(x) for x in dv]:
                warn.append(f"描述出现 {[f'{x:g}V' for x in dv]}，与属性 {v_nominal:g}V 不一致")

        # ---------- 功率 ----------
        power_w = None
        p_raw = str(attrs.get("Potencia", "") or "")
        p = num(p_raw)
        if p is not None:
            power_w = p * 1000 if ("kw" in p_raw.lower() or p < 10) else p
            if power_w >= 3500:
                warn.append(f"功率 {power_w:g}W 在 127V 下约 {power_w/127:.0f}A，物理上不可信，需核实铭牌")
        elif v_nominal:
            mv = re.findall(r"(\d{3,4})\s*W", desc)
            if mv:
                power_w = float(mv[0])
                warn.append(f"功率取自描述（{power_w:g}W），属性缺失")
        if is_battery and power_w and power_w >= 600:
            warn.append(f"电池工具标 {power_w:g}W 偏高（多为等效功率或充电输入），核实后再写进卖点")

        # ---------- 容量 / 尺寸 / 重量 / 件数 ----------
        capacity = attrs.get("Capacidad en volumen") or attrs.get("Capacidad de la batería") or ""
        dims = []
        for k, label in (("Largo", "largo"), ("Ancho", "ancho"), ("Alto", "alto"), ("Altura", "alto"),
                         ("Diámetro", "diámetro"), ("Tamaño", "tamaño"), ("Medidas", "medidas"),
                         ("Mínima altura levantada - Máxima altura levantada", "altura")):
            if attrs.get(k):
                dims.append(f"{label} {attrs[k]}")
        if not dims:
            m = re.search(r"(?:tama[ñn]o|medidas?)\s*[:：]?\s*([0-9.,*\s x]+(?:cm|mm)?)", desc, re.I)
            if m:
                dims.append(m.group(1).strip())
        weight = attrs.get("Peso") or attrs.get("Peso del producto") or attrs.get("Peso de la hidrolavadora") or ""
        pieces = attrs.get("Cantidad de piezas") or ""
        material = attrs.get("Material de la bomba") or ""
        if not material:
            m = re.search(r"(acero[^.,;]{0,30}|aluminio|ABS|cobre|hierro)", desc, re.I)
            material = m.group(1) if m else ""
        brand = attrs.get("Marca", "")
        model = attrs.get("Modelo", "")

        # ---------- 品牌一致性 ----------
        low_desc = desc.lower()
        if brand and brand.lower() not in low_desc and "atverce" in low_desc and brand.lower() != "atverce":
            warn.append(f"品牌冲突：属性「{brand}」/ 描述出现 Atverce")

        # ---------- ML 残留 ----------
        for n in NOISE:
            if n in low_desc:
                warn.append(f"源描述含 ML 残留（{n}），已在新 Listing 中剔除")
                break

        # ---------- 必带信息缺口 ----------
        if not material:
            warn.append("缺材质：TikTok 五金/家电类必填项建议补")
        if not dims and not capacity:
            warn.append("缺尺寸/容量：影响搜索属性完整性")

        rows.append([
            data.get("product_id", d.name), data.get("category", ""), brand, model,
            "电池" if is_battery else "插电/手动",
            (f"{v_battery:g}V" if v_battery else ""),
            (f"{v_charger:g}V" if v_charger else (f"{v_nominal:g}V" if v_nominal else "")),
            (f"{power_w:g}W" if power_w else ""),
            str(capacity),
            " / ".join(dims),
            str(weight),
            str(pieces),
            material,
            " | ".join(warn),
        ])

    wb = Workbook()
    ws = wb.active
    ws.title = "属性映射"
    headers = ["商品ID", "类目", "品牌", "型号", "供电类型", "电池电压", "额定/充电器电压",
               "功率", "容量", "尺寸", "重量", "件数", "材质", "冲突与风险"]
    ws.append(headers)
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="1F4E79")
        c.alignment = Alignment(horizontal="center")
    for r in rows:
        ws.append(r)
    widths = [14, 10, 10, 12, 12, 10, 16, 10, 10, 30, 10, 8, 22, 70]
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[chr(64 + i)].width = w
    for row in ws.iter_rows(min_row=2):
        for c in row:
            c.alignment = Alignment(wrap_text=True, vertical="top")
        if row[13].value:
            row[13].fill = PatternFill("solid", fgColor="FFF2CC")
    ws.freeze_panes = "B2"

    out = Path(args.out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out)
    warn_count = sum(1 for r in rows if r[13])
    print(f"已写出 {len(rows)} 行 -> {out}")
    print(f"有冲突/风险的商品：{warn_count} / {len(rows)}")
    for r in rows:
        if r[13]:
            print(f"  - {r[0]}: {r[13]}")


if __name__ == "__main__":
    main()
