# HANDOFF｜交接文档

> 最后更新：**2026-10-30**（工具链 v2.0 完成、首批 8 条上架、进入 14 天观察期）
> 仓库：https://github.com/ruanxiaoer888/listing-pipeline （private，main）
> 本文件位置 = 仓库根目录 = 流水线主本
> 交互约定：**用户只发一句话，Agent 全自动做完，不展示命令**（见 `AGENTS.md`）
> 新手入口：**`新手怎么用.md`（零命令）**；技术用法见 `README.md`

---

## 0. 一句话

**工具链已经够用（81 条 0 缺陷、交付闭环、一致性门禁），现在的卡点不在文案，在「认证 / 主图 / 履约质量」；首批 8 条已上架，进入 14 天观察期，期间冻结新 Listing。**

---

## 1. 当前任务

**给新开的 TikTok Shop 墨西哥店做上架与冷启动**，来源是美客多商品图 + 粗描述。

当前位置：

- 旧店已放弃，只留教训：30 天 GMV 11,373 MXN / 20 单、**退款 41%**、退货申请 **14/20**、99.4% 流量来自商品卡、实际成交价约标价 6 折。
- 新店品牌确定 **Atverce**；首批 **8 条已上架**（清单见 `首批上架候选-20261029.md`）。
- Listing 侧已就绪：批次20261022-v2 **81 条成稿，P0/P1/P2 全 0**。
- **当前处于 14 天冻结期**：不生成新 Listing、不改提示词，先拿真实数据。
- 待拍板：**63 款电动/电池产品缺证书**——补证，还是把选品收缩到免认证手动工具（当前可售池约 18 款）。

---

## 2. 已完成（2026-10-29 ~ 10-30，已推送）

### 2.1 工具链 v2.0（Pattern 化 + 闭环）

| 模块 | 内容 |
|---|---|
| Pattern | `patterns\listing_write`（初稿）、`patterns\listing_fix`（按违规清单改稿） |
| 脚本 | `scripts\render_prompt.py`（组装 + 版本/sha256）、`render_listing.py`（JSON→纯文本，格式由代码保证）、`eval_pattern.py`（复用校验器打分） |
| 事实一致性 | 新增 `qa\check_consistency.py`（供电方向 / 瓦数 / 容量 / 认证），已接入 `run_batch` |
| 合规闸门 | `check_listing --fail-on-p1`（P1 真阻断）、`--input-root`（类目必带项按 facts 可用性判断） |
| 平台限制单一源 | `denylist.json` 新增 `images`；标题区间经 `qa\_limits.py` 统一读取 |
| 交付闭环 | `make_upload_pack` 兼容扁平布局并归位 SKU 文件夹；新增 `qa\normalize_listing.py` |
| 评测 | 黄金集 20 条（approved）+ 基线 `output\_eval\` |

### 2.2 数据与交付

- 批次20261022-v2 从扁平迁移为 **81 个 SKU 文件夹**（81 标题 / 81 描述 / 81 上架信息 / 730 张图），根目录只有 README。
- 清洗 81 份成稿的 `**` 与全角标点，并补了标点后空格（374 处）。
- 修 2 张主图：`ATVMX18200` 1182×1182（裁掉带「AI生成」水印的场景带）、`ABTL00000J` 1920×1920（补白）。
- **`AMU5000000` 事实卡纠错**：原始描述是 8000mAh 锂电 + 6–8.4V，属性误解析成 127V 插电；已写 overrides 重建并重新核验。

### 2.3 基础设施

- `core.hooksPath=.githooks` 生效，pre-commit 会跑 `selftest`（4/4）。
- `sync-all` 后仓库与 `~\.agents` 两个技能哈希一致。
- 已推送 5 个提交：`7b631db` → `3e8b2a0`（HEAD）。

---

## 3. 卡住的问题

| # | 问题 | 规模 | 需要谁 / 怎么解 |
|---|---|---|---|
| 1 | **认证阻断** | MX 口径 122 条 / 74 SKU（NOM-003 73、UN38.3 49），台账 `certificates: []` | 供应商/认证机构给证书号+有效期，填 `qa\certifications.json` |
| 2 | **27 个 SKU 生成不了** | 16 draft + 13 quarantined，缺包装清单/电池电压，原始描述里也没有 | 实物或供应商资料 → overrides → 重建 → 核验 |
| 3 | **图片 P0** | 55 条 / 40 SKU（低分辨率为主） | 低清不可裁，需重拍或向供应商要原图；主图裁方可批量做 |
| 4 | **没有后台数据** | 8 条刚上架 | 第 14 天导 曝光/点击率/成交/退货 |
| 5 | **BR 站从未实测** | 规则已备 | MX 跑通后再做（INMETRO/ANATEL、110V/220V） |
| 6 | **首批选品结构偏** | 6 千斤顶 + 2 工具组 | 第二批按品类分散，不然测不出品类信号 |
| 7 | **5 个 SKU 无原始数据** | `VB0B000001` 等 | 从采集机补 input.json/item.json/img |

---

## 4. 下一步计划

### 本周：用户只做 3 件事

1. **今天**：向供应商要 10 款主推的 NOM-003 / UN38.3 证书（号 + 有效期）；仓库按 facts 逐件核对首批 8 条包装清单。
2. **明天**：8 条主图换实物高清图（1:1、短边 ≥800）；低清找供应商要原图。
3. **本周**：定死打包 SOP——逐件核对、封箱拍照、重货双箱、退货品禁止二次销售（41% 退款大概率出在这里）。

### 我这边（不用催）

1. 建首批 8 条的 **14 天监控表**（每天 4 个数）。
2. 第 7 天中期归因；第 14 天给下一步（加推 / 淘汰 / 改文案）。
3. 第二批 8 条选品建议（品类分散、优先免认证）。

### 之后

- 证书到位后扩电动品类；BR 等 MX 跑通再启动。
- 有数据后再调 `skill\转化层.md` 阈值，否则都是猜。

---

## 5. 踩过的坑（按主题）

### 5.1 数据与事实

1. **facts 本身会错**：`AMU5000000` 属性 127V/200W ↔ 描述 8000mAh 电池。属性不一定比描述可信，冲突要人工判。
2. **CAT-REQ 与 facts 打架**：facts 明确 `state_power=false` 或尺寸置空，规则仍要求写 → 改稿永远清不掉，闭环空转。已改成「facts 没有的项不要求写」。
3. **包装清单会被截断**：部分 SKU 只剩最后一件，必须回原文核对。
4. **尺寸解析吃错数**：`3200 RPM` 当 cm、`300 Nm` 当 cm；哨兵会把不可信尺寸置空，别再拿它写文案。
5. **电压口径混用**：美客多 `Voltaje:127V` 常是充电器输入；电池工具看 `battery_v`。
6. **「93 个只有 facts」是过期数字**：实际 108/113 有原始数据，只有 5 个没有。数字一律跑命令。

### 5.2 校验与交付

7. **交付最后一步从未跑通**：`make_upload_pack` 只认 `<SKU>\标题.txt`，而批次一直是扁平文件 → 全仓 0 个交付文件夹。已修。
8. **P1 从不阻断**：`run_batch` 只传 `--fail-on-p0`，「P0/P1 必须清零」没有代码支撑。已修。
9. **全角冒号转半角丢空格**：清洗后出现 `tipo:plana`，374 处。已修。
10. **一致性检查要防误报**：`1,200 W` 的千分位、汽车电瓶的 `batería`、充电器 `127 V` 都是假阳性。已收紧规则。
11. **`**` 后台不解析**：会原样显示星号；新流程由 `render_listing` 从源头保证纯文本。

### 5.3 图片

12. **主图可能是合成图带中文水印**：`ATVMX18200` 左上角「AI生成」，裁方去不掉，只能裁掉整条场景带。
13. **低分辨率不可裁**：500px 的图放大只会糊，必须重拍/换图。
14. **图片不进 git**：交付靠 `input\<SKU>\img` 现生成。

### 5.4 工程

15. **技能副本会漂移**：仓库改了但 `~\.agents` 没同步，DSH 读旧规则。改完必须 `sync-all`。
16. **pre-commit 默认不生效**：要 `git config core.hooksPath .githooks`。
17. **PowerShell 写 JSON 会带 BOM**：`golden\manifest.json` 中过招；解析用 `utf-8-sig`，写盘用 Python。
18. **批次迁移在 git 里显示删除**：旧扁平文件被跟踪、新布局被 ignore；要保留交付就 `git add -f`。
19. **文档数字手抄必过期**：README 曾写 110/READY 81/93 缺 raw，全错。一律命令取数。

### 5.5 旧店业务教训（别重复）

20. 退款 41% 的主因是漏件/破损/二手，不是文案；**先修品控再放量**。
21. 热销款恰好退货最高（砂光机、电锯、搅拌机）：先小批量验证，别一次压库存。
22. 标价是划线价，实际成交约 6 折；定价按到手价算利润。

---

## 6. 关键命令（维护者用）

```powershell
python qa\check_facts.py                                      # 事实卡门禁
python qa\run_batch.py --input-root input --listing-dir output\批次YYYYMMDD --site MX
python qa\check_images.py --input-root input                  # 图片 P0
python qa\check_certificates.py --input-root input --site MX  # 认证卡口
python scripts\render_prompt.py --sku <SKU> --site MX         # 组装 prompt
python scripts\render_listing.py --json output\_draft\<SKU>.json --out-root output\批次YYYYMMDD
python scripts\eval_pattern.py --batch output\批次YYYYMMDD --golden eval\golden\manifest.json
python qa\selftest.py                                         # 一键回归（4 项）
.\sync-all.cmd                                                # 同步技能副本
```

---

## 7. 数字快照（2026-10-30，跑命令为准）

| 项 | 数值 |
|---|---|
| 输入 SKU | 113（108 有原始数据，5 个没有） |
| 事实卡 | READY=84 / PENDING=16 / QUARANTINED=13 / skip=0 |
| 已出稿（v2） | 81 条，P0=0 P1=0 P2=0 |
| 已上架 | 8 条（Atverce） |
| 黄金集 | 20 条 approved |
| 图片 | 108 SKU：P0=55（40 SKU）/ P1=167/ P2=56 |
| 认证阻断（MX） | 122 条 / 74 SKU（NOM-003 73 + UN38.3 49） |
| 代码版本 | `3e8b2a0`（main，已推送） |

---

## 8. 一句话给下一个人

**工具已经够用，别再打磨；盯三件事：证书、主图、退货率。**
下一批商品等 14 天数据回来再动，别在没数据时优化文案。
