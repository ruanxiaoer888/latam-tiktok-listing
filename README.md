# listing-pipeline｜拉美 TikTok Shop Listing 生产流水线

> 2026-10-20 建立，v1.3（2026-10-21 加转化层）；2026-10-22 门禁强制化 + 同步/自检基础设施（见 `HANDOFF.md` 抬头那一节）。把 Gemini GEM 那套「内容标准」搬进可批量、可校验的运行环境。

## 身份

**一个技能（SKILL.md）+ 一套规则包 + 一个校验脚本 + 一份案例索引。** 不依赖任何平台：

- **技能入口**：`SKILL.md`（DSH / Claude Code / Codex 可识别）
- **全局安装**：`%USERPROFILE%\.agents\skills\latam-tiktok-listing\`（副本，DSH 自动加载）
- **主本**：本目录。改规则只改这里，改完跑 **`sync-all.cmd`**（一次同步两个技能 + SHA256 校验 + 三处状态表；老的 `sync-to-skill.cmd` 仍可用）
- **版本库**：本目录就是 git 仓库根目录（`origin` = GitHub 私有库）。提交数 / 文件数**不抄数字**，跑 `git rev-list --count HEAD` / `git ls-files | wc -l`；换电脑 / 迁移步骤见 `迁移到新电脑.md`
- **交接**：`HANDOFF.md`（当前任务、已完成、卡住的问题、下一步、踩过的坑）；全量审计见 `审计报告-20261022.md`

## 目录

```
listing-pipeline\
├─ SKILL.md               技能入口（什么时候用、怎么用、硬约束）
├─ README.md              本文件
├─ HANDOFF.md             交接文档（现状 / 已修 / 仍开放 / 坑 / 命令速查）
├─ 使用说明.md            日常操作版（采集 → 事实卡 → 生成 → 校验 四步）
├─ 迁移到新电脑.md        换机手册（家里 ↔ 公司）
├─ 采集怎么用.md          采集动作说明（给人看的版本）
├─ 采集清单.md            采集清单（2026-10-21 快照；当前以 input\ 目录为准）
├─ 审计报告-20261022.md   全量审计（P0/P1/P2 + 待拍板）
├─ requirements.txt       系统 Python 依赖（openpyxl / Pillow；DSH 自带 Python 已含）
├─ .gitattributes         换行与二进制策略（跨机器稳定）
├─ .githooks\pre-commit   提交前自动跑 qa\selftest.py（装法见 迁移到新电脑.md）
├─ setup-new-pc.cmd/.ps1  新电脑：装两个技能 + hooksPath + 自检
├─ sync-all.cmd/.ps1      一次同步两个技能 → ~\.agents，逐文件 SHA256 校验 + DuMate 副本只告警
├─ sync-to-skill.cmd/.ps1       只同步「Listing 生成」技能（保留兼容）
├─ sync-collector-skill.cmd/.ps1 只同步「美客多采集」技能（保留兼容）
├─ source-gemini\         V3.2 四份原始文件副本（只读）
├─ collector\             美客多采集技能（mercadolibre-listing-collector：SKILL.md + references\ + scripts\）
├─ skill\
│  ├─ 生成提示词.md       模型无关 prompt 模板（角色/工作流/硬约束/模块开关）
│  ├─ 骨架.md             Listing 输出结构 + 排版硬规范
│  ├─ 转化层.md           转化率手册（首屏/卖点排序/疑虑/权益/替代表达/6 条自检）
│  ├─ 属性映射.md         ML 属性 → TikTok 槽位映射规则（电池电压 vs 充电器电压等）
│  ├─ rules-mx.md         墨西哥规则包（es-MX）
│  ├─ rules-br.md         巴西规则包（pt-BR，重写非机翻）
│  ├─ 类目\               8 个类目包
│  ├─ 案例库索引.md       9 条案例 → 类目映射、盲区、few-shot 规则
│  └─ 短视频脚本.md       可选模块 B（Hook/CTA/结构），默认不生成
├─ qa\
│  ├─ denylist.json         违规词 + 结构规则 + 8 类目必带信息（MX/BR）+ 合规来源
│  ├─ certifications.json   认证台账（规则 + 证书明细；上架前卡口主本）
│  ├─ check_certificates.py 认证检查器（缺失/过期/待确认 + 换证提醒）
│  ├─ 认证台账说明.md        字段定义、维护 SOP、飞书导入
│  ├─ 认证台账_导入模板.csv  飞书多维表格导入模板（含示例行）
│  ├─ check_listing.py      合规 + 转化校验器 v1.3
│  ├─ build_facts.py        事实卡构建（input.json + overrides → facts.json）
│  ├─ index_kb.py           事实库索引（kb\_index\products.csv）
│  ├─ verify_facts.py       人工核验后批量置 verified
│  ├─ source_digest.py      原始摘要（input.json → output\_batch\digest.md）
│  ├─ facts_digest.py       生成用事实摘要（facts.json → 摘要；默认只出 verified）
│  ├─ check_facts.py        事实卡门禁（schema 必填/完整度 → kb\_index\完整度报告.md）
│  ├─ check_facts_quality.py 数据质量哨兵（品牌/电压/功率/单位/价格口径）
│  ├─ map_attributes.py     ML 属性 → TikTok 槽位映射（电池工具电压口径等）
│  ├─ build_batch_csv.py    批量：input + listing → 校验用 CSV
│  ├─ make_batch_xlsx.py    批量：校验结果 + 备注 → 批次结果.xlsx
│  ├─ make_review_notes.py  事实卡 → review_notes.json + 待补数据清单.md
│  ├─ run_batch.py          一条命令跑完 门禁 + 映射 + 校验 + 出表
│  ├─ selftest.py           一键回归（4 组基线断言，供 pre-commit 用）
│  ├─ collect_inputs.py     采集入参整理（辅助）
│  ├─ build_check_csv.py    校验 CSV 构建（辅助）
│  ├─ 测试样例.csv          回归用例（含 核心词 / 类目 两列）
│  └─ 报告\<日期>\          扫描输出（check_listing 单独跑时写这里）
├─ kb\                    产品事实库：_schemas\（4 个类目 schema + _fields.md）、_index\（脚本生成，不进 git）
├─ input\                 待处理商品（一个子目录一个 SKU；facts.json / overrides.json / img_manifest.csv 进 git，图与原始 json 不进）
└─ output\                生成结果：批次<日期>\（当期成稿随批次入库，见下）、_batch\ _smoke\ 报告不入库
```

> **SKU 数不要抄**：以 `input\` 实际目录为准（当前 110 个，其中 2 个「服装」类目未登记 schema，会被 `check_facts.py` 跳过 → 见「门禁」一节）。同理 `kb\_schemas\` 当前 4 个类目 schema（五金工具 / 汽车摩托 / 家电 / 运动户外）。

## V3.2 整合对照表（四份文件去哪了）

| V3.2 内容 | 落到哪 | 状态 |
|---|---|---|
| Gem 提示词：角色定义 / 工作流 | `skill\生成提示词.md` + SKILL.md 步骤 | ✅ |
| 防幻觉、`[POR CONFIRMAR]` 占位 | 生成提示词 + 骨架 + 校验 P0 | ✅ |
| 模块 A：标题区/详情区结构、代码块 | `skill\骨架.md`（改为直接出文件，比复制更彻底） | ✅ |
| 模块 B：短视频脚本 | `skill\短视频脚本.md`（默认关闭，按需开） | ✅ 迁入但默认不用 |
| 模块 C：中文审核备注 | 骨架 第 4 节 | ✅ |
| 词库：本地化表达 | `rules-mx` 第 3 节 / `rules-br` 第 3 节 | ✅（俚语降级到脚本） |
| 信任 / CTA 词 | `rules-*` 第 4 节 | ✅ 修正 `Compra protegida` |
| 语法基调（Tú / 倒标点 / 度量衡 / MXN） | `rules-*` 第 1–2 节 | ✅ |
| 标签库 | `rules-*` 第 5 节 | ⚠️ 有意改为默认关闭（待 A/B） |
| 消费节点 | `rules-mx` 第 6 节 + 补巴西节点 | ✅ |
| 违禁词表 | `rules-*` 第 7 节 + `denylist.json` | ✅（`100%` 改上下文判定） |
| 5 个品类写作公式 | `skill\类目\` 8 个包 | ✅ 扩到 8，补建材/汽摩适配 |
| 9 条案例 | `skill\案例库索引.md` + `source-gemini\` | ✅ 索引 + 标注 4 条需修 |
| 短视频 Hook / CTA 库 | `skill\短视频脚本.md` | ✅ |
| Pro Tip：事实边界 | 生成提示词 + SKILL 硬约束 | ✅ |

**未整合（有意）**：代码块"一键复制"的交互方式——流水线直接出文件/表格，不需要复制这一步。

## 怎么用

全部命令**在仓库根执行**，需要时先 `cd qa`（不写盘符，换机器不失效）。

```powershell
cd qa

python check_listing.py --input 导出.csv --site MX                 # 基本扫描
python check_listing.py --input 导出.csv --site MX --category 家电  # 加类目必带信息
python check_listing.py --input 导出.csv --site BR                 # 巴西（会拦"混入西语"）
python check_listing.py --input 导出.csv --site MX --fail-on-p0    # P0 时退出码 3
python check_listing.py --demo --site MX                           # 回归自检（基线 0/4/9/14）
python check_listing.py --input 测试样例.csv --site MX

# 认证卡口（上架前）：缺失/过期/待确认 + 换证提醒
python check_certificates.py --input-root ..\input --site auto          # 按 facts 已声明站点
python check_certificates.py --input-root ..\input --site ALL --strict  # 双站口径，有阻断项退出码 3
python check_certificates.py --demo                                     # 自检
# --site 只收 AUTO / MX / BR / ALL（大小写不敏感，拼错 exit 2）；--today 可覆盖当天日期

# 事实卡两道检查（生成前，零模型成本）
python check_facts.py                                              # schema 必填/完整度门禁；READY 才可生成
python check_facts.py --fail-on-skip                               # 有 SKU 因类目 schema 未登记被跳过 → exit 3
python check_facts.py --fail-on-blocked                            # 有 BLOCKED 或 FAIL → exit 3
python check_facts_quality.py --input-root ..\input --strict        # 口径一致性，P0 退出码 3
python check_facts_quality.py --demo                                # 自检

# 生成用事实摘要（默认只输出 verified，避免拿 draft 去写文案）
python facts_digest.py                                             # 81 条 verified
python facts_digest.py --status all --include-pending              # 排查用：连缺必填项的 draft 一起看

# 一条命令跑完 属性映射 + 校验 + 出表（生成仍由 Agent 完成）
python run_batch.py --input-root ..\input --listing-dir ..\output\批次YYYYMMDD --site MX
# 退出码：0 通过 / 1 运行期错误 / 2 参数错误 / 3 门禁拦截（有被拒 SKU，或 listing 有 P0）
# 被拒 SKU 默认不校验（facts 缺失或 status != verified）；仅调试可加 --allow-unverified
```

**每次跑完的校验明细在 `output\_smoke\run_batch_<时间戳>_<pid>\`**（每次唯一目录，不会撞分钟；gitignored）。
`check_listing.py` 单独跑时仍写 `qa\报告\<日期>\`。

**可选列**（有就用，没有跳过）：`核心词/keyword`（检查前 30 字符）、`类目/category`（按行套类目检查）、`SKU/商品ID`（报告区分条目）。

## 校验能力（v1.3）

三层同时校：**合规（P0/P1）+ 结构（P2-结构）+ 转化（P2-转化）**。

**P0（上架必失败）**：中文残留、`[POR CONFIRMAR]` 占位、标题超平台上限、描述超 10000、**空标题/空描述**

**P1（违规/误导）**：绝对化、医疗宣称、虚假紧迫、站外导流、未验证物流/信任承诺、`100%` 上下文、跨语言混入

**P2-结构（影响流量与退货）**：标题不在 60–80、核心词不在前 30、标题重复词堆砌、描述过短、缺 📋📦💡 分段、单行 Emoji >2、模型腔结构标签残留、标签过多、**类目必带信息缺失**、**英制单位未换算**、**价格未标币种**

**P2-转化（影响点击后的转化率）**：标题无 `para…` 用途词、首屏空泛开场（`alta calidad` 这类）、首屏以参数开头、卖点 >5 或 1–2 条、第一条卖点先讲参数、出现折扣/权益词需核实、FAQ <2 条

> P2-结构 是「写得像不像样」，P2-转化 是「卖不卖得动」。处理顺序：P0 → P1 → P2-转化 → P2-结构。
> 报告与明细里两类分开计数；`批次结果.xlsx` 有独立的 `P2结构` / `P2转化` 两列（转化超标黄）。

**查不了**：参数与图/原文是否一致、证书真伪、汽配适配表准确性（需事实卡 + 人工）；**也没有转化率数据**——后台的曝光/点击/转化需要你导出，脚本只判断文案质量。

## 认证卡口（v1.0，2026-10-22 修误报）

上架前回答三个问题：**这个 SKU 在这个站点要不要认证、有没有、过没过期**。

| 检查 | 触发 | 严重度 |
|---|---|---|
| NOM-003 | MX 电动类（五金/家电/汽摩）+ **仅 127V 市电**（`min_voltage_v: 100`，12V 直流车充不触发） | 阻断 |
| INMETRO | BR 电动类 | 提醒（适用范围待确认） |
| ANATEL | 含蓝牙/WiFi/射频模块（`inalámbrico` 不算） | 阻断 |
| UN38.3 | 含锂电池（含随包电池）——**只认正面电池证据**：`Incluye batería: No`、电瓶夹、点烟器线都不算 | 阻断 |

- 主本：`qa/certifications.json`（规则 + 证书；**证书明细现在是空的，全部报 missing 是事实**）
- 检查器：`qa/check_certificates.py`，状态 `valid / expiring / expired / unverified / missing`
- **口径**：认证卡口**只挡上架、不挡生成**（生成端只受 `facts.json` 门禁约束）
- 当前阻断 = **116 条**（NOM-003 70 + UN38.3 46，覆盖 71 个 SKU，`--strict` 退出码 3）——**「条」是行数不是 SKU 数**，一个 SKU 可能要两张证
- `--site` 只收 `AUTO / MX / BR / ALL`（大小写不敏感；`AUTO` 按 facts 已声明站点，当前 110 份全是 MX）；`--today YYYY-MM-DD` 可覆盖当天日期
- 换证提醒窗口默认 60 天，`--days` 可调
- 飞书导入：`qa/认证台账_导入模板.csv`；字段与 SOP 见 `qa/认证台账说明.md`
- `--strict` 有阻断项退出码 3，可接上架前卡口

## 事实卡检查（生成前）

| 工具 | 查什么 | 产物 |
|---|---|---|
| `qa/check_facts.py` | 按 `kb/_schemas/<类目>.schema.json` 查必填/完整度/门禁 | `kb/_index/完整度报告.md` |
| `qa/check_facts_quality.py` | **字段之间的口径一致性** | `qa/报告/<日期>/数据质量检查.csv` |
| `qa/facts_digest.py` | facts.json → 生成用摘要（**默认只出 `verified`**） | `output\_batch\facts_digest.md` |

**口径检查项**：品牌冲突（`identity.brand` vs `raw.Marca`）、型号不一致、电池电压/充电器电压混用、电压口径冲突（18V vs 21V）、功率物理不可能（>27A）、电池工具功率偏高（>600W）、回路偏高（16–27A）、功率字段与属性不一致、容量/重量单位错、噪音异常、价格/币种、属性键值错位、材质仅来自描述、标题英制单位。

**历史实测（2026-10-21，15 个 SKU，修复误报前）**：P0=2、P1=7、P2=8。
- P0：`ATVMX11700` 6800W / 127V ≈ 53.5A；`BKU0000000` 品牌 `Atverce` vs `Marca=Fanny`
- P1：`MMV2000000` 18V/21V 冲突；`ABU5000000`(1500W)、`AMU6000005`(900W)、`MMV2000000`(850W) 电池功率偏高；`MBU6000001`(19.7A)、`ZK2604270H`(22A) 电流偏高

**退出码**：`0` 正常；`2` 输入/文件问题；`3` `--strict` 且有 P0 / `--fail-on-blocked` 有 BLOCKED 或 FAIL / `--fail-on-skip` 有类目未登记的 SKU 被跳过。

## 门禁（2026-10-22 起是强制的，不是建议）

| 环节 | 命令 | 拦截行为 |
|---|---|---|
| 事实卡 | `python qa\check_facts.py` | 四态：`verified`=可生成 / `draft`=待核 / `quarantined`=移出 / `blocked`=硬伤。当前 READY=81、PENDING=14、QUARANTINED=13、跳过 2（类目未登记） |
| 跳过保护 | `python qa\check_facts.py --fail-on-skip` | 有 SKU 因类目 schema 未登记被跳过 → exit 3 |
| 口径哨兵 | `python qa\check_facts_quality.py --input-root input --strict` | P0 时 exit 3 |
| 认证卡口 | `python qa\check_certificates.py --input-root input --strict` | 只挡上架，不挡生成 |
| 生成摘要 | `python qa\facts_digest.py` | 默认只输出 `verified`（81 条）；`--status` 可指定状态，但缺必填项的 draft 仍会被门禁挡住，只有排查时才加 `--include-pending` |
| 批次卡口 | `python qa\run_batch.py ...` | 任一步骤失败立即中止；默认拒绝 facts 缺失或 `status != verified` 的 SKU 并 exit 3，被拒原因写进 `批次结果.xlsx` 备注；`--allow-unverified` 仅供调试 |

> `verified` 的现状提醒：当前 81 个 `verified` 是批量核验产出的（`_meta.verified_by` 自述「待人工抽查」），**不等于人工逐条核过**——见 `HANDOFF.md`「仍开放」第 1 条。

## 转化层是什么（v1.3）

`skill\转化层.md`——把「合规合格」升级成「有人买」。核心四件事：

| 关卡 | 内容 | 为什么 |
|---|---|---|
| GATE 1 标题 | L1 品类词 + L2 用途词（`para…`）落在前 30 字符 | 手机端截断；用途词直接扩搜索面 |
| GATE 2 首屏 | 描述第 1 行 = 具体场景/痛点，≤60 字符 | 折叠区内决定「留不留」 |
| GATE 3 卖点 | 3–5 条，按痛点→兼容→材质→易用排，第一条不是参数 | 买家按这个顺序决策 |
| GATE 4 疑虑 | 兼容 / 含什么 / 隐藏成本 三问答清，FAQ ≥2 条 | 既提转化又降退货 |
| GATE 5 权益 | 只写后台真实存在的，不叠时效 | 合规与转化的交汇点 |

**关键判断**：合规 ≠ 保守 ≠ 低转化。同样合规的两种写法，转化差几倍；转化层全部在合规红线内操作。

## 已验证结果

> 下表是**历史记录**（2026-10-21 / 10-22 实测），不是当前基线；**当前基线一条命令跑**：`python qa\selftest.py`（4 组断言，0.6–0.8 秒，全 PASS 才算没改坏）。

| 验证项 | 结果 |
|---|---|
| V3.2 的 9 条黄金案例自检 | 9/9 命中：P0=0，P1=4（全是 `Compra protegida`），P2=9（描述内标签） |
| 5 条回归用例 | 4/5 命中：P0=2（中文、占位符）、P1=3、P2=14；1 条干净判干净 |
| 西语文案用 BR 规则扫 | 拦出 6 处"混入西语" |
| `100%` 上下文 | `100% acero inoxidable` 不报，`100% garantizada` 报 |
| 空字段 | 空标题 → P0；空描述 → P1 |
| 英制/币种 | `12 pulgadas`、`2 lb`、`$299` 无 MXN → 均报 |
| 正常分段不误报 | `📋 Especificaciones:` 不再被判"结构标签" |
| 退出码 | 3（P0）/ 2（参数错）/ 0（正常） |
| **转化侧 7 条检查**（v1.3） | 3 条构造用例命中 8 处：好例子 0 处、空泛开场 5 处、参数开场+卖点堆砌 3 处，逐条命中正确 |
| **转化侧回归**（v1.3） | 9 案例 / 15 批次：P0、P1、P2-结构 三项与 v1.2 **完全一致**（0/4/9、0/0/3），新增 P2-转化 14 / 14 |
| 自有产出的真实缺口 | 15 条批次里 **9 条标题无 `para…` 用途词、5 条第一条卖点是参数**——都是老提示词生成的，按新规则重生成即修 |
| **单条前后对照**（v1.3） | `ABU5000000` 按转化层重写：P2-转化 **2 → 0**，P0/P1/P2-结构 保持 0，标题 79 字符（升版前：标题无用途词 + 首条卖点是参数）。新旧两版见 `output\批次20261020\` 与 `output\批次20261021\` |
| **20261022 批次（81 条）** | P0=0 / P1=0 / P2-结构=50 / P2-转化=0（`output\批次20261022\批次结果.xlsx`） |
| **基础设施回归** | `python qa\selftest.py` → 4/4 PASS：`check_listing --demo` = 0/4/9/14；`check_facts` = READY 81 / QUARANTINED 13 / skip 2；两个 `--demo` 自检 |

## 待办

0. **拿后台数据做定向优化**：导出已上架 SKU 的 曝光 / 点击率 / 转化率 / 退货率。点击低 → 改主图和标题；点了不买 → 改首屏和价格。没有这组数，转化层只能做「下限提升」
1. **扫真实存量**：导出 200–500 条已上架 Listing 跑一遍，出命中率（>10% 说明必须进流程）
2. **接生成端**：`input\商品ID\`（图片 + input.json）→ 事实卡 facts.json → 按 `生成提示词.md` 生成 → 过校验 → 出 `output\批次.xlsx`
3. **汽配适配表结构化**（退货最大头）
4. **补 BR 案例**：现在 0 条葡语案例，规则有了但缺锚点
5. **认证台账**：✅ v1.0 已建（`qa/certifications.json` + `qa/check_certificates.py`），待向供应商/认证机构收集证书号与有效期后填入
6. **补服装/时尚配件 schema**：当前 2 个「服装」SKU 无 schema，被 `check_facts.py` 跳过 → 门禁不覆盖

## 同步与自检（2026-10-22 新增）

```powershell
# 改完规则后（一次同步两个技能 + 逐文件 SHA256 校验 + 三处状态表）
.\sync-all.cmd                 # DuMate 副本只告警，需在 DuMate 内自己更新
.\sync-all.ps1 -DryRun         # 只看状态表，不写任何文件

# 一键回归（4 组基线断言）
python qa\selftest.py          # 详细；--quiet 只留失败与汇总
```

- **提交前自动跑**：`.githooks/pre-commit`（装法：`git config core.hooksPath .githooks`，`setup-new-pc.ps1` 会自动设）；selftest 失败则阻止提交
- **依赖**：系统 Python 需要 `openpyxl` / `Pillow` → `python -m pip install -r requirements.txt`；DSH 自带 Python 已含两者
- **换行策略**：`.gitattributes` 统一（`.ps1/.cmd` = CRLF，图与 xlsx = binary），两台机器来回换不会产生假 diff

## 注意

- 平台规则会变（标题上限、认证要求）：建议 `denylist.json` 加 `verified_at`，每季度回后台核一次
- 只做"生成 + 校验"，**不做自动上传**
- `output\` 结构：`批次<日期>\` 是正式产出，**当期成稿随批次入库（现状）**；`_batch\`、`_smoke\`、`_归档\`、报告不入库。是否长期入库待定（见 `审计报告-20261022.md` §七-2）。`input\output` 里**以下划线开头的目录/文件不参与批次**（脚本自动跳过）
- 本机 shell 是 Windows PowerShell 5.1：`.ps1` 要么纯 ASCII、要么存成带 BOM 的 UTF-8，否则中文注释会让脚本语法报错
- **暂不接模型 API 跑生成**：规则还在迭代（每批都会暴露新的源数据坑），先让 Agent 按 skill 生成、人工校准 2–3 批再自动化；`run_batch.py` 只封装"门禁 + 映射 + 校验 + 出表"这段确定性工作
