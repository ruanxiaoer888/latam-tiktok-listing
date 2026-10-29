# -*- coding: utf-8 -*-
r"""facts ↔ 成稿一致性检查（确定性，不调模型）。

补的是 check_listing 查不出的盲区：文案本身合规，但和事实卡矛盾。
（`AMU5000000` 的教训：事实卡 127V 插电，文案写 8000mAh 无线，两边都"合规"却互相打架。）

规则（P0 阻断 / P1 风险 / P2 提示）：
  1. CERT-FORBIDDEN      facts 认证 missing，正文出现 NOM/INMETRO/ANATEL/UN38.3 → P0
  2. POWER-TYPE-CONFLICT facts=manual/corded，正文称"无线/电池/充电" → P0
                         facts=battery，正文称"127V/插电/交流"  → P0
  3. POWER-NOT-ALLOWED   facts.state_power=false，正文出现瓦数 → P1
  4. POWER-MISMATCH      facts 有 w，正文瓦数与它对不上 → P1
  5. CAPACITY-MISMATCH   facts 有容量，正文 mAh/Ah 对不上 → P1
  6. VOLTAGE-RANGE       facts 有电池电压，正文电压偏离 >25% → P2

用法（仓库根执行）：
  python qa\check_consistency.py --check-csv <run_batch 的 check.csv> --input-root input --out <_smoke 目录>
  python qa\check_consistency.py ... --strict     # 有 P0 时 exit 3

退出码：0 正常；2 参数/文件问题；3 有 P0（--strict 时）。
"""
import argparse
import csv
import json
import re
import sys
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent
ROOT = BASE.parent

CERT_WORDS = re.compile(r"NOM-?003|INMETRO|ANATEL|UN38\.?3", re.I)
# 只认强证据：不算裸 "batería"（可能是「汽车电瓶」），也不算裸 "enchufe"（可能只是场景描述）
WIRELESS = re.compile(r"inal[aá]mbric|recargable|bater[ií]a de litio|bater[ií]a incluida|sin cable", re.I)
WIRED = re.compile(r"\b127\s?V\b|corriente alterna|a la red", re.I)
WATTS = re.compile(r"(\d+(?:[.,]\d+)?)\s?W\b", re.I)
CAPS = re.compile(r"(\d+(?:[.,]\d+)?)\s?(mAh|Ah)\b", re.I)
VOLTS = re.compile(r"(\d+(?:[.,]\d+)?)\s?V\b", re.I)


def num(s):
    """兼容西语数字：`1.200,5` / `1,200` / `2,5`。"""
    s = str(s).strip()
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".") if s.rfind(",") > s.rfind(".") else s.replace(",", "")
    elif "," in s:
        s = s.replace(",", "") if re.fullmatch(r"\d{1,3}(,\d{3})+", s) else s.replace(",", ".")
    return float(s)


def load_facts(root, pid):
    p = root / pid / "facts.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8-sig"))
    except Exception:  # noqa: BLE001
        return None


def check_one(pid, title, desc, facts):
    out = []
    body = f"{title}\n{desc}"

    def add(sev, rid, label, field, snip, fix):
        out.append({"id": pid, "severity": sev, "rule": rid, "label": label,
                    "field": field, "snippet": snip, "fix": fix})

    if not facts:
        add("P2", "NO-FACTS", "没有 facts.json，无法核对", "-", pid, "补事实卡")
        return out
    cert = (facts.get("certification") or {}).get("status")
    if cert == "missing":
        m = CERT_WORDS.search(body)
        if m:
            add("P0", "CERT-FORBIDDEN", "认证未登记却写了认证字样", "正文",
                body[max(0, m.start() - 40):m.start() + 40].replace("\n", " "),
                "删除认证名；台账登记后再写")

    p = facts.get("power") or {}
    ptype = str(p.get("type") or "").lower()
    if ptype in ("manual", "corded"):
        m = WIRELESS.search(body)
        if m:
            add("P0", "POWER-TYPE-CONFLICT", f"facts 供电={ptype}，正文却称无线/电池", "正文",
                m.group(0), "按事实卡改：手动工具不写电池/无线")
    if ptype == "battery":
        for m in WIRED.finditer(body):
            ctx = body[max(0, m.start() - 45):m.end() + 45].lower()
            if re.search(r"cargador|entrada|input|cable|adaptador|fuente", ctx):
                continue
            add("P0", "POWER-TYPE-CONFLICT", "facts 供电=battery，正文却称 127V/插电", "正文",
                m.group(0), "按事实卡改：电池工具不写 127V/插电")
            break

    if p.get("state_power") is False:
        m = WATTS.search(body)
        if m:
            add("P1", "POWER-NOT-ALLOWED", "facts 明确不可写功率，正文仍出现瓦数", "正文",
                m.group(0), "删除瓦数（电池工具多数是等效峰值，不写）")
    elif p.get("state_power") is True and p.get("w"):
        vals = [num(x) for x in WATTS.findall(body)]
        if vals and all(abs(v - num(p["w"])) > max(1, num(p["w"]) * 0.01) for v in vals):
            add("P1", "POWER-MISMATCH", f"正文瓦数与 facts（{p['w']}W）不一致", "正文",
                "、".join(m.group(0) for m in WATTS.finditer(body))[:60], "以事实卡为准")

    cap = facts.get("capacity")
    if cap:
        cm = re.search(r"(\d+(?:[.,]\d+)?)\s?(mAh|Ah)", str(cap), re.I)
        if cm:
            want = num(cm.group(1)) * (1000 if cm.group(2).lower() == "ah" else 1)
            got = [(num(v) * (1000 if u.lower() == "ah" else 1), f"{v} {u}")
                   for v, u in CAPS.findall(body)]
            if got and all(abs(v - want) > want * 0.01 for v, _ in got):
                add("P1", "CAPACITY-MISMATCH", f"正文容量与 facts（{cap}）不一致", "正文",
                    "、".join(x for _, x in got)[:60], "以事实卡为准")

    bv = p.get("battery_v")
    if bv:
        got = [num(v) for v in VOLTS.findall(body)]
        if got and all(abs(v - num(bv)) > num(bv) * 0.25 for v in got):
            add("P2", "VOLTAGE-RANGE", f"正文电压与电池电压（{bv}V）偏差 >25%", "正文",
                "、".join(f"{v} V" for v in got)[:60], "确认电压口径（工作电压/充电输入）")
    return out


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="facts ↔ 成稿一致性检查")
    ap.add_argument("--check-csv", required=True, help="build_batch_csv 的 check.csv")
    ap.add_argument("--input-root", default=str(ROOT / "input"))
    ap.add_argument("--out", default="", help="报告目录；默认 qa\\报告\\<日期>")
    ap.add_argument("--strict", action="store_true", help="有 P0 时退出码 3")
    args = ap.parse_args()

    src = Path(args.check_csv)
    if not src.exists():
        raise SystemExit(f"找不到 CSV：{src}")
    root = Path(args.input_root).resolve()
    outdir = Path(args.out) if args.out else BASE / "报告" / f"{datetime.now():%Y%m%d}"
    outdir.mkdir(parents=True, exist_ok=True)

    with open(src, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    hits = []
    for r in rows:
        pid = r.get("id") or ""
        hits += check_one(pid, r.get("标题", ""), r.get("描述", ""), load_facts(root, pid))

    order = {"P0": 0, "P1": 1, "P2": 2}
    hits.sort(key=lambda h: (order[h["severity"]], h["id"]))
    counts = {k: sum(1 for h in hits if h["severity"] == k) for k in order}

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    csv_path = outdir / f"一致性检查_{stamp}.csv"
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["id", "severity", "rule", "label", "field", "snippet", "fix"])
        w.writeheader()
        w.writerows(hits)

    lines = [f"# facts ↔ 文案一致性检查（{stamp}）", "",
             f"- 样本：{len(rows)} 条", f"- 命中：{len(hits)} 处",
             f"- 分级：P0={counts['P0']} P1={counts['P1']} P2={counts['P2']}", ""]
    if hits:
        lines += ["| SKU | 级别 | 规则 | 说明 | 命中 | 建议 |", "|---|---|---|---|---|---|"]
        for h in hits:
            lines.append(f"| {h['id']} | {h['severity']} | {h['rule']} | {h['label']} | "
                         f"{h['snippet']} | {h['fix']} |")
    else:
        lines.append("没有发现事实与文案矛盾。")
    md_path = outdir / f"一致性检查_{stamp}.md"
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"样本 {len(rows)} 条，命中 {len(hits)} 处（P0={counts['P0']} P1={counts['P1']} P2={counts['P2']}）")
    print(f"报告：{md_path}")
    for h in hits:
        print(f"  [{h['severity']}] {h['id']:<12} {h['rule']:<20} {h['label']}（{h['snippet']}）")
    if args.strict and counts["P0"] > 0:
        raise SystemExit(3)


if __name__ == "__main__":
    main()
