# 从美客多信息生成 TikTok Shop Listing（一条流水线）

> 核心就一句话：**一个 SKU → 一份生成包 → 发给任意 Agent → 产出可上架的 Listing**。
> 事实只取 `facts.json`，场景只取场景卡，写法按生成包里的硬规则；生成后必须过 `run_batch` 校验。

---

## 一、新 SKU 怎么跑（5 条命令）

```powershell
# 0. 采集已经落盘：input\<SKU>\{input.json, item.json, img\}
cd E:\AUSU\DSHProjects\Tiktok\latam-tiktok-listing

# 1. 建事实卡（美客多信息 → facts.json）
python qa\build_facts.py --only <SKU>

# 2. 过门禁（READY 才能生成）
python qa\check_facts.py --only <SKU>
python qa\check_facts_quality.py --input-root input --strict

# 3. 抽场景卡（原文 → 场景/痛点/差异化/包装/注意事项）
python qa\build_scene.py --only <SKU>

# 4. 出生成包（一个 md，包含全部材料和规则）
python qa\make_listing_pack.py --sku <SKU>
#    -> output\_packs\<SKU>.md

# 5. 把生成包发给 Agent，让它直接产出（成稿就是交付文件）：
#    output\批次YYYYMMDD\<SKU>\标题.txt + 描述.txt

# 6. 校验（机器文件自动进 output\_smoke）+ 补上架信息/图片/README
python qa\run_batch.py --input-root input --listing-dir output\批次YYYYMMDD --site MX
python qa\make_upload_pack.py --batch output\批次YYYYMMDD
```

批量：

```powershell
python qa\build_scene.py                 # 全部 SKU 的场景卡
python qa\make_listing_pack.py --all     # 全部 verified SKU 的生成包（当前 81 份）
```

## 二、生成包里有什么

打开 `output\_packs\<SKU>.md`，一份约 13 KB，Agent 不需要再读别的文件：

| 章节 | 内容 |
|---|---|
| 1. 任务 | 写什么、输出到哪、怎么自检 |
| 2. 硬规则 | 标题/首行/卖点/规格/包装/FAQ/颜色/禁词（浓缩版 BRIEF） |
| 3. 事实卡 | 品牌、型号、核心词、价格（不写正文）、功率、电压、尺寸、材质、包装、颜色、数据警告 |
| 4. 场景卡 | 原文抽取的使用场景、痛点、差异化、原文包装、注意事项 |
| 5. 类目要点 | 该类目的标题公式、必带信息、FAQ、常见坑 |
| 6. 范本 | 同/近类目已通过校验的 1–2 条成稿（学结构，不抄参数） |
| 7. 输出与验收 | 文件路径、自检命令、批次校验命令 |

## 三、已经生成好的

- **81 条成稿**：`output\批次20261022-v2\listing-<SKU>.txt`（P0=0 / P1=0 / P2-转化=0）
- **81 份生成包**：`output\_packs\<SKU>.md`（可随时重生成任意一条）
- **上架表**：`output\批次20261022-v2\上架清单.xlsx`
- **待确认清单**：`output\批次20261022-v2\待确认清单.md`

## 四、三条不能破的纪律

1. **参数只取 facts**：没出处的不写、不猜；电压一律以 facts 为准；`可写功率=不写` 时全文不出现瓦数。
2. **认证 missing 时**，全文不得出现 `NOM / INMETRO / ANATEL / UN38.3`。
3. **生成完必须跑 `run_batch`**：P0/P1 必须为 0 才能交付；P2-转化优先清。

## 五、常见问题

- **只有 `facts.json`、没有 `input.json/item.json`**：出不了场景卡（场景为空），只能写通用场景——先去采集机补 raw。
- **`status` 不是 `verified`**：生成包会跳过（脚本会打印原因），先补数据或写 `overrides.json`。
- **要换批次目录**：命令里把 `批次YYYYMMDD` 换成实际目录即可，脚本不绑定批次。
- **要改语气/结构**：改 `qa\make_listing_pack.py` 里的 `RULES`，或 `_BRIEF.md`，不用改每条稿。
