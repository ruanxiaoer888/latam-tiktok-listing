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
├─ _schemas/
│  ├─ 五金工具.schema.json
│  ├─ 汽车摩托.schema.json
│  ├─ 家电.schema.json
│  └─ _fields.md       ← 字段字典（中文说明）
└─ _index/
   ├─ products.csv     ← 一行一个 SKU（脚本生成）
   ├─ 完整度报告.md
   └─ facts_check.json
```

## 状态

| 状态 | 含义 | 能否生成 |
|---|---|---|
| `draft` | 草稿，待人工核 | 否 |
| `verified` | 人工核过，必填齐全 | **是** |
| `quarantined` | 已隔离：事实有未解决疑点，移出生成集 | 否 |
| `blocked` | 有硬伤（品牌冲突/电压冲突等） | 否 |

## 命令

```powershell
# 1) 从 input.json/item.json 生成/更新事实卡草稿 + 图片清单
python qa\build_facts.py

# 2) 门禁检查 + 完整度报告（有 blocked 时可加 --fail-on-blocked）
python qa\check_facts.py
python qa\check_facts.py --fail-on-blocked

# 3) 汇总索引
python qa\index_kb.py

# 4) 人工核完，批量置为 verified（示例）
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
- 硬门槛（`schema.required`）：品牌、供电类型、电压（按类型）、包装清单；家电另加认证状态。
- 软门槛（`schema.recommended`）：尺寸、材质、重量、可写功率——缺了提醒，不阻断，但 Listing 会少信息。
- 功率物理不可信（插电 ≥3500W / 电池 ≥600W）→ `state_power=false`，**Listing 不写瓦数**。
- 认证 `missing` → Listing 不得出现 NOM/INMETRO/ANATEL。

## 边界

- 本库只放“生成 Listing 需要、ERP 里又没有”的事实与素材；
- **不放**成本、供应商、库存、MOQ、备货周期、HS 编码；
- 飞书「产品知识库」是发布后的共享/审核视图，**不是第二主本**；
- WeKnora 只做规格书/规则的文档问答（可选），不回写 facts。

## 当前批次（2026-10-21）

- 15 个 SKU 全部是 MX 站；
- **硬门槛齐全（15/15，平均完整度 100%）**，但都还没置 `verified`；
- **已隔离 4 个（不参与本批生成）**：疑点未解决前不进结果，避免污染：
  - `ATVMX11700`：功率 4800/6800W 与 127V 家庭电路矛盾，且拿不到铭牌；
  - `AMR3000002`：电池电压 18V 仅为口述估计，无电池标签/铭牌；
  - `BKU0000000`：包装清单为推断（是否含充电器未核对实物）；
  - `MMV2000000`：电池 18V / 整机标称 21V 口径未确认。
- **干净候选 11 个**：`ABTL000006`、`ABU5000000`、`ABU6000008`、`ABU600000T`、
  `AHR6C50002`、`AMU0000003`、`AMU3CI0000`、`AMU6000005`、`ATVMX18200`、
  `MBU6000001`、`ZK2604270H`；
- 隔离只是“移出生成集”，事实卡和 overrides 都保留；补到证据后，删掉
  `input/<SKU>/overrides.json` 里的 `quarantine` 块即可恢复，再走人工核验。
- 软缺（不阻断、Listing 会少信息）：多数 SKU 缺整机重量/尺寸；部分材质为描述推断，已在 warnings 标注。
