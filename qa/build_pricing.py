# -*- coding: utf-8 -*-
r"""
利润定价表：把「挂牌价 -> 真实净利 -> 采购成本上限」算清楚，输出可编辑的 xlsx。

单件、成交口径的核心公式：
  预计成交价    F = 挂牌价 x 折扣系数
  退款后净收入  I = F x (1 - 平台扣点) x (1 - 退款率)
  履约成本      J = F x 履约率 + 固定包装
  单件净利      O = I - 采购价 x (1 + 头程率) - J
  净利率        P = O / F
  采购成本上限  L = (I - J - 目标净利率 x F) / (1 + 头程率)

折扣系数取老店实测（12 个 SKU 实收/挂牌 = 0.631），其余费率是可改的假设，
全部集中在「费率假设」页，改完 Excel/WPS 会自动重算。

用法：
  python qa\build_pricing.py                          # 首批 12 条
  python qa\build_pricing.py --all                    # 所有 verified（带 MX 价格）
  python qa\build_pricing.py --skus A,B,C             # 指定 SKU
  python qa\build_pricing.py --out output\_利润\x.xlsx
"""
import argparse
import datetime as dt
import json
import sys
from pathlib import Path

from openpyxl import Workbook
from openpyxl.formatting.rule import CellIsRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

ROOT = Path(__file__).resolve().parent.parent
INPUT = ROOT / "input"
OUT_DIR = ROOT / "output" / "_利润"

# 首批 12 条（按挂牌价升序）
FIRST_BATCH = [
    "ABU3C50000", "ME260105", "ME260104", "AMU600000G", "ME260117", "ZK26050816",
    "AMU600000J", "ATVMX22700", "ATVMX15600", "ABU6000019", "ZK2604270H", "ATVMX09400",
]

# 假设值：(key, 名称, 值, 单位, 数字格式, 来源/说明)
ASSUMPTIONS = [
    ("discount", "实测折扣系数（成交价/挂牌价）", 0.631, "倍", "0.000",
     "老店 12 个 SKU 实测：实收/挂牌 均值 0.631（区间 0.44~0.95）。硬数据，别随便改高。"),
    ("commission", "平台佣金", 0.08, "比例", "0.0%",
     "TikTok Shop MX 类目佣金，按你后台实际扣点核实后改。"),
    ("payment", "支付/结算手续费", 0.025, "比例", "0.0%",
     "收款通道费，待核实；本土店跨境店口径不同。"),
    ("fulfil_rate", "履约成本率（占成交价）", 0.08, "比例", "0.0%",
     "本地仓配/尾程派送。待核实。"),
    ("pack_fixed", "每单固定包装", 15, "MXN", "0.00",
     "加固包装盒+填充。老店破损退货占 18.7%，这项别省。"),
    ("freight_rate", "头程+清关（占采购价）", 0.15, "比例", "0.0%",
     "海运集运+清关分摊。待核实。"),
    ("refund_rate", "退款率", 0.25, "比例", "0.0%",
     "中性情景。老店实测 41%，目标 15%（见「情景对比」页）。"),
    ("target_margin", "目标净利率", 0.20, "比例", "0.0%",
     "净利润/成交价。低于 10% 不建议规模化铺货。"),
    ("fx", "汇率 CNY -> MXN", 2.60, "MXN/CNY", "0.000",
     "按实际结汇价更新；只影响人民币列。"),
]

A_ROW = {}  # key -> 费率假设 页的行号


def load_facts(root: Path):
    out = {}
    for d in sorted(root.iterdir()):
        f = d / "facts.json"
        if not f.is_file():
            continue
        try:
            j = json.loads(f.read_text(encoding="utf-8-sig"))
        except Exception:
            continue
        out[d.name] = j
    return out


def short_name(j):
    ident = j.get("identity") or {}
    t = ident.get("title_raw") or ""
    if not t:
        return ""
    t = " ".join(str(t).split())
    return t if len(t) <= 46 else t[:45] + "…"


def pick_skus(args, facts):
    if args.skus:
        return [s.strip() for s in args.skus.split(",") if s.strip()]
    if args.all:
        rows = []
        for sku, j in facts.items():
            if j.get("status") != "verified":
                continue
            if ((j.get("site_profiles") or {}).get("MX") or {}).get("price"):
                rows.append((sku, j))
        rows.sort(key=lambda kv: kv[1]["site_profiles"]["MX"]["price"])
        return [kv[0] for kv in rows]
    return list(FIRST_BATCH)


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-root", default=str(INPUT))
    ap.add_argument("--skus", default="")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    root = Path(args.input_root).resolve()
    facts = load_facts(root)
    skus = pick_skus(args, facts)

    out = Path(args.out) if args.out else (
        OUT_DIR / ("利润定价表-全部.xlsx" if args.all else "利润定价表-首批12条.xlsx"))
    out.parent.mkdir(parents=True, exist_ok=True)

    wb = Workbook()
    ws = wb.active
    ws.title = "定价明细"
    fz = wb.create_sheet("费率假设")
    sc = wb.create_sheet("情景对比", 2)
    rev = wb.create_sheet("报价反查")
    base = wb.create_sheet("老店基准")
    how = wb.create_sheet("怎么用")

    # ---------- 样式 ----------
    H1 = Font(bold=True, size=14)
    HDR = Font(bold=True, size=10, color="FFFFFF")
    HDR_FILL = PatternFill("solid", fgColor="2F5597")
    INPUT_FILL = PatternFill("solid", fgColor="FFF2CC")   # 可 / 待填
    KEY_FILL = PatternFill("solid", fgColor="E2EFDA")     # 关键结论列
    THIN = Side(style="thin", color="BFBFBF")
    BOX = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
    CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)
    LEFT = Alignment(horizontal="left", vertical="center", wrap_text=True)

    def header(ws_, row, cols, widths=None):
        for i, c in enumerate(cols, start=1):
            cell = ws_.cell(row=row, column=i, value=c)
            cell.font = HDR
            cell.fill = HDR_FILL
            cell.alignment = CENTER
            cell.border = BOX
        ws_.row_dimensions[row].height = 32
        if widths:
            for i, w in enumerate(widths, start=1):
                ws_.column_dimensions[get_column_letter(i)].width = w

    # ---------- 费率假设 ----------
    fz["A1"] = "费率假设（改这里，其他页全部自动重算）"
    fz["A1"].font = H1
    fz["A2"] = "黄色单元格是假设值；绿色是硬数据（老店实测）。不确定的请到 TikTok 后台核对后改。"
    fz["A2"].font = Font(size=10, color="C00000")
    header(fz, 3, ["参数", "值", "单位", "来源 / 说明"], [30, 12, 12, 66])
    for i, (key, name, val, unit, fmt, note) in enumerate(ASSUMPTIONS, start=4):
        A_ROW[key] = i
        fz.cell(row=i, column=1, value=name).alignment = LEFT
        v = fz.cell(row=i, column=2, value=val)
        v.number_format = fmt
        v.alignment = CENTER
        v.fill = KEY_FILL if key == "discount" else INPUT_FILL
        fz.cell(row=i, column=3, value=unit).alignment = CENTER
        fz.cell(row=i, column=4, value=note).alignment = LEFT
        for c in range(1, 5):
            fz.cell(row=i, column=c).border = BOX
        fz.row_dimensions[i].height = 30
    for r in range(4, 4 + len(ASSUMPTIONS)):
        fz.row_dimensions[r].height = 30

    def ref(key):
        return "'费率假设'!$B$%d" % A_ROW[key]

    D, C, PAY = ref("discount"), ref("commission"), ref("payment")
    FR, PF = ref("fulfil_rate"), ref("pack_fixed")
    HR, RR = ref("freight_rate"), ref("refund_rate")
    TM, FX = ref("target_margin"), ref("fx")

    # ---------- 定价明细 ----------
    ws["A1"] = "首批定价明细：挂牌价 -> 真实净收入 -> 采购成本上限"
    ws["A1"].font = H1
    ws["A2"] = ("口径：单件、成交后口径。挂牌价取自事实卡 site_profiles.MX.price；"
                "折扣系数取老店实测。N 列填你的实际采购价（人民币），O/P/Q 列自动出净利。")
    ws["A2"].font = Font(size=10, color="595959")
    ws["A2"].alignment = LEFT

    cols = ["SKU", "商品（西语标题）", "类目", "挂牌价\nMXN", "实测折扣",
            "预计成交价\nMXN", "平台扣点\n合计", "退款率", "退款后\n净收入 MXN",
            "履约成本\nMXN", "目标\n净利率", "采购上限\nMXN", "采购上限\nCNY",
            "采购价CNY\n(待填)", "单件净利\nMXN", "净利率", "判断"]
    widths = [12, 44, 10, 11, 9, 12, 10, 8, 13, 11, 8, 12, 12, 12, 12, 9, 20]
    header(ws, 4, cols, widths)

    row = 5
    for sku in skus:
        j = facts.get(sku)
        if not j:
            print(f"[!] 跳过 {sku}：无 facts.json", file=sys.stderr)
            continue
        mx = (j.get("site_profiles") or {}).get("MX") or {}
        price = mx.get("price")
        if not price:
            print(f"[!] 跳过 {sku}：无 MX 价格", file=sys.stderr)
            continue
        ws.cell(row=row, column=1, value=sku).alignment = LEFT
        ws.cell(row=row, column=2, value=short_name(j)).alignment = LEFT
        ws.cell(row=row, column=3, value=j.get("category", "")).alignment = CENTER
        c4 = ws.cell(row=row, column=4, value=float(price))
        c4.number_format = "#,##0.00"
        ws.cell(row=row, column=5, value=f"={D}").number_format = "0.000"
        ws.cell(row=row, column=6, value=f"=D{row}*E{row}").number_format = "#,##0.00"
        ws.cell(row=row, column=7, value=f"={C}+{PAY}").number_format = "0.0%"
        ws.cell(row=row, column=8, value=f"={RR}").number_format = "0.0%"
        ws.cell(row=row, column=9, value=f"=F{row}*(1-G{row})*(1-H{row})").number_format = "#,##0.00"
        ws.cell(row=row, column=10, value=f"=F{row}*{FR}+{PF}").number_format = "#,##0.00"
        ws.cell(row=row, column=11, value=f"={TM}").number_format = "0.0%"
        ws.cell(row=row, column=12, value=f"=(I{row}-J{row}-K{row}*F{row})/(1+{HR})").number_format = "#,##0.00"
        ws.cell(row=row, column=13, value=f"=L{row}/{FX}").number_format = "#,##0.00"
        c14 = ws.cell(row=row, column=14, value=None)
        c14.number_format = "#,##0.00"
        c14.fill = INPUT_FILL
        ws.cell(row=row, column=15,
                value=f'=IF(N{row}="","",I{row}-N{row}*{FX}*(1+{HR})-J{row})').number_format = "#,##0.00"
        ws.cell(row=row, column=16, value=f'=IF(N{row}="","",O{row}/F{row})').number_format = "0.0%"
        ws.cell(row=row, column=17,
                value=(f'=IF(N{row}="","待填采购价",IF(O{row}<0,"亏损",'
                       f'IF(P{row}<0.1,"薄利：建议提价或换品",'
                       f'IF(P{row}<0.2,"接近目标","达标，可放量"))))')).alignment = LEFT
        for c in range(1, 18):
            cell = ws.cell(row=row, column=c)
            cell.border = BOX
            if c in (2,):
                cell.alignment = LEFT
            elif c in (1, 3):
                cell.alignment = CENTER
            else:
                cell.alignment = Alignment(horizontal="right", vertical="center")
        for c in (12, 13):
            ws.cell(row=row, column=c).fill = KEY_FILL
        ws.row_dimensions[row].height = 28
        row += 1
    last = row - 1

    ws.freeze_panes = "D5"
    ws.auto_filter.ref = f"A4:Q{last}"

    # 采购上限越低越危险：<20 红，<50 黄
    red = PatternFill("solid", fgColor="FFC7CE")
    yellow = PatternFill("solid", fgColor="FFEB9C")
    rng = f"M5:M{last}"
    ws.conditional_formatting.add(rng, CellIsRule(operator="lessThan", formula=["20"], fill=red))
    ws.conditional_formatting.add(rng, CellIsRule(operator="between", formula=["20", "50"], fill=yellow))

    # ---------- 情景对比 ----------
    sc["A1"] = "情景对比：三种退款率下的采购成本上限（人民币）"
    sc["A1"].font = H1
    sc["A2"] = "退款率是这盘生意最大的不确定性。老店 41%、中性 25%、目标 15%。采购价超过对应列，就是亏。"
    sc["A2"].font = Font(size=10, color="595959")
    header(sc, 4, ["SKU", "挂牌价\nMXN",
                   "采购上限\n@退款41%\n(老店实测)", "采购上限\n@退款25%\n(中性)",
                   "采购上限\n@退款15%\n(目标)", "同款差距\n(41%vs15%)"],
           [12, 12, 18, 16, 16, 16])

    def cap_cny(frow, rate):
        F = f"'定价明细'!$D{frow}*{D}"
        J = f"({F}*{FR}+{PF})"
        return (f"=((({F}*(1-({C}+{PAY}))*(1-{rate}))-{J})-{TM}*({F}))"
                f"/(1+{HR})/{FX}")

    r2 = 5
    for i in range(5, last + 1):
        sc.cell(row=r2, column=1, value=f"='定价明细'!A{i}").alignment = CENTER
        sc.cell(row=r2, column=2, value=f"='定价明细'!D{i}").number_format = "#,##0.00"
        sc.cell(row=r2, column=3, value=cap_cny(i, "0.41")).number_format = "#,##0.0"
        sc.cell(row=r2, column=4, value=cap_cny(i, "0.25")).number_format = "#,##0.0"
        sc.cell(row=r2, column=5, value=cap_cny(i, "0.15")).number_format = "#,##0.0"
        sc.cell(row=r2, column=6, value=f"=E{r2}-C{r2}").number_format = "#,##0.0"
        for c in range(1, 7):
            cell = sc.cell(row=r2, column=c)
            cell.border = BOX
            if c > 2:
                cell.alignment = Alignment(horizontal="right", vertical="center")
        sc.row_dimensions[r2].height = 24
        r2 += 1
    sc.freeze_panes = "B5"

    # ---------- 报价反查：采购价 -> 需要挂牌价 ----------
    rev["A1"] = "报价反查：工厂报价多少，挂牌价最低要卖到多少"
    rev["A1"].font = H1
    rev["A2"] = ("反算公式：需要成交价 = (采购价x(1+头程) + 固定包装) / ((1-平台扣点)x(1-退款率) - 履约率 - 目标净利率)；"
                 "需要挂牌价 = 需要成交价 / 折扣系数。改「费率假设」页会自动重算。")
    rev["A2"].font = Font(size=10, color="595959")
    header(rev, 4, ["采购价\nCNY", "采购价\nMXN", "到仓成本\nMXN",
                    "需要成交价\n@退款25%", "需要挂牌价\n@退款25%",
                    "需要挂牌价\n@退款41%", "需要挂牌价\n@退款15%"],
           [10, 11, 12, 14, 14, 14, 14])

    def need_f(cny_row, rate):
        """给定采购价与退款率，需要的成交价（未除以折扣系数）。"""
        num = f"($A{cny_row}*{FX}*(1+{HR})+{PF})"
        den = f"((1-({C}+{PAY}))*(1-{rate})-{FR}-{TM})"
        return f"={num}/{den}"

    def need_p(cny_row, rate):
        """需要的挂牌价 = 需要成交价 / 折扣系数。"""
        return f"={need_f(cny_row, rate)[1:]}/{D}"

    r3 = 5
    for cny in (20, 30, 50, 80, 100, 150, 200, 300, 500):
        a = rev.cell(row=r3, column=1, value=cny)
        a.number_format = "#,##0"
        a.fill = INPUT_FILL
        rev.cell(row=r3, column=2, value=f"=A{r3}*{FX}").number_format = "#,##0.00"
        rev.cell(row=r3, column=3, value=f"=A{r3}*{FX}*(1+{HR})").number_format = "#,##0.00"
        rev.cell(row=r3, column=4, value=need_f(r3, "0.25")).number_format = "#,##0.00"
        rev.cell(row=r3, column=5, value=need_p(r3, "0.25")).number_format = "#,##0.00"
        rev.cell(row=r3, column=6, value=need_p(r3, "0.41")).number_format = "#,##0.00"
        rev.cell(row=r3, column=7, value=need_p(r3, "0.15")).number_format = "#,##0.00"
        for c in range(1, 8):
            cell = rev.cell(row=r3, column=c)
            cell.border = BOX
            cell.alignment = Alignment(horizontal="right", vertical="center")
        for c in (5, 6, 7):
            rev.cell(row=r3, column=c).fill = KEY_FILL
        rev.row_dimensions[r3].height = 24
        r3 += 1
    rev.cell(row=r3 + 1, column=1, value="怎么读：").font = Font(bold=True)
    rev.cell(row=r3 + 2, column=1,
             value="工厂报 80 元 -> 看 80 那一行的 E 列，就是你挂牌价的下限；低于这个价，卖一单亏一单。").alignment = LEFT
    rev.cell(row=r3 + 3, column=1,
             value="想留安全垫，按 F 列（退款 41%）定价；想激进冲量，按 G 列（退款 15%）定价。").alignment = LEFT
    rev.freeze_panes = "B5"

    # ---------- 老店基准 ----------
    base["A1"] = "老店基准（这些是实测，不是估算）"
    base["A1"].font = H1
    base["A2"] = "来源：output\\_research\\后台数据诊断-20261022.md（TikTok 后台 30 天导出 2026-09-23~10-22）"
    base["A2"].font = Font(size=10, color="595959")
    header(base, 4, ["指标", "数值", "说明"], [30, 18, 70])
    baseline = [
        ("GMV（30 天）", "11,373.88 MXN", "20 单，且 92% 集中在 9/23–9/30 这 8 天，10 月 0 单"),
        ("客单价 AOV", "568.69 MXN", "标价普遍在 200~1400 之间"),
        ("实收 / 挂牌", "0.631", "12 个 SKU 实测均值（0.44~0.95），本表折扣系数的来源"),
        ("退款金额 / GMV", "41%", "4,708.25 MXN；近 30 天 14 单退货申请 / 20 单成交 = 70%"),
        ("退货原因 Top", "破损35% / 物流32% / 少件20% / 描述不符4.4%", "只有 4.4% 是文案问题，其余是打包、品控、物流"),
        ("曝光 -> 点击 CTR", "3.96%", "99.4% 流量来自商品卡，视频/直播/联盟不到 1%"),
        ("点击 -> 成交 CTOR", "1.43%", "1,397 点击只出 20 单"),
        ("已完成退款（30 天）", "2,818 MXN", "5 单，另有 7 单被拒、2 单处理中"),
    ]
    for i, (k, v, n) in enumerate(baseline, start=5):
        base.cell(row=i, column=1, value=k).alignment = LEFT
        base.cell(row=i, column=2, value=v).alignment = CENTER
        base.cell(row=i, column=3, value=n).alignment = LEFT
        for c in range(1, 4):
            base.cell(row=i, column=c).border = BOX
        base.row_dimensions[i].height = 26
    base.cell(row=5 + len(baseline) + 1, column=1,
              value="一句话：老店不是不赚钱，是「打折 37% + 退款 41%」把利润吃干了。").font = Font(bold=True, color="C00000")

    # ---------- 怎么用 ----------
    how["A1"] = "怎么用这张表（5 步）"
    how["A1"].font = H1
    how.column_dimensions["A"].width = 4
    how.column_dimensions["B"].width = 120
    steps = [
        ("1", "先看「定价明细」的 M 列（采购上限 CNY）：这是你这个 SKU 最多能花的采购价。"),
        ("2", "红色（<20 元）说明按现价和现折扣，几乎没有采购空间——要么提价，要么别做这个 SKU。"),
        ("3", "拿 M 列去跟工厂谈价，或用来筛掉不合适的品。谈不到就换品，不要硬做。"),
        ("4", "工厂给出报价后，打开「报价反查」页，找到对应采购价那一行，就是你挂牌价的最低线。"),
        ("5", "拿到真实采购价后再填「定价明细」N 列（人民币），O/P/Q 三列自动出净利、净利率和判断。"),
        ("6", "「费率假设」页的佣金、履约、头程，从 TikTok 后台和实际账单核实后改，全部页自动重算。"),
        ("", ""),
        ("要记住的三件事", ""),
        ("A", "挂牌价 ≠ 实收。老店实测只收到 63%（平台折扣 + 优惠券）。定价必须按实收算。"),
        ("B", "退款率比佣金更致命。41% 退款率下，一个 SKU 的采购上限会掉到 15% 退款率时的一半。"),
        ("C", "低客单价 SKU 在 63% 折扣 + 25% 退款下基本没有采购空间。要么做高客单价，要么把折扣收窄。"),
    ]
    r = 3
    for a, b in steps:
        if a == "要记住的三件事":
            how.cell(row=r, column=2, value=b).font = Font(bold=True, size=12, color="2F5597")
        else:
            how.cell(row=r, column=1, value=a).alignment = CENTER
            how.cell(row=r, column=2, value=b).alignment = LEFT
        if b:
            how.row_dimensions[r].height = 24
        r += 1

    wb.save(out)

    # ---------- 控制台核对（Python 侧独立算一遍，便于核对表内公式） ----------
    A = {k: v for k, _, v, _, _, _ in ASSUMPTIONS}
    print(f"输出：{out}")
    print(f"{'SKU':<12}{'挂牌':>9}{'成交':>9}{'净收':>9}{'履约':>7}{'上限MXN':>9}{'上限CNY':>9}")
    for sku in skus:
        j = facts.get(sku) or {}
        price = ((j.get("site_profiles") or {}).get("MX") or {}).get("price")
        if not price:
            continue
        f = price * A["discount"]
        i_ = f * (1 - A["commission"] - A["payment"]) * (1 - A["refund_rate"])
        jj = f * A["fulfil_rate"] + A["pack_fixed"]
        cap = (i_ - jj - A["target_margin"] * f) / (1 + A["freight_rate"])
        print(f"{sku:<12}{price:>9.2f}{f:>9.2f}{i_:>9.2f}{jj:>7.2f}"
              f"{cap:>9.2f}{cap / A['fx']:>9.2f}")
    print(f"行数：{last - 4}")


if __name__ == "__main__":
    main()
