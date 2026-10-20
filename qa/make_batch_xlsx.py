# -*- coding: utf-8 -*-
r"""
把一批生成的 listing + 校验结果 + 人工备注合成一个 xlsx，供直接排期修改/上架。

用法：
  python make_batch_xlsx.py --check-csv ..\output\批次20261020\check.csv ^
      --detail-csv ..\output\批次20261020\_findings.csv ^
      --notes ..\output\批次20261020\review_notes.json ^
      --out ..\output\批次20261020\批次结果.xlsx
"""
import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path


def read_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Font, PatternFill
        from openpyxl.utils import get_column_letter
    except ImportError:
        raise SystemExit("需要 openpyxl：请用带 openpyxl 的 Python 运行")

    ap = argparse.ArgumentParser()
    ap.add_argument("--check-csv", required=True)
    ap.add_argument("--detail-csv", required=True)
    ap.add_argument("--notes", default="")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    rows = read_csv(args.check_csv)
    details = read_csv(args.detail_csv)
    notes = {}
    if args.notes and Path(args.notes).exists():
        notes = json.loads(Path(args.notes).read_text(encoding="utf-8"))

    sev = defaultdict(Counter)
    issues = defaultdict(list)
    for d in details:
        pid = d.get("商品ID", "").strip()
        s = d.get("严重度", "").strip()
        sev[pid][s] += 1
        if s in ("P0", "P1", "P2"):
            issues[pid].append(f"[{s}] {d.get('说明','')} → {d.get('建议','')}")

    wb = Workbook()
    ws = wb.active
    ws.title = "批次结果"
    headers = ["序号", "商品ID", "类目", "原价MXN", "标题", "描述", "P0", "P1", "P2",
               "问题清单", "待确认/备注", "图片目录"]
    ws.append(headers)
    head_fill = PatternFill("solid", fgColor="1F4E79")
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = head_fill
        c.alignment = Alignment(horizontal="center", vertical="center")

    for i, r in enumerate(rows, 1):
        pid = r["id"]
        ws.append([
            i, pid, r.get("类目", ""), r.get("原价MXN", ""), r.get("标题", ""),
            r.get("描述", ""),
            sev[pid]["P0"], sev[pid]["P1"], sev[pid]["P2"],
            "\n".join(issues.get(pid, [])),
            notes.get(pid, ""),
            r.get("图片目录", ""),
        ])

    widths = {"A": 6, "B": 14, "C": 10, "D": 12, "E": 45, "F": 70,
              "G": 6, "H": 6, "I": 6, "J": 45, "K": 50, "L": 40}
    for col, w in widths.items():
        ws.column_dimensions[col].width = w
    for row in ws.iter_rows(min_row=2):
        for c in row:
            c.alignment = Alignment(wrap_text=True, vertical="top")
        # P0/P1 标红
        for col in (7, 8):
            if row[col - 1].value:
                row[col - 1].fill = PatternFill("solid", fgColor="FFC7CE")
    ws.freeze_panes = "C2"

    # 说明页
    ws2 = wb.create_sheet("说明")
    ws2.append(["本文件是什么", "TikTok Shop MX Listing 批次产出 + 合规校验结果"])
    ws2.append(["生成规则", "latam-tiktok-listing 技能：骨架 + rules-mx + 类目包"])
    ws2.append(["校验口径", "P0 上架必失败 / P1 违规风险 / P2 影响转化"])
    ws2.append(["待确认", "见「待确认/备注」列；多为源数据自相矛盾处，需回工厂或后台核对"])
    ws2.append(["未做", "未做自动上传；认证编号、保修条款需人工填后台"])
    ws2.column_dimensions["A"].width = 14
    ws2.column_dimensions["B"].width = 90
    for row in ws2.iter_rows():
        for c in row:
            c.alignment = Alignment(wrap_text=True, vertical="top")

    out = Path(args.out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out)
    print(f"已写出 {len(rows)} 行 -> {out}")
    total = Counter()
    for pid in sev:
        total.update(sev[pid])
    print(f"合计：P0={total['P0']} P1={total['P1']} P2={total['P2']}")


if __name__ == "__main__":
    main()
