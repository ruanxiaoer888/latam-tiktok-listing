#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TikTok 图片合规检查器 v1.0

定位：上架前的「图片卡口」。现有流程只判「图片能不能打开」（pack_and_verify），
这里按 TikTok Shop 主图/详情图规则逐张查：数量、尺寸、比例、格式/损坏、重复、首图白底。

不做的事：不改 input/ 里的图、不压缩、不做文字/水印自动判定（只在报告里固定输出人工核对项）。

依赖：Pillow（PIL）。系统 python 默认没有 Pillow，脚本会检测并明确报错退出 2，
不静默跳过。本机请用 DSH 自带 python（含 Pillow 12.3）：
  C:\\Users\\Michael\\.dsh\\dsh-runtimes\\dsh-primary-runtime\\dependencies\\python\\python.exe

用法：
  # 全量：扫 input 下所有含 img/ 的 SKU
  <DSH python> qa\\check_images.py --input-root input

  # 单个 SKU
  <DSH python> qa\\check_images.py --input-root input --sku AXNJCPS300

  # 自检（在系统 TEMP 构造假图，不写仓库、不碰 input）
  <DSH python> qa\\check_images.py --demo

输出：
  qa/报告/<YYYYMMDD>/图片检查.md    （utf-8）
  qa/报告/<YYYYMMDD>/图片检查.csv   （utf-8-sig，Excel 友好）
  单 SKU 模式文件名带 SKU：图片检查_<SKU>.md/.csv，避免覆盖全量报告

主图定义：每个 SKU 的 img/ 目录下，按文件名排序的第一张（正常就是 01.jpg），其余为详情图。

退出码：
  0  正常（无 P0）
  3  存在 P0 阻断项
  2  参数/环境错误（目录不存在、缺 Pillow、没有可检查的 img 等）
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import os
import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path

try:  # Windows 控制台默认 GBK，固定成 UTF-8，避免中文报告乱码
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

BASE = Path(__file__).resolve().parent
DEFAULT_INPUT = BASE.parent / "input"
DEFAULT_OUTDIR = BASE / "报告"

# ============================================================================
# 规则常量（全部集中在这里；后台规则核对后只改这一段）
# ============================================================================
# 1) 数量：TikTok 建议 5–9 张；当前事实卡/skill 口径 5–6 张
MIN_IMAGES = 5
MAX_IMAGES = 9
SUGGEST_RANGE = (5, 9)          # 平台建议区间
FACTS_CARD_RANGE = (5, 6)       # 事实卡口径
# 2) 尺寸：任一边 <800px → P0；宽高比 1:1，容差 ±3%（主图 P0，详情图 P1）
MIN_EDGE_PX = 800
ASPECT_TOL = 0.03
# 3) 格式/大小：只允许 JPEG/PNG；<10 KB 或 >5 MB → P1
ALLOWED_FORMATS = ("JPEG", "PNG")
ALLOWED_EXTS = (".jpg", ".jpeg", ".png")
MIN_FILE_KB = 10
MAX_FILE_MB = 5
# 4) 重复图：同 SKU 内 sha256 相同 → P1（主图与详情图重复同样 P1）
# 5) 首图白底：启发式，只作 P2，不当阻断
WHITE_EDGE_PCT = 0.08           # 取四边各 8% 边框
WHITE_BRIGHTNESS = 235.0        # 平均亮度阈值
WHITE_SATURATION = 0.10         # 平均饱和度阈值（HSV 的 S，0–1）
# 6) 文字/水印/边框：不做自动判定，报告固定输出这一行
HUMAN_CHECK = "需人工核对：首图是否有文字/水印/边框"

LEVEL_ORDER = {"P0": 0, "P1": 1, "P2": 2}
LEVEL_LABEL = {"P0": "P0 阻断", "P1": "P1 风险", "P2": "P2 提示"}


def _apply_platform_limits():
    """图片阈值统一从 qa/denylist.json 的 sites.MX.images 读；读不到就保留上面的默认值。"""
    global MIN_IMAGES, MAX_IMAGES, SUGGEST_RANGE, FACTS_CARD_RANGE, MIN_EDGE_PX, ASPECT_TOL
    global MIN_FILE_KB, MAX_FILE_MB, ALLOWED_EXTS, WHITE_EDGE_PCT, WHITE_BRIGHTNESS, WHITE_SATURATION
    import json
    try:
        img = json.loads((BASE / "denylist.json").read_text(encoding="utf-8"))["sites"]["MX"]["images"]
    except Exception:  # noqa: BLE001
        return
    count = img.get("count") or [MIN_IMAGES, MAX_IMAGES]
    MIN_IMAGES, MAX_IMAGES = int(count[0]), int(count[1])
    SUGGEST_RANGE = (MIN_IMAGES, MAX_IMAGES)
    FACTS_CARD_RANGE = tuple(img.get("facts_card_range") or FACTS_CARD_RANGE)
    MIN_EDGE_PX = int(img.get("min_edge_px", MIN_EDGE_PX))
    ASPECT_TOL = float(img.get("aspect_tol", ASPECT_TOL))
    MIN_FILE_KB = int(img.get("min_file_kb", MIN_FILE_KB))
    MAX_FILE_MB = int(img.get("max_file_mb", MAX_FILE_MB))
    ALLOWED_EXTS = tuple(img.get("allowed_exts") or ALLOWED_EXTS)
    WHITE_EDGE_PCT = float(img.get("white_edge_pct", WHITE_EDGE_PCT))
    WHITE_BRIGHTNESS = float(img.get("white_brightness", WHITE_BRIGHTNESS))
    WHITE_SATURATION = float(img.get("white_saturation", WHITE_SATURATION))


_apply_platform_limits()
RULE_ORDER = ["COUNT-LOW", "COUNT-HIGH", "SIZE-MIN", "RATIO-MAIN", "RATIO-DETAIL",
              "FORMAT", "CORRUPT", "FILESIZE-LOW", "FILESIZE-HIGH", "DUP-MAIN", "DUP", "WHITE"]
RULE_TITLE = {
    "COUNT-LOW": "数量不足",
    "COUNT-HIGH": "数量过多",
    "SIZE-MIN": "分辨率不足",
    "RATIO-MAIN": "主图非 1:1",
    "RATIO-DETAIL": "详情图非 1:1",
    "FORMAT": "格式不支持",
    "CORRUPT": "图片损坏/打不开",
    "FILESIZE-LOW": "文件过小",
    "FILESIZE-HIGH": "文件过大",
    "DUP-MAIN": "主图与详情图重复",
    "DUP": "重复图",
    "WHITE": "首图非纯白底（启发式）",
}
RULE_CATEGORY = {
    "COUNT-LOW": "数量", "COUNT-HIGH": "数量",
    "SIZE-MIN": "尺寸", "RATIO-MAIN": "尺寸", "RATIO-DETAIL": "尺寸",
    "FORMAT": "格式", "CORRUPT": "格式", "FILESIZE-LOW": "格式", "FILESIZE-HIGH": "格式",
    "DUP-MAIN": "重复", "DUP": "重复",
    "WHITE": "白底",
}

try:
    from PIL import Image
    import PIL
    PIL_VERSION = getattr(PIL, "__version__", "?")
except Exception:  # noqa: BLE001  —— 缺 Pillow 时不在 import 期炸，留到运行时给明确提示
    Image = None  # type: ignore[assignment]
    PIL_VERSION = ""


# ---------------------------------------------------------------- 环境/参数
def pil_hint() -> str:
    """给出本机可用的含 Pillow 的 python 命令（找不到就返回通用提示）。"""
    home = os.environ.get("DSH_HOME") or str(Path.home() / ".dsh")
    p = (Path(home) / "dsh-runtimes" / "dsh-primary-runtime" / "dependencies"
         / "python" / "python.exe")
    if p.exists():
        return f'"{p}" "{BASE / "check_images.py"}" --input-root input'
    return "含 Pillow 的 python（本机可先用 DSH 自带运行时里的 python）"


def require_pil() -> bool:
    if Image is not None:
        return True
    print("[ERROR] 缺少 Pillow（PIL）：图片检查必须用它读取尺寸、格式和像素。", file=sys.stderr)
    print("        系统 python 默认没装 Pillow，不要 pip install，直接用 DSH 自带 python：",
          file=sys.stderr)
    print(f"          {pil_hint()}", file=sys.stderr)
    print("        用其他环境时先 `python -m pip install Pillow` 再跑。", file=sys.stderr)
    return False


def die(msg: str, code: int = 2) -> int:
    print(f"[ERROR] {msg}", file=sys.stderr)
    return code


# ---------------------------------------------------------------- 单图检查
def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def white_border_stats(path: Path):
    """首图白底启发式：取四边各 WHITE_EDGE_PCT 的边框像素，算平均亮度与平均饱和度。

    返回 (平均亮度, 平均饱和度)；当前实现不看中间区域，也识别不了文字/水印/边框，
    所以结论只记 P2，人工核对项在报告里固定输出。
    """
    with Image.open(path) as src:
        im = src
        if im.mode in ("RGBA", "LA", "P"):
            # 透明底按白底合成，避免透明像素被当成黑色
            im = im.convert("RGBA")
            bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
            im = Image.alpha_composite(bg, im)
        im = im.convert("RGB")
        # 大图缩到长边 512 再采样，像素级统计足够，速度稳定
        if max(im.size) > 512:
            scale = 512 / max(im.size)
            im = im.resize((max(1, int(im.width * scale)), max(1, int(im.height * scale))),
                           Image.Resampling.BILINEAR)
        w, h = im.size
        bw = max(1, int(round(w * WHITE_EDGE_PCT)))
        bh = max(1, int(round(h * WHITE_EDGE_PCT)))
        boxes = [(0, 0, w, bh), (0, h - bh, w, h), (0, 0, bw, h), (w - bw, 0, w, h)]
        pixels = []
        for box in boxes:
            pixels.append(im.crop(box).tobytes())
    raw = b"".join(pixels)
    n = len(raw) // 3
    if n == 0:
        return 0.0, 1.0
    total_b = 0.0
    total_s = 0.0
    for i in range(0, len(raw), 3):
        r, g, b = raw[i], raw[i + 1], raw[i + 2]
        mx, mn = max(r, g, b), min(r, g, b)
        total_b += (r + g + b) / 3.0
        total_s += (mx - mn) / mx if mx else 0.0
    return total_b / n, total_s / n


def check_sku(sku: str, sku_dir: Path):
    """检查一个 SKU 的 img/ 目录，返回 (findings, meta)。

    findings 每条：sku / file / is_main / level / rule / title / detail / suggestion
                  / w / h / ratio / kb / sha
    meta：张数、主图尺寸、首图白底统计
    """
    findings = []

    def add(rule, level, file_label, detail, suggestion, is_main=False,
            w=None, h=None, ratio=None, kb=None, sha=""):
        findings.append({
            "sku": sku, "file": file_label, "is_main": is_main,
            "level": level, "rule": rule, "title": RULE_TITLE[rule],
            "detail": detail, "suggestion": suggestion,
            "w": w, "h": h, "ratio": ratio, "kb": kb, "sha": sha,
            "category": RULE_CATEGORY[rule],
        })

    img_dir = sku_dir / "img"
    files = sorted([p for p in img_dir.iterdir() if p.is_file()], key=lambda p: p.name)
    meta = {"n": len(files), "main": files[0].name if files else "",
            "main_size": "", "main_kb": "", "white": None}

    # 1) 数量
    n = len(files)
    if n == 0:
        add("COUNT-LOW", "P1", "（整个 SKU）",
            f"img/ 目录为空，0 张图（TikTok 建议 {SUGGEST_RANGE[0]}–{SUGGEST_RANGE[1]} 张）",
            "重新采集/导出该 SKU 图片，至少 5 张")
        return findings, meta
    if n < MIN_IMAGES:
        add("COUNT-LOW", "P1", "（整个 SKU）",
            f"图片仅 {n} 张，少于下限 {MIN_IMAGES} 张"
            f"（TikTok 建议 {SUGGEST_RANGE[0]}–{SUGGEST_RANGE[1]} 张，"
            f"事实卡口径 {FACTS_CARD_RANGE[0]}–{FACTS_CARD_RANGE[1]} 张）",
            "补到 5 张以上：白底主图 + 场景图 + 细节图 + 尺寸图 + 包装清单图")
    elif n > MAX_IMAGES:
        add("COUNT-HIGH", "P1", "（整个 SKU）",
            f"图片 {n} 张，超过上限 {MAX_IMAGES} 张",
            "按信息量保留 9 张，删掉重复/低信息量图")

    hashes = {}
    for idx, p in enumerate(files):
        name = p.name
        is_main = (idx == 0)
        try:
            kb = p.stat().st_size / 1024.0
        except OSError as e:  # noqa: BLE001
            add("CORRUPT", "P0", name, f"读不到文件信息：{e}", "确认文件权限/路径后重试", is_main)
            continue
        sha = ""
        try:
            sha = sha256_of(p)
        except OSError:
            pass
        if sha:
            hashes[name] = sha

        # 2) 文件大小（独立于能否打开，损坏的小文件也会命中）
        if kb < MIN_FILE_KB:
            add("FILESIZE-LOW", "P1", name,
                f"{kb:.1f} KB，小于 {MIN_FILE_KB} KB 下限",
                "小图大概率是缩略图或被压过，换高清原图", is_main, kb=kb)
        elif kb > MAX_FILE_MB * 1024:
            add("FILESIZE-HIGH", "P1", name,
                f"{kb / 1024:.1f} MB，超过 {MAX_FILE_MB} MB 上限",
                f"压缩到 {MAX_FILE_MB} MB 以内（JPEG 质量 85 左右）再上架", is_main, kb=kb)

        # 3) 格式/损坏
        try:
            with Image.open(p) as im:
                fmt = (im.format or "").upper()
                w, h = im.size
        except Exception as e:  # noqa: BLE001
            suffix = p.suffix.lower()
            if suffix not in ALLOWED_EXTS:
                add("FORMAT", "P0", name,
                    f"扩展名 {suffix or '（无）'} 不是 JPEG/PNG，且 PIL 打不开：{e}",
                    "转成 .jpg/.png 再上架", is_main, kb=kb, sha=sha)
            else:
                add("CORRUPT", "P0", name, f"PIL 打不开（文件损坏/不是图片）：{e}",
                    "重新下载或重新导出该图，确认文件完整", is_main, kb=kb, sha=sha)
            continue

        ratio = (w / h) if h else 0.0
        meta_hw = (w, h)
        if is_main:
            meta["main_size"] = f"{w}x{h}"
            meta["main_kb"] = f"{kb:.0f} KB"
        if fmt not in ALLOWED_FORMATS:
            add("FORMAT", "P0", name,
                f"实际格式 {fmt or '未知'}（只允许 {'/'.join(ALLOWED_FORMATS)}）",
                "转成 JPEG/PNG 再上架", is_main, w, h, ratio, kb, sha)
            # 格式已 P0，尺寸/比例照样报，便于一次改好

        # 4) 尺寸
        if min(w, h) < MIN_EDGE_PX:
            add("SIZE-MIN", "P0", name,
                f"尺寸 {w}x{h}，短边 {min(w, h)}px < {MIN_EDGE_PX}px",
                "换高清原图（不要拿采集小图放大，会糊）", is_main, w, h, ratio, kb, sha)
        # 5) 宽高比：主图 P0，详情图 P1
        if ratio <= 0 or abs(ratio - 1.0) > ASPECT_TOL:
            if is_main:
                add("RATIO-MAIN", "P0", name,
                    f"主图 {w}x{h}，宽高比 {ratio:.3f}，非 1:1（容差 ±{int(ASPECT_TOL * 100)}%）",
                    "主图裁成 1:1（如 1000x1000）；TikTok 首图按方图展示，非方图会被裁",
                    is_main, w, h, ratio, kb, sha)
            else:
                add("RATIO-DETAIL", "P1", name,
                    f"详情图 {w}x{h}，宽高比 {ratio:.3f}，非 1:1（容差 ±{int(ASPECT_TOL * 100)}%）",
                    "建议统一 1:1；长图至少在商品页不被裁切", is_main, w, h, ratio, kb, sha)

        # 6) 首图白底（只看主图，启发式，只作 P2）
        if is_main:
            try:
                brightness, saturation = white_border_stats(p)
                meta["white"] = (brightness, saturation)
                if brightness < WHITE_BRIGHTNESS or saturation > WHITE_SATURATION:
                    add("WHITE", "P2", name,
                        f"首图四边 {int(WHITE_EDGE_PCT * 100)}% 边框平均亮度 {brightness:.1f}"
                        f"（阈值 ≥{WHITE_BRIGHTNESS:.0f}）、平均饱和度 {saturation:.2f}"
                        f"（阈值 ≤{WHITE_SATURATION:.2f}）；启发式判定：非纯白底",
                        "若站点要求白底主图，换纯白底；服装/场景类目可对照后台该类目规则再定",
                        is_main, w, h, ratio, kb, sha)
            except Exception as e:  # noqa: BLE001
                print(f"[WARN] {sku}/{name} 白底采样失败：{e}", file=sys.stderr)

    # 7) 重复图（同 SKU 内 sha256 相同）
    groups = {}
    for name, sha in hashes.items():
        groups.setdefault(sha, []).append(name)
    for sha, names in groups.items():
        if len(names) < 2:
            continue
        names = sorted(names)
        is_main_dup = bool(meta["main"]) and meta["main"] in names
        rule = "DUP-MAIN" if is_main_dup else "DUP"
        label = "、".join(names)
        add(rule, "P1", label,
            f"{len(names)} 张图内容完全相同（sha256 {sha[:12]}）"
            + ("，其中含主图" if is_main_dup else ""),
            "主图不能和详情图重复；重复图按低质处理，换成不同角度/场景"
            if is_main_dup else "删掉重复图，换不同角度/场景/细节图",
            is_main_dup and names[0] == meta.get("main"))

    findings.sort(key=lambda f: (LEVEL_ORDER[f["level"]], RULE_ORDER.index(f["rule"])))
    return findings, meta


# ---------------------------------------------------------------- 扫描/汇总
def collect_targets(input_root: Path, sku_arg: str):
    """返回 (要检查的 [(sku, dir)], 无 img 被跳过的 sku 名)。"""
    targets, skipped = [], []
    if sku_arg:
        d = input_root / sku_arg
        if not d.is_dir():
            raise FileNotFoundError(f"找不到 SKU 目录：{d}")
        if not (d / "img").is_dir():
            raise FileNotFoundError(f"SKU {sku_arg} 没有 img 目录：{d / 'img'}")
        return [(sku_arg, d)], []
    for d in sorted(input_root.iterdir()):
        if not d.is_dir() or d.name.startswith("_"):
            continue
        if (d / "img").is_dir():
            targets.append((d.name, d))
        else:
            skipped.append(d.name)
    return targets, skipped


def summarize(sku: str, meta: dict, findings) -> dict:
    row = {"sku": sku, "n": meta["n"], "p0": 0, "p1": 0, "p2": 0,
           "main_size": meta["main_size"], "main_kb": meta["main_kb"], "white": meta["white"]}
    for f in findings:
        row[f["level"].lower()] += 1
    return row


# ---------------------------------------------------------------- 输出
def write_reports(findings, sku_rows, skipped, input_root: Path, outdir: Path,
                  scope: str = "") -> "tuple[Path, Path]":
    day = datetime.now().strftime("%Y%m%d")
    out_dir = outdir / day
    out_dir.mkdir(parents=True, exist_ok=True)
    suffix = f"_{scope}" if scope else ""
    md_path = out_dir / f"图片检查{suffix}.md"
    csv_path = out_dir / f"图片检查{suffix}.csv"

    total = {"P0": 0, "P1": 0, "P2": 0}
    skus_with = {"P0": set(), "P1": set(), "P2": set()}
    per_rule = {}
    for f in findings:
        total[f["level"]] += 1
        skus_with[f["level"]].add(f["sku"])
        key = (f["rule"], f["level"])
        per_rule[key] = per_rule.get(key, 0) + 1
    n_img = sum(r["n"] for r in sku_rows)
    n_sku = len(sku_rows)

    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        "# TikTok 图片合规检查报告",
        "",
        f"- 检查时间：{ts}",
        f"- 输入目录：`{input_root}`",
        f"- 检查范围：{n_sku} 个 SKU / {n_img} 张图"
        "（主图 = 每个 SKU 的 img/ 目录下按文件名排序第一张，其余为详情图）",
        (f"- 跳过的 SKU：未扫描其他 SKU（本次为单 SKU 模式）" if scope else
         f"- 跳过的 SKU：{len(skipped)} 个（没有 img/ 目录，**未检查，不计入通过**）"),
        f"- 图片工具：Pillow {PIL_VERSION}",
        "",
    ]
    if skipped and not scope:
        lines += [f"  无 img 的 SKU（{len(skipped)} 个）：" + "、".join(skipped), ""]

    lines += [
        "## 一、总览",
        "",
        "| 级别 | 命中数 | 涉及 SKU | 含义 |",
        "|---|---|---|---|",
        f"| P0 阻断 | {total['P0']} | {len(skus_with['P0'])} | 尺寸 <{MIN_EDGE_PX}px、主图非 1:1、格式非 JPEG/PNG、图片损坏 |",
        f"| P1 风险 | {total['P1']} | {len(skus_with['P1'])} | 数量不在 {MIN_IMAGES}–{MAX_IMAGES} 张、详情图非 1:1、文件过小/过大、重复图 |",
        f"| P2 提示 | {total['P2']} | {len(skus_with['P2'])} | 首图非纯白底（启发式，不阻断） |",
        "",
        "## 二、按检查项",
        "",
        "| 检查项 | 级别 | 命中数 |",
        "|---|---|---|",
    ]
    for (rule, level), cnt in sorted(per_rule.items(),
                                     key=lambda x: (LEVEL_ORDER[x[0][1]], RULE_ORDER.index(x[0][0]))):
        lines.append(f"| {rule} · {RULE_TITLE[rule]} | {level} | {cnt} |")
    if not per_rule:
        lines.append("| - | - | 0 |")

    lines += ["", "## 三、逐 SKU 明细", ""]
    by_sku = {}
    for f in findings:
        by_sku.setdefault(f["sku"], []).append(f)
    for row in sku_rows:
        white = row["white"]
        white_txt = ""
        if white:
            ok = white[0] >= WHITE_BRIGHTNESS and white[1] <= WHITE_SATURATION
            white_txt = (f"，首图白底启发式{'通过' if ok else '未通过'}"
                         f"（亮度 {white[0]:.1f} / 饱和 {white[1]:.2f}）")
        lines.append(f"### {row['sku']}（{row['n']} 张"
                     f"{'，主图 ' + row['main_size'] if row['main_size'] else ''}{white_txt}）")
        lines.append("")
        fs = by_sku.get(row["sku"])
        if not fs:
            lines.append("- 通过：无 P0/P1/P2 命中")
        else:
            for f in fs:
                lines.append(f"- **[{f['level']}] {f['rule']} · {f['title']}**"
                             f"（{f['file']}）：{f['detail']} → {f['suggestion']}")
        lines.append("")

    lines += [
        "## 四、需人工核对",
        "",
        f"- {HUMAN_CHECK}",
        "- 说明：文字/水印/边框不做自动判定（机器识别不可靠，误报会掩盖真问题），"
        "每条链接上架前人工过一遍首图。",
        "",
        "## 五、规则常量（后台核对后改 qa/check_images.py 顶部）",
        "",
        "| 常量 | 当前值 | 说明 |",
        "|---|---|---|",
        f"| MIN_IMAGES | {MIN_IMAGES} | 图片数量下限，少于它记 P1 |",
        f"| MAX_IMAGES | {MAX_IMAGES} | 图片数量上限，多于它记 P1 |",
        f"| SUGGEST_RANGE | {SUGGEST_RANGE[0]}–{SUGGEST_RANGE[1]} | TikTok 建议张数（写进提示文案） |",
        f"| FACTS_CARD_RANGE | {FACTS_CARD_RANGE[0]}–{FACTS_CARD_RANGE[1]} | 事实卡/skill 口径（写进提示文案） |",
        f"| MIN_EDGE_PX | {MIN_EDGE_PX} | 任一边小于它记 P0 |",
        f"| ASPECT_TOL | ±{int(ASPECT_TOL * 100)}% | 宽高比 1:1 容差；超差主图 P0、详情图 P1 |",
        f"| ALLOWED_FORMATS | {'/'.join(ALLOWED_FORMATS)} | 允许的图片格式，其余 P0 |",
        f"| MIN_FILE_KB | {MIN_FILE_KB} KB | 小于它记 P1 |",
        f"| MAX_FILE_MB | {MAX_FILE_MB} MB | 大于它记 P1 |",
        f"| WHITE_EDGE_PCT | {int(WHITE_EDGE_PCT * 100)}% | 首图白底采样边框比例 |",
        f"| WHITE_BRIGHTNESS | {WHITE_BRIGHTNESS:.0f} | 平均亮度阈值（≥ 才算白底） |",
        f"| WHITE_SATURATION | {WHITE_SATURATION:.2f} | 平均饱和度阈值（≤ 才算白底） |",
        f"| 主图 | 文件名排序第一张 | 当前数据即 01.jpg，其余为详情图 |",
        f"| 人工核对 | 文字/水印/边框 | 不自动判定，报告固定输出 |",
        "",
    ]
    md_path.write_text("\n".join(lines), encoding="utf-8")

    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["SKU", "文件名", "是否主图", "级别", "检查项", "说明", "建议",
                    "宽", "高", "宽高比", "大小KB", "sha256前12"])
        for r in findings:
            if r["is_main"]:
                main_txt = "是"
            elif r["file"] == "（整个 SKU）":
                main_txt = ""
            else:
                main_txt = "否"
            w.writerow([
                r["sku"], r["file"], main_txt,
                r["level"], f"{r['rule']} · {r['title']}", r["detail"], r["suggestion"],
                r["w"] if r["w"] is not None else "",
                r["h"] if r["h"] is not None else "",
                f"{r['ratio']:.3f}" if r["ratio"] else "",
                f"{r['kb']:.1f}" if r["kb"] is not None else "",
                r["sha"][:12],
            ])
    return md_path, csv_path


def print_report(findings, sku_rows, skipped, md_path: Path, csv_path: Path, scope: str = ""):
    total = {"P0": 0, "P1": 0, "P2": 0}
    for f in findings:
        total[f["level"]] += 1
    n_img = sum(r["n"] for r in sku_rows)
    print(f"\n图片合规检查  |  今天 {datetime.now().strftime('%Y-%m-%d')}")
    if scope:
        print(f"扫描 1 个 SKU / {n_img} 张图；范围：{scope}（其他 SKU 未扫描）")
    else:
        print(f"扫描 {len(sku_rows)} 个 SKU / {n_img} 张图；"
              f"跳过 {len(skipped)} 个无 img 的 SKU（未检查，不算通过）")
    print("=" * 78)
    print(f"{'SKU':<14}{'张数':>4}{'P0':>4}{'P1':>4}{'P2':>4}  结论")
    print("-" * 78)
    for r in sku_rows:
        verdict = "阻断" if r["p0"] else ("风险" if r["p1"] else ("通过" if not r["p2"] else "提示"))
        print(f"{r['sku']:<14}{r['n']:>4}{r['p0']:>4}{r['p1']:>4}{r['p2']:>4}  {verdict}")
    print("-" * 78)
    print(f"汇总：SKU {len(sku_rows)} 个（P0 涉及 {len({f['sku'] for f in findings if f['level'] == 'P0'})} 个 / "
          f"P1 涉及 {len({f['sku'] for f in findings if f['level'] == 'P1'})} 个），"
          f"P0={total['P0']}  P1={total['P1']}  P2={total['P2']}")

    p0 = [f for f in findings if f["level"] == "P0"]
    if p0:
        print(f"\n[阻断] {len(p0)} 条：上架前必须处理")
        for f in p0:
            print(f"  - {f['sku']} / {f['file']} / {f['title']}：{f['detail']}")
    p1 = [f for f in findings if f["level"] == "P1"]
    if p1:
        print(f"\n[风险] {len(p1)} 条：不阻断，但建议清掉（详见 CSV）")
        shown = 0
        for f in p1:
            if shown >= 10:
                print(f"  - 其余 {len(p1) - shown} 条见 CSV")
                break
            print(f"  - {f['sku']} / {f['file']} / {f['title']}：{f['detail']}")
            shown += 1
    p2 = [f for f in findings if f["level"] == "P2"]
    if p2:
        print(f"\n[提示] {len(p2)} 条：首图非纯白底（启发式，不阻断）")

    print(f"\n{HUMAN_CHECK}（不做自动判定）")
    print(f"报告：{md_path}")
    print(f"明细：{csv_path}")
    if total["P0"]:
        print(f"\n退出码 3：存在 {total['P0']} 条 P0 阻断项")
    else:
        print("\n退出码 0：无 P0 阻断项")


# ---------------------------------------------------------------- 自检
def prepare_demo_dir() -> Path:
    """给 demo 找一个可写工作目录：优先系统 TEMP，沙箱禁止时退回 output/_audit。

    本机 DSH 沙箱只允许写工作区，系统 TEMP 能建目录但往里写文件会被拒绝，
    所以先探测；两种情况都只放构造用例，跑完立即删除。
    """
    tmp = None
    try:
        tmp = Path(tempfile.mkdtemp(prefix="tiktok_img_demo_"))
        probe = tmp / "_probe.txt"
        probe.write_text("x", encoding="utf-8")
        probe.unlink()
        print(f"[demo] 工作目录（系统 TEMP）：{tmp}")
        return tmp
    except OSError:
        if tmp is not None:
            shutil.rmtree(tmp, ignore_errors=True)
        base = BASE.parent / "output" / "_audit"
        base.mkdir(parents=True, exist_ok=True)
        tmp = base / f"_img_demo_{os.getpid()}"
        shutil.rmtree(tmp, ignore_errors=True)
        tmp.mkdir(parents=True, exist_ok=True)
        print(f"[demo] 系统 TEMP 不可写（沙箱限制），工作目录：{tmp}"
              f"（在 output/_audit 下，gitignore 范围，跑完删除）")
        return tmp


def demo() -> int:
    """构造假图验证各条规则，不写仓库正式产物、不碰 input。"""
    tmp = prepare_demo_dir()
    checked = []
    ok = True

    def expect(label, cond):
        nonlocal ok
        checked.append((label, cond))
        if not cond:
            ok = False
        print(f"[{'OK ' if cond else 'FAIL'}] {label}")

    try:
        # SKU A：4 张（数量不足 P1）+ 600x900 灰图（尺寸 P0、详情图比例 P1）
        #        + 02 的副本（重复 P1）+ 损坏 jpg（损坏 P0 / 文件过小 P1）；01 为纯白方图
        a_dir = tmp / "DEMO_A" / "img"
        a_dir.mkdir(parents=True)
        Image.new("RGB", (1000, 1000), (255, 255, 255)).save(a_dir / "01.jpg", quality=90)
        # 用噪点图让文件大小 >10 KB，避免顺带命中「文件过小」，保证每条规则独立可验证
        Image.effect_noise((600, 900), 80).convert("RGB").save(a_dir / "02.jpg", quality=90)
        shutil.copyfile(a_dir / "02.jpg", a_dir / "03.jpg")
        (a_dir / "04.jpg").write_bytes(b"\x00not-an-image")
        # SKU B：1 张 BMP（格式 P0 + 数量 P1），灰底大白图（白底 P2）
        b_dir = tmp / "DEMO_B" / "img"
        b_dir.mkdir(parents=True)
        Image.new("RGB", (1000, 1000), (180, 180, 180)).save(b_dir / "01.bmp")

        targets, skipped = collect_targets(tmp, "")
        findings = []
        rows = []
        for sku, d in targets:
            fs, meta = check_sku(sku, d)
            findings.extend(fs)
            rows.append(summarize(sku, meta, fs))

        def rules_for(sku):
            return [f["rule"] for f in findings if f["sku"] == sku]

        def count(sku, rule):
            return rules_for(sku).count(rule)

        expect("SKU A 数量不足 4<5 → P1 COUNT-LOW", count("DEMO_A", "COUNT-LOW") == 1)
        expect("SKU A 600x900 两张 → 尺寸 P0 SIZE-MIN 2 条", count("DEMO_A", "SIZE-MIN") == 2)
        expect("SKU A 600x900 两张 → 详情图比例 P1 RATIO-DETAIL 2 条",
               count("DEMO_A", "RATIO-DETAIL") == 2)
        expect("SKU A 主图 1000x1000 方图 → 无 RATIO-MAIN", count("DEMO_A", "RATIO-MAIN") == 0)
        expect("SKU A 02/03 同内容 → P1 DUP 1 条", count("DEMO_A", "DUP") == 1)
        expect("SKU A 损坏 jpg → P0 CORRUPT 1 条", count("DEMO_A", "CORRUPT") == 1)
        expect("SKU A 损坏 jpg 9 字节 → P1 FILESIZE-LOW 1 条",
               count("DEMO_A", "FILESIZE-LOW") == 1)
        expect("SKU A 主图纯白 → 无 WHITE P2", count("DEMO_A", "WHITE") == 0)
        expect("SKU B BMP → 格式 P0 FORMAT 1 条", count("DEMO_B", "FORMAT") == 1)
        expect("SKU B 数量 1<5 → P1 COUNT-LOW 1 条", count("DEMO_B", "COUNT-LOW") == 1)
        expect("SKU B 灰底 → P2 WHITE 1 条", count("DEMO_B", "WHITE") == 1)
        a_row = next(r for r in rows if r["sku"] == "DEMO_A")
        b_row = next(r for r in rows if r["sku"] == "DEMO_B")
        expect("SKU A 统计 P0=3 P1=5 P2=0",
               (a_row["p0"], a_row["p1"], a_row["p2"]) == (3, 5, 0))
        expect("SKU B 统计 P0=1 P1=1 P2=1",
               (b_row["p0"], b_row["p1"], b_row["p2"]) == (1, 1, 1))
        expect("主图按文件名排序第一张（DEMO_A=01.jpg）", a_row["main_size"] == "1000x1000")

        # 报告写出（写临时目录，不写仓库）
        md, csvp = write_reports(findings, rows, skipped, tmp, tmp / "报告")
        md_txt = md.read_text(encoding="utf-8")
        expect("md 报告已生成", md.exists() and csvp.exists())
        expect("md 含人工核对项", HUMAN_CHECK in md_txt)
        expect("md 含规则常量表", "MIN_EDGE_PX" in md_txt)
        with csvp.open("rb") as f:
            expect("CSV 为 utf-8-sig（Excel 友好）", f.read(3) == b"\xef\xbb\xbf")
        expect("跳过 0 个无 img 的 SKU（demo 两个都有 img）", len(skipped) == 0)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    passed = sum(1 for _, c in checked if c)
    print(f"\n自检结果：{passed}/{len(checked)} 通过 → " + ("通过" if ok else "失败"))
    return 0 if ok else 2


# ---------------------------------------------------------------- 主流程
def main() -> int:
    ap = argparse.ArgumentParser(description="TikTok 图片合规检查器 v1.0（数量/尺寸/比例/格式/重复/白底）")
    ap.add_argument("--input-root", default=str(DEFAULT_INPUT), help="商品目录（每个 SKU 下有 img/）")
    ap.add_argument("--sku", default="", help="只查这个 SKU（目录名）")
    ap.add_argument("--outdir", default=str(DEFAULT_OUTDIR), help="报告输出目录（自动按日期建子目录）")
    ap.add_argument("--demo", action="store_true", help="自检：在系统 TEMP 构造假图验证规则，不碰 input")
    args = ap.parse_args()

    if not require_pil():
        return 2
    if args.demo:
        return demo()

    input_root = Path(args.input_root).expanduser()
    if not input_root.is_dir():
        return die(f"输入目录不存在：{input_root}")
    try:
        targets, skipped = collect_targets(input_root, args.sku)
    except FileNotFoundError as e:
        return die(str(e))
    if not targets:
        return die(f"{input_root} 下没有任何含 img/ 目录的 SKU（无法检查）")

    findings = []
    sku_rows = []
    for sku, d in targets:
        fs, meta = check_sku(sku, d)
        findings.extend(fs)
        sku_rows.append(summarize(sku, meta, fs))

    scope = args.sku or ""
    md_path, csv_path = write_reports(findings, sku_rows, skipped, input_root,
                                      Path(args.outdir), scope)
    print_report(findings, sku_rows, skipped, md_path, csv_path, scope)

    total_p0 = sum(1 for f in findings if f["level"] == "P0")
    return 3 if total_p0 else 0


if __name__ == "__main__":
    sys.exit(main())
