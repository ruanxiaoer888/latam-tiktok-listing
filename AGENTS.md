# TikTok 工作区约定（一句话生成规则）

> 本文件是 Skill `/latam-tiktok-listing` 源码仓库的协作约定，跟着 GitHub 仓库走。
> **命名说明**：工作区目录 `skills/latam-tiktok-listing` = Skill `/latam-tiktok-listing` 的源码母版 + 数据仓库（input/output/qa）。DSH 调用时用 `/latam-tiktok-listing`，两者是同一套东西。
> **换电脑**：把本文件放到工作区根目录（与 `SKILL.md` 同级），DSH 会自动加载，无需再说一遍规则。

## 0. 默认交互方式：一句话，全自动

用户不看也不敲命令。当用户用自然语言说下面这类话时，**直接开工，不要问“要不要开始”，不要展示命令行、脚本路径、内部步骤**：

- 「把 <SKU> 生成 TikTok 上架稿」
- 「把还没生成的商品都生成一下」
- 「把新采集的这批美客多商品生成 Listing」
- 「这个商品（贴美客多链接或 SKU）帮我写成 TikTok 的」

只有用户主动问「你是怎么做的 / 用了什么命令」时才解释技术细节。

## 1. 收到一句话后自动做什么

1. **定范围**
   - 给了 SKU / 商品名 → 单个；
   - 说「这批 / 全部 / 还没生成的」→ `input\` 下所有 `status=verified` 且还没有成稿的 SKU；
   - 给的是美客多链接而不是 SKU → 先采集（需要住宅网络 + 浏览器通道），采不到就一句话说明，不要硬试。
2. **查数据**：检查 `input\<SKU>\` 的 `input.json / item.json / img\ / facts.json`。
3. **补事实卡**：缺 `facts.json` 就自动建；然后跑事实门禁（必填 / 口径 / 认证）。
4. **抽场景卡**：从美客多原文抽用途、痛点、差异化、包装、注意事项。
5. **生成**：按每个 SKU 的生成包写标题 + 描述（卖点 / 规格 / 包装 / FAQ / CTA）。
6. **自检并自动修**：跑批次校验，P0 / P1 必须清零；P2-转化尽量清零。
7. **交付**：落盘 + 一句话汇总（生成几条、放在哪、哪几个要补资料）。

## 2. 交付物的固定位置

只有两个数据目录：`input\` 是原料，`output\` 是产物。**交付物全部在批次目录里，不许在仓库根新开目录。**

- **成稿就在交付文件夹里**：`output\批次YYYYMMDD\<SKU>\上架信息.md`（标题+描述+后台字段+变体图片对应+待办，一个文件搞定）+ `图片\`（从源素材复制白底主图，01 是主图）
- 批次说明：`output\批次YYYYMMDD\README.md`（怎么用、本期 SKU、校验结论）
- **每个 SKU 交付目录只有两样东西：`上架信息.md` + `图片\` 文件夹**。不拆标题.txt、描述.txt 等零散文件——运营打开一个文件就能完成所有复制粘贴。
- **批次根目录只放：README.md + SKU 文件夹；一个机器文件都不许放**。校验/映射/明细等机器文件全部写进 `output\_smoke\run_batch_<时间戳>_<pid>\`，用户不用看
- 原始素材：`input\<SKU>\`（**不是给人上架用的**，别让运营从这里拿图片）

同一批次目录已存在就续写，不新建重复目录。每次交付都要出 SKU 文件夹：运营拿到一个 SKU 文件夹就能上架，批次根目录不许再堆机器文件。

### 2.1 中间产物目录（Agent 自用，运营不看）

以下目录是流水线的中间缓存，**不是交付物**。可以安全清理，不影响任何已交付批次。

| 目录 | 用途 | 生命周期 |
|---|---|---|
| `output\_batch\` | `source_digest.py` / `facts_digest.py` / `build_scene.py` 的产物（原始摘要、事实摘要、场景卡） | 下次批量生成前可清；重跑脚本会自动重建 |
| `output\_packs\` | `make_listing_pack.py` 的产物（每个 SKU 的生成包） | 对应批次交付完成后可清；重跑会自动重建 |
| `output\_smoke\` | `run_batch.py` 每次校验的机器文件（check.csv / 明细 / 属性映射 / 批次结果） | 永久保留用于回溯；磁盘紧张时可归档或删除 7 天前的 |
| `output\_research\` | 市场调研、技术对接等研究资料 | 长期保留；不属于 Listing 流水线 |
| `output\经营台账\` | 定价模型与经营分析 | 长期保留；不属于 Listing 流水线 |
| `output\_归档\` | 历史对照样本（A/B 测试、定稿快照） | 长期保留 |

> **原则**：`_batch` 和 `_packs` 是临时缓存，随时可删可重建；`_smoke` 是校验审计日志，按需清理；其余是独立资料库，不动。

## 3. 数据不全时怎么说（人话，不甩报错）

- 缺包装清单 / 承载 / 电池电压：`<SKU> 缺包装清单，补上就能生成`
- 功率或件数矛盾：`<SKU> 的参数对不上（功率 6800W / 127V），需要铭牌确认`
- 没有原始数据（只有 facts）：`<SKU> 只有事实卡、没有原图原描述，需要从采集机补`
- 类目没有 schema：`<SKU> 的类目还没登记，先补类目规则`

## 4. 内部执行顺序（Agent 自用，不展示给用户）

```text
python qa\build_facts.py --only <SKU>            # 缺 facts 时
python qa\check_facts.py --only <SKU>            # READY 才继续
python qa\check_facts_quality.py --input-root input --strict
python qa\build_scene.py --only <SKU>            # 或 --all 批量
python qa\make_listing_pack.py --sku <SKU>       # 或 --all；产物 output\_packs\<SKU>.md
# 按生成包直接写 output\批次YYYYMMDD\<SKU>\上架信息.md（标题+描述+后台字段+变体图片对应，一个文件）+ 图片\（白底主图）
python qa\run_batch.py --input-root input --listing-dir output\批次YYYYMMDD --site MX
# 机器文件全部进 output\_smoke\run_batch_<时间戳>_<pid>\，批次目录不动
python qa\make_upload_pack.py --batch output\批次YYYYMMDD
# 补 上架信息.md + 图片\ + 批次 README.md
```

> 批次根目录只留 README + SKU 文件夹；机器文件在 `output\_smoke\`，用户不用打开。

批量超过 10 条时，用子代理按 SKU 分组并行写，主控统一自检；写入范围按 SKU 分组互不重叠。

## 5. 事实纪律（任何情况下不破）

- 参数只取 `facts.json`；缺的不写、不猜；
- `power.state_power=false` 不写瓦数；电压以 facts 为准；
- `certification.status=missing` 时全文不出现 NOM / INMETRO / ANATEL / UN38.3；
- 包装按 `facts.package.included`；颜色按 `raw_attributes.Color`；
- 价格不进正文；不编赠品 / 保修 / 包邮 / 时效。
- **正文是纯文本**：不写 `**加粗**` / `__` / `#` / 表格 `|`，标点只用半角——TikTok 后台是富文本编辑器，不解析 Markdown，`**` 会原样显示成星号，加粗由运营在后台手动设置。`check_listing.py` 会报 P1。
