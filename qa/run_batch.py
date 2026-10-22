# -*- coding: utf-8 -*-
r"""
批次流水线的"薄封装"：一条命令跑完 属性映射 + 生成前门禁 + 校验 + 出表。

用法：
  python run_batch.py --input-root ..\input --listing-dir ..\output\批次0921 --site MX
  python run_batch.py --input-root ..\input --listing-dir ..\output\批次0921 --site MX --allow-unverified

步骤：
  0. 生成前门禁      遍历 listing-<SKU>.txt，读 input/<SKU>/facts.json：
                     facts 缺失 / 读取失败 / status != "verified" 的 SKU 不参与校验，
                     逐个打印原因并计数。默认最终 exit 3；--allow-unverified 打印警告后放行。
  1. 属性映射        input.json → 属性映射.xlsx（含冲突与风险）
  2. 汇总校验用 CSV  listing-<id>.txt + input.json → check.csv（全部 rows 进批次结果表）
  3. 合规校验        仅 verified 行 → check_listing --fail-on-p0：报告 md + 明细 csv
                     每次运行使用唯一目录 output\_smoke\run_batch_<时间>_<随机>，不再猜"本次明细"
  4. 批次结果表      校验结果 + review_notes.json + 被拒原因 → 批次结果.xlsx
缺少 listing 的商品跳过 2-4，只出属性表并提示"待生成"。

退出码：
  0   全部通过（--allow-unverified 放行且 listing 无 P0）
  1   运行期错误（子进程失败 / IO / 报告文件缺失）
  2   参数错误（argparse）
  3   门禁拦截：有被拒 SKU（默认，除非 --allow-unverified），或 check_listing 出现 P0
任意子步骤返回非 0 时立即中止，不执行后续步骤（不再"失败继续下一步"）。
"""
import argparse
import csv
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

# 这些 SKU 目录不算商品（与 build_facts / check_facts 保持一致）
SKIP_DIRS = {"示例商品", "示例商品001"}


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
    """跑一个子步骤；非 0 立即中止（退出码原样透传），绝不继续下一步。"""
    print(f"\n=== {label} ===")
    print("$ " + " ".join(str(c) for c in cmd))
    rc = subprocess.call([str(c) for c in cmd])
    if rc != 0:
        print(f"\n[X] {label} 失败（exit={rc}），已中止；后续步骤未执行。", file=sys.stderr)
        sys.exit(rc)
    return rc


def make_scan_dir(ldir):
    """本次校验独有目录：output\\_smoke\\run_batch_<时间戳>_<pid>；不可写时退回 listing-dir 下。

    不用 tempfile.mkdtemp()：本机沙箱下 mkdtemp 建的 0700 目录里无法再创建文件（PermissionError），
    所以统一用普通 mkdir 建唯一目录。
    """
    stamp = f"{datetime.now():%Y%m%d_%H%M%S_%f}_{os.getpid()}"
    last = None
    for p in (BASE.parent / "output" / "_smoke" / f"run_batch_{stamp}",
              ldir / f"_scan_{stamp}"):
        try:
            p.mkdir(parents=True, exist_ok=False)
            return p
        except OSError as e:  # noqa: PERF203
            last = e
    raise SystemExit(f"无法创建本次校验目录（output/_smoke 与 listing-dir 都不可写）：{last}")


def read_facts_status(inroot, pid):
    """返回 (status, error)。facts.json 缺失/读不了时 status=None。"""
    p = inroot / pid / "facts.json"
    if not p.exists():
        return None, None
    try:
        data = json.loads(p.read_text(encoding="utf-8-sig"))
    except Exception as e:  # noqa: BLE001
        return None, f"facts.json 读取失败：{e}"
    return str(data.get("status") or "draft"), None


def filter_check_csv(src, dst, keep_ids):
    """从 build_batch_csv 的 check.csv 里只留 verified SKU，写一份给 check_listing。"""
    with open(src, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    kept = [r for r in rows if r.get("id") in keep_ids]
    dst.parent.mkdir(parents=True, exist_ok=True)
    with open(dst, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else ["id", "标题", "描述", "核心词", "类目", "原价MXN", "图片目录"])
        w.writeheader()
        w.writerows(kept)
    return kept


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="批次流水线薄封装（门禁+映射+校验+出表）")
    ap.add_argument("--input-root", required=True, help="原始商品目录：每个商品一个子目录，含 input.json")
    ap.add_argument("--listing-dir", required=True, help="生成结果的目录：listing-<id>.txt")
    ap.add_argument("--site", default="MX", choices=["MX", "BR"])
    ap.add_argument("--notes", default="", help="可选：review_notes.json，人工待确认备注")
    ap.add_argument("--allow-unverified", action="store_true",
                    help="放行未 verified/缺 facts 的 SKU（打印警告）；默认拒绝并 exit 3，"
                         "放行后若 listing 仍有 P0 仍 exit 3")
    args = ap.parse_args()

    ensure_openpyxl()

    inroot = Path(args.input_root).resolve()
    ldir = Path(args.listing_dir).resolve()
    ldir.mkdir(parents=True, exist_ok=True)

    # 0. 输入清点
    ids = []
    for d in sorted(inroot.iterdir()):
        f = d / "input.json"
        if f.exists() and not d.name.startswith("_") and d.name not in SKIP_DIRS:
            ids.append(d.name)
    print(f"输入商品 {len(ids)} 个；输出目录：{ldir}")

    # 1. 属性映射（失败立即中止）
    attr_xlsx = ldir / "属性映射.xlsx"
    run([sys.executable, BASE / "map_attributes.py",
         "--input-root", inroot, "--out", attr_xlsx], "属性映射")

    # 2. 检查 listing 覆盖 + 生成前门禁
    have = [i for i in ids if (ldir / f"listing-{i}.txt").exists()]
    lack = [i for i in ids if i not in have]
    print(f"\n已有 listing：{len(have)} 个；待生成：{len(lack)} 个")
    if lack:
        print("待生成：" + "、".join(lack))

    accepted, rejected = [], []
    for pid in have:
        status, err = read_facts_status(inroot, pid)
        if err:
            rejected.append((pid, err))
        elif status is None:
            rejected.append((pid, "facts.json 缺失（未建事实卡）"))
        elif status != "verified":
            rejected.append((pid, f"facts.status={status}（未核验/隔离/阻断）"))
        else:
            accepted.append(pid)

    print(f"\n生成前门禁：通过 {len(accepted)} 个；拒绝 {len(rejected)} 个")
    for pid, why in rejected:
        print(f"  [拒] {pid:<12} {why}")
    if rejected:
        if args.allow_unverified:
            print("[!] --allow-unverified：以上 SKU 仍会参与本次校验，仅用于调试；正式批次不要用。")
        else:
            print("[!] 默认拒绝：被拒 SKU 不参与校验；本次最终退出码 3（加 --allow-unverified 可放行）。")

    checked = have if args.allow_unverified else accepted
    if checked:
        scan_dir = make_scan_dir(ldir)
        print(f"[i] 本次校验输出目录：{scan_dir}")
        check_csv = ldir / "check.csv"
        run([sys.executable, BASE / "build_batch_csv.py",
             "--input-root", inroot, "--listing-dir", ldir, "--out", check_csv], "汇总校验用 CSV")

        verified_csv = scan_dir / "check_verified.csv"
        kept = filter_check_csv(check_csv, verified_csv, set(checked))
        if not kept:
            print("[!] 过滤后没有可校验的行（listing 与 input.json 对不上），跳过校验与出表。")
        else:
            run([sys.executable, BASE / "check_listing.py",
                 "--input", verified_csv, "--site", args.site, "--out", scan_dir, "--fail-on-p0"], "合规校验")
            details = sorted(scan_dir.glob("*/明细_*.csv"))
            if len(details) != 1:
                print(f"[X] 期望 1 份明细，实际 {len(details)} 份：{details}", file=sys.stderr)
                sys.exit(1)
            findings = ldir / "_findings.csv"
            findings.write_bytes(details[0].read_bytes())
            print(f"[i] 本次明细：{details[0]}")

            notes_path = args.notes or str(ldir / "review_notes.json")
            notes = {}
            if notes_path and Path(notes_path).exists():
                try:
                    notes = json.loads(Path(notes_path).read_text(encoding="utf-8"))
                except Exception as e:  # noqa: BLE001
                    print(f"[!] 读不了 notes（{notes_path}）：{e}，忽略", file=sys.stderr)
                    notes = {}
            for pid, why in rejected:
                old = notes.get(pid) or ""
                notes[pid] = (old + "；" if old else "") + f"未参与校验：{why}"
            merged_notes = scan_dir / "review_notes.merged.json"
            merged_notes.write_text(json.dumps(notes, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            run([sys.executable, BASE / "make_batch_xlsx.py",
                 "--check-csv", check_csv, "--detail-csv", findings,
                 "--notes", merged_notes, "--out", ldir / "批次结果.xlsx"], "批次结果表")
    elif rejected:
        print("[i] 没有可校验的 listing（全部被门禁拒绝），跳过校验与出表。")
    else:
        print("[i] 没有 listing，只出属性表。")

    print("\n=== 完成 ===")
    for p in sorted(ldir.glob("*")):
        if p.is_file() and p.suffix in (".xlsx", ".csv", ".json"):
            print(f"  {p.name}  ({p.stat().st_size} bytes)")
    if lack:
        print(f"\n下一步：让 Agent 按 skill 生成这 {len(lack)} 个商品的 listing-<id>.txt，然后重跑本命令。")
    if rejected and not args.allow_unverified:
        print(f"\n[门禁] {len(rejected)} 个 SKU 未通过生成前门禁，本次退出码 3："
              f"{'、'.join(pid for pid, _ in rejected)}")
        raise SystemExit(3)


if __name__ == "__main__":
    main()
