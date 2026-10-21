#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
认证台账检查器 v1.0

定位：上架前的合规卡口。读 input/*/facts.json + certifications.json，
判断每个 SKU 在目标站点「需要哪些认证、有没有、过没过期」，出表 + 退出码。

不做的事：不写 facts.json、不猜证书号、不判定认证真伪。

用法：
  python check_certificates.py --input-root ..\\input --site auto
  python check_certificates.py --input-root ..\\input --site ALL --days 60
  python check_certificates.py --input-root ..\\input --strict   # 有缺失/过期时退出码 3
  python check_certificates.py --demo                            # 自检，不需要 input
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

try:  # Windows 控制台默认 GBK，固定成 UTF-8，避免中文报告乱码
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

BASE = Path(__file__).resolve().parent
DEFAULT_LEDGER = BASE / "certifications.json"
DEFAULT_INPUT = BASE.parent / "input"
DEFAULT_OUTDIR = BASE / "报告"

STATUS_LABEL = {
    "valid": "有效",
    "expiring": "即将到期",
    "expired": "已过期",
    "unverified": "待确认",
    "missing": "未登记",
    "not_required": "不需要",
}
SEVERITY_LABEL = {"block": "阻断", "warn": "提醒"}
WIRELESS_PAT = ("bluetooth", "bt ", "wifi", "wi-fi", "2.4g", "5.8g", "radio", "inalambrico", "inalámbrico")
# 注意：西语/葡语 inalámbrico 常指「无线电动工具/无绳」，不等于无线通信模块。
# 因此只有在同时出现通信类词（bluetooth/wifi/2.4g/radio）时才算 ANATEL；
# 单出现 inalambrico 不算，避免把电锯误判成无线模块。


def norm(s: str | None) -> str:
    return (s or "").strip().lower()


def is_placeholder(v) -> bool:
    if v is None:
        return True
    s = str(v).strip()
    return s == "" or "待确认" in s or s.upper() in ("TBD", "N/A", "NA", "UNKNOWN")


def parse_date(v):
    if not v:
        return None
    s = str(v).strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%Y年%m月%d日"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def load_facts(input_root: Path):
    out = []
    if not input_root.exists():
        return out
    for d in sorted(input_root.iterdir()):
        if not d.is_dir() or d.name.startswith("_"):
            continue
        f = d / "facts.json"
        if not f.exists():
            continue
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except Exception as e:  # noqa: BLE001
            print(f"[WARN] 读不了 {f}: {e}", file=sys.stderr)
            continue
        data["_dir"] = d.name
        out.append(data)
    return out


def has_battery(facts: dict) -> bool:
    power = facts.get("power") or {}
    if norm(power.get("type")) == "battery":
        return True
    pkg = facts.get("package") or {}
    blob = " ".join(str(x) for x in (pkg.get("included") or []))
    if any(k in blob.lower() for k in ("bater", "battery", "lítio", "lithium", "锂")):
        return True
    attrs = facts.get("raw_attributes") or {}
    blob2 = " ".join(f"{k} {v}" for k, v in attrs.items()).lower()
    return any(k in blob2 for k in (" bater", "battery", "batería", "bateria"))


def has_wireless(facts: dict) -> bool:
    parts = [facts.get("identity", {}).get("title_raw") or ""]
    parts += facts.get("features") or []
    parts += [str(v) for v in (facts.get("raw_attributes") or {}).values()]
    blob = " ".join(parts).lower()
    return any(k in blob for k in ("bluetooth", "wifi", "wi-fi", "2.4g", "5.8g", "radio frecuencia", "无线"))


def sites_for(facts: dict, site_arg: str):
    if site_arg and site_arg.upper() != "AUTO":
        if site_arg.upper() == "ALL":
            return ["MX", "BR"]
        return [site_arg.upper()]
    profiles = facts.get("site_profiles") or {}
    if profiles:
        return list(profiles.keys())
    return ["MX"]


def req_matches(req: dict, facts: dict, site: str) -> bool:
    if req.get("site") not in ("ALL", "GLOBAL", site):
        return False
    when = req.get("when") or {}
    cats = when.get("categories") or ["*"]
    if "*" not in cats and (facts.get("category") or "") not in cats:
        return False
    if "power_types" in when:
        ptype = norm((facts.get("power") or {}).get("type"))
        if ptype not in [norm(x) for x in when["power_types"]]:
            return False
    if when.get("battery") is True and not has_battery(facts):
        return False
    if when.get("wireless") is True and not has_wireless(facts):
        return False
    return True


def find_cert(ledger: dict, facts: dict, site: str, cert_type: str):
    pid = facts.get("product_id") or facts.get("_dir")
    model = norm((facts.get("identity") or {}).get("model"))
    brand = norm((facts.get("identity") or {}).get("brand"))
    for c in ledger.get("certificates", []):
        if c.get("type") != cert_type:
            continue
        csite = (c.get("site") or "").upper()
        if csite not in ("", "ALL", "GLOBAL", site.upper()):
            continue
        skus = [str(x) for x in (c.get("skus") or [])]
        if skus and pid in skus:
            return c, "sku"
        models = [norm(str(x)) for x in (c.get("models") or [])]
        if models and model and model in models:
            return c, "model"
        if not skus and not models and brand and norm(c.get("brand")) == brand:
            return c, "brand"
    return None, None


def cert_status(cert: dict, today: date, warn_days: int):
    if cert is None:
        return "missing", None
    if is_placeholder(cert.get("number")) or is_placeholder(cert.get("expires_at")):
        return "unverified", None
    exp = parse_date(cert.get("expires_at"))
    if exp is None:
        return "unverified", None
    left = (exp - today).days
    if left < 0:
        return "expired", left
    if left <= warn_days:
        return "expiring", left
    return "valid", left


def evaluate(facts_list, ledger, site_arg, today, warn_days):
    rows = []
    for facts in facts_list:
        for site in sites_for(facts, site_arg):
            for req in ledger.get("requirements", []):
                if not req_matches(req, facts, site):
                    continue
                cert, match_by = find_cert(ledger, facts, site, req["cert"])
                status, left = cert_status(cert, today, warn_days)
                rows.append({
                    "sku": facts.get("product_id") or facts.get("_dir"),
                    "site": site,
                    "category": facts.get("category") or "",
                    "power_type": norm((facts.get("power") or {}).get("type")),
                    "cert_type": req["cert"],
                    "label": req.get("label") or "",
                    "severity": req.get("severity", "block"),
                    "confirmed": bool(req.get("confirmed", True)),
                    "req_id": req.get("id") or "",
                    "cert_id": cert.get("cert_id") if cert else "",
                    "number": cert.get("number") if cert else "",
                    "holder": cert.get("holder") if cert else "",
                    "expires_at": cert.get("expires_at") if cert else "",
                    "days_left": left,
                    "status": status,
                    "match_by": match_by or "",
                    "source_url": cert.get("source_url") if cert else "",
                    "note": req.get("note") or "",
                })
    return rows


def action_for(row) -> str:
    st = row["status"]
    if st == "missing":
        return "补证书：向供应商/认证机构索取后登记到 certifications.json"
    if st == "unverified":
        return "补证书号与有效期，别留【待确认】"
    if st == "expired":
        return "已过期：立即停售/换证，换证后重新登记"
    if st == "expiring":
        return "启动换证，到期前完成"
    return "—"


def print_report(rows, today, warn_days, strict, site_arg="auto"):
    print(f"\n认证台账检查  |  今天 {today}  |  到期提醒窗口 {warn_days} 天")
    if str(site_arg).upper() == "ALL":
        print("口径说明：站点=ALL 是按「MX+BR 双站规划」检查，不代表该 SKU 当前已在两个站点在售。")
    print("=" * 100)
    if not rows:
        print("没有命中任何认证要求（可能没有 facts.json，或类目/供电类型不触发规则）")
        return
    print(f"{'SKU':<13}{'站点':<5}{'认证':<10}{'状态':<7}{'到期':<12}{'剩余':<6}{'严重度':<5}匹配")
    print("-" * 100)
    for r in sorted(rows, key=lambda x: (x["sku"], x["site"], x["cert_type"])):
        left = "-" if r["days_left"] is None else str(r["days_left"])
        print(f"{r['sku']:<13}{r['site']:<5}{r['cert_type']:<10}{STATUS_LABEL.get(r['status'], r['status']):<7}"
              f"{str(r['expires_at'] or '-'):<12}{left:<6}{SEVERITY_LABEL.get(r['severity'], r['severity']):<5}{r['match_by'] or '-'}")
    print("-" * 100)
    cnt = {}
    for r in rows:
        cnt[r["status"]] = cnt.get(r["status"], 0) + 1
    print("汇总：" + "  ".join(f"{STATUS_LABEL.get(k, k)}={v}" for k, v in sorted(cnt.items())))

    blockers = [r for r in rows if r["severity"] == "block" and r["status"] in ("missing", "unverified", "expired")]
    warnings = [r for r in rows if r["severity"] == "warn" and r["status"] in ("missing", "unverified", "expired", "expiring")]
    expiring = [r for r in rows if r["status"] == "expiring"]
    if blockers:
        print(f"\n[阻断] {len(blockers)} 条：上架前必须处理")
        for r in blockers:
            print(f"  - {r['sku']} / {r['site']} / {r['cert_type']}：{action_for(r)}")
    if warnings:
        print(f"\n[提醒] {len(warnings)} 条：规则未确认或缺资料，不阻断但需跟进")
        for r in warnings:
            print(f"  - {r['sku']} / {r['site']} / {r['cert_type']}：{r['note']}")
    if expiring:
        print(f"\n[换证] {len(expiring)} 条：{warn_days} 天内到期")
        for r in expiring:
            print(f"  - {r['sku']} / {r['site']} / {r['cert_type']}：{r['expires_at']}（剩 {r['days_left']} 天）")
    if strict and blockers:
        print("\n--strict：存在阻断项，退出码 3")
    elif blockers:
        print("\n（未加 --strict，退出码仍为 0）")


def write_csv(rows, out_path: Path):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    headers = ["SKU", "站点", "类目", "供电类型", "认证类型", "要求来源", "严重度", "证书ID", "证书号",
               "持有人", "到期日期", "剩余天数", "状态", "匹配方式", "来源URL", "备注", "建议动作"]
    with out_path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(headers)
        for r in rows:
            w.writerow([r["sku"], r["site"], r["category"], r["power_type"], r["cert_type"], r["req_id"],
                        r["severity"], r["cert_id"], r["number"], r["holder"], r["expires_at"],
                        r["days_left"] if r["days_left"] is not None else "", r["status"], r["match_by"],
                        r["source_url"], r["note"], action_for(r)])
    return out_path


def demo(today: date) -> int:
    ledger = {
        "requirements": [
            {"id": "MX-NOM003", "site": "MX", "cert": "NOM-003", "severity": "block", "confirmed": True},
            {"id": "GLOBAL-UN383", "site": "GLOBAL", "cert": "UN38.3", "severity": "block", "confirmed": True},
            {"id": "BR-ANATEL", "site": "BR", "cert": "ANATEL", "severity": "block", "confirmed": True,
             "when": {"categories": ["*"], "wireless": True}},
        ],
        "certificates": [
            {"cert_id": "A", "site": "MX", "type": "NOM-003", "number": "NYCE-001", "expires_at": "2028-01-01",
             "brand": "Atverce", "models": ["M1"]},
            {"cert_id": "B", "site": "MX", "type": "NOM-003", "number": "NYCE-002", "expires_at": "2026-11-15",
             "brand": "Atverce", "models": ["M2"]},
            {"cert_id": "C", "site": "MX", "type": "NOM-003", "number": "NYCE-003", "expires_at": "2026-01-01",
             "brand": "Atverce", "models": ["M3"]},
        ],
    }
    base = {"category": "五金工具", "site_profiles": {"MX": {}}, "package": {"included": ["Batería"]}}

    def mk(pid, model, site_profiles=None):
        f = dict(base)
        f = {"product_id": pid, "category": "五金工具", "power": {"type": "battery"},
             "identity": {"brand": "Atverce", "model": model, "title_raw": "Taladro"},
             "package": {"included": ["Batería"]}, "site_profiles": site_profiles or {"MX": {}}}
        return f

    facts = [mk("S1", "M1"), mk("S2", "M2"), mk("S3", "M3"), mk("S4", "M4")]
    rows = evaluate(facts, ledger, "auto", today, 60)
    by = {(r["sku"], r["cert_type"]): r["status"] for r in rows}
    checks = [
        ("S1", "NOM-003", "valid"),
        ("S2", "NOM-003", "expiring"),
        ("S3", "NOM-003", "expired"),
        ("S4", "NOM-003", "missing"),
        ("S1", "UN38.3", "missing"),
    ]
    ok = True
    for sku, ct, want in checks:
        got = by.get((sku, ct))
        flag = "OK " if got == want else "FAIL"
        if got != want:
            ok = False
        print(f"[{flag}] {sku} {ct}: 期望 {want}，实际 {got}")
    # 无线模块判定：cordless 不能触发 ANATEL
    f = mk("S5", "M5", {"BR": {}})
    f["identity"]["title_raw"] = "Motosierra Inalámbrica 21V"
    rows2 = evaluate([f], ledger, "auto", today, 60)
    anatel = [r for r in rows2 if r["cert_type"] == "ANATEL"]
    if anatel:
        ok = False
        print("[FAIL] cordless 被误判为无线模块（触发 ANATEL）")
    else:
        print("[OK ] cordless 未触发 ANATEL")
    print("\n自检结果：" + ("通过" if ok else "失败"))
    return 0 if ok else 2


def main() -> int:
    ap = argparse.ArgumentParser(description="认证台账检查器 v1.0（上架前合规卡口）")
    ap.add_argument("--input-root", default=str(DEFAULT_INPUT), help="商品目录（含 */facts.json）")
    ap.add_argument("--ledger", default=str(DEFAULT_LEDGER), help="认证台账 JSON")
    ap.add_argument("--site", default="auto", help="auto（按 facts 的 site_profiles）/ MX / BR / ALL")
    ap.add_argument("--today", default="", help="覆盖今天日期 YYYY-MM-DD（测试用）")
    ap.add_argument("--days", type=int, default=60, help="到期提醒窗口（天）")
    ap.add_argument("--strict", action="store_true", help="有阻断项时退出码 3")
    ap.add_argument("--outdir", default=str(DEFAULT_OUTDIR), help="报告目录")
    ap.add_argument("--demo", action="store_true", help="自检，不使用 input")
    args = ap.parse_args()

    today = parse_date(args.today) or date.today()
    if args.demo:
        return demo(today)

    ledger_path = Path(args.ledger)
    if not ledger_path.exists():
        print(f"[ERROR] 找不到台账：{ledger_path}", file=sys.stderr)
        return 2
    try:
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        print(f"[ERROR] 台账 JSON 解析失败：{e}", file=sys.stderr)
        return 2

    facts_list = load_facts(Path(args.input_root))
    if not facts_list:
        print(f"[ERROR] {args.input_root} 下没有 facts.json", file=sys.stderr)
        return 2

    rows = evaluate(facts_list, ledger, args.site, today, args.days)
    print_report(rows, today, args.days, args.strict, args.site)

    out = Path(args.outdir) / today.strftime("%Y%m%d") / "认证检查.csv"
    write_csv(rows, out)
    print(f"\n明细已写入：{out}")

    blockers = [r for r in rows if r["severity"] == "block" and r["status"] in ("missing", "unverified", "expired")]
    return 3 if (args.strict and blockers) else 0


if __name__ == "__main__":
    sys.exit(main())
