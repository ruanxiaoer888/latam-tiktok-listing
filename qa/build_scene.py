# -*- coding: utf-8 -*-
r"""build_scene.py — 从美客多原始描述里抽「场景 / 痛点 / 差异点 / 注意事项」，供 Listing 生成时做“具体化”依据。

背景：facts.json 只有参数，没有“客户为什么买、用在哪、和普通款差在哪”，
生成端只能编场景，导致首屏钩子空泛、卖点像参数表。
本脚本只做**抽取**（原文里已有的话），不推断、不翻译、不新增事实。

产物（不进 git）：
    output\_batch\scene\<SKU>.md      每个 SKU 一份（给生成 Agent 读，约 30 行）
    output\_batch\scene\_index.md     汇总索引

用法：
    python qa\build_scene.py                 # 只处理 input\*\item.json 存在的 SKU
    python qa\build_scene.py --only SKU1,SKU2
"""
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INPUT = ROOT / "input"
OUT = ROOT / "output" / "_batch" / "scene"

# 平台宣传/店铺套话，全部丢弃（含 Mercado Libre 字样，不能带进 TikTok）
DROP_PAT = re.compile(
    r"(mercado\s*libre|env[ií]o gratis|299 pesos|bienvenido|nuestra tienda|"
    r"nuestros otros productos|reclamo|calificaci[oó]n positiva|experiencia de compra|"
    r"cont[aá]ctenos|comun[ií]quese|whatsapp|facebook|instagram)",
    re.I,
)
USAGE_PAT = re.compile(
    r"(usos recomendados|apto para|aplicaci[oó]n(es)?|alcance de la aplicaci[oó]n|"
    r"ideal para|adecuado para|perfecto para|se utiliza|se usa|para uso)",
    re.I,
)
PAIN_PAT = re.compile(
    r"(evita|sin necesidad|no da[nñ]a|ahorra|reduce|f[aá]cil de|problema|cansancio|"
    r"riesgo|no se afloja|no resbala|estable|precisi[oó]n)",
    re.I,
)
NOTE_PAT = re.compile(
    r"(^nota|^notas|advertencia|precauci[oó]n|tenga en cuenta|no exceda|no se recomienda|"
    r"cuidado|importante:)",
    re.I,
)
NOT_INCL_PAT = re.compile(
    r"(no incluye[^.\n]{0,90}|sin bater[ií]a[^.\n]{0,60}|bater[ií]a no incluida[^.\n]{0,60}|"
    r"no viene con[^.\n]{0,70}|no se incluye[^.\n]{0,70})",
    re.I,
)
NUM_ITEM = re.compile(r"^\s*(?:\(?(\d{1,2})\)?[\.\)、]|[-•*])\s*(.+)$")


def clean(s):
    s = re.sub(r"\s+", " ", str(s or "")).strip(" .;:-")
    s = re.sub(r"^[>#\s]+", "", s)
    return s


def sentences(s):
    return [clean(x) for x in re.split(r"(?<=[.!?])\s+", clean(s)) if clean(x)]


def parse_sections(text):
    """按 >>> 标记切段，返回 [(title, [lines])]。"""
    text = text.replace("\r", "")
    i = text.find("IMPORTANTE")
    if i > 0:
        text = text[:i]
    sections, cur = [], {"title": "(head)", "lines": []}
    for raw in text.split("\n"):
        line = raw.strip()
        if line.startswith(">>>"):
            sections.append(cur)
            cur = {"title": clean(line.strip(">").strip(" :")), "lines": []}
        else:
            cur["lines"].append(line)
    sections.append(cur)
    return sections


def extract(desc_text):
    out = {"package": [], "specs": [], "usage": [], "benefits": [], "notes": [],
           "not_included": []}
    for sec in parse_sections(desc_text):
        title, lines = sec.get("title") or "", sec.get("lines") or []
        tl = title.lower()
        is_list = "lista de productos" in tl
        is_carac = "caracter" in tl
        is_info = "informaci" in tl
        is_note = "nota" in tl
        for line in lines:
            if not line or DROP_PAT.search(line):
                continue
            if is_list:
                if line.startswith((">", "---")):
                    continue
                item = clean(line)
                if item and len(item) < 160:
                    out["package"].append(item)
                continue
            if is_carac:
                m = NUM_ITEM.match(line)
                if m:
                    body = m.group(2)
                    if USAGE_PAT.search(body):
                        out["usage"].append(clean(re.sub(r"^[^:]{0,50}:", "", body))[:200])
                    else:
                        sents = sentences(body)
                        if sents:
                            out["benefits"].append(sents[0][:200])
                continue
            if is_note or NOTE_PAT.search(line):
                out["notes"].append(clean(line)[:200])
                continue
            if USAGE_PAT.search(line):
                out["usage"].append(clean(re.sub(r"^[^:]{0,40}:", "", line))[:200])
                continue
            if is_info and ":" in line:
                k, v = line.split(":", 1)
                if clean(k) and clean(v) and len(clean(k)) < 40:
                    out["specs"].append("%s: %s" % (clean(k), clean(v)[:120]))
                continue
            if PAIN_PAT.search(line):
                sents = sentences(re.sub(r"^[^:]{0,40}:", "", line)) if ":" in line else sentences(line)
                if sents:
                    out["benefits"].append(sents[0][:200])
    for m in NOT_INCL_PAT.finditer(desc_text or ""):
        out["not_included"].append(clean(m.group(0)))

    # 去重 + 限制条数（给 Agent 的上下文要短）
    def dedup(seq, n):
        seen, res = set(), []
        for x in seq:
            k = re.sub(r"\W+", "", x.lower())[:60]
            if k and k not in seen:
                seen.add(k)
                res.append(x)
        return res[:n]

    out["package"] = dedup(out["package"], 30)
    out["specs"] = dedup(out["specs"], 14)
    out["usage"] = dedup(out["usage"], 6)
    out["benefits"] = dedup(out["benefits"], 8)
    out["notes"] = dedup(out["notes"], 6)
    out["not_included"] = dedup(out["not_included"], 4)
    return out


def fnum(v):
    return "" if v is None else str(v)


def main():
    for s in (sys.stdout, sys.stderr):
        if hasattr(s, "reconfigure"):
            s.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-root", default=str(INPUT))
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--only", default="")
    args = ap.parse_args()

    root = Path(args.input_root).resolve()
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    only = {x.strip() for x in args.only.split(",") if x.strip()}

    rows, n = [], 0
    for d in sorted(root.iterdir()):
        if not d.is_dir() or (only and d.name not in only):
            continue
        item = d / "item.json"
        facts = d / "facts.json"
        if not item.exists():
            continue
        it = json.load(open(item, encoding="utf-8-sig"))
        fa = json.load(open(facts, encoding="utf-8-sig")) if facts.exists() else {}
        desc = (it.get("description") or {}).get("text") or ""
        ext = extract(desc)
        scene = {
            "sku": d.name,
            "category": fa.get("category") or (it.get("category") or {}).get("bucket_zh") or "",
            "status": fa.get("status") or "no-facts",
            "title_raw": fa.get("identity", {}).get("title_raw") or it.get("title") or "",
            "core_keyword": (fa.get("extras") or {}).get("core_keyword") or it.get("core_keyword") or "",
            "price": ((fa.get("site_profiles") or {}).get("MX") or {}).get("price"),
            "images": len(fa.get("images") or []),
            "desc_chars": len(desc),
            **ext,
        }
        (out / (d.name + ".json")).write_text(json.dumps(scene, ensure_ascii=False, indent=1), encoding="utf-8")

        lines = ["# %s · %s · %s" % (scene["sku"], scene["category"], scene["status"]), ""]
        lines.append("- 原标题（ML）：%s" % scene["title_raw"])
        lines.append("- 平台核心词：%s" % (scene["core_keyword"] or "-"))
        lines.append("- 原图：%d 张　原文长度：%d 字符" % (scene["images"], scene["desc_chars"]))
        lines.append("")
        lines.append("## 场景与用途（原文依据，可改写语言，不可新增）")
        lines += ["- " + x for x in (ext["usage"] or ["（原文没有明确写用途，只能从品类常识写通用场景，不得编具体机型/场景）"])]
        lines.append("")
        lines.append("## 卖点/差异化（原文要点，改写成人话）")
        lines += ["- " + x for x in (ext["benefits"] or ["（原文无结构化卖点）"])]
        lines.append("")
        lines.append("## 原文规格（只用于核对；正文参数一律以 facts.json 为准）")
        lines += ["- " + x for x in (ext["specs"] or ["-"])]
        lines.append("")
        lines.append("## 原文包装清单（正文以 facts.package.included 为准）")
        lines += ["- " + x for x in (ext["package"] or ["-"])]
        if ext["not_included"]:
            lines.append("")
            lines.append("## 原文「不含」（写正文时必须保留）")
            lines += ["- " + x for x in ext["not_included"]]
        if ext["notes"]:
            lines.append("")
            lines.append("## 使用/安全提示（可放进 FAQ 或规格脚注）")
            lines += ["- " + x for x in ext["notes"]]
        (out / (d.name + ".md")).write_text("\n".join(lines) + "\n", encoding="utf-8")
        rows.append(scene)
        n += 1

    idx = ["# 场景摘要索引（%d 个 SKU）" % n, "",
           "| SKU | 类目 | 状态 | 原文场景 | 原文卖点 | 包装项 | 提示 |", "|---|---|---|---|---|---|---|"]
    for s in rows:
        idx.append("| %s | %s | %s | %d | %d | %d | %d |" % (
            s["sku"], s["category"], s["status"], len(s["usage"]), len(s["benefits"]),
            len(s["package"]), len(s["notes"])))
    (out / "_index.md").write_text("\n".join(idx) + "\n", encoding="utf-8")
    print("生成 %d 个 SKU 场景摘要 -> %s" % (n, out))


if __name__ == "__main__":
    main()
