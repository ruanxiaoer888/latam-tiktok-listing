# -*- coding: utf-8 -*-
r"""把 pattern 输出的 JSON 渲染成可粘贴的纯文本（标题.txt / 描述.txt）。

为什么要有这一步：TikTok 后台是富文本编辑器，不解析 Markdown；`**` 会原样显示成星号，
全角标点粘进去也是错的。格式由代码保证，而不是让模型「记得别写**」。

输入 JSON（见 patterns\listing_write\system.md 的 OUTPUT CONTRACT）：
  {title, hook, bullets[], specs[{label,value}], package_included[],
   package_not_included[], faq[{q,a}], cta, notes}

用法（仓库根执行）：
  python scripts\render_listing.py --json output\_draft\ABU5000000.json --out-root output\批次20261030
  python scripts\render_listing.py --dir output\_draft --out-root output\批次20261030 --site MX
"""
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BOLD = re.compile(r"\*\*(.+?)\*\*")
BOLD_LEFT = re.compile(r"\*\*")
FULLWIDTH = re.compile(r"[：，。（）；！？、]")
HALF = str.maketrans({"：": ": ", "，": ", ", "（": "(", "）": ")",
                      "。": ". ", "；": "; ", "！": "! ", "？": "? ", "、": ", "})
LABEL = {
    "MX": {"specs": "📋 Especificaciones Técnicas:",
           "pkg": "📦 Contenido del Paquete:",
           "faq": "💡 Preguntas Frecuentes (FAQ):",
           "noinc": "No incluye:"},
    "BR": {"specs": "📋 Especificações Técnicas:",
           "pkg": "📦 Conteúdo da Embalagem:",
           "faq": "💡 Perguntas Frequentes (FAQ):",
           "noinc": "Não incluso:"},
}


def clean(s):
    """去掉 Markdown 残留与全角标点，压掉多余空白。"""
    s = BOLD.sub(r"\1", str(s or ""))
    s = BOLD_LEFT.sub("", s)
    s = FULLWIDTH.sub(lambda m: m.group(0).translate(HALF), s)
    return " ".join(s.split())


def need(d, key):
    if key not in d or d[key] in (None, "", []):
        raise SystemExit(f"草稿缺字段：{key}")
    return d[key]


def render(d, site):
    title = clean(need(d, "title"))
    hook = clean(need(d, "hook"))
    bullets = [clean(x) for x in need(d, "bullets")]
    specs = [(clean(x["label"]), clean(x["value"])) for x in need(d, "specs")]
    inc = [clean(x) for x in d.get("package_included") or []]
    exc = [clean(x) for x in d.get("package_not_included") or []]
    faq = [(clean(x["q"]), clean(x["a"])) for x in need(d, "faq")]
    cta = clean(d.get("cta") or "")
    L = LABEL[site]

    lines = [hook, ""]
    for b in bullets:
        lines += [f"⭐ {b}", ""]
    lines += [L["specs"], ""]
    lines += [f"- {a}: {v}" for a, v in specs]
    lines += ["", L["pkg"], ""]
    lines += [f"- {x}" for x in inc]
    lines += [f"- {L['noinc']} {x}" for x in exc]
    lines += ["", L["faq"], ""]
    lines += [f"- {q} {a}" for q, a in faq]
    if cta:
        lines += ["", cta]

    warnings = []
    if not (3 <= len(bullets) <= 5):
        warnings.append(f"卖点 {len(bullets)} 条（应 3–5）")
    if len(faq) < 2:
        warnings.append(f"FAQ {len(faq)} 条（应 ≥2）")
    if not (60 <= len(title) <= 80):
        warnings.append(f"标题 {len(title)} 字符（默认 60–80；汽配 80–120）")
    if not re.search(r"\bpara\b", title, re.I):
        warnings.append("标题缺用途词 para…")
    return title, "\n".join(lines).rstrip() + "\n", warnings


def write_one(draft_path: Path, out_root: Path, site):
    sku = draft_path.stem
    d = json.loads(draft_path.read_text(encoding="utf-8-sig"))
    title, desc, warnings = render(d, site)
    out_dir = out_root / sku
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "标题.txt").write_text(title + "\n", encoding="utf-8")
    (out_dir / "描述.txt").write_text(desc, encoding="utf-8")
    flag = "OK" if not warnings else "!!"
    print(f"  [{flag}] {sku}: 标题 {len(title)} 字符, 描述 {len(desc)} 字符")
    for w in warnings:
        print(f"        - {w}")
    if d.get("notes"):
        print(f"        备注：{d['notes']}")
    return not warnings


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="JSON 草稿 → 纯文本成稿")
    ap.add_argument("--json", default="", help="单个草稿 JSON")
    ap.add_argument("--dir", default="", help="草稿目录（每个 <SKU>.json）")
    ap.add_argument("--out-root", required=True, help="批次目录，如 output\\批次20261030")
    ap.add_argument("--site", default="MX", choices=["MX", "BR"])
    args = ap.parse_args()

    out_root = Path(args.out_root).resolve()
    if args.json:
        files = [Path(args.json).resolve()]
    elif args.dir:
        files = sorted(Path(args.dir).resolve().glob("*.json"))
    else:
        ap.print_help()
        raise SystemExit(2)
    if not files:
        raise SystemExit("没有找到草稿 JSON")

    ok = sum(write_one(p, out_root, args.site) for p in files)
    print(f"\n渲染 {len(files)} 条；无告警 {ok} 条；输出：{out_root}")
    if ok != len(files):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
