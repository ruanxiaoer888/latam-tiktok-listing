# -*- coding: utf-8 -*-
r"""按 pattern 组装自包含 prompt（等价 fabric 的 --print-prompt，只渲染不发模型）。

组成：pattern/system.md + contexts（站点规则/转化层/骨架/类目包）+ 事实块 + 场景卡
改稿模式（--findings）：再拼上「当前草稿」与「违规清单」，用于 listing_fix。

产物：output\_prompts\<SKU>.md（改稿模式为 <SKU>-fix.md），头部写 pattern 版本 + renderer
      版本 + sha256，以后改规则能让「生成包与生成器不一致」一眼看出来。

用法（仓库根执行）：
  python scripts\render_prompt.py --sku ABU5000000 --site MX --print
  python scripts\render_prompt.py --sku ABU5000000 --site MX

  # 改稿模式：把 check_listing 的明细喂进来，生成 listing_fix 的 prompt
  python scripts\render_prompt.py --sku ABU5000000 --site MX --pattern listing_fix `
    --findings output\_smoke\run_batch_xxx\20261029\明细_MX_check_verified_xxx.csv `
    --batch output\批次20261022-v2
"""
import argparse
import csv
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "qa"))
from facts_digest import fact_lines  # noqa: E402

RENDERER_VERSION = "1.1.0"
LANG = {"MX": "es-MX", "BR": "pt-BR"}


def load_json(p: Path):
    return json.loads(Path(p).read_text(encoding="utf-8-sig"))


def resolve_context(spec, site, category):
    rel = spec["path"].format(site_lower=site.lower(), category=category)
    hits = sorted(ROOT.glob(rel))
    if not hits:
        raise SystemExit(f"context 缺失：{rel}（检查 patterns/*/meta.json 或类目名）")
    return hits[0]


def load_findings(path: Path, sku: str):
    """从 check_listing 的明细 CSV 里取当前 SKU 的违规行。"""
    rows = []
    with open(path, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            if r.get("商品ID") == sku:
                rows.append(r)
    return rows


def format_violations(rows):
    out = ["# VIOLATIONS（只改这几条，不要顺手重写合格部分）", ""]
    for i, r in enumerate(rows, 1):
        out.append(
            f"{i}. [{r.get('严重度','')}] {r.get('检查项','')} · {r.get('说明','')}"
            f" | 字段：{r.get('字段','')} | 命中：{r.get('命中片段','')}"
            f" → 改法：{r.get('建议','')}"
        )
    return "\n".join(out)


def current_draft(args, sku):
    """当前草稿：优先 JSON，其次批次里的纯文本成稿；都没有返回 ''。"""
    dj = Path(args.draft_json) if args.draft_json else ROOT / "output" / "_draft" / f"{sku}.json"
    if dj.exists():
        d = load_json(dj)
        return ("# CONTEXT: 当前草稿（保留合格部分，只改 VIOLATIONS）\n\n```json\n"
                + json.dumps(d, ensure_ascii=False, indent=2) + "\n```")
    if args.batch:
        b = Path(args.batch) / sku
        t, dsc = b / "标题.txt", b / "描述.txt"
        if t.exists() and dsc.exists():
            return ("# CONTEXT: 当前成稿（纯文本，保留合格部分，只改 VIOLATIONS）\n\n"
                    "标题：\n" + t.read_text(encoding="utf-8").strip()
                    + "\n\n描述：\n" + dsc.read_text(encoding="utf-8").strip())
    return ""


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="组装 pattern prompt（只渲染）")
    ap.add_argument("--pattern", default="listing_write")
    ap.add_argument("--sku", required=True)
    ap.add_argument("--site", default="MX", choices=["MX", "BR"])
    ap.add_argument("--input-root", default=str(ROOT / "input"))
    ap.add_argument("--out", default="", help="输出路径；默认 output\\_prompts\\<SKU>.md")
    ap.add_argument("--print", dest="do_print", action="store_true", help="打印到 stdout，不写文件")
    ap.add_argument("--allow-unverified", action="store_true", help="允许 draft/quarantined（仅预览）")
    ap.add_argument("--findings", default="", help="check_listing 明细 CSV；给定时进入改稿模式")
    ap.add_argument("--draft-json", default="", help="当前草稿 JSON；缺省找 output\\_draft\\<SKU>.json")
    ap.add_argument("--batch", default="", help="当前成稿批次目录（改稿时读 标题/描述）")
    args = ap.parse_args()

    pdir = ROOT / "patterns" / args.pattern
    if not (pdir / "system.md").exists():
        raise SystemExit(f"pattern 不存在：{pdir}")
    meta = load_json(pdir / "meta.json")
    system = (pdir / "system.md").read_text(encoding="utf-8")

    facts_path = Path(args.input_root) / args.sku / "facts.json"
    if not facts_path.exists():
        raise SystemExit(f"没有事实卡：{facts_path}")
    facts = load_json(facts_path)
    status = facts.get("status")
    if status != "verified" and not args.allow_unverified:
        raise SystemExit(f"{args.sku} facts.status={status}，未核验；确认要预览加 --allow-unverified")

    category = facts.get("category") or ""
    parts = []
    for spec in meta.get("contexts", []):
        p = resolve_context(spec, args.site, category)
        parts.append(f"# CONTEXT: {spec['title']}（{p.relative_to(ROOT).as_posix()}）\n\n"
                     + p.read_text(encoding="utf-8").strip())

    scene = ROOT / "output" / "_batch" / "scene" / f"{args.sku}.md"
    if scene.exists():
        parts.append("# CONTEXT: 场景卡（自动抽取，只作参考，不当事实源）\n\n"
                     + scene.read_text(encoding="utf-8").strip())

    parts.append("# CONTEXT: 商品事实（唯一事实来源，来自 facts.json）\n\n"
                 + "\n".join(fact_lines(facts)))

    if args.findings:
        fpath = Path(args.findings)
        if not fpath.exists():
            raise SystemExit(f"找不到明细 CSV：{fpath}")
        rows = load_findings(fpath, args.sku)
        if not rows:
            print(f"{args.sku} 在明细里没有违规项，不需要改稿。")
            raise SystemExit(2)
        draft = current_draft(args, args.sku)
        if not draft:
            raise SystemExit("改稿模式需要当前草稿：加 --draft-json 或 --batch")
        parts.append(draft)
        parts.append(format_violations(rows))
        print(f"改稿模式：{args.sku} 命中 {len(rows)} 条违规")

    body = "\n\n---\n\n".join(parts)
    body += "\n\n---\n\n# PATTERN\n\n" + system.replace("{{SITE}}", args.site).replace("{{LANGUAGE}}", LANG[args.site])
    body += f"\n\n商品：{args.sku}\n"

    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()[:16]
    header = (f"<!-- pattern: {meta['name']}@{meta['version']} | renderer: {RENDERER_VERSION} | "
              f"site: {args.site} | sku: {args.sku} | sha256: {digest} | {datetime.now():%Y-%m-%d %H:%M:%S} -->\n")
    text = header + body

    if args.do_print:
        print(text)
        return

    suffix = "-fix" if args.findings else ""
    out = Path(args.out) if args.out else ROOT / "output" / "_prompts" / f"{args.sku}{suffix}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(f"pattern：{meta['name']}@{meta['version']}")
    print(f"contexts：{len(meta.get('contexts', []))} 个（类目={category}，站点={args.site}）")
    print(f"长度：{len(text)} 字符")
    print(f"输出：{out}")


if __name__ == "__main__":
    main()
