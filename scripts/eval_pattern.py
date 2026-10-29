# -*- coding: utf-8 -*-
r"""用现有确定性检查器给一批成稿打分，按 pattern 版本存档基线。

不调模型：复用 qa\build_batch_csv.py + qa\check_listing.py，输出四项计数与失败规则 ID。
改提示词后跑同一批，和上一版基线比，才知道是变好还是变坏（fabric 自己没有这层）。

用法（仓库根执行）：
  python scripts\eval_pattern.py --batch output\批次20261022-v2 --pattern listing_write@1.0.0 --site MX
  python scripts\eval_pattern.py --batch output\批次20261030 --baseline output\_eval\listing_write@1.0.0.json
  python scripts\eval_pattern.py --batch output\批次20261022-v2 --golden eval\golden\manifest.json

退出码：0 = 已评测（P0/P1 均为 0）；3 = 评测完成但有 P0/P1（可接 CI）；1 = 运行错误。
"""
import argparse
import csv
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SUMMARY = re.compile(r"样本 (\d+) 条，命中 (\d+) 条（P0=(\d+) P1=(\d+) P2-结构=(\d+) P2-转化=(\d+)）")


def run(cmd):
    return subprocess.run([str(c) for c in cmd], cwd=ROOT, capture_output=True,
                          text=True, encoding="utf-8", errors="replace")


def filter_golden(src: Path, dst: Path, manifest: Path):
    """只保留黄金集 manifest 里的 SKU，返回 (数量, manifest 条目数)。"""
    man = json.loads(manifest.read_text(encoding="utf-8-sig"))
    entries = man.get("entries", [])
    keep = {e["sku"] for e in entries}
    with open(src, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    kept = [r for r in rows if r.get("id") in keep]
    with open(dst, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else ["id"])
        w.writeheader()
        w.writerows(kept)
    return len(kept), len(entries)


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="成稿批次 → 评测分（复用 check_listing）")
    ap.add_argument("--batch", required=True)
    ap.add_argument("--pattern", default="listing_write@1.0.0")
    ap.add_argument("--site", default="MX", choices=["MX", "BR"])
    ap.add_argument("--input-root", default=str(ROOT / "input"))
    ap.add_argument("--out-root", default=str(ROOT / "output" / "_eval"))
    ap.add_argument("--baseline", default="", help="上一版评测 JSON，给出则打印差值")
    ap.add_argument("--golden", default="", help="黄金集 manifest；给出则只评其中 SKU")
    args = ap.parse_args()

    batch = Path(args.batch).resolve()
    if not batch.is_dir():
        raise SystemExit(f"找不到批次：{batch}")
    stamp = f"{datetime.now():%Y%m%d_%H%M%S}_{__import__('os').getpid()}"
    work = ROOT / "output" / "_smoke" / f"eval_{stamp}"
    work.mkdir(parents=True, exist_ok=True)

    r = run([sys.executable, ROOT / "qa" / "build_batch_csv.py",
             "--input-root", args.input_root, "--listing-dir", batch, "--out", work / "check.csv",
             "--site", args.site])
    if r.returncode != 0:
        print(r.stdout + r.stderr, file=sys.stderr)
        raise SystemExit(1)

    check_csv = work / "check.csv"
    golden_n = 0
    if args.golden:
        gp = Path(args.golden)
        if not gp.exists():
            raise SystemExit(f"找不到黄金集：{gp}")
        check_csv = work / "check_golden.csv"
        golden_n, total = filter_golden(work / "check.csv", check_csv, gp)
        print(f"黄金集：{golden_n}/{total} 条有本批成稿")

    r = run([sys.executable, ROOT / "qa" / "check_listing.py",
             "--input", check_csv, "--site", args.site, "--out", work,
             "--input-root", args.input_root])
    m = SUMMARY.search(r.stdout)
    if not m:
        print(r.stdout + r.stderr, file=sys.stderr)
        raise SystemExit(1)
    n, hit, p0, p1, p2s, p2c = (int(x) for x in m.groups())

    detail = next(iter(work.glob("*/明细_*.csv")), None)
    rules = []
    if detail:
        with open(detail, encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                if row.get("严重度") in ("P0", "P1"):
                    rules.append(row.get("检查项", ""))
    fail_ids = sorted({x for x in rules if x})

    score = {"pattern": args.pattern, "site": args.site, "batch": str(batch),
             "samples": n, "hit_rows": hit, "P0": p0, "P1": p1,
             "P2_struct": p2s, "P2_conv": p2c,
             "golden": args.golden or "", "golden_samples": golden_n,
             "verdict": "PASS" if p0 == 0 and p1 == 0 else "FAIL",
             "fail_rule_ids": fail_ids,
             "evaluated_at": datetime.now().isoformat(timespec="seconds")}

    out_root = Path(args.out_root)
    out_root.mkdir(parents=True, exist_ok=True)
    slug = args.pattern.replace("/", "_") + ("-golden" if args.golden else "")
    latest = out_root / f"{slug}.json"
    latest.write_text(json.dumps(score, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with open(out_root / "history.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(score, ensure_ascii=False) + "\n")

    print(f"pattern：{args.pattern}　站点：{args.site}　样本：{n} 条")
    print(f"P0={p0}  P1={p1}  P2-结构={p2s}  P2-转化={p2c}  → {score['verdict']}")
    if fail_ids:
        print("失败规则：" + "、".join(fail_ids[:12]))
    print(f"存档：{latest}")

    if args.baseline and Path(args.baseline).exists():
        base = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
        keys = ["P0", "P1", "P2_struct", "P2_conv"]
        delta = "　".join(f"{k} {base.get(k, '-')}→{score[k]}" for k in keys)
        print(f"基线对比：{delta}")
        worse = [k for k in keys if k in base and score[k] > base[k]]
        if worse:
            print("[!] 变差的指标：" + "、".join(worse))

    raise SystemExit(0 if score["verdict"] == "PASS" else 3)


if __name__ == "__main__":
    main()
