# -*- coding: utf-8 -*-
r"""
批次流水线的"薄封装"：一条命令跑完 属性映射 + 校验 + 出表。
**不包含生成**——生成由 Agent 按 skill 规则完成（当前阶段刻意不接模型 API，理由见 README/说明）。

用法：
  python run_batch.py --input-root ..\input\批次0921 --listing-dir ..\output\批次0921 --site MX

步骤：
  1. 属性映射        input.json → 属性映射.xlsx（含冲突与风险）
  2. 汇总校验用 CSV  listing-<id>.txt + input.json → check.csv
  3. 合规校验        check.csv → 报告 md + 明细 csv
  4. 批次结果表      校验结果 + review_notes.json → 批次结果.xlsx
缺少 listing 的商品会跳过 2-4，只出属性表并提示"待生成"。
"""
import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent
# DSH 自带 Python 的位置按当前用户解析，换电脑/换用户名也能找到（不要写死 C:\Users\AUSU）
_HOME = Path(os.environ.get("USERPROFILE") or Path.home())
FALLBACK_PY = str(_HOME / ".dsh" / "dsh-runtimes" / "dsh-primary-runtime" / "dependencies" / "python" / "python.exe")


def ensure_openpyxl():
    """本机系统 Python 没有 openpyxl；自动切到 DSH 自带 Python。"""
    try:
        import openpyxl  # noqa: F401
        return
    except ImportError:
        pass
    if Path(FALLBACK_PY).exists() and Path(sys.executable).resolve() != Path(FALLBACK_PY).resolve():
        print(f"[i] 系统 Python 缺 openpyxl，切换到：{FALLBACK_PY}")
        sys.exit(subprocess.call([FALLBACK_PY, str(Path(__file__).resolve())] + sys.argv[1:]))
    raise SystemExit("需要 openpyxl，且未找到 DSH 自带 Python，请手动安装 openpyxl")


def run(cmd, label):
    print(f"\n=== {label} ===")
    print("$ " + " ".join(str(c) for c in cmd))
    rc = subprocess.call([str(c) for c in cmd])
    if rc != 0:
        print(f"[!] {label} 失败（exit={rc}），继续下一步")
    return rc


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="批次流水线薄封装（映射+校验+出表）")
    ap.add_argument("--input-root", required=True, help="原始商品目录：每个商品一个子目录，含 input.json")
    ap.add_argument("--listing-dir", required=True, help="生成结果的目录：listing-<id>.txt")
    ap.add_argument("--site", default="MX", choices=["MX", "BR"])
    ap.add_argument("--notes", default="", help="可选：review_notes.json，人工待确认备注")
    args = ap.parse_args()

    ensure_openpyxl()

    inroot = Path(args.input_root).resolve()
    ldir = Path(args.listing_dir).resolve()
    ldir.mkdir(parents=True, exist_ok=True)
    batch_tag = ldir.name or datetime.now().strftime("批次%Y%m%d")

    # 0. 输入清点
    ids = []
    for d in sorted(inroot.iterdir()):
        f = d / "input.json"
        if f.exists() and not d.name.startswith("_") and d.name not in ("示例商品", "示例商品001"):
            ids.append(d.name)
    print(f"输入商品 {len(ids)} 个；输出目录：{ldir}")

    # 1. 属性映射
    attr_xlsx = ldir / "属性映射.xlsx"
    run([sys.executable, BASE / "map_attributes.py",
         "--input-root", inroot, "--out", attr_xlsx], "属性映射")

    # 2. 检查 listing 覆盖
    have = [i for i in ids if (ldir / f"listing-{i}.txt").exists()]
    lack = [i for i in ids if i not in have]
    print(f"\n已有 listing：{len(have)} 个；待生成：{len(lack)} 个")
    if lack:
        print("待生成：" + "、".join(lack))

    # 3-4. 校验 + 出表
    if have:
        check_csv = ldir / "check.csv"
        run([sys.executable, BASE / "build_batch_csv.py",
             "--input-root", inroot, "--listing-dir", ldir, "--out", check_csv], "汇总校验用 CSV")
        # 只认「本次」生成的明细：跑之前先记下 qa\报告 里已有的文件。
        # 不能按全目录 mtime 取最新——跑到一半又跑过 demo / 别的批次时会拿错文件。
        before = set(BASE.glob("报告/*/*"))
        run([sys.executable, BASE / "check_listing.py",
             "--input", check_csv, "--site", args.site], "合规校验")
        fresh = [p for p in BASE.glob("报告/*/明细_*.csv") if p not in before]
        if not fresh:
            raise SystemExit("没找到本次校验的明细，check_listing 可能失败了；"
                             "不要拿上一次的旧明细顶替，先看上面的报错")
        newest = sorted(fresh, key=lambda p: p.stat().st_mtime)[-1]
        findings = ldir / "_findings.csv"
        findings.write_bytes(newest.read_bytes())
        print(f"[i] 本次明细：{newest}")
        notes = args.notes or str(ldir / "review_notes.json")
        run([sys.executable, BASE / "make_batch_xlsx.py",
             "--check-csv", check_csv, "--detail-csv", findings,
             "--notes", notes if Path(notes).exists() else "",
             "--out", ldir / "批次结果.xlsx"], "批次结果表")

    print("\n=== 完成 ===")
    for p in sorted(ldir.glob("*")):
        if p.is_file() and p.suffix in (".xlsx", ".csv", ".json"):
            print(f"  {p.name}  ({p.stat().st_size} bytes)")
    if lack:
        print(f"\n下一步：让 Agent 按 skill 生成这 {len(lack)} 个商品的 listing-<id>.txt，然后重跑本命令。")


if __name__ == "__main__":
    main()
