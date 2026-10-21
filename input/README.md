# input 目录说明

一个商品一个子目录。`_` 开头的目录（如 `_归档`）会被脚本自动跳过，不放真实商品。

```
input\
├─ ABTL000006\              真实商品（15 个一批）
│  ├─ input.json            商品信息（结构见下方字段；不进 git）
│  ├─ item.json             原始抓取数据（可选，留档用；不进 git）
│  ├─ facts.json            事实卡（知识库主本，进 git）
│  ├─ overrides.json        人工确认覆盖（进 git，重建时自动重放）
│  ├─ img_manifest.csv      图片清单/哈希/主图（进 git）
│  └─ img\                  5–10 张图（不进 git）
├─ ABU5000000\
├─ …
├─ _归档\                   ⛔ 不参与批次，仅留档
│  ├─ 示例商品模板\          input.json 空白模板
│  └─ 示例商品001-千斤顶\    首个测试品，结果在 output\示例商品001\
└─ README.md                本文件
```

## input.json 必填字段

| 字段 | 说明 |
|---|---|
| `product_id` | 与目录名一致 |
| `site` | `MX` 或 `BR` |
| `category` | 五金工具 / 汽车摩托 / 家居建材 / 运动户外 / 宠物用品 / 厨房用品 / 家电 / 时尚配件 |
| `title_raw` | 原商品标题 |
| `description_raw` | 原描述原文，多乱都行 |
| `attributes_raw` | 原属性键值对（品牌/型号/电压/功率/尺寸…） |
| `images` | 图片相对路径 |
| `core_keyword` | 买家搜索词（西语/葡语） |
| `price_source` | 原价与币种 |

`item.json` 是抓取的完整原始数据，脚本目前只用 `input.json` 的属性；`facts.json` 由 `qa\build_facts.py` 从两者生成，是生成 Listing 的唯一事实来源。

## 运行方式

```powershell
# 在仓库根目录执行
cd qa
# 生成之后，一条命令出 属性映射 + 校验 + 批次结果表
python run_batch.py --input-root ..\input --listing-dir ..\output\批次20261020 --site MX
```

## 新批次怎么进

1. 新建批次目录（不要用 `_` 开头），把商品子目录放进去
2. 或者直接平铺在 `input\` 下（当前 15 个就是平铺的）
3. 告诉 Agent 批次名 → Agent 生成 `output\批次…\listing-<id>.txt` → 你跑上面那条命令
