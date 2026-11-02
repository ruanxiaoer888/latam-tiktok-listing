# -*- coding: utf-8 -*-
r"""
批次流水线的"薄封装"：一条命令跑完 属性映射 + 生成前门禁 + 校验 + 出表。

用法：
  python run_batch.py --input-root ..\input --listing-dir ..\output\批次0921 --site MX

listings 的三种布局都认（先扁平、再 SKU 文件夹、再上架信息.md）：
  <batch>\listing-<SKU>.txt                      旧布局
  <batch>\<SKU>\标题.txt + 描述.txt              中间布局
  <batch>\<SKU>\上架信息.md                      新布局（推荐，一个文件搞定）

机器文件去哪：**全部写进本次 output\_smoke\run_batch_<时间戳>\_<pid>\**，
批次目录一个机器文件都不落（批次根只留 README + SKU 文件夹）。

步骤：
  0. 生成前门禁      遍历<batch>下已生成的 SKU，读 input/<SKU>/facts.json：
                    facts 缺失 / 读取失败 / status != "verified" 的 SKU 不参与校验，逐个打印原因并计数。
                    默认最终 exit 3；--allow-unverified 打印警告后放行。
  1. 属性映射        input.json → 属性映射.xlsx（写进 _smoke 目录）
  2. 汇总校验用 CSV  listing + input.json → check.csv（写进 _smoke 目录）
  3. 合规校验        仅 verified 行 → check_listing --fail-on-p1：P0/P1 任一 >0 即 exit 3（写进 _smoke）
  4. 事实一致性      check_consistency --strict：文案与 facts 矛盾（供电方向/瓦数/容量/认证）P0 即 exit 3
  5. 批次结果表      校验结果 + 事实卡警告 → 批次结果.xlsx（写进 _smoke）

退出码：
  0   全部通过（--allow-unverified 放行且 listing 无 P0/P1）
  1   运行期错误（子进程失败 / IO / 报告文件缺失）
  2   参数错误（argparse）
  3   门禁拦截：有被拒 SKU（默认，除非 --allow-unverified），或 check_listing 出现 P0/P1
"""
import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent
ROOT = BASE.parent
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
    """本次校验独有目录：output\\_smoke\\run_batch_<时间戳>_<pid>；不可写时退回 batch 下的临时目录。"""
    stamp = f"{datetime.now():%Y%m%d_%H%M%S_%f}_{os.getpid()}"
    last = None
    for p in (ROOT / "output" / "_smoke" / f"run_batch_{stamp}",
              ldir / f"_scan_{stamp}"):
        try:
            p.mkdir(parents=True, exist_ok=False)
            return p
        except OSError as e:  # noqa: PERF203
            last = e
    raise SystemExit(f"无法创建本次校验目录（output/_smoke 与 batch 都不可写）：{last}")


def read_facts(inroot, pid):
    """返回 (facts, error)。facts.json 缺失/读不了时 facts=None。"""
    p = inroot / pid / "facts.json"
    if not p.exists():
        return None, None
    try:
        return json.loads(p.read_text(encoding="utf-8-sig")), None
    except Exception as e:  # noqa: BLE001
        return None, f"facts.json 读取失败：{e}"


def find_listing(ldir, pid):
    """扁平 listing-<SKU>.txt 或 <SKU>\\标题.txt 或 <SKU>\\上架信息.md，三种布局都认。"""
    flat = ldir / f"listing-{pid}.txt"
    if flat.exists():
        return flat
    d = ldir / pid
    if (d / "标题.txt").exists() and (d / "描述.txt").exists():
        return d / "标题.txt"
    md = d / "上架信息.md"
    if md.exists():
        return md
    return None


def facts_note(facts):
    """事实卡里的警告 + 人工覆盖说明 → 一行备注（给批次结果表用）。"""
    warnings = (facts.get("gates") or {}).get("warnings") or []
    parts = [w for w in warnings if "facts 已按同一来源重建" not in w]
    note = (facts.get("_meta") or {}).get("overrides_note") or ""
    if note:
        parts.append(note)
    return "；".join(parts)


def filter_check_csv(src, dst, keep_ids):
    """从 build_batch_csv 的 check.csv 里只留 verified SKU，写一份给 check_listing。"""
    import csv as _csv
    with open(src, encoding="utf-8-sig", newline="") as f:
        rows = list(_csv.DictReader(f))
    kept = [r for r in rows if r.get("id") in keep_ids]
    dst.parent.mkdir(parents=True, exist_ok=True)
    with open(dst, "w", encoding="utf-8-sig", newline="") as f:
        w = _csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else ["id", "标题", "描述", "核心词", "类目", "原价MXN", "图片目录"])
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
    ap.add_argument("--listing-dir", required=True, help="批次目录：listing-<id>.txt 或 <id>\\标题.txt")
    ap.add_argument("--site", default="MX", choices=["MX", "BR"])
    ap.add_argument("--notes", default="", help="可选：额外备注 JSON（默认用事实卡警告）")
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
    print(f"输入商品 {len(ids)} 个；批次目录：{ldir}")

    have = [i for i in ids if find_listing(ldir, i)]
    lack = [i for i in ids if i not in have]
    print(f"\n已生成的 SKU：{len(have)} 个；待生成：{len(lack)} 个")
    if lack:
        print("待生成：" + "、".join(lack))

    accepted, rejected = [], []
    for pid in have:
        facts, err = read_facts(inroot, pid)
        if err:
            rejected.append((pid, err))
        elif facts is None:
            rejected.append((pid, "facts.json 缺失（未建事实卡）"))
        elif facts.get("status") != "verified":
            rejected.append((pid, f"facts.status={facts.get('status')}（未核验/隔离/阻断）"))
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
        print(f"\n[i] 本次机器文件全部写到：{scan_dir}")

        attr_xlsx = scan_dir / "属性映射.xlsx"
        run([sys.executable, BASE / "map_attributes.py",
             "--input-root", inroot, "--out", attr_xlsx], "属性映射")

        check_csv = scan_dir / "check.csv"
        run([sys.executable, BASE / "build_batch_csv.py",
             "--input-root", inroot, "--listing-dir", ldir, "--out", check_csv,
             "--site", args.site], "汇总校验用 CSV")

        verified_csv = scan_dir / "check_verified.csv"
        kept = filter_check_csv(check_csv, verified_csv, set(checked))
        if not kept:
            print("[!] 过滤后没有可校验的行（清单与 input.json 对不上），跳过校验与出表。")
        else:
            run([sys.executable, BASE / "check_listing.py",
                 "--input", verified_csv, "--site", args.site, "--out", scan_dir,
                 "--fail-on-p1", "--input-root", inroot], "合规校验")
            details = sorted(scan_dir.glob("*/明细_*.csv"))
            if len(details) != 1:
                print(f"[X] 期望 1 份明细，实际 {len(details)} 份：{details}", file=sys.stderr)
                sys.exit(1)
            print(f"[i] 本次明细：{details[0]}")

            run([sys.executable, BASE / "check_consistency.py",
                 "--check-csv", verified_csv, "--input-root", inroot,
                 "--out", scan_dir, "--strict"], "事实一致性校验")

            notes = {}
            extra = {}
            if args.notes and Path(args.notes).exists():
                try:
                    extra = json.loads(Path(args.notes).read_text(encoding="utf-8"))
                except Exception as e:  # noqa: BLE001
                    print(f"[!] 读不了 notes（{args.notes}）：{e}，忽略", file=sys.stderr)
            for pid in checked:
                facts, _ = read_facts(inroot, pid)
                parts = [facts_note(facts)] if facts else []
                if extra.get(pid):
                    parts.append(extra[pid])
                notes[pid] = "；".join(p for p in parts if p)
            for pid, why in rejected:
                old = notes.get(pid) or ""
                notes[pid] = (old + "；" if old else "") + f"未参与校验：{why}"
            merged_notes = scan_dir / "review_notes.merged.json"
            merged_notes.write_text(json.dumps(notes, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

            batch_xlsx = scan_dir / "批次结果.xlsx"
            run([sys.executable, BASE / "make_batch_xlsx.py",
                 "--check-csv", check_csv, "--detail-csv", details[0],
                 "--notes", merged_notes, "--out", batch_xlsx], "批次结果表")
    elif rejected:
        print("[i] 没有可校验的清单（全部被门禁拒绝），跳过校验与出表。")
    else:
        print("[i] 批次目录里还没有任何 SKU，先让 Agent 生成成稿（上架信息.md）。")

    print("\n=== 完成 ===")
    if checked:
        print(f"  批次目录（只放交付文件）：{ldir}")
        print(f"  机器文件（不用看）：{scan_dir}")
    if lack:
        print(f"\n下一步：让 Agent 生成这 {len(lack)} 个 SKU 的 <批次>\\<SKU>\\上架信息.md + 图片\\，然后重跑本命令。")
    if rejected and not args.allow_unverified:
        print(f"\n[门禁] {len(rejected)} 个 SKU 未通过生成前门禁，本次退出码 3："
              f"{'、'.join(pid for pid, _ in rejected)}")
        raise SystemExit(3)


if __name__ == "__main__":
    main()
