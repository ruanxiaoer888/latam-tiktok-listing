# -*- coding: utf-8 -*-
r"""批次成稿 → 交付文件夹（README + 每个 SKU 的 上架信息.md / 图片\）。

成稿两种布局都认：`<batch>\<SKU>\标题.txt` + `描述.txt`（推荐），或旧的扁平 `listing-<SKU>.txt`
（遇到扁平件会先归位成 SKU 文件夹，原件保留为 `原始成稿.txt`，不丢内容）。
本脚本补三样：`上架信息.md`、`图片\`（从 input\<SKU>\img 复制）、批次 `README.md`。

用法：
  python qa\make_upload_pack.py --batch output\批次20261023
  python qa\make_upload_pack.py --batch output\批次20261023 --site BR
  python qa\make_upload_pack.py --batch output\批次20261023 --scan-dir output\_smoke\run_batch_xxx

机器文件（校验明细）在 output\_smoke\run_batch_*\ 里，本脚本不往批次目录写任何机器文件。
"""
import argparse
import csv
import hashlib
import json
import shutil
import sys
from pathlib import Path

from _limits import title_ok, title_range

ROOT = Path(__file__).resolve().parent.parent
LANG = {"MX": "墨西哥 MX / es-MX", "BR": "巴西 BR / pt-BR"}
CUR = {"MX": "MXN", "BR": "BRL"}


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def load_json(p: Path, default=None):
    try:
        return json.loads(p.read_text(encoding="utf-8-sig"))
    except Exception:
        return default


def parse_flat(path: Path):
    """扁平 listing-<SKU>.txt：第 1 个非空行是标题，其后是描述。"""
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    while lines and not lines[0].strip():
        lines.pop(0)
    if not lines:
        return None
    title = lines[0].strip()
    rest = lines[1:]
    while rest and not rest[0].strip():
        rest.pop(0)
    return title, "\n".join(rest).strip()


def ensure_layout(batch: Path):
    """把扁平成稿归位成 <SKU>\\标题.txt + 描述.txt，原件保留为 原始成稿.txt。"""
    moved = []
    for p in sorted(batch.glob("listing-*.txt")):
        sku = p.stem[len("listing-"):]
        out = batch / sku
        if (out / "标题.txt").exists() and (out / "描述.txt").exists():
            print(f"[!] {sku} 已有 SKU 文件夹，跳过扁平件（{p.name} 未移动）")
            continue
        parsed = parse_flat(p)
        if not parsed:
            print(f"[!] {p.name} 是空文件，跳过")
            continue
        title, desc = parsed
        out.mkdir(exist_ok=True)
        (out / "标题.txt").write_text(title + "\n", encoding="utf-8")
        (out / "描述.txt").write_text(desc + "\n", encoding="utf-8")
        shutil.move(str(p), str(out / "原始成稿.txt"))
        moved.append(sku)
    return moved


def list_images(img_dir: Path):
    if not img_dir.is_dir():
        return []
    return sorted(p for p in img_dir.iterdir()
                  if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"))


def facts_notes(facts):
    """事实卡里的警告 + 人工覆盖来源（§5 备注，不再单独维护 review_notes.json）。"""
    warnings = (facts.get("gates") or {}).get("warnings") or []
    parts = [w for w in warnings if "facts 已按同一来源重建" not in w]
    note = (facts.get("_meta") or {}).get("overrides_note") or ""
    return parts, note


def extra_fields(facts):
    """后台还要补/要填的字段（全部来自事实卡，缺就说缺）。"""
    size = facts.get("size") or {}
    has_size = any(size.get(k) for k in ("length_cm", "width_cm", "height_cm", "diameter_cm")) or size.get("raw")
    weight = facts.get("weight_kg")
    color = (facts.get("raw_attributes") or {}).get("Color")
    cert = (facts.get("certification") or {}).get("status")
    out = [
        "尺寸：已登记" if has_size else "尺寸：缺（需量实物）",
        f"整机重量：{weight:g} kg".replace(".0 kg", " kg") if weight else "整机重量：缺（需称重）",
        f"颜色：{color}" if color else "颜色：属性没有，按实物填",
    ]
    if cert == "missing":
        out.append("认证：NOM-003 / UN38.3 台账未登记，上架会卡")
    elif cert == "not_applicable":
        out.append("认证：不适用")
    else:
        out.append(f"认证：{cert}")
    return out


def count_findings(path: Path):
    n = {"P0": 0, "P1": 0, "结构": 0, "转化": 0}
    with open(path, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            sev, cat = r.get("严重度", ""), r.get("类别", "")
            if sev in ("P0", "P1"):
                n[sev] += 1
            elif sev == "P2":
                n["转化" if cat == "转化" else "结构"] += 1
    return n


def find_counts(scan_dir, skus):
    """找一份覆盖本批全部 SKU 的校验明细，算 P0/P1/P2 数量。"""
    if scan_dir:
        cands = list(Path(scan_dir).glob("*/明细_*.csv")) or list(Path(scan_dir).glob("明细_*.csv"))
    else:
        root = ROOT / "output" / "_smoke"
        cands = []
        if root.is_dir():
            for d in root.iterdir():
                if d.is_dir():
                    cands += list(d.glob("*/明细_*.csv"))
    want = set(skus)
    for p in sorted(cands, key=lambda x: x.stat().st_mtime, reverse=True):
        ids = set()
        with open(p, encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                ids.add(r.get("商品ID"))
        if want <= ids:
            return count_findings(p)
    return None


def write_sku_info(sku, title, desc, facts, img_count, out_dir, site):
    lo, hi = title_range(site, facts.get("category", ""))
    price = ((facts.get("site_profiles") or {}).get(site) or {}).get("price")
    lines = [
        f"# {sku} · TikTok Shop {LANG.get(site, site)} 上架信息",
        "",
        "| 项 | 值 |",
        "|---|---|",
        f"| 站点 / 语言 | {LANG.get(site, site)} |",
        f"| 类目 | {facts.get('category', '')} |",
        f"| 品牌 | {(facts.get('identity') or {}).get('brand', '')} |",
        f"| 型号 | {(facts.get('identity') or {}).get('model', '')} |",
        (f"| 价格（后台填） | {price:.2f} {CUR.get(site, '')} |" if price else "| 价格（后台填） | 【待确认】 |"),
        f"| 图片 | {img_count} 张（图片/，01 是主图） |",
        "",
        "## 1. 标题",
        "",
        "```text",
        title,
        "```",
        "",
        f"字符数：{len(title)}（建议 {lo}–{hi}）",
        "",
        "## 2. 描述（整段复制）",
        "",
        "> 后台不解析 Markdown，所以正文里没有 `**`。粘进后台后，把每条 ⭐ 后面、冒号前的短语选中手动加粗。",
        "",
        "```text",
        desc,
        "```",
        "",
        "## 3. 图片（按文件名顺序上传）",
        "",
    ]
    if img_count:
        lines.append("- 按 `图片` 文件夹里的文件名顺序上传，01 是主图")
    else:
        lines.append("- 【缺图片】input 目录下没有 img\\")
    lines += ["", "## 4. 后台还要补的字段", ""]
    lines += [f"- {x}" for x in extra_fields(facts)]
    lines += ["", "## 5. 备注 / 待确认", ""]
    warnings, note = facts_notes(facts)
    lines += [f"- {x}" for x in warnings] or ["- 无"]
    if note:
        lines += ["", f"来源：{note}"]
    lines += ["", "> 事实纪律：正文不写价格、不写瓦数、不写认证编号；包装按事实卡。", ""]
    (out_dir / "上架信息.md").write_text("\n".join(lines), encoding="utf-8")


def write_readme(batch, rows, counts, site):
    lines = [
        f"# {batch.name} · 上架说明",
        "",
        "> **要上架，只看下面几个 SKU 文件夹**（每个里面是标题 / 描述 / 图片 / 上架信息）。",
        "> 批次目录里没有别的文件——校验明细在 `output\\_smoke\\`，不用看。",
        "",
        "## 怎么用（3 步）",
        "",
        "1. 打开某个 SKU 文件夹，打开 `上架信息.md`。",
        "2. 按文件里的 **§1 标题** 复制到后台商品标题；按 **§2 描述** 整段复制到详情描述（后台不认 Markdown，粘完后把每条 ⭐ 冒号前的短语选中手动加粗）。",
        "3. 打开 `图片` 文件夹，按文件名顺序（01 是主图）上传。",
        "",
        "## 本期 SKU",
        "",
        "| SKU | 标题 | 价格 | 图片 | 文件夹 |",
        "|---|---|---|---|---|",
    ]
    cur = CUR.get(site, "")
    for sku, title, price, n in rows:
        lines.append(f"| {sku} | {title.replace('|', chr(92) + '|')} | {price:.2f} {cur} | {n} 张 | `{sku}` |")
    lines += [
        "",
        "## 目录里哪些是你用的",
        "",
        "| 文件 / 文件夹 | 给谁 | 说明 |",
        "|---|---|---|",
        "| " + " / ".join(f"`{r[0]}`" for r in rows) + " | **你** | 标题 / 描述 / 图片 / 上架信息 |",
        "| `README.md` | **你** | 本文件 |",
    ]
    if counts:
        lines += [
            "",
            "## 批次校验",
            "",
            f"P0={counts['P0']}，P1={counts['P1']}，P2-转化={counts['转化']}，P2-结构={counts['结构']}",
            "",
            "P0 / P1 不为 0 时不要上架，先改稿。",
        ]
    lines += [
        "",
        "## 上架前必须知道",
        "",
        "- 每条的待确认项见该 SKU 的 `上架信息.md` 第 4、5 节。",
        "- 首图有没有文字/水印/边框，机器不判，上架前人工看一眼。",
        "- 认证未登记时后台认证卡口会拦。",
        "",
        "## 其他",
        "",
        "- 原始素材在 `input\\<SKU>\\`；裁图前的原件在 `output\\_backup\\`。",
        "- `图片` 是副本，方便一次上传；要重出就重跑 `qa\\make_upload_pack.py`。",
        "",
    ]
    (batch / "README.md").write_text("\n".join(lines), encoding="utf-8")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="成稿 → SKU 交付文件夹（上架信息/图片/README）")
    ap.add_argument("--batch", required=True, help="批次目录，如 output\\批次20261023")
    ap.add_argument("--site", default="MX", choices=["MX", "BR"])
    ap.add_argument("--input-root", default=str(ROOT / "input"))
    ap.add_argument("--scan-dir", default="", help="可选：run_batch 的 _smoke 目录（算 P0/P1 数量）")
    args = ap.parse_args()

    batch = Path(args.batch).resolve()
    inroot = Path(args.input_root).resolve()
    if not batch.is_dir():
        raise SystemExit(f"找不到批次目录：{batch}")

    moved = ensure_layout(batch)
    if moved:
        print(f"[i] 已把 {len(moved)} 份扁平成稿归位成 SKU 文件夹（原件保留为 原始成稿.txt）")

    skus = sorted(d.name for d in batch.iterdir()
                  if d.is_dir() and not d.name.startswith("_")
                  and (d / "标题.txt").exists() and (d / "描述.txt").exists())
    if not skus:
        raise SystemExit(f"{batch} 下没有成稿：需要 <SKU>\\标题.txt + 描述.txt，或扁平 listing-<SKU>.txt")

    rows = []
    for sku in skus:
        facts = load_json(inroot / sku / "facts.json")
        if facts is None:
            print(f"[!] {sku} 没有 facts.json，跳过")
            continue
        out_dir = batch / sku
        title = (out_dir / "标题.txt").read_text(encoding="utf-8").strip().splitlines()[0]
        desc = (out_dir / "描述.txt").read_text(encoding="utf-8").strip()

        img_out = out_dir / "图片"
        if img_out.exists():
            shutil.rmtree(img_out)
        img_out.mkdir()
        copied = []
        for p in list_images(inroot / sku / "img"):
            dst = img_out / p.name
            shutil.copy2(p, dst)
            if sha(p) != sha(dst):
                raise SystemExit(f"图片复制校验失败：{p}")
            copied.append(p.name)

        write_sku_info(sku, title, desc, facts, len(copied), out_dir, args.site)
        # 上架信息.md 已包含标题+描述全文；删除中间 txt，交付目录只留 上架信息.md + 图片\
        for stale in ("标题.txt", "描述.txt"):
            (out_dir / stale).unlink(missing_ok=True)
        price = ((facts.get("site_profiles") or {}).get(args.site) or {}).get("price") or 0
        rows.append((sku, title, price, len(copied)))
        flag = "OK" if title_ok(args.site, title, facts.get("category", "")) else "!!"
        print(f"  [{flag}] {sku}: {len(copied)} 张图, 标题 {len(title)} 字符")

    counts = find_counts(args.scan_dir or None, skus)
    write_readme(batch, rows, counts, args.site)
    print(f"\n批次目录：{batch}")
    print("  根目录只有 README.md + SKU 文件夹；机器文件在 output\\_smoke\\")


if __name__ == "__main__":
    main()
