# kb｜产品事实库（本地主本）

> 定位：**生成 Listing 唯一事实来源**。规则在 `skill/`，产出在 `output/`，本目录 + `input/<SKU>/facts.json` 是事实层。
> 原则：缺失写 `null`，冲突标 `blocked`，**不猜参数**；生成端只读 `verified` 的事实。

## 目录

```
input/<SKU>/
├─ facts.json          ← 事实卡（主本，进 git）
├─ overrides.json      ← 人工确认覆盖（进 git，重建时自动重放）
├─ img_manifest.csv    ← 图片哈希/主图/重复组（进 git）
├─ input.json          ← ML 原始抓取（不进 git）
├─ item.json           ← 完整采集明细（不进 git）
└─ img/                ← 原图（不进 git，走 U 盘/网盘）
kb/
├─ _schemas/           5 个类目 schema（五金工具 / 汽车摩托 / 家电 / 运动户外 / 服装）
│  ├─ 五金工具.schema.json
│  ├─ 汽车摩托.schema.json
│  ├─ 家电.schema.json
│  ├─ 运动户外.schema.json
│  ├─ 服装.schema.json  ← 外套/风衣/衬衫外套：品牌+面料+尺码+包装清单为硬门槛
│  └─ _fields.md       ← 字段字典（中文说明）
└─ _index/             （脚本生成，进 .gitignore）
   ├─ products.csv     ← 一行一个 SKU
   ├─ 完整度报告.md
   └─ facts_check.json
```

> **类目未登记 schema 的 SKU 不许生成**：`check_facts.py` 会把它们标成「跳过」、不计入样本（当前跳过 0 个；但 9 个类目包里还有 4 个没有 schema：家居建材 / 宠物用品 / 厨房用品 / 时尚配件，碰到就补），`run_batch.py` 也不会放行。补 schema（或把 category 改成已有的类目）后才纳入门禁。

## 状态

| 状态 | 含义 | 能否生成 |
|---|---|---|
| `draft` | 草稿，待人工核 | 否 |
| `verified` | 必填齐全、可生成 | **是** |
| `quarantined` | 已隔离：事实有未解决疑点，移出生成集 | 否 |
| `blocked` | 有硬伤（品牌冲突/电压冲突等） | 否 |

> ⚠️ **`verified` 目前不等于人工核过**：现有 81 个 `verified` 是 2026-10-22 批量核验产出的，`_meta.verified_by` 自述「DSH 自动核验（可追溯性检查，待人工抽查）」。抽查/退回流程见 `HANDOFF.md`「仍开放」第 1 条。

## 命令

```powershell
# 1) 从 input.json/item.json 生成/更新事实卡草稿 + 图片清单
python qa\build_facts.py

# 2) 门禁检查 + 完整度报告
python qa\check_facts.py
python qa\check_facts.py --fail-on-blocked   # 有 BLOCKED 或 FAIL → exit 3
python qa\check_facts.py --fail-on-skip      # 有 SKU 因类目未登记被跳过 → exit 3

# 3) 汇总索引
python qa\index_kb.py

# 4) 生成用摘要（默认只输出 verified）
python qa\facts_digest.py
python qa\facts_digest.py --status all --include-pending   # 排查用

# 5) 尺寸回填（facts 里尺寸量级/单位不对 → 置 null，原值留在 _meta.size_fix）
python qa\fix_size_fields.py                 # dry-run，只打印清单
python qa\fix_size_fields.py --apply         # 真正写回 facts.json（2026-10-22 已跑过一次：11 SKU / 18 字段）

# 6) 图片来源检查（上架前；有 P0 → exit 3）
python qa\check_images.py --input-root input
python qa\check_images.py --sku AXNJCPS300   # 只查一个 SKU
python qa\check_images.py --demo             # 自检 19/19

# 7) 人工核完，批量置为 verified（示例）
python qa\verify_facts.py ABU5000000 ABU6000008 --by "运营-张三"
```

## 审核流程（每条 2–3 分钟）

1. 打开 `input/<SKU>/facts.json`，先看 `gates.warnings` 和软缺项；
2. 核对：品牌、电压/电池电压、功率口径、尺寸/重量、包装清单、材质；
3. 缺的补上（不确定就留 `null`，别猜）；冲突的写进 `overrides.json`（不要手改 facts 业务字段，重建会覆盖）；
4. 确认无误 → `status: "verified"`，填 `_meta.verified_by` / `verified_at`；
5. 跑 `python qa\check_facts.py`，`READY` 才进生成。

## 门禁规则

- `blocked` / `quarantined` / `draft` → 生成端拒绝。
- 硬门槛（`schema.required`）：品牌、供电类型、电压（按类型）、包装清单；家电另加认证状态；**服装除外**——服装的硬门槛是 品牌 / 面料成分 / 尺码 / 包装清单（没有供电与电压）。
- 软门槛（`schema.recommended`）：尺寸、材质、重量、可写功率——缺了提醒，不阻断，但 Listing 会少信息。
- 功率物理不可信（插电 ≥3500W / 电池 ≥600W）→ `state_power=false`，**Listing 不写瓦数**。
- 认证 `missing` → Listing 不得出现 NOM/INMETRO/ANATEL。

## 边界

- 本库只放“生成 Listing 需要、ERP 里又没有”的事实与素材；
- **不放**成本、供应商、库存、MOQ、备货周期、HS 编码；
- 飞书「产品知识库」是发布后的共享/审核视图，**不是第二主本**；
- WeKnora 只做规格书/规则的文档问答（可选），不回写 facts。

## 当前状态（2026-10-22）

数字以脚本输出为准，别抄本文：`python qa\check_facts.py`（会重写 `kb\_index\完整度报告.md`）。

- **`input\` 下 110 个 SKU 目录**，全部 MX 站（`site_profiles` 只有 MX / MXN / 127V）；
- 门禁样本 **110**，**跳过 0 个**（2026-10-22 补了 `服装.schema.json`，`AXNJCPS300`、`AXNJCQS502` 已纳入门禁，当前判定 `draft` → PENDING）；
- 当前 **READY=81 / PENDING=16 / QUARANTINED=13 / BLOCKED=0 / 跳过 0**；类目 schema 5 个；
- 2 个服装 SKU 的硬缺：面料成分（`material` 为空，属性里已有 `Material principal: Poliéster`）、尺码（`size.raw` 为空）、包装清单（`package.included` 为空）——补进 facts 后才能进生成；
- 81 个 `verified` 是批量核验产出（`verified_by` 自述「待人工抽查」），**待人工抽查**；
- 已隔离 13 个（明细见 `完整度报告.md` 第三节「已隔离」）：`ATVMX11700` 功率与家庭电路矛盾、`AMR3000002` 电池电压仅口述、`BKU0000000` 包装清单推断、`MMV2000000` 18V/21V 口径未确认，另有 6 个电池工具缺电池电压、2 个功率不可信；
- 隔离只是"移出生成集"，事实卡和 overrides 都保留；补到证据后，删掉
  `input/<SKU>/overrides.json` 里的 `quarantine` 块即可恢复，再走人工核验。
- 软缺（不阻断、Listing 会少信息）：多数 SKU 缺整机重量/尺寸；部分材质为描述推断，已在 warnings 标注。
- **尺寸垃圾值已修（2026-10-22）**：`fix_size_fields.py --apply` 修 **11 个 SKU / 18 个字段**（置 null，原值留在 `facts._meta.size_fix`）；`check_facts_quality.py` 新增 `FQ-P0-SIZE-IMPLAUSIBLE`，`build_facts.py` 已加固（量级 1–150 cm、mm 未 ÷10 直接置 null + warning）。**新 SKU 不会再产出 3200 cm 这类值**；旧值如要恢复，去 `_meta.size_fix` 看原值再人工确认。
- **原始数据缺口**：`input\` 110 个目录里 **只有 17 个是完整的**（有 input.json / item.json / img），93 个只剩 facts —— 用 `gen_manifest.py --plan` 查，exit 1 就是有缺口；这些 SKU 不能重建、不能重新打包。
- **图片合规**：`qa\check_images.py` 覆盖 17 个有图的 SKU（其余 93 个无 img，未检查、不算通过）；当前 P0=11 / 9 个 SKU。文字/水印仍需人工核对。
