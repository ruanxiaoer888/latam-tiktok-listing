# -*- coding: utf-8 -*-
r"""
事实卡构建器 v1.0：input/<SKU>/input.json (+item.json) -> facts.json + img_manifest.csv

定位：把「美客多原始属性 + 描述」翻译成生成 Listing 唯一可读的结构化事实。
原则：
  1. 只做翻译与校验，不生成文案、不猜参数
  2. 缺写 null；同槽位多值冲突 -> hard block
  3. 功率物理不可信 -> 保留标称值，但 state_power=false（Listing 不写瓦数）
  4. 图片只做清单（哈希/主图/重复组），不做事实来源

用法：
  python qa\build_facts.py                     # 处理 input\ 下全部 SKU
  python qa\build_facts.py --only ABU5000000   # 只处理一个
  python qa\build_facts.py --check             # 只报告，不写文件
"""
import argparse
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT = ROOT / "input"
SCHEMA_DIR = ROOT / "kb" / "_schemas"
RULES_VERSION = "v1.3"
SKIP_DIRS = {"示例商品", "示例商品001"}
NOISE = ["mercado libre", "mercado pago", "envío gratis", "envio gratis"]

# 属性键 -> 事实卡尺寸字段
DIM_KEYS = {
    "Largo": "length_cm",
    "Ancho": "width_cm",
    "Alto": "height_cm",
    "Altura": "height_cm",
    "Diámetro": "diameter_cm",
    "Diámetro de oscilación": "diameter_cm",
    "Largo de la hidrolavadora": "length_cm",
    "Ancho de la hidrolavadora": "width_cm",
    "Alto de la hidrolavadora": "height_cm",
    "Tamaño": "raw",
    "Medidas": "raw",
}

SPEC_KEYS = [
    "Tipo de tecnología del motor", "Modos de operación", "Sistema de encastre",
    "Energía de impacto", "Golpes por minuto", "Velocidad máxima de rotación",
    "Velocidad mínima de rotación", "Caudal de aire", "Velocidad de soplado",
    "Presión máxima", "Caudal de agua", "Diámetro del disco",
    "Profundidad de corte 90 grados", "Profundidad de corte 45 grados",
    "Largo de la barra", "Tiempo de calentamiento", "Presión máxima de vapor",
    "Nivel de ruido", "Nivel de presión sonora", "Frecuencia",
    "Eficiencia energética", "Amperaje de la bateria", "Cantidad de velocidades",
    "Máxima velocidad", "Número de oscilaciones", "Golpes por minuto",
]

CAT_BRANDS = re.compile(
    r"\b(nissan|toyota|honda|chevrolet|volkswagen|ford|mazda|kia|hyundai|suzuki|yamaha|italika|bajaj)\b", re.I
)


def die(msg, code=2):
    try:
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    sys.stderr.write(msg + "\n")
    raise SystemExit(code)


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def rel(path):
    try:
        return str(Path(path).resolve().relative_to(ROOT)).replace("\\", "/")
    except Exception:
        return str(path)


def es_number(s):
    """西语数字：2,500 -> 2500（千分位）；2,5 -> 2.5（小数）"""
    s = str(s).strip().replace(" ", "")
    if re.fullmatch(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?", s):
        s = s.replace(",", "")
    else:
        s = s.replace(",", ".")
    return float(s)


def first_num(s):
    m = re.search(r"(\d+(?:[.,]\d+)?)", str(s).replace(" ", ""))
    return es_number(m.group(1)) if m else None


def volts(text):
    if not text:
        return []
    return [es_number(x) for x in re.findall(r"(\d{2,3}(?:[.,]\d+)?)\s*V\b", str(text), re.I)]


def parse_watts(s):
    """'6.8 kW' / '2,500 W' / '1500w' -> W"""
    if not s:
        return None
    t = str(s).replace(" ", "")
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*(k?w)\b", t, re.I)
    if not m:
        return None
    v = es_number(m.group(1))
    return v * 1000 if m.group(2).lower() == "kw" else v


def all_watts(text):
    out = set()
    for m in re.finditer(r"(\d+(?:[.,]\d+)?)\s*(k?w)\b", text or "", re.I):
        v = es_number(m.group(1))
        out.add(int(v * 1000) if m.group(2).lower() == "kw" else int(v))
    return sorted(out)


def dim_cm(s):
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*(mm|cm|m)\b", str(s), re.I)
    if not m:
        return None
    v = es_number(m.group(1))
    u = m.group(2).lower()
    return round(v / 10, 2) if u == "mm" else (round(v * 100, 2) if u == "m" else round(v, 2))


# 尺寸可信区间：超出 1–150 cm 视为解析错误，字段置空并留 warning，不静默写垃圾
SIZE_MIN_CM, SIZE_MAX_CM = 1.0, 150.0
# 非尺寸单位（转速/扭矩/功率/重量/电压等）出现在「尺寸」候选行里 → 不可信
# 只在该数字正好是前三个「尺寸数字」之一时才判不可信（避免同行的 1.3 kg 误伤 23 x 12 x 4 cm）
SIZE_BAD_UNIT = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*(?:rpm|r\s*/\s*min|r\.p\.m\.?|nm|n\.?m\.?|kg|hz|dba?|ah|w|v)\b", re.I)


def plausible_cm(v):
    return v is not None and SIZE_MIN_CM <= float(v) <= SIZE_MAX_CM


def size_value_in(text):
    """判断字符串里是否出现「2 x 9,5 x 7 mm」这类三边尺寸（返回 [cm...] 或 None）。"""
    nums = re.findall(r"\d+(?:[.,]\d+)?", text or "")
    if len(nums) < 3:
        return None
    unit = "mm" if re.search(r"\d\s?mm\b", text or "", re.I) else "cm"
    vals = [float(n.replace(",", ".")) for n in nums[:3]]
    if unit == "mm":
        vals = [round(v / 10, 2) for v in vals]
    return vals


def detect_power_type(attrs, title, desc):
    t = title or ""
    a = attrs or {}
    if (re.search(r"inal[aá]mbric|bater[ií]a|recargable|litio", t, re.I)
            or str(a.get("Es inalámbrico", "")).strip().lower() in ("sí", "si")
            or "batería" in str(a.get("Tipo de alimentación", "")).lower()):
        return "battery"
    vv = volts(str(a.get("Voltaje", "")))
    if vv and any(100 <= v <= 240 for v in vv):
        return "corded"
    if a.get("Potencia") or re.search(r"el[eé]ctric|cargador|corriente dom|enchufe", (t + " " + (desc or "")), re.I):
        return "corded"
    return "manual"


def battery_values(attrs, title):
    vals = set()
    for v in volts(str(attrs.get("Voltaje de la batería", ""))):
        vals.add(v)
    for v in volts(str(attrs.get("Voltaje", ""))):
        if 12 <= v <= 60:
            vals.add(v)
    for v in volts(title):
        if 12 <= v <= 60:
            vals.add(v)
    return sorted(vals)


def normalize_voltage(v):
    return 127.0 if 100 <= v <= 120 else v


def parse_package(desc):
    items = []
    m = re.search(
        r"(?:>>>\s*)?(?:el paquete incluye|lista de productos|listado de productos|"
        r"contenido del paquete|contenido de la caja|incluye)\s*:?\s*\n",
        desc or "", re.I)
    if not m:
        return items
    tail = desc[m.end():]
    stop = re.search(r"\n\s*(?:>>>|nota|atenci[oó]n|importante|caracter[ií]sticas|advertencia)", tail, re.I)
    if stop:
        tail = tail[:stop.start()]
    for line in tail.splitlines():
        s = line.strip(" -*•\t")
        if not s:
            if items:
                break
            continue
        if len(s) > 90:
            continue
        if re.search(r"[A-Za-zÁÉÍÓÚÑáéíóúñ]", s):
            items.append(s)
    return items[:15]


def split_list(value):
    if not value:
        return []
    s = str(value).strip()
    if re.search(r"muestra la imagen|como la imagen|ver imagen", s, re.I):
        return []
    parts = [p.strip() for p in re.split(r"[,;]\s*", s) if p.strip()]
    return parts if len(parts) > 1 else [s]


def build_one(d, img_dir, check_only=False):
    pid = d.get("product_id") or ""
    cat = d.get("category") or ""
    attrs = d.get("attributes_raw") or {}
    title = d.get("title_raw") or ""
    desc = d.get("description_raw") or ""
    body = title + "\n" + desc

    hard, warn = [], []
    ptype = detect_power_type(attrs, title, desc)

    # ---------- 品牌冲突 ----------
    brand = str(attrs.get("Marca", "") or "").strip()
    desc_low = desc.lower()
    if brand and "atverce" in desc_low and brand.lower() != "atverce":
        hard.append(f"品牌冲突：属性「{brand}」/ 描述出现 Atverce")

    # ---------- 电压 ----------
    voltage_v = battery_v = charger_v = None
    if ptype == "battery":
        bvals = battery_values(attrs, title)
        if len(bvals) > 1:
            hard.append(f"电池电压多值冲突：{[int(v) if v == int(v) else v for v in bvals]} V")
        battery_v = bvals[0] if len(bvals) == 1 else None
        for v in volts(str(attrs.get("Voltaje", ""))):
            if 100 <= v <= 240:
                charger_v = normalize_voltage(v)
        if not bvals:
            warn.append("未找到电池电压（电池工具必须写清，如 21V）")
        if charger_v is None:
            warn.append("充电器输入电压未提供（Listing 不写充电器电压）")
    elif ptype == "corded":
        vv = volts(str(attrs.get("Voltaje", "")))
        raw = vv[0] if vv else None
        if raw is None:
            warn.append("插电类缺电压属性")
        else:
            voltage_v = normalize_voltage(raw)
            if raw != voltage_v:
                warn.append(f"源数据写 {raw:g}V，墨西哥规范为 {voltage_v:g}V")
        dv = sorted(set(volts(desc)))
        if voltage_v and dv and int(voltage_v) not in [int(x) for x in dv]:
            warn.append(f"描述出现 {[f'{x:g}V' for x in dv]}，与属性 {voltage_v:g}V 不一致")

    # ---------- 功率 ----------
    p_raw = str(attrs.get("Potencia", "") or "")
    w = parse_watts(p_raw)
    basis = "attribute" if w else None
    if w is None:
        m = re.search(r"(\d{2,5})\s*W\b", desc)
        if m:
            w = es_number(m.group(1))
            basis = "description"
    claims = set(all_watts(body))
    if w:
        claims.add(int(w))
    claims = sorted(claims)
    state_power = w is not None and ptype in ("corded", "battery")
    limit = 3500 if ptype == "corded" else 600
    if state_power and w >= limit:
        state_power = False
        if ptype == "battery":
            warn.append(f"电池类标 {w:g}W 偏高（多为等效/峰值功率，不是持续功率）；Listing 不写瓦数")
        else:
            amp = w / (voltage_v or 127)
            warn.append(f"功率 {w:g}W 在 {voltage_v or 127:g}V 下约 {amp:.0f}A，物理上不可信；Listing 不写瓦数")

    power = {
        "type": ptype,
        "voltage_v": voltage_v,
        "battery_v": battery_v,
        "charger_v": charger_v,
        "w": w if state_power else None,
        "claimed_w": max(claims) if claims else None,
        "rated_claimed_w": min(claims) if len(claims) > 1 else None,
        "claims_w": claims,
        "basis": basis,
        "state_power": state_power,
        "listing_policy": "do_not_state_power" if (claims and not state_power) else "state_verified_only",
        "device_v": None,
        "listing_voltage_v": battery_v if ptype == "battery" else (voltage_v if ptype == "corded" else None),
    }

    # ---------- 尺寸 ----------
    # 规则：只接受 1–150 cm 的可信值；非尺寸单位（rpm/Nm/kg/W/V）与量级不合理的解析结果
    # 一律置空 + gates.warnings 留痕，绝不静默写垃圾（历史垃圾用 fix_size_fields.py 回填）。
    size = {"length_cm": None, "width_cm": None, "height_cm": None, "diameter_cm": None, "raw": []}
    for k, v in attrs.items():
        target = DIM_KEYS.get(k)
        if not target:
            continue
        if target == "raw":
            size["raw"].append(f"{k}: {v}")
            continue
        cm = dim_cm(v)
        if cm is None:
            continue
        if not plausible_cm(cm):
            warn.append(f"尺寸不可信，已置空：{k}={v}（解析为 {cm:g} cm，超出 "
                        f"{SIZE_MIN_CM:g}–{SIZE_MAX_CM:g} cm）")
            continue
        if size[target] is None:
            size[target] = cm
    if not any(size[k] for k in ("length_cm", "width_cm", "height_cm")):
        for line in desc.splitlines():
            if not re.search(r"(tama[ñn]o|medidas?|dimensiones?)", line, re.I):
                continue
            nums = re.findall(r"\d+(?:[.,]\d+)?", line)
            if len(nums) < 3:
                continue
            dim_nums = [float(n.replace(",", ".")) for n in nums[:3]]
            bad_hit = next((m.group(0).strip() for m in SIZE_BAD_UNIT.finditer(line)
                            if float(m.group(1).replace(",", ".")) in dim_nums), None)
            if bad_hit:
                warn.append(f"尺寸不可信，已置空：描述「{line.strip()[:50]}」含非尺寸单位"
                            f"「{bad_hit}」（转速/扭矩/功率等），不是长宽高")
                continue
            vals = size_value_in(line)
            if not vals or not all(plausible_cm(v) for v in vals):
                warn.append(f"尺寸不可信，已置空：描述「{line.strip()[:50]}」解析为 {vals} cm，"
                            f"超出 {SIZE_MIN_CM:g}–{SIZE_MAX_CM:g} cm")
                continue
            explicit = bool(re.search(r"\d\s?(mm|cm)\b", line, re.I))
            if not explicit:
                warn.append(f"描述尺寸「{line.strip()[:50]}」未标单位，按 cm 处理，需核实")
            size["length_cm"], size["width_cm"], size["height_cm"] = vals
            size["raw"].append(line.strip()[:80])
            break

    # ---------- 重量 / 容量 / 件数 ----------
    weight = None
    for k in ("Peso", "Peso del producto", "Peso de la hidrolavadora", "Peso neto"):
        if attrs.get(k):
            weight = first_num(attrs[k])
            break
    if weight is None:
        m = re.search(r"peso(?:\s+(?:neto|del producto|de la unidad))?\s*[:：]?\s*(\d+(?:[.,]\d+)?)\s*kg", desc, re.I)
        if m:
            weight = es_number(m.group(1))

    capacity = ""
    for k in ("Capacidad en volumen", "Peso máximo soportado", "Capacidad de la batería", "Capacidad"):
        if attrs.get(k):
            capacity = str(attrs[k]).strip()
            break
    pieces = first_num(attrs.get("Cantidad de piezas")) if attrs.get("Cantidad de piezas") else None

    # ---------- 材质 ----------
    material = []
    material_basis = None
    for k in ("Material de la bomba", "Material de la rejilla", "Material"):
        if attrs.get(k):
            material.append(str(attrs[k]).strip())
            material_basis = "attribute"
            break
    if not material:
        m = re.search(r"(acero inoxidable|acero al carbono|acero|aluminio)", desc, re.I)
        if m:
            material.append(m.group(1))
            material_basis = "description"
            warn.append(f"材质取自描述推断（{m.group(1)}），需人工核实")

    # ---------- 起升范围（千斤顶） ----------
    lift_range = None
    for k, v in attrs.items():
        if "altura levantada" in k.lower():
            nums = [float(x.replace(",", ".")) for x in re.findall(r"\d+(?:[.,]\d+)?", str(v))]
            unit_mm = bool(re.search(r"mm", str(v), re.I))
            if len(nums) >= 2:
                lift_range = [round(n if unit_mm else n * 10, 2) for n in nums[:2]]

    # ---------- 包装 ----------
    attr_acc = str(attrs.get("Accesorios incluidos", "") or "").strip()
    pkg = parse_package(desc)
    src = "description" if pkg else ""
    if not pkg and attr_acc:
        pkg = split_list(attr_acc)
        src = "attribute"
    not_included = []
    for m in re.finditer(r"(cargador|bater[ií]a)\s+no\s+(?:est[aá]|viene|incluye)", desc, re.I):
        not_included.append(m.group(1).lower())

    # ---------- 功能点 ----------
    features = []
    for k, v in attrs.items():
        if k.startswith("Con ") and str(v).strip().lower() in ("sí", "si", "yes"):
            features.append(k[4:].strip())
    usage = []
    if attrs.get("Usos recomendados"):
        usage.append(str(attrs["Usos recomendados"]))
    specs = {k: attrs[k] for k in SPEC_KEYS if attrs.get(k)}

    # ---------- 图片清单 ----------
    images = []
    manifest = []
    seen = {}
    files = sorted([p for p in Path(img_dir).glob("*") if p.is_file()]) if Path(img_dir).is_dir() else []
    for i, p in enumerate(files):
        h = sha256_file(p)
        dup = seen.get(h)
        seen.setdefault(h, p.name)
        images.append({"file": f"img/{p.name}", "bytes": p.stat().st_size, "sha256": h, "main": i == 0})
        manifest.append({
            "file": f"img/{p.name}", "bytes": p.stat().st_size, "sha256": h,
            "main": "yes" if i == 0 else "", "duplicate_of": dup or "",
        })
    dup_groups = len(manifest) - len(seen)
    if dup_groups:
        warn.append(f"有 {dup_groups} 张重复图（哈希相同）")

    # ---------- 认证 ----------
    cert_status = "not_applicable" if ptype == "manual" else "missing"

    # ---------- 状态 ----------
    status = "blocked" if hard else "draft"

    facts = {
        "schema": "facts/v1",
        "product_id": pid,
        "category": cat,
        "status": status,
        "gates": {"hard_blocks": hard, "warnings": warn},
        "identity": {
            "brand": brand,
            "brand_aliases": [],
            "model": str(attrs.get("Modelo", "") or "").strip(),
            "title_raw": title,
        },
        "power": power,
        "size": size,
        "weight_kg": weight,
        "capacity": capacity,
        "pieces": pieces,
        "material": material,
        "material_basis": material_basis,
        "extras": {
            "lift_range_mm": lift_range,
            "source_url": d.get("source_url", ""),
            "store_id": d.get("store_id", ""),
            "core_keyword": d.get("core_keyword", ""),
        },
        "package": {"included": pkg, "not_included": sorted(set(not_included)), "source": src or None},
        "compatibility": [],
        "certification": {"nom": None, "inmetro": None, "anatel": None, "status": cert_status},
        "features": features,
        "usage": usage,
        "specs": specs,
        "raw_attributes": attrs,
        "site_profiles": {
            d.get("site", "MX"): {
                "price": (d.get("price_source") or {}).get("amount"),
                "currency": (d.get("price_source") or {}).get("currency", "MXN"),
                "plug": "A/B" if d.get("site", "MX") == "MX" else "N",
                "nominal_v": 127 if d.get("site", "MX") == "MX" else None,
            }
        },
        "images": images,
        "unknowns": [],
        "_meta": {
            "rules_version": RULES_VERSION,
            "built_at": datetime.now().isoformat(timespec="seconds"),
            "built_from": [],
            "source_sha256": {},
            "verified_by": None,
            "verified_at": None,
        },
    }
    return facts, manifest


def set_path(obj, path, val):
    parts = path.split(".")
    cur = obj
    for p in parts[:-1]:
        if p not in cur or not isinstance(cur[p], dict):
            cur[p] = {}
        cur = cur[p]
    cur[parts[-1]] = val


def apply_override(facts, ov, ov_path=None):
    """人工确认写进 input/<SKU>/overrides.json，重建时自动重放。"""
    for path, val in (ov.get("set") or {}).items():
        set_path(facts, path, val)
    if ov.get("brand_aliases"):
        facts.setdefault("identity", {})["brand_aliases"] = ov["brand_aliases"]
    for key in ("resolve_blocks", "remove_warnings"):
        target = facts["gates"]["hard_blocks"] if key == "resolve_blocks" else facts["gates"]["warnings"]
        for s in ov.get(key, []) or []:
            target[:] = [x for x in target if s not in x]
    for w in ov.get("add_warnings", []) or []:
        if w not in facts["gates"]["warnings"]:
            facts["gates"]["warnings"].append(w)
    if facts.get("status") == "blocked" and not facts["gates"]["hard_blocks"]:
        facts["status"] = "draft"
    # 人工隔离：移出生成集，保留事实卡与审计记录（解除时删掉 overrides 里的 quarantine）
    q = ov.get("quarantine")
    if q:
        facts["status"] = "quarantined"
        facts["_meta"]["quarantine"] = {
            "reason": (q.get("reason") or "") if isinstance(q, dict) else str(q),
            "by": (q.get("by") or None) if isinstance(q, dict) else None,
            "at": (q.get("at") or None) if isinstance(q, dict) else None,
        }
    facts["_meta"]["overrides"] = rel(ov_path) if ov_path else None
    facts["_meta"]["overrides_note"] = ov.get("source", "")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="input JSON -> facts.json + img_manifest.csv")
    ap.add_argument("--input-root", default=str(DEFAULT_INPUT))
    ap.add_argument("--only", default="", help="只处理一个 product_id")
    ap.add_argument("--check", action="store_true", help="只报告，不写文件")
    ap.add_argument("--force", action="store_true", help="重建并清空人工核验状态")
    args = ap.parse_args()

    root = Path(args.input_root).resolve()
    if not root.is_dir():
        die(f"目录不存在：{root}")

    dirs = [d for d in sorted(root.iterdir()) if d.is_dir() and (d / "input.json").exists()
            and d.name not in SKIP_DIRS and not d.name.startswith("_")]
    if args.only:
        dirs = [d for d in dirs if d.name == args.only]
        if not dirs:
            die(f"没有找到商品：{args.only}")

    for d in dirs:
        data = load_json(d / "input.json")
        item_path = d / "item.json"
        facts, manifest = build_one(data, d / "img")
        facts["_meta"]["built_from"] = [rel(d / "input.json")] + ([rel(item_path)] if item_path.exists() else [])
        facts["_meta"]["source_sha256"] = {"input.json": sha256_file(d / "input.json")}
        if item_path.exists():
            facts["_meta"]["source_sha256"]["item.json"] = sha256_file(item_path)

        # 重建保护：来源未变则保留人工核验状态；来源变了才退回 draft
        old_path = d / "facts.json"
        if old_path.exists() and not args.force:
            try:
                old = load_json(old_path)
            except Exception:
                old = None
            if old and old.get("_meta", {}).get("source_sha256") == facts["_meta"]["source_sha256"]:
                if old.get("status") == "verified":
                    facts["status"] = "verified"
                    facts["_meta"]["verified_by"] = old.get("_meta", {}).get("verified_by")
                    facts["_meta"]["verified_at"] = old.get("_meta", {}).get("verified_at")
                    facts["gates"]["warnings"].append("facts 已按同一来源重建；人工核验状态已保留")
                elif old.get("status") == "blocked":
                    facts["status"] = "blocked"  # 保留，交给 overrides 决定是否解封
            elif old and old.get("status") == "verified":
                facts["gates"]["warnings"].append("来源文件已变更，原 verified 状态已退回 draft，需重新核验")

        # 人工确认覆盖（品牌/电压/包装等），重建时自动重放
        ov_path = d / "overrides.json"
        if ov_path.exists():
            apply_override(facts, load_json(ov_path), ov_path)

        status = facts["status"]
        flag = {"draft": "草稿", "verified": "已核", "blocked": "阻断", "quarantined": "隔离"}[status]
        power = facts["power"]
        w_txt = f"{power['w']:g}W" if power["w"] else (f"标称{power['claimed_w']}W不写" if power["claimed_w"] else "-")
        print(f"[{flag}] {facts['product_id']:<11} {facts['category']:<5} "
              f"{power['type']:<7} {w_txt:<14} "
              f"blocks={len(facts['gates']['hard_blocks'])} warn={len(facts['gates']['warnings'])} "
              f"imgs={len(facts['images'])}")
        for b in facts["gates"]["hard_blocks"]:
            print(f"        ! {b}")
        for w in facts["gates"]["warnings"]:
            print(f"        - {w}")

        if args.check:
            continue
        (d / "facts.json").write_text(json.dumps(facts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        with open(d / "img_manifest.csv", "w", encoding="utf-8-sig", newline="") as f:
            f.write("file,bytes,sha256,main,duplicate_of\n")
            for r in manifest:
                f.write(f"{r['file']},{r['bytes']},{r['sha256']},{r['main']},{r['duplicate_of']}\n")

    if not args.check:
        print(f"\n完成：{len(dirs)} 个 SKU -> facts.json + img_manifest.csv")


if __name__ == "__main__":
    main()
