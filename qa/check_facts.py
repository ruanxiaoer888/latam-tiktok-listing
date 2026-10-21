# -*- coding: utf-8 -*-
r"""
事实卡门禁 v1.0：按 kb/_schemas/<类目>.schema.json 检查 15 份 facts.json。

用法：
  python qa\check_facts.py                 # 报告 + 退出码 0（有 blocked 时打印）
  python qa\check_facts.py --fail-on-blocked  # 有 blocked 时退出码 3，便于接自动化
  python qa\check_facts.py --only ABU5000000

产出：
  kb\_index\完整度报告.md
  kb\_index\facts_check.json

判定：
  quarantined                 → 已移出生成集（人工隔离）
  blocked                      → 禁止生成
  draft + 缺必填                → 待人工补/核
  verified + 缺必填或硬伤       → FAIL（生成端必须拒绝）
  verified + 齐全 + 无硬伤      → READY（可生成）
"""
import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT = ROOT / "input"
SCHEMA_DIR = ROOT / "kb" / "_schemas"
INDEX_DIR = ROOT / "kb" / "_index"
SKIP_DIRS = {"示例商品", "示例商品001"}
CAR_BRAND = re.compile(
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


def load_json(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def get_path(obj, path):
    cur = obj
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def empty(v):
    return v is None or v == "" or v == [] or v == {}


def load_schema(category):
    p = SCHEMA_DIR / f"{category}.schema.json"
    if not p.exists():
        die(f"缺少类目 schema：{p}")
    return load_json(p)


def requirements(facts, schema):
    reqs = list(schema.get("required", []))
    rules = schema.get("power_rules", {}) or {}
    ptype = (facts.get("power") or {}).get("type")
    for t, path in (rules.get("voltage_required") or {}).items():
        if ptype == t:
            reqs.append({"path": path, "label": "电压（按供电类型必填）"})
    for cond in schema.get("conditional", []) or []:
        if cond.get("when") == "title_has_car_brand":
            if CAR_BRAND.search((facts.get("identity") or {}).get("title_raw", "") or ""):
                for path in cond.get("require", []):
                    reqs.append({"path": path, "label": "车型适配（汽配）", "non_empty": True})
    return reqs


def recommended_fields(facts, schema):
    return list(schema.get("recommended", []))


def missing_of(facts, reqs):
    missing = []
    for req in reqs:
        if "any_of" in req:
            if all(empty(get_path(facts, p)) for p in req["any_of"]):
                missing.append(req["label"])
            continue
        if empty(get_path(facts, req["path"])):
            missing.append(req["label"])
    return missing


def check_one(d, schema):
    f = load_json(d / "facts.json")
    status = f.get("status", "draft")
    blocks = list((f.get("gates") or {}).get("hard_blocks") or [])
    warnings = list((f.get("gates") or {}).get("warnings") or [])
    hard_reqs = requirements(f, schema)
    recommended = recommended_fields(f, schema)
    missing = missing_of(f, hard_reqs)
    soft_missing = missing_of(f, recommended)
    if not (f.get("power") or {}).get("state_power"):
        # 功率策略是「不写瓦数」时，power.w 为空不算缺
        soft_missing = [m for m in soft_missing if not str(m).startswith("可写功率")]

    # 功率门禁
    power = f.get("power") or {}
    ptype = power.get("type")
    w = power.get("w")
    if ptype == "corded" and w and w >= 3500:
        blocks.append(f"插电类功率 {w:g}W 在 127V 下超过 27A，不可信")
    if ptype == "battery" and w and w >= 600:
        blocks.append(f"电池类功率 {w:g}W 偏高，不能当持续功率")
    if power.get("claims_w") and not power.get("state_power"):
        warnings.append(f"标称功率 {power.get('claims_w')} 不在 Listing 中使用（policy={power.get('listing_policy')}）")

    # 图片
    images = f.get("images") or []
    if len(images) < 5:
        warnings.append(f"图片仅 {len(images)} 张（建议 ≥5）")
    hashes = [i.get("sha256") for i in images if i.get("sha256")]
    if len(hashes) != len(set(hashes)):
        warnings.append(f"有 {len(hashes) - len(set(hashes))} 张重复图")

    # 认证
    cert = (f.get("certification") or {}).get("status")
    if ptype in ("corded", "battery") and cert == "missing":
        warnings.append("认证状态 missing：Listing 不得写 NOM/INMETRO/ANATEL")

    # 状态判定
    quarantine = (f.get("_meta") or {}).get("quarantine") or {}
    if status == "quarantined":
        verdict = "QUARANTINED"
    elif status == "blocked":
        verdict = "BLOCKED"
    elif status == "verified" and (missing or blocks):
        verdict = "FAIL"
    elif status == "verified":
        verdict = "READY"
    else:
        verdict = "PENDING" if missing else "DRAFT-OK"

    return {
        "product_id": f.get("product_id", d.name),
        "category": f.get("category", ""),
        "status": status,
        "verdict": verdict,
        "quarantine_reason": quarantine.get("reason", ""),
        "required_total": len(hard_reqs),
        "required_missing": missing,
        "recommended_missing": soft_missing,
        "hard_blocks": blocks,
        "warnings": warnings,
        "images": len(images),
        "power_type": ptype,
        "power_w": w,
        "claimed_w": power.get("claimed_w"),
        "state_power": power.get("state_power"),
        "updated_at": f.get("_meta", {}).get("built_at", ""),
    }


def write_report(results, fail_on_blocked):
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    day = datetime.now().strftime("%Y-%m-%d %H:%M")
    counts = {k: 0 for k in ("READY", "FAIL", "BLOCKED", "QUARANTINED", "PENDING", "DRAFT-OK")}
    for r in results:
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1

    lines = [
        "# 事实卡完整度报告",
        "",
        f"- 生成时间：{day}",
        f"- 样本：{len(results)} 个 SKU",
        f"- READY（verified + 齐全）：{counts.get('READY', 0)}　"
        f"FAIL：{counts.get('FAIL', 0)}　BLOCKED：{counts.get('BLOCKED', 0)}　"
        f"PENDING（草稿缺字段）：{counts.get('PENDING', 0)}　"
        f"已隔离（移出生成集）：{counts.get('QUARANTINED', 0)}",
        "",
        "> 口径：`verified` 才允许生成；`quarantined` 已移出生成集；`blocked` 禁止生成；`draft` 待人工核。",
        "",
        "## 一、逐 SKU",
        "",
        "| SKU | 类目 | 状态 | 判定 | 硬缺（阻断生成） | 软缺（建议补） | 图片 | 功率策略 | 阻断项 |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in results:
        if r["verdict"] == "QUARANTINED":
            miss = soft = blocks = "—"
        else:
            miss = "、".join(r["required_missing"]) if r["required_missing"] else "—"
            soft = "、".join(r["recommended_missing"]) if r["recommended_missing"] else "—"
            blocks = "<br>".join(r["hard_blocks"]) if r["hard_blocks"] else "—"
        policy = "不写瓦数" if r["state_power"] is False and r["claimed_w"] else (
            f"{r['power_w']:g}W" if r["power_w"] else "—")
        lines.append(
            f"| {r['product_id']} | {r['category']} | {r['status']} | {r['verdict']} | {miss} | {soft} | {r['images']} | {policy} | {blocks} |"
        )
    lines += ["", "## 二、需要人工确认的项", ""]
    for r in results:
        if r["verdict"] == "QUARANTINED":
            continue
        if not (r["hard_blocks"] or r["required_missing"] or r["recommended_missing"] or r["warnings"]):
            continue
        lines.append(f"### {r['product_id']}（{r['status']} / {r['verdict']}）")
        lines.append("")
        for b in r["hard_blocks"]:
            lines.append(f"- **阻断**：{b}")
        if r["required_missing"]:
            lines.append(f"- **硬缺（必须补）**：{'、'.join(r['required_missing'])}")
        if r["recommended_missing"]:
            lines.append(f"- 软缺（建议补）：{'、'.join(r['recommended_missing'])}")
        for w in r["warnings"]:
            lines.append(f"- 待核：{w}")
        lines.append("")
    lines += ["## 三、已隔离（不参与生成）", ""]
    quarantined = [r for r in results if r["verdict"] == "QUARANTINED"]
    if quarantined:
        lines += ["| SKU | 隔离原因 |", "|---|---|"]
        for r in quarantined:
            lines.append(f"| {r['product_id']} | {r['quarantine_reason'] or '—'} |")
    else:
        lines.append("无。")
    lines += [
        "",
        "## 四、下一步",
        "",
        "1. 隔离项先补证据（铭牌/实物照片/包装核对），确认后删掉 `overrides.json` 里的 `quarantine` 再参与核验。",
        "2. 其余 `draft` 逐条人工核；确认后置 `verified`（`_meta.verified_by/at` 填上）。",
        "3. 再跑 `python qa\\check_facts.py`，`READY` 的才进生成。",
        "",
    ]
    (INDEX_DIR / "完整度报告.md").write_text("\n".join(lines), encoding="utf-8")
    (INDEX_DIR / "facts_check.json").write_text(
        json.dumps({"generated_at": day, "counts": counts, "results": results}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")
    return counts


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="facts.json 门禁检查")
    ap.add_argument("--input-root", default=str(DEFAULT_INPUT))
    ap.add_argument("--only", default="")
    ap.add_argument("--fail-on-blocked", action="store_true")
    args = ap.parse_args()

    root = Path(args.input_root).resolve()
    if not root.is_dir():
        die(f"目录不存在：{root}")
    dirs = [d for d in sorted(root.iterdir()) if (d / "facts.json").exists()
            and d.name not in SKIP_DIRS and not d.name.startswith("_")]
    if args.only:
        dirs = [d for d in dirs if d.name == args.only]
    if not dirs:
        die("没有找到 facts.json，先运行 python qa\\build_facts.py")

    results = []
    for d in dirs:
        f = load_json(d / "facts.json")
        schema = load_schema(f.get("category", ""))
        results.append(check_one(d, schema))

    counts = write_report(results, args.fail_on_blocked)
    print(f"样本 {len(results)} 个 | READY={counts.get('READY', 0)} FAIL={counts.get('FAIL', 0)} "
          f"BLOCKED={counts.get('BLOCKED', 0)} QUARANTINED={counts.get('QUARANTINED', 0)} "
          f"PENDING={counts.get('PENDING', 0)} "
          f"DRAFT-OK={counts.get('DRAFT-OK', 0)}")
    for r in results:
        miss = f" 硬缺：{'、'.join(r['required_missing'])}" if r["required_missing"] else ""
        soft = f" 软缺：{'、'.join(r['recommended_missing'])}" if r["recommended_missing"] else ""
        blk = f" 阻断：{'；'.join(r['hard_blocks'])}" if r["hard_blocks"] else ""
        print(f"  {r['verdict']:<8} {r['product_id']:<12} {r['status']:<8}{miss}{soft}{blk}")
    print(f"\n报告：{INDEX_DIR / '完整度报告.md'}")
    if args.fail_on_blocked and counts.get("BLOCKED", 0) > 0:
        raise SystemExit(3)


if __name__ == "__main__":
    main()
