# -*- coding: utf-8 -*-
"""
Listing 合规校验器 v1.1

用法（在本文件所在目录执行，或给绝对路径）：
  python check_listing.py --demo --site MX
  python check_listing.py --input 你的导出.csv --site BR
  python check_listing.py --input 你的导出.xlsx --site MX --category 家电
  python check_listing.py --input 你的导出.csv --site MX --fail-on-p0

v1.1 新增：
  --category        检查该类目"必带信息"是否缺失（P2 提醒）
  核心词列          输入带"核心词/keyword"列时，检查核心词是否落在标题前 30 字符
  类目列            输入带"类目/category"列时，按行自动套用类目检查
  --fail-on-p0      出现 P0 时退出码 3，方便自动化卡口
  报告按日期分目录   qa/报告/<YYYYMMDD>/

输出：
  qa/报告/<日期>/合规扫描_<site>_<来源>_<时间>.md
  qa/报告/<日期>/明细_<site>_<来源>_<时间>.csv

支持输入：
  .csv / .xlsx   需含标题、描述两列（列名模糊匹配）；可选 核心词、类目、SKU 列
  .md            兼容 Gemini V3.2 案例库格式（**Título**: / **Descripción**:）
  .txt           每行一条：标题<TAB>描述

退出码：0 正常；2 参数/文件错误；3 出现 P0（仅 --fail-on-p0 时）
"""
import argparse
import csv
import json
import re
import sys
import unicodedata
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent
ROOT = BASE.parent
DEFAULT_RULES = BASE / "denylist.json"
REPORT_DIR = BASE / "报告"

COL_ID = ["id", "商品id", "商品编号", "sku", "product_id", "item_id", "货号"]
COL_TITLE = ["标题", "title", "título", "titulo", "nombre", "product_title", "商品标题"]
COL_DESC = ["描述", "description", "descripción", "descripcion", "descricao", "descrição",
            "desc", "body", "商品描述", "详情"]
COL_KEYWORD = ["核心词", "关键词", "keyword", "palabra clave", "palavra-chave"]
COL_CATEGORY = ["类目", "category", "categoría", "categoria", "品类"]

CHINESE = re.compile(r"[\u4e00-\u9fff]")
PLACEHOLDER = re.compile(r"\[\s*POR\s+CONFIRMAR\s*\]", re.I)
HASHTAG = re.compile(r"#[^\s#]{2,}")
EMOJI = re.compile("[\U0001F300-\U0001FAFF\u2600-\u27BF]")
# 结构标签：只抓"模型腔"的整行标签（Gancho: / Título: / Descripción:），
# 不抓 📋 Especificaciones 这种正常分段标题（那是骨架要求的）
STRUCT_LINE = re.compile(r"^\s*(gancho|t[ií]tulo|descripci[óo]n|caracter[ií]sticas)\s*[:：]", re.I)
STRUCT_PHRASES = ["以下是", "here is", "aquí tienes", "卖点1", "卖点2", "卖点3"]
SECTION_MARKS = {"📋", "📦", "💡"}
PERCENT = re.compile(r"100\s*%|cien\s+por\s+ciento|cem\s+por\s+cento", re.I)
WORDS = re.compile(r"[^\W\d_]{3,}")
STOPWORDS = {"de", "del", "la", "el", "los", "las", "y", "o", "para", "con", "en", "un", "una", "por"}
# 英制单位残留（V3.2 要求全部换算公制）
UNIT_RE = re.compile(r"\d+(?:[.,]\d+)?\s?(inch|pulgadas?|pulg\.?|lbs?|oz)\b", re.I)


def die(msg, code=2):
    """统一报错出口：写 stderr（UTF-8）并给指定退出码。"""
    try:
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    sys.stderr.write(msg + "\n")
    raise SystemExit(code)


# ---------------------------------------------------------------- 读数
def norm(s):
    return (s or "").strip()


def fold(s):
    """去重音 + 小写，用于核心词比对（ML 的核心词一般不带重音）"""
    s = unicodedata.normalize("NFD", (s or "").lower())
    return "".join(c for c in s if not unicodedata.combining(c))


def pick(cols, candidates):
    low = {str(c).strip().lower(): c for c in cols}
    for cand in candidates:
        if cand in low:
            return low[cand]
    for key, orig in low.items():
        for cand in candidates:
            if cand in key:
                return orig
    return None


def _rows_from_table(header, body):
    c_id = pick(header, COL_ID)
    c_title = pick(header, COL_TITLE)
    c_desc = pick(header, COL_DESC)
    if not c_title or not c_desc:
        # 无表头：按列位置取，第一列标题、第二列描述
        return [{"id": norm(r[0]) or f"row{i+1}", "title": norm(r[0]),
                 "desc": norm(r[1]) if len(r) > 1 else "",
                 "keyword": "", "category": ""} for i, r in enumerate(body)]
    cols = {"id": c_id, "title": c_title, "desc": c_desc,
            "keyword": pick(header, COL_KEYWORD), "category": pick(header, COL_CATEGORY)}
    idx = {name: header.index(c) for name, c in cols.items() if c}
    out = []
    for r in body:
        get = lambda k: r[idx[k]] if k in idx and idx[k] < len(r) else ""
        out.append({"id": norm(get("id")) or f"row{len(out)+1}",
                    "title": norm(get("title")), "desc": norm(get("desc")),
                    "keyword": norm(get("keyword")), "category": norm(get("category"))})
    return out


def read_csv(path):
    rows = None
    for enc in ("utf-8-sig", "gb18030", "utf-8", "latin-1"):
        try:
            with open(path, "r", encoding=enc, newline="") as f:
                sample = f.read(4096)
                f.seek(0)
                try:
                    dialect = csv.Sniffer().sniff(sample, delimiters=",\t;")
                except csv.Error:
                    dialect = csv.excel
                rows = list(csv.reader(f, dialect))
            break
        except UnicodeDecodeError:
            continue
    if rows is None:
        die(f"无法解码文件：{path}")
    if not rows:
        return []
    return _rows_from_table(rows[0], rows[1:])


def read_xlsx(path):
    try:
        from openpyxl import load_workbook
    except ImportError:
        die("读 xlsx 需要 openpyxl；请改用 CSV，或用带 openpyxl 的 Python 运行")
    wb = load_workbook(path, read_only=True, data_only=True)
    ws = wb.active
    data = [["" if c is None else str(c) for c in row] for row in ws.iter_rows(values_only=True)]
    wb.close()
    if not data:
        return []
    return _rows_from_table(data[0], data[1:])


def read_demo_md(path):
    """解析 Gemini V3.2 案例库：### Caso N: 标题 / **Título**: / **Descripción**:"""
    text = path.read_text(encoding="utf-8")
    blocks = re.split(r"^###\s*Caso\s*\d+\s*[:：]", text, flags=re.M)[1:]
    rows = []
    for i, b in enumerate(blocks, 1):
        name = b.strip().splitlines()[0].strip() if b.strip() else f"Caso {i}"
        m = re.search(r"\*\*T[íi]tulo\*\*\s*[:：]\s*\n?\s*(.+)", b)
        title = m.group(1).strip() if m else ""
        desc = ""
        if "**Descripción**:" in b:
            desc = b.split("**Descripción**:", 1)[1]
        elif "**Descripción**：" in b:
            desc = b.split("**Descripción**：", 1)[1]
        desc = desc.split("\n---")[0].strip()
        rows.append({"id": f"Caso {i} {name}", "title": title, "desc": desc,
                     "keyword": "", "category": ""})
    return rows


def read_txt(path):
    rows = []
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        parts = re.split(r"\t|\s\|\s", line, maxsplit=1)
        rows.append({"id": f"line{i}", "title": parts[0].strip(),
                     "desc": parts[1].strip() if len(parts) > 1 else "",
                     "keyword": "", "category": ""})
    return rows


def load_rows(path: Path):
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return read_csv(path)
    if suffix == ".xlsx":
        return read_xlsx(path)
    if suffix == ".md":
        return read_demo_md(path)
    return read_txt(path)


# ---------------------------------------------------------------- 校验
def snippet(text, start, width=60):
    s = max(0, start - width // 2)
    frag = text[s:s + width].replace("\n", " ")
    return re.sub(r"\s+", " ", frag).strip()


def check_row(row, site, cfg, g, cats=None, default_cat=""):
    findings = []
    title, desc = row.get("title", ""), row.get("desc", "")
    body = f"{title}\n{desc}"

    def add(sev, cid, label, field, snip, fix="", pos=-1):
        findings.append({"severity": sev, "id": cid, "label": label,
                         "field": field, "snippet": snip, "fix": fix, "pos": pos})

    # P0/P1：空字段（多半是导出列名没匹配上，静默放过最危险）
    if not title:
        add("P0", f"{site}-P0-TITLE-EMPTY", "标题为空（导出列名或内容缺失）",
            "标题", "", "检查导出文件的列名是否为 标题/title")
    if not desc:
        add("P1", f"{site}-P1-DESC-EMPTY", "描述为空（导出列名或内容缺失）",
            "描述", "", "检查导出文件的列名是否为 描述/description")

    # P0：中文字符
    for field, text in (("标题", title), ("描述", desc)):
        m = CHINESE.search(text)
        if m:
            add("P0", f"{site}-P0-CHINESE", "含中文字符（上架大概率失败）",
                field, snippet(text, m.start()), "删除或翻译成站点语言")

    # P0：占位符
    for field, text in (("标题", title), ("描述", desc)):
        m = PLACEHOLDER.search(text)
        if m:
            add("P0", f"{site}-P0-PLACEHOLDER", "含 [POR CONFIRMAR] 占位符",
                field, snippet(text, m.start()), "补齐参数后再上架")

    # P0/P2：标题长度
    tcfg = cfg["title"]
    if title:
        if len(title) > tcfg["max"]:
            add("P0", f"{site}-P0-TITLE-MAX", f"标题超上限（>{tcfg['max']}）",
                "标题", f"当前 {len(title)} 字符：{title[:40]}…", "截断或拆分")
        elif len(title) < tcfg["min"]:
            add("P0", f"{site}-P0-TITLE-MIN", f"标题过短（<{tcfg['min']}）",
                "标题", f"当前 {len(title)} 字符：{title}", "补充品类词与核心规格")
        else:
            lo, hi = tcfg["recommended"]
            if not (lo <= len(title) <= hi):
                add("P2", f"{site}-P2-TITLE-LEN", f"标题不在建议区间 {lo}-{hi}（移动端）",
                    "标题", f"当前 {len(title)} 字符", "压缩到 60-80 更利于手机端展示")

    # P2：核心词覆盖（不要求整句连续命中，按"词"判断；忽略重音和虚词）
    kw = (row.get("keyword") or "").strip()
    if kw and title:
        tfold = fold(title)
        front = tcfg["keyword_front"]
        kw_words = [w for w in re.findall(r"[^\W\d_]{3,}", fold(kw)) if w not in STOPWORDS]
        missing = [w for w in kw_words if w not in tfold]
        if missing:
            add("P2", f"{site}-P2-KEYWORD", "标题缺核心词片段：" + "、".join(missing), "标题",
                title[:40], f"补进标题前 {front} 字符；核心词：{kw}")
        elif kw_words:
            pos = tfold.find(kw_words[0])
            if pos >= front:
                add("P2", f"{site}-P2-KEYWORD", f"核心词首字「{kw_words[0]}」在第 {pos + 1} 字符（>{front}）",
                    "标题", title[:40], f"前移到前 {front} 字符内")

    # P2：标题重复词（疑似堆砌）
    if title:
        words = [w.lower() for w in WORDS.findall(title)]
        dup = {w: words.count(w) for w in set(words) if words.count(w) >= 3}
        if dup:
            top = sorted(dup.items(), key=lambda x: -x[1])[:4]
            add("P2", f"{site}-P2-STUFF", "标题重复词（疑似堆砌）", "标题",
                "、".join(f"{w}×{n}" for w, n in top), "删掉重复词，读起来像人话")

    # P0/P2：描述长度
    dcfg = cfg["description"]
    if len(desc) > dcfg["max"]:
        add("P0", f"{site}-P0-DESC-MAX", f"描述超上限（>{dcfg['max']}）", "描述",
            f"当前 {len(desc)} 字符", "删减")
    elif desc and len(desc) < dcfg["recommended_min"]:
        add("P2", f"{site}-P2-DESC-MIN", f"描述偏短（<{dcfg['recommended_min']} 字符）", "描述",
            f"当前 {len(desc)} 字符", "补充材质/规格/包装/FAQ")

    # P2：度量衡未换算（V3.2 硬规则：inch/lb/oz 必须转公制）
    # 例外：同一处已经同时给出 cm/mm 的，视为已换算（如 "12 Pulgadas (30.48 cm)"）
    m = UNIT_RE.search(body)
    if m:
        window = body[max(0, m.start() - 30): m.end() + 30]
        if not re.search(r"\d+\s?(cm|mm)\b", window, re.I):
            add("P2", f"{site}-P2-UNIT", "度量衡未换算成公制", "描述",
                snippet(body, m.start()), "inch→cm、lb→kg、oz→ml；本地只认公制")

    # P2：价格未带币种（V3.2 硬规则）
    cur = cfg.get("currency", "")
    if "$" in body:
        ok = (cur == "MXN" and re.search(r"MXN", body, re.I)) or (cur == "BRL" and "R$" in body)
        if not ok:
            add("P2", f"{site}-P2-CURRENCY", f"价格未标币种（应为 {cur}）", "描述",
                snippet(body, body.find("$")), "价格必须带币种：$299 MXN / R$ 199,90")

    # P2：类目必带信息（缺了不一定上不了架，但一定影响转化/退货）
    cat = (row.get("category") or default_cat or "").strip()
    if cats and cat:
        entry = cats.get(cat)
        if entry:
            for item in entry.get("required", []):
                # 条件必带：if_pattern 不命中就跳过（如手动工具不需要电压/功率）
                if item.get("if_pattern") and not re.search(item["if_pattern"], body, re.I):
                    continue
                if not re.search(item["pattern"], body, re.I):
                    add("P2", f"{site}-P2-CAT-REQ", f"可能缺必带信息：{item['label']}",
                        "描述", f"类目「{cat}」未检出「{item['label']}」",
                        "按类目包补齐后再上架")

    # P1/P2：词表
    for c in cfg["checks"]:
        ctype = c["type"]
        if ctype == "terms":
            for term in c["terms"]:
                m = re.search(re.escape(term), body, re.I)
                if m:
                    field = "标题" if re.search(re.escape(term), title, re.I) else "描述"
                    add(c["severity"], c["id"], c["label"], field,
                        snippet(body, m.start()), c.get("fix", ""), m.start())
        elif ctype == "foreign":
            if any(f["id"] == c["id"] for f in findings):
                continue
            pos = -1
            for term in c["terms"]:
                m = re.search(r"(?<!\w)" + re.escape(term) + r"(?!\w)", body, re.I)
                if m:
                    pos = m.start()
                    break
            if pos < 0:
                for ch in c.get("chars", []):
                    i = body.find(ch)
                    if i >= 0:
                        pos = i
                        break
            if pos >= 0:
                add(c["severity"], c["id"], c["label"], "描述",
                    snippet(body, pos), c.get("fix", ""), pos)
        elif ctype == "hashtag":
            hits = HASHTAG.findall(desc)
            if len(hits) > 5:
                add(c["severity"], c["id"], c["label"], "描述",
                    f"共 {len(hits)} 个：{' '.join(hits[:6])}…", c.get("fix", ""))
            elif hits:
                add("P2", c["id"] + "-INFO", c["label"] + "（少量）", "描述",
                    " ".join(hits[:6]), c.get("fix", ""))

    # 100% 上下文判定（与绝对化词条命中去重，避免同一处报两遍）
    for m in PERCENT.finditer(body):
        window = body[m.end(): m.end() + 45].lower()
        if any(w in window for w in g["material_words"]):
            continue
        if any(f["pos"] >= 0 and abs(f["pos"] - m.start()) < 50
               and ("ABSOLUTE" in f["id"] or "MEDICAL" in f["id"]) for f in findings):
            continue
        add("P1", f"{site}-P1-PERCENT", "绝对化 100% 宣称",
            "标题" if m.start() < len(title) else "描述",
            snippet(body, m.start()), "材质成分可保留；保证/效果语境必须删除", m.start())

    # 结构标签残留（只抓"模型腔"的整行标签与前言，不误伤 📋 Especificaciones 这类正常分段）
    for line in desc.splitlines():
        if STRUCT_LINE.match(line) and not any(mk in line for mk in SECTION_MARKS):
            add("P2", f"{site}-P2-LABEL", "残留结构标签（模型腔）", "描述",
                line.strip()[:50], "删除标签行，正文只保留内容本身")
            break
    for ph in STRUCT_PHRASES:
        i = body.lower().find(ph.lower())
        if i >= 0:
            add("P2", f"{site}-P2-LABEL", "残留前言/结构提示", "描述",
                snippet(body, i), "删除前言，直接输出正文")
            break

    # 排版：必需分段
    if desc:
        for mark, name in (("📋", "规格段"), ("📦", "包装清单段"), ("💡", "FAQ 段")):
            if mark not in desc:
                add("P2", f"{site}-P2-SECTION", f"缺少{name}（{mark}）", "描述", "", "按骨架补齐")

    # 排版：单行装饰性 Emoji 超 2 个（📋📦💡 是结构符号，不计入）
    for line in desc.splitlines():
        deco = [e for e in EMOJI.findall(line) if e not in SECTION_MARKS]
        if len(deco) > 2:
            add("P2", f"{site}-P2-EMOJI", "单行装饰性 Emoji 超过 2 个", "描述",
                line.strip()[:50], "每行最多 2 个")
            break

    return findings


# ---------------------------------------------------------------- 输出
SEV_ORDER = {"P0": 0, "P1": 1, "P2": 2}


def write_reports(rows, results, site, source, out_dir, slug="scan"):
    day = datetime.now().strftime("%Y%m%d")
    out_dir = out_dir / day
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M")
    safe = re.sub(r"[^\w\-]+", "_", slug)[:24]
    md_path = out_dir / f"合规扫描_{site}_{safe}_{ts}.md"
    csv_path = out_dir / f"明细_{site}_{safe}_{ts}.csv"

    total = {"P0": 0, "P1": 0, "P2": 0}
    per_check = {}
    for f in results:
        total[f["severity"]] += 1
        per_check.setdefault((f["id"], f["label"], f["severity"]), 0)
        per_check[(f["id"], f["label"], f["severity"])] += 1
    hit_rows = len({f["row_id"] for f in results})

    lines = [
        f"# Listing 合规扫描报告 · {site}",
        "",
        f"- 扫描时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"- 数据来源：`{source}`",
        f"- 样本条数：{len(rows)}　命中条数：{hit_rows}　命中率：{(hit_rows/len(rows)*100 if rows else 0):.0f}%",
        "",
        "## 一、总览",
        "",
        "| 严重度 | 命中数 | 含义 |",
        "|---|---|---|",
        f"| P0 | {total['P0']} | 上架必失败/必被拒（中文、超长、占位符） |",
        f"| P1 | {total['P1']} | 违规或误导风险（禁词、未验证承诺、跨语言） |",
        f"| P2 | {total['P2']} | 影响转化与流量（排版、长度、核心词、必带信息） |",
        "",
        "## 二、按检查项",
        "",
        "| 检查项 | 严重度 | 命中数 |",
        "|---|---|---|",
    ]
    for (cid, label, sev), n in sorted(per_check.items(), key=lambda x: (SEV_ORDER[x[0][2]], -x[1])):
        lines.append(f"| {cid} · {label} | {sev} | {n} |")

    lines += ["", "## 三、逐条命中明细", ""]
    by_row = {}
    for f in results:
        by_row.setdefault(f["row_id"], []).append(f)
    for row in rows:
        fs = by_row.get(row["id"])
        if not fs:
            continue
        lines.append(f"### {row['id']}")
        lines.append("")
        lines.append(f"- 标题：{row['title'][:90]}")
        for f in sorted(fs, key=lambda x: SEV_ORDER[x["severity"]]):
            lines.append(f"- **[{f['severity']}] {f['label']}**（{f['field']}）：`{f['snippet']}` → {f['fix']}")
        lines.append("")

    clean = len(rows) - hit_rows
    lines += [
        "## 四、结论",
        "",
        f"- 干净条目：{clean} 条 / {len(rows)} 条",
        f"- P0 命中 {total['P0']} 处：这些是机器能直接判死的，必须清零。",
        f"- P1 命中 {total['P1']} 处：违规或误导风险，优先清。",
        f"- P2 命中 {total['P2']} 处：影响转化与流量，不影响上架。",
        "- 处理顺序：P0 → P1 → P2。P2 里「必带信息缺失」建议优先，直接关联退货率。",
        "",
    ]
    md_path.write_text("\n".join(lines), encoding="utf-8")

    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["商品ID", "严重度", "检查项", "说明", "字段", "命中片段", "建议"])
        for r in results:
            w.writerow([r["row_id"], r["severity"], r["id"], r["label"],
                        r["field"], r["snippet"], r["fix"]])
    return md_path, csv_path, total, hit_rows


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="Listing 合规校验器 v1.1")
    ap.add_argument("--input", help="CSV / XLSX / MD / TXT 文件路径")
    ap.add_argument("--demo", action="store_true", help="用 source-gemini 里的 9 条案例做自检")
    ap.add_argument("--site", default="MX", help="站点（按 denylist.json 里的键：MX / BR）")
    ap.add_argument("--category", default="", help="类目名（五金工具/汽车摩托/家居建材/运动户外/宠物用品/厨房用品/家电/时尚配件）")
    ap.add_argument("--out", default=str(REPORT_DIR), help="报告输出目录（会自动按日期建子目录）")
    ap.add_argument("--fail-on-p0", action="store_true", help="出现 P0 时退出码 3")
    args = ap.parse_args()

    rules = json.loads(DEFAULT_RULES.read_text(encoding="utf-8"))
    sites = rules["sites"]
    if args.site not in sites:
        die(f"站点 {args.site} 不存在；可用：{', '.join(sites)}")
    cfg, g = sites[args.site], rules["global"]
    cats = rules.get("categories", {})

    if args.category and cats and args.category not in cats:
        die(f"类目 {args.category} 不存在；可用：{', '.join(cats)}")

    if args.demo:
        src = ROOT / "source-gemini" / "2_案例库与排版模板_V3.2.md"
        if not src.exists():
            die(f"找不到案例库：{src}")
    elif args.input:
        src = Path(args.input).expanduser().resolve()
        if not src.exists():
            die(f"找不到输入文件：{src}")
    else:
        ap.print_help()
        raise SystemExit(2)

    rows = load_rows(src)
    if not rows:
        die("没有读到任何商品行，检查列名/文件格式")

    results = []
    for row in rows:
        for f in check_row(row, args.site, cfg, g, cats, args.category):
            f["row_id"] = row["id"]
            results.append(f)

    md, csvf, total, hit_rows = write_reports(rows, results, args.site, src, Path(args.out),
                                              slug="demo" if args.demo else src.stem)
    print(f"样本 {len(rows)} 条，命中 {hit_rows} 条（P0={total['P0']} P1={total['P1']} P2={total['P2']}）")
    print(f"报告：{md}")
    print(f"明细：{csvf}")
    if args.fail_on_p0 and total["P0"] > 0:
        raise SystemExit(3)


if __name__ == "__main__":
    main()
