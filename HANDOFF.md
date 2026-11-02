# HANDOFF｜交接文档

> 最后更新：**2026-11-02**（P0/P1/P2 优化完成、9 类目 schema 齐全、pre-commit 三重防护）
> 仓库：https://github.com/ruanxiaoer888/latam-tiktok-listing （private，main）
> 本文件位置 = 仓库根目录 = 流水线主本
> 交互约定：**用户只发一句话，Agent 全自动做完，不展示命令**（见 `AGENTS.md`）
> 新手入口：**`新手怎么用.md`（零命令）**；技术用法见 `README.md`

---

## 0. 一句话

**工具链已完成全面优化（命名统一、结构清理、9 类目 schema 齐全、黄金集 PASS、pre-commit 三重防护），现在可以正常使用了。当前卡点不在工程侧，在「认证 / 主图 / 履约质量」；首批 8 条已上架，进入 14 天观察期。**

---

## 1. 当前任务

**给新开的 TikTok Shop 墨西哥店做上架与冷启动**，来源是美客多商品图 + 粗描述。

当前位置：

- 旧店已放弃，只留教训：30 天 GMV 11,373 MXN / 20 单、**退款 41%**、退货申请 **14/20**、99.4% 流量来自商品卡、实际成交价约标价 6 折。
- 新店品牌确定 **Atverce**；首批 **8 条已上架**（清单见 `首批上架候选-20261029.md`）。
- Listing 侧已就绪：批次20261022-v2 **81 条成稿，P0/P1/P2 全 0**。
- **当前处于 14 天冻结期**：不生成新 Listing、不改提示词，先拿真实数据。
- 待拍板：**63 款电动/电池产品缺证书**——补证，还是把选品收缩到免认证手动工具（当前可售池约 18 款）。
- **工程侧已全部就绪**：命名统一为 `latam-tiktok-listing`，9 个类目都有 schema，不再被事实门禁阻断。

---

## 2. 已完成（2026-11-02，已推送）

### 2.1 P0 清理（安全/数据风险消除）

| 任务 | 详情 |
|---|---|
| `.dumate/` 会话痕迹 | 物理删除，未被 git 追踪 |
| `collector/_work/pack_soplad/` 冗余图片 | 删除 25 张（11.85 MB） |
| `output/` 产物追踪 | 从 git 索引移除 338 个文件（本地保留） |
| `input/` 大文件追踪 | 从 git 索引移除 416 个文件（含 6 个 >100MB 视频），更新 .gitignore |

### 2.2 P1 命名统一

- 全局替换 `listing-pipeline` → `latam-tiktok-listing`（6 文件 12 处）
- GitHub 仓库名、README 标题、git remote 全部统一
- 历史文档（`fabric对照分析`、`审计报告`）中的旧路径标注"已废弃"

### 2.3 P2 结构优化

| 任务 | 详情 |
|---|---|
| 双源关系标注 | `skill/references/` 3 个文件添加来源说明 + README 维护提醒表格 |
| sync 脚本文档统一 | `sync-to-skill.cmd` / `sync-collector-skill.cmd` 添加 ⚠️ 警告，README 明确推荐 `sync-all.cmd` |
| 工具脚本整理 | 4 个 Python 脚本从 `output/_batch/` 移到 `scripts/` |
| requirements.txt 验证 | openpyxl + Pillow 已覆盖所有第三方依赖 |
| 黄金集定位 | manifest.json 添加 `listing_location` 字段，20 个 listing 本地完整 |
| 文档归档 | 2 个一次性分析报告移到 `docs/archive/`，根目录 .md 从 14→12 |
| stale file detection | `sync-all.ps1` 末尾添加残留文件检测，能正确报告"无残留" |

### 2.4 类目 schema 补全

- 新增 4 个类目 schema：家居建材、宠物用品、厨房用品、时尚配件
- 现在 **9 个类目全部有 schema**，不再被事实门禁阻断
- SKILL.md description 更新为"9 个类目包 + schema"

### 2.5 pre-commit hook 增强

- Check 1: 拦截 >50MB 大文件（建议用 Git LFS）
- Check 2: 拦截 `.dumate/` 和 `_work/` 等敏感/临时路径
- Check 3: 保留原有 selftest 回归测试

### 2.6 黄金集回归测试

- P0=0 P1=0 P2-结构=0 P2-转化=0 → **PASS**
- 存档：`output\_eval\listing_write@1.0.0.json`

### 2.7 同步验证

- 全局技能目录：64+8+15 文件，hash OK
- selftest：4/4 PASS
- DuMate 副本：已在应用内手动更新

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
20. **GitHub 连接不稳定**：偶尔超时属正常，本地提交成功后稍后再推即可。
21. **嵌套文件夹问题**：之前同步时出现过 `latam-tiktok-listing/latam-tiktok-listing/` 嵌套，已通过删除 + 重新同步解决，现在 `sync-all.ps1` 有 stale file detection 防止复发。

### 5.5 旧店业务教训（别重复）

22. 退款 41% 的主因是漏件/破损/二手，不是文案；**先修品控再放量**。
23. 热销款恰好退货最高（砂光机、电锯、搅拌机）：先小批量验证，别一次压库存。
24. 标价是划线价，实际成交约 6 折；定价按到手价算利润。

---

## 6. 关键命令（维护者用）

```powershell
python qa\check_facts.py                                      # 事实卡门禁
python qa\run_batch.py --input-root input --listing-dir output\批次YYYYMMDD --site MX
python qa\check_images.py --input-root input                  # 图片 P0
python qa\check_certificates.py --input-root input --site MX  # 认证卡口
python scripts\render_prompt.py --sku <SKU> --site MX         # 组装 prompt
python scripts\render_listing.py --json output\_draft\<SKU>.json --out-root output\批次YYYYMMDD
python scripts\eval_pattern.py --batch output\批次YYYYMMDD --pattern listing_write@1.0.0
python qa\selftest.py                                         # 一键回归（4 项）
.\sync-all.cmd                                                # 同步技能副本 + stale 检测
```

---

## 7. 数字快照（2026-11-02，跑命令为准）

| 项 | 数值 |
|---|---|
| 输入 SKU | 113（108 有原始数据，5 个没有） |
| 事实卡 | READY=84 / PENDING=16 / QUARANTINED=13 / skip=0 |
| 已出稿（v2） | 81 条，P0=0 P1=0 P2=0 |
| 已上架 | 8 条（Atverce） |
| 黄金集 | 20 条 approved，回归测试 PASS |
| 类目 schema | 9 个齐全（五金工具/汽车摩托/家居建材/运动户外/宠物/厨房/家电/时尚配件/服装） |
| 图片 | 108 SKU：P0=55（40 SKU）/ P1=167/ P2=56 |
| 认证阻断（MX） | 122 条 / 74 SKU（NOM-003 73 + UN38.3 49） |
| pre-commit 防护 | 三重：大文件 + 敏感路径 + selftest |
| 代码版本 | `4e15cae`（main，已推送） |

---

## 8. 一句话给下一个人

**工具已经够用且经过全面优化，别再打磨工程侧；盯三件事：证书、主图、退货率。**
下一批商品等 14 天数据回来再动，别在没数据时优化文案。
