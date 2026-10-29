# -*- coding: utf-8 -*-
r"""清理成稿里的 Markdown 残留与中文全角标点（默认 dry-run）。

对齐 qa\check_listing.py 的两条 P1：
  - `**加粗**` → `加粗`；残留的 `**` 直接删除
  - `：，。（）；！？、` → 半角 `: , . ( ) ; ! ? ,`
  - 含中文字符的整份文件跳过（中文备注不进正文，先人工处理）

为什么需要：TikTok 后台是富文本编辑器，不解析 Markdown，`**` 会原样显示成星号；
旧批次成稿是强调格式，粘进后台就是错的。阶段 1 起由 scripts\render_listing.py 在
生成时保证纯文本，本脚本只用于清洗存量。

用法（仓库根执行）：
  python qa\normalize_listing.py --dir output\批次20261022-v2            # 只看
  python qa\normalize_listing.py --dir output\批次20261022-v2 --apply    # 写盘（先备份）
"""
import argparse
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CJK = re.compile(r"[\u4e00-\u9fff]")
BOLD = re.compile(r"\*\*(.+?)\*\*")
BOLD_LEFT = re.compile(r"\*\*")
FULLWIDTH = re.compile(r"[：，。（）；！？、]")
HALF = str.maketrans({"：": ": ", "，": ", ", "（": "(", "）": ")",
                      "。": ". ", "；": "; ", "！": "! ", "？": "? ", "、": ", "})
# 全角转半角后可能缺空格（如 `tipo:plana`）；西语标点后应有空格
SPACING = re.compile(r"([:;])(?=[A-Za-zÁÉÍÓÚÜÑáéíóúüñ¿¡])")


def clean(text):
    """返回 (清理后文本, 统计)。保持原有换行符不变。"""
    stats = {"md": 0, "punct": 0}

    def bold(m):
        stats["md"] += 1
        return m.group(1)

    out = BOLD.sub(bold, text)
    left = len(BOLD_LEFT.findall(out))
    if left:
        stats["md"] += left
        out = BOLD_LEFT.sub("", out)

    def punct(m):
        stats["punct"] += 1
        return m.group(0).translate(HALF)

    out = FULLWIDTH.sub(punct, out)
    out, n_space = SPACING.subn(r"\1 ", out)
    stats["punct"] += n_space
    return out, stats


def targets(base: Path):
    files = sorted(base.glob("listing-*.txt"))
    for d in sorted(base.iterdir()):
        if d.is_dir() and not d.name.startswith("_"):
            for name in ("标题.txt", "描述.txt"):
                p = d / name
                if p.exists():
                    files.append(p)
    return files


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="清理成稿里的 Markdown / 全角标点（默认 dry-run）")
    ap.add_argument("--dir", required=True, help="批次目录，如 output\\批次20261022-v2")
    ap.add_argument("--apply", action="store_true", help="真正写盘；不加只打印清单")
    ap.add_argument("--backup-root", default=str(ROOT / "output" / "_backup"),
                    help="备份根目录（默认 output\\_backup）")
    args = ap.parse_args()

    base = Path(args.dir).resolve()
    if not base.is_dir():
        raise SystemExit(f"找不到目录：{base}")

    files = targets(base)
    if not files:
        raise SystemExit(f"{base} 下没有 listing-*.txt / 标题.txt / 描述.txt")

    changed, skipped = [], []
    backup = Path(args.backup_root) / f"normalize_{datetime.now():%Y%m%d_%H%M%S}"
    for p in files:
        with open(p, encoding="utf-8-sig", newline="") as f:
            text = f.read()
        if CJK.search(text):
            skipped.append((p, "含中文字符"))
            continue
        new, st = clean(text)
        if new == text:
            continue
        changed.append((p, st))
        if args.apply:
            rel = p.relative_to(base)
            dst = backup / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, dst)
            with open(p, "w", encoding="utf-8", newline="") as f:
                f.write(new)

    for p, st in changed:
        print(f"  [改] {p.relative_to(base)}  **:{st['md']}  全角:{st['punct']}")
    for p, why in skipped:
        print(f"  [跳] {p.relative_to(base)}  {why}")
    print(f"\n扫描 {len(files)} 个文件；需改 {len(changed)} 个；跳过 {len(skipped)} 个")
    if not changed:
        print("已是纯文本，无需处理。")
    elif args.apply:
        print(f"已写盘；备份：{backup}")
    else:
        print("（dry-run，未写盘；确认后加 --apply）")


if __name__ == "__main__":
    main()
