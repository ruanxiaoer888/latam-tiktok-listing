# HANDOFF｜交接文档

> 最后更新：**2026-10-22**（审计 + 修复；v1.3 转化层 + 生成前事实门禁 + 门禁强制化）
> 仓库：https://github.com/ruanxiaoer888/listing-pipeline （private）
> 本文件位置 = 仓库根目录 = 流水线主本

---

## 2026-10-22 审计与修复（最新，先读这节）

全量审计见 `审计报告-20261022.md`（7 条 P0 + P1/P2 清单 + 4 个待拍板）。**两轮**共修完 9 组：

| 已修（第一轮） | 结果 |
|---|---|
| 1. 门禁强制化 | `run_batch.py` 默认拒绝非 `verified` / 缺 facts 的 SKU（exit 3）、任一步骤失败立即中止、P0 也 exit 3；`check_facts.py` 新增 `--fail-on-skip`；`facts_digest.py` 默认只出 `verified` |
| 2. 同步与哈希校验 | 新增 `sync-all.cmd/.ps1`：一次同步两个技能 + 逐文件 SHA256 + 「仓库 / ~\.agents / DuMate」三处状态表；`-DryRun` 只看不写；DuMate 副本只告警不写 |
| 3. 自检与钩子 | 新增 `qa\selftest.py`（4 组基线断言）+ `.githooks/pre-commit`（提交前自动跑）+ `requirements.txt` + `.gitattributes` |
| 4. 卫生清理 | `.dumate\` 页面快照（含疑似 token）删除并加 `.gitignore`；`使用说明.md`、2 个服装 SKU 的 facts 入库；旧机路径清空；打包 zip 移除 |
| 5. 认证误报 | 125 → **116 条**（NOM-003 70 + UN38.3 46，71 个 SKU）：摘掉 2 条 12V 车充 NOM-003、7 条 UN38.3 误判 |

| 已修（第二轮） | 结果 |
|---|---|
| 6. 尺寸哨兵 | 新增 `qa\fix_size_fields.py`（默认 dry-run，`--apply` 才写），已 apply：**11 个 SKU / 18 个字段**置 null，原值留在 `facts._meta.size_fix`；`check_facts_quality.py` 新增 `FQ-P0-SIZE-IMPLAUSIBLE`；`build_facts.py` 加固（量级/单位不对直接置 null + warning）。`--strict` = P0=0 P1=21 P2=52，exit 0 |
| 7. 图片检查 | 新增 `qa\check_images.py`（数量/尺寸/比例/格式/重复/白底）：17 SKU / 145 图 → **P0=11（9 个 SKU）/ P1=29（13 个）/ P2=10**，exit 3；`--demo` 19/19。文字/水印仍需人工核对 |
| 8. 清单自动化 | `gen_manifest.py --plan` 现在出「完整/只有 facts/损坏」三计数且**非 0 退出**（本次 17/93/0，exit 1；`--allow-incomplete` → 0）；自动清单 `output\_batch\采集清单-自动.md`（185 行，含 110 个目录状态表）；`build_input.py` 类目白名单改为动态读 `kb\_schemas\*.schema.json`（5 个） |
| 9. 服装类目 | 新增 `kb\_schemas\服装.schema.json`（required：品牌 / 面料成分 / 尺码 / 包装清单）+ `skill\类目\09-服装.md`；类目 8→9、schema 4→5。`check_facts` = **样本 110 / READY=81 / PENDING=16 / QUARANTINED=13 / 跳过 0 / FAIL=0**，`--fail-on-skip` 现 exit 0 |

**仍开放 5 项**（都需要人拍板或补资料）：
1. 81 个 `verified` 是批量核验产出（`verified_by` 自述「待人工抽查」）→ 抽查 10 个再决定是否退回 `draft`（审计 §七-1）；
2. 110 个 SKU 里 **93 个缺 `input.json/item.json/img`**（只剩 facts）→ facts 不可重建，需从原采集机补；
3. 认证台账仍为空 → 116 条 `missing`，只挡上架不挡生成；
4. **服装 2 个 SKU 待补**：`AXNJCPS300` / `AXNJCQS502` 缺面料成分、尺码、包装清单（PENDING），且图片检查 P0=2（`AXNJCPS300` 01.jpg 562×1200，短边 <800 且主图非 1:1）→ **主图需重采/裁方**；
5. **BR 站未实测**（110 份 facts 的 `site_profiles` 全是 MX，INMETRO/ANATEL 从未真正触发）。

> 图片合规检查本身已落地（原「图片校验未做」一项已关闭）；剩下的是**补图**和**人工核水印**。

---

## 0. 如果只看三件事

1. **目标别跑偏**：这一切的最终目的只有一个——**在合规前提下，写出能提高转化率的 Listing**。校验器、事实库、门禁都是手段，不是目的。
2. **环境**：公司电脑 clone → 覆盖 `input` → 双击 `setup-new-pc.cmd`，看到 `ALL DONE.` 即可开工。
3. **成本**：白天（峰时）只做零模型成本的活（脚本校验、核事实、改规则）；批量生成留到夜间谷时。
4. **现在的卡点**：门禁已是强制的 → `READY=81` 可生成，但**这 81 个 `verified` 是批量核验产的、缺人工抽查**；另有 16 个 `draft`（14 个缺包装清单 + 2 个服装缺面料/尺码/包装）、13 个 `quarantined`；**跳过 0**（服装 schema 已补）。上架前还有两道：认证台账空（116 条 missing）+ 图片检查 P0=11（9 个 SKU，服装主图需重采）。

---

## 1. 当前任务

**核心目的**：生产**高转化率**的 TikTok Shop 商品 Listing，前提是**安全合规**。
- 转化率 = 流量精准度 × 承接效率 × 价格/信任。Listing 只负责中间那段「承接效率」。
- 所以 **Listing 需要满足的不只是「不违规」，还要「被看懂、被相信、被推一把」**。
- 合规 ≠ 保守 ≠ 低转化：同样合规的两种写法转化能差几倍，转化层全在红线内操作。

**工程主线**：拉美 TikTok Shop（墨西哥 5 店 + 巴西 6 店，全部本土店，运营团队在国内）的 Listing 生产流水线，从「能生成」推进到「能批量、能校验、能投产」。

**当前所处的阶段**：
- 合规层 + 转化层 + 工具链已成型（v1.3）；**门禁已是强制的**（2026-10-22），MX 站跑通 81 条批次；
- 事实层落地（`kb/` + 每 SKU 一份 `facts.json`，生成唯一事实来源）+ 生成前三道门禁（事实卡 / 口径 / 认证）；
- **2026-10-22 审计后**：同步哈希校验、一键自检、pre-commit、依赖与换行策略补齐；认证误报摘掉 9 条；
- 还差的东西：**后台真实数据**（曝光/点击/转化/退货），没有它只能做下限提升，做不了定向优化。
- BR 站还没实际跑过（所有验证都是 MX）。
- 具体数字不写死：跑 `python qa\check_facts.py`（事实卡）、`python qa\check_certificates.py --input-root input --strict`（认证）、`git rev-list --count HEAD`（提交数）。

---

## 2. 已完成的内容

### 2.1 流水线本体

| 模块 | 内容 | 状态 |
|---|---|---|
| 技能入口 | `SKILL.md`，已装到全局 `%USERPROFILE%\.agents\skills\latam-tiktok-listing` | ✅ DSH 可加载 |
| 站点规则 | `skill\rules-mx.md`（es-MX）、`skill\rules-br.md`（pt-BR，重写非机翻） | ✅ |
| 类目包 | `skill\类目\01~08`（五金工具/汽车摩托/家居建材/运动户外/宠物/厨房/家电/时尚配件） | ✅ 8 个 |
| 输出骨架 | `skill\骨架.md`（标题结构、分区、长度 + 转化侧首屏/卖点规则、⭐ 行间空行） | ✅ |
| 转化层 | `skill\转化层.md`（5 个 GATE + 关键词三层 + 合规替代表达 + 6 条转化自检） | ✅ |
| 属性映射 | `skill\属性映射.md` + `qa\map_attributes.py`（13 个槽位，5 条硬规则） | ✅ |
| 合规校验 | `qa\check_listing.py` v1.3 + `qa\denylist.json` v1.1（含官方来源清单） | ✅ |
| 批次脚本 | `collect_inputs` / `map_attributes` / `build_batch_csv` / `check_listing` / `make_batch_xlsx` / `run_batch` | ✅ |
| 案例库 | `skill\案例库索引.md`（9 条）+ `source-gemini\` 原始 V3.2 四份 | ✅ |
| 换机脚本 | `setup-new-pc.cmd/.ps1`、`sync-all.cmd/.ps1`（两个技能 + 哈希校验）、`迁移到新电脑.md` | ✅ |
| 自检 | `qa\selftest.py`（4 组基线断言）+ `.githooks/pre-commit`（提交前自动跑） | ✅ |

### 2.2 事实层（历史快照 · 2026-10-21 公司电脑新增）

> ⚠️ 本节数字是 2026-10-21 那一刻的状态（15 个 SKU），**不是现状**；现状见 §9 与 `kb\_index\完整度报告.md`。

| 项 | 内容 |
|---|---|
| 事实卡 | `input\<SKU>\facts.json` × 15（当时）：品牌/供电/电压/功率/尺寸/包装/兼容/认证/图片哈希/门禁 |
| 图片清单 | `input\<SKU>\img_manifest.csv`：哈希、主图、重复组 |
| 人工确认 | `input\<SKU>\overrides.json` × 4（当时）：按点路径覆盖 + 解除阻断 + 加警告 + 隔离；重建自动重放 |
| 字段字典 | `kb\_schemas\_fields.md` + 类目 schema（当时 3 个；现为 **5 个**：五金工具/汽车摩托/家电/运动户外/服装） |
| 状态机 | `draft`（待核）→ `verified`（可生成）/ `quarantined`（移出生成集）/ `blocked`（硬伤） |
| 版本库 | `facts.json`、`overrides.json`、`img_manifest.csv` **进 git**；`input.json`/`item.json`/`img/` 不进 |
| 构建/门禁 | `qa\build_facts.py`（`--check` 只报告不写）/ `check_facts.py` / `index_kb.py` / `verify_facts.py` |
| 数据质量哨兵 | `qa\check_facts_quality.py`：品牌/型号冲突、电池 vs 充电器电压、电压口径、功率物理、单位、价格币种、属性键值错位 |
| 认证卡口 | `qa\check_certificates.py` + `qa\certifications.json` + `认证台账说明.md` + 飞书导入模板 |
| 生成摘要 | `qa\source_digest.py`（原始摘要）、`qa\facts_digest.py`（facts → 摘要，默认只出 verified） |

**认证规则**：NOM-003（MX 电动类 + ≥100V，阻断）、INMETRO（BR，范围待确认→只提醒）、ANATEL（只认 bluetooth/wifi/2.4G/radio，`inalámbrico` 不算）、UN38.3（只认正面电池证据）。**认证只挡上架、不挡生成**。

**历史隔离 4 个（2026-10-21 当时）**：`ATVMX11700`、`AMR3000002`、`BKU0000000`、`MMV2000000`（现状已隔离 13 个，见 `完整度报告.md`）。

**历史干净候选 11 个（当时）**：`ABTL000006`、`ABU5000000`、`ABU6000008`、`ABU600000T`、`AHR6C50002`、`AMU0000003`、`AMU3CI0000`、`AMU6000005`、`ATVMX18200`、`MBU6000001`、`ZK2604270H`。

### 2.3 换机与版本管理

| 项 | 结果 |
|---|---|
| 仓库根目录 | 就是本目录（`listing-pipeline`），两层结构已是历史（现在 clone 出来这层就是根） |
| GitHub | 私有库 `ruanxiaoer888/listing-pipeline`；**文件数/提交数不写死**：`git ls-files \| wc -l`、`git rev-list --count HEAD` |
| remote | SSH：`git@github.com:ruanxiaoer888/listing-pipeline.git` |
| 提交邮箱 | `203290839+ruanxiaoer888@users.noreply.github.com`（GH007 规避） |
| 忽略规则 | `.gitignore` 排除 `input/*`（放行 facts/overrides/manifest）、`collector\_work\`、`qa\报告\`、`kb\_index\`、`output\_batch\`、`output\_smoke\`、`.dumate\`、缓存、zip |
| output 口径 | **当期成稿随批次入库（现状）**（如 `批次20261022`）；是否长期入库待定（审计 §七-2） |

### 2.4 已验证结果（历史快照 · 都可重跑）

> 当前基线一条命令：`python qa\selftest.py`（4/4 PASS 才算没改坏）。下面是 2026-10-21 的留档。

**转化侧**
- 9 条黄金案例：P0=0，P1=4（全是 `Compra protegida`），P2-结构=9，P2-转化=14；
- 15 个商品批次：P0=0，P1=0，P2-结构=3，P2-转化=14；
- **v1.3 回归**：加转化检查后 P0 / P1 / P2-结构 三项与 v1.2 完全一致；
- 自有产出真实缺口：15 条里 9 条标题无 `para…`、5 条第一条卖点是参数；
- 单条实测 `ABU5000000`：按转化层重写后 P2-转化 2 → 0，标题 79 字符（旧版存 `output\批次20261020\`）。

**事实侧（2026-10-21 实跑）**
- `check_facts.py`：15 个 → READY=0、DRAFT-OK=11、已隔离=4、BLOCKED=0；
- `check_facts_quality.py --strict`：P0=0、P1=4、P2=8，退出码 0（修掉两个误报后，见 §5.6）；
- `check_certificates.py --strict`：跳过 4 个隔离，剩 **14 条未登记**，退出码 3（真实阻塞：台账为空）；
- `build_facts.py --check`：15 条，退出码 0，不写文件；
- `index_kb.py`：候选 11 个，必填齐全 11/11；
- `source_digest.py`：15 个 SKU → `output\_batch\digest.md`；
- 两个 `--demo` 自检通过；`check_listing.py --demo` 仍是 0/4/9/14（没被改坏）。

---

## 3. 卡住 / 待确认的问题

> 下表是 **2026-10-21 的快照**；2026-10-22 之后的现状以本文件开头「审计与修复」节 + `审计报告-20261022.md` 为准。

| # | 问题 | 影响 | 需要谁 |
|---|---|---|---|
| 1 | ~~15 个 SKU 全 `draft`，0 个 `verified`~~ → 现状：READY=81（**批量核验产出，待人工抽查**）、14 `draft`、13 `quarantined` | 81 条已可生成，但"人工核过"不成立 | 抽查 10 个再定是否退回 `draft` |
| 2 | **认证台账 `certificates: []` 是空的** | 现状 **116 条** NOM-003 / UN38.3 全部 `未登记`，上架必卡（不挡生成） | 向供应商/认证机构拿证书号 + 有效期 |
| 3 | ATVMX11700 功率 6800W/127V 不可信 | 已隔离，补齐铭牌才能恢复 | 铭牌/规格书 |
| 4 | AMR3000002 电池电压仅口述 | 已隔离 | 电池标签照片 |
| 5 | BKU0000000 包装清单是推断 | 已隔离 | 实物/包装核对 |
| 6 | MMV2000000 18V vs 21V | 已隔离 | 确认电池平台 |
| 7 | 电池工具属性写 `Voltaje:127V`（那是充电器输入） | 已由 `state_power` / `charger_v` 区分，别直接抄 | 已进 facts，生成时读 facts |
| 8 | 类目 schema 现 **5 个**（五金/汽摩/家电/运动户外/**服装**）；仍缺「时尚配件/家居建材/宠物/厨房」 | 碰到这些类目会被跳过、不许生成 | 补 schema（照 `服装.schema.json` 的结构） |
| 9 | **没有后台转化数据**（曝光/点击率/转化率/退货率） | 只能做「下限提升」，做不了定向优化 | 从 TikTok 后台导出已上架 SKU 的 7 天数据 |
| 10 | 后台搜索词数据拿不到（只有下拉和竞品标题） | L1 关键词靠猜 | 能导则导 |
| 11 | 转化层规则未 A/B 验证 | 只是「按经验该更好」 | 挑 2 个商品各投 7 天 |
| 12 | `采集清单.md` 未接进批次核对 | 漏做商品不会被发现 | 可选 |
| 13 | TikTok 后台批量模板列名未提供 | 不能直接出「上传就绪」表格 | 后台导一份空模板 |
| 14 | **93 个 SKU 缺 `input.json/item.json/img`** | facts 不可重建、不可重新打包 | 从原采集机补 raw |
| 15 | ~~图片合规校验未做~~ → ✅ 已落地 `qa\check_images.py`（P0=11 / 9 个 SKU，exit 3）；剩下的是**补图**（服装主图 562×1200）与**人工核水印** | 主图比例/尺寸合不合规已能机器判 | 重采/裁方 2 个服装主图 |

> 生成仍由 Agent 按规则完成，**刻意不接模型 API**：规则还在每天变，过早自动化会固化错误。

---

## 4. 下一步计划

### 立刻（零模型成本）
- [x] 门禁强制化 + 同步/自检基础设施（第一轮，已完成）
- [x] 尺寸哨兵 + 图片检查 + 清单自动化 + 服装类目（第二轮，已完成）
- [ ] **抽查 10 个 `verified`** → 对得上的保持、对不上的退回 `draft` 并写 `overrides.json`
- [ ] `python qa\selftest.py` + `.\sync-all.cmd`（两台机器各跑一次）

### 本周（白天，不花模型钱）
- [ ] 补 93 个 SKU 的 `input.json/item.json/img`（从原采集机 / U 盘），补完跑 `build_facts.py --check` 验证可重建、`check_images.py` 才能覆盖到它们
- [ ] **服装 2 个 SKU 补数据**：面料成分、尺码（S–2XL 胸围/肩宽/袖长/衣长）、包装清单；`AXNJCPS300` 主图重采/裁方到 ≥800px 且 1:1
- [ ] 按 `check_images.py` 的 P0/P1 清单修图（11 条 P0 涉及 9 个 SKU）
- [ ] 认证台账填第一批证书（哪怕先填 2–3 个 SKU 的）
- [ ] 用 1–2 个商品做生成验证（别批量），重点看标题 `para…`、首行痛点、首条卖点是利益

### 本周（业务侧）
- [ ] **导后台数据**：已上架 SKU 的曝光 / 点击率 / 转化率 / 退货率
- [ ] A/B 喂数据：挑 2 个商品旧版 vs 转化层版，各投 7 天
- [ ] BR 站首次实测
- [ ] 拿后台上传模板 → 填 `qa\field_map.json` → 出上传就绪表

---

## 5. 踩过的坑（下次别重复）

### 5.1 环境 / 脚本
1. **PowerShell 5.1 + 中文**：UTF-8 无 BOM 的 `.ps1` 含中文会解析报错。一律 **ASCII-only** 或 UTF-8 with BOM。
2. **ExecutionPolicy**：统一 `powershell -NoProfile -ExecutionPolicy Bypass -File xxx.ps1`（`.cmd` 已带好）。
3. **写死用户路径**：一律 `$env:USERPROFILE`。
4. **openpyxl 缺失**：系统 Python 没有 → `run_batch.py` 自动切 DSH 自带 Python（`~\.dsh\dsh-runtimes\...`）。
5. **`python -c "..."` 带管道/复杂引号**易崩，逻辑写进 `.py`。
6. **DSH 沙箱**：写工作区外（全局 skill 目录）会被拒；git→ssh 子进程也会被拦（`couldn't create signal pipe`），push / 同步全局技能要放行。

### 5.2 Git / GitHub
7. **GH007**：仓库内设 noreply 邮箱（换电脑要重设）。
8. **家里 `github.com:443` 连不上** → remote 走 SSH。
9. **force push 后要 `git push -u origin main`** 重新绑定上游。
10. **改动 `input` 的忽略规则**：`input/*` 忽略后用 `!input/*/` 放行子目录，再单独忽略 `input.json`/`item.json`/`img/`——顺序错了 facts.json 进不了库。

### 5.3 数据层（最值钱的教训）
11. ML 数据不能直接搬：**电池工具属性里的 `Voltaje:127V` 是充电器输入**，不是工具工作电压。
12. **110V/120V 一律按 127V 处理**，但必须写明是规范值，不能悄悄改。
13. 单位错乱：`1500Ah` 应为 `1500mAh`；转速 `1150rpm` vs `12000` 描述与属性冲突。
14. **功率物理不可信**：6800W/127V≈54A、2500W≈19.7A 这类要标出来，`state_power=false`，Listing 不写瓦数。
15. 品牌冲突不猜：`Fanny` / `Atverce` 必须人工确认，确认后写进 `overrides.json`（不要手改 facts，重建会覆盖）。

### 5.4 校验器自身修过的 bug
16. 命中行取值用错字段；emoji 把分区标记算进去；`📋 Especificaciones:` 误判；`100%` 重复报；`baño` 词边界误伤；关键词重音不一致；单位换算误报；手工/液压工具被要求电压。
17. `HOOK-PARAM` 第一版误伤好钩句 → 改成「行首是数字 + 40 字符内有单位」。**新规则必须先用「好例子」跑一遍确认不误伤。**

### 5.5 转化层时期的教训（v1.3）
18. **最大的坑是方向跑偏**：精力全花在 Git、换机、校验器上，那是工具不是目标。任何时候问一句「这一小时让 Listing 更好卖了吗」。
19. **合规跟转化不是一回事**：P0/P1 全清零，但 9 条标题没用途词、5 条卖点第一条讲参数——机器判合格，人不会买单。
20. **新检查要能区分「回归失败」和「新增指标」**：把 P2 拆成 `P2-结构` / `P2-转化` 两行，加完检查后旧三项数字必须一模一样。

### 5.6 事实门禁时期的教训（2026-10-21 晚）
21. **门禁建好 ≠ 能生成**：`check_facts` 要求 `verified`，但没人跑 `verify_facts`，结果 11 个「干净」SKU 一个都生成不了。**建门禁当天就要把核验动作排进流程**。
22. **门禁也会误报**：口径哨兵原来不读 `identity.brand_aliases`，已人工确认的 `BKU` 品牌（Atverce / Fanny）被反复报 P0，`--strict` 会误拦整批。修法：别名归一后不算冲突。
23. **隔离 ≠ 从报告里消失**：已隔离 SKU 的问题仍会被扫到（`ATVMX11700` 功率 P0）。现在质量和认证两个检查都改成「隔离中：单独列出，不参与阻断判定」，否则要么漏看、要么误拦。
24. **技能入口是单独一份文件**：`SKILL.md` 没跟着提示词一起改，就会「规则写进库里、Agent 却按旧流程走」。**改规则时四件套一起改：`skill/` + `qa/` + `SKILL.md` + `HANDOFF.md`**。
25. **同步脚本是白名单**：`sync-to-skill.ps1` 不拷 `kb/`，`check_facts.py` 在全局技能目录里会报「缺少类目 schema」。已补 `kb`，并清掉 `kb\_index`、`qa\报告`。
26. **一个 SKU 的 facts 有 6KB 左右，进 git 不心疼；但 `input.json`/图不进**，换机靠 U 盘/网盘。

---

## 6. 关键命令速查

```powershell
# 换电脑一次性安装 + 自检（含 hooksPath + selftest）
powershell -NoProfile -ExecutionPolicy Bypass -File .\setup-new-pc.ps1 -FullCheck

# 改完规则后：一次同步两个技能 + SHA256 校验 + 三处状态表（老的 sync-to-skill.cmd 仍可用）
.\sync-all.cmd
.\sync-all.ps1 -DryRun          # 只看状态表，不写文件

# 一键回归（4 组基线断言；提交时 .githooks/pre-commit 自动跑）
python qa\selftest.py

# —— 生成前三道门（零模型成本，先跑这个）——
python qa\check_facts.py                                        # READY 才可生成
python qa\check_facts.py --fail-on-skip                         # 有类目未登记被跳过 → exit 3
python qa\check_facts_quality.py --input-root input --strict    # P0 时退出码 3
python qa\check_certificates.py --input-root input --strict     # 上架卡口，阻断退出码 3（只挡上架不挡生成）

# 事实卡维护
python qa\build_facts.py --check                 # 只看不写
python qa\verify_facts.py ABU5000000 --by "名字"  # 人工核完置 verified
python qa\index_kb.py                            # 汇总索引
python qa\facts_digest.py                        # 生成用摘要（默认只出 verified）；排查加 --status all --include-pending
python qa\source_digest.py                       # 原始摘要

# 合规 + 转化回归（9 黄金案例，退出码 0 = 通过）
cd qa
python check_listing.py --demo --site MX         # 应为 P0=0 P1=4 P2-结构=9 P2-转化=14

# 跑一个批次（纯脚本；报告写 output\_smoke\run_batch_<时间戳>_<pid>\）
python run_batch.py --input-root ..\input --listing-dir ..\output\批次YYYYMMDD --site MX
# exit 0 通过 / 1 运行期错误 / 2 参数错误 / 3 门禁拦截（被拒 SKU 或 listing 有 P0）

# 提交推送（pre-commit 会先跑 selftest）
git add -A; git commit -m "说明"; git pull; git push
```

---

## 7. 目录地图

```
listing-pipeline\            ← git 仓库根目录
├─ SKILL.md                  技能入口（三道门 + facts 唯一事实源 + 未登记类目禁止生成）
├─ README.md                 身份、目录、校验能力、认证卡口、门禁、同步与自检
├─ 使用说明.md                日常四步（采集 → 事实卡 → 生成 → 校验出表）
├─ HANDOFF.md                本文件
├─ 审计报告-20261022.md       全量审计（P0/P1/P2 + 待拍板）
├─ 迁移到新电脑.md            换机手册 + 坑
├─ 采集怎么用.md / 采集清单.md  采集中文说明 + 采集清单（正文自动生成，含 110 个目录状态表）
├─ requirements.txt          系统 Python 依赖（openpyxl / Pillow）
├─ .gitattributes           换行与二进制策略
├─ .githooks\pre-commit     提交前跑 qa\selftest.py
├─ setup-new-pc.cmd/.ps1     新电脑安装 + 自检（含 hooksPath）
├─ sync-all.cmd/.ps1         两个技能一起同步 + SHA256 校验 + 三处状态表
├─ sync-to-skill.cmd/.ps1    只同步「Listing 生成」（兼容保留）
├─ sync-collector-skill.cmd/.ps1 只同步「美客多采集」（兼容保留）
├─ collector\                美客多采集技能（SKILL.md + references\ + scripts\：含 gen_manifest.py）
├─ skill\                    规则：骨架/转化层/站点包/9 类目/属性映射/案例库/脚本库
├─ kb\                       事实库：_schemas\（5 类目 + 字段字典）、_index\（脚本生成，不进 git）
├─ qa\                       校验器 + 图片检查 + 事实工具 + 认证台账 + 批次脚本 + selftest + denylist + 报告
├─ source-gemini\            V3.2 原始四份（只读存档）
├─ input\<SKU>\              商品：facts.json / overrides.json / img_manifest.csv 进 git；图与原始 json 不进
└─ output\                   生成结果
   ├─ 批次20261022\          81 条成稿 + 批次结果.xlsx（当期成稿随批次入库，现状）
   ├─ 批次20261020\ / 批次_20261021\   旧规则产出 / 单条前后对照（本地留存）
   ├─ _归档\示例商品001…\    黄金对照样例（入库，别删）
   ├─ _batch\                facts_digest / BRIEF / 采集清单-自动.md（不入库）
   ├─ _smoke\                run_batch 校验明细（不入库）
   └─ _research\             调研资料（不入库）
```

---

## 8. 对外依赖（换人接手要知道）

- **TikTok Shop 后台**：无 API 对接，Listing 靠人工/批量模板上传；
- **MercadoLibre**：只作为历史数据来源，本流水线不读写它；
- **DSH**：技能加载与生成环境，版本不影响规则文件（纯文本 + Python）；
- **Python**：3.9+；xlsx 输出需要 openpyxl、图片校验需要 Pillow（DSH 自带环境已含；系统 Python 按 `requirements.txt` 装）。

---

## 9. 2026-10-22 批次记录（门禁样本 108 → 81）

> 本节的 108 / PENDING=14 / 跳过 2 是**这一批跑的时候**的口径（服装 schema 当时还没补）；**现状见 §10**（样本 110 / 跳过 0 / PENDING=16）。

采集层扩到 **108 个 MX SKU**（`采集清单.md`：首批 15 + 公司新增 79 + 夜间补采 14；2026-10-22 又补采 2 个服装 SKU，`input\` 实际 110 个目录），本批跑完整链路的结果：

| 环节 | 结果 |
|---|---|
| `build_facts.py` | 108 个全部生成 `facts.json` + `img_manifest.csv` |
| `check_facts.py` | READY=81 / PENDING=14 / QUARANTINED=13 / 跳过 2（类目未登记） |
| `check_facts_quality.py --strict` | P0=0（8 条新 P0 → 隔离 8 个 + 修 2 个品牌字段互换）；P1=21 P2=52 仅提示，退出码 0 |
| `check_certificates.py --strict` | 未登记 **116 条**（NOM-003 70 + UN38.3 46，71 个 SKU；原 125 条，摘掉 9 条误报），**挡上架不挡生成** |
| 生成 | 81 份 `output\批次20261022\listing-<SKU>.txt`（4 个执行者并行，同一份 `output\_batch\BRIEF-批次20261022.md`） |
| `run_batch.py` 校验 | **P0=0 P1=0 P2-结构=50 P2-转化=0**（`批次结果.xlsx` 逐行核对） |
| 交付 | `批次结果.xlsx`（81 行含问题清单/待确认备注）、`待补数据清单.md`、`qa\报告\20261022\` md+csv |

本批新增/修的东西：
- `kb\_schemas\运动户外.schema.json`（第 4 个类目 schema）
- `qa\facts_digest.py`（facts.json → 生成用摘要，Agent 批量写文案时读这个，不必读原图原描述）
- `qa\make_review_notes.py`（事实卡 → `review_notes.json` + `待补数据清单.md`）
- `qa\check_listing.py`：标题区间按类目取（汽摩 80–120）；分数英寸（`1/2 pulgada`）不再误报未换算；新增 `regex` 检查类型
- `qa\denylist.json`：`teléfono/telefone` 从「站外导流」词表移除，改成 `MX/BR-P1-CONTACT` 正则（只抓"电话+数字"，不再误伤 `lámpara del teléfono`）

数据层教训（补进 §5.3 的同类问题）：
1. 美客多 `Marca` / `Modelo` 两个字段会互换（`20208202`：Marca=ED-02、Modelo=ATVERCE）→ 用 `overrides.json` 的 `set` 校正，不要当品牌冲突硬拦；
2. 电池工具缺电压时**不要**拿充电器电压顶；
3. 12V 车充类（电动千斤顶）不是 127V 市电，标题里的 `12v` 可作电压依据；
4. 手工具（套筒/钻头套装）会被误判 `corded`，用 `overrides` 改 `power.type=manual` 即可解锁，不必补电压；
5. 包装清单缺失是最高频硬缺（14 个 PENDING 里 9 个是它），补 `package.included` 后重跑 `build_facts --force` + `verify_facts` 就能进下一批。

## 10. 2026-10-22 第二轮（审计修复收尾）

| 环节 | 结果 |
|---|---|
| 尺寸哨兵 | `fix_size_fields.py --apply` 修 **11 个 SKU / 18 个字段**；`check_facts_quality --strict` = P0=0 P1=21 P2=52，exit 0 |
| 图片检查 | `check_images.py`：17 SKU / 145 图 → P0=11（9 个）/ P1=29（13 个）/ P2=10；跳过 93 个无 img 的 SKU；demo 19/19 |
| 采集完整性 | `gen_manifest --plan` = 完整 17 / 只有 facts 93 / 损坏 0，exit 1；自动清单 `output\_batch\采集清单-自动.md`（185 行，含 110 个目录状态表） |
| 服装类目 | `服装.schema.json` + `skill\类目\09-服装.md`；类目 9 个、schema 5 个；`check_facts` = 样本 110 / READY=81 / PENDING=16 / QUARANTINED=13 / 跳过 0 |
| 认证 | 仍 116 条（NOM-003 70 + UN38.3 46），exit 3；只挡上架不挡生成 |

数据层教训（本轮新增）：
6. **尺寸解析会吃错东西**：`3200 RPM`、`300 Nm`、`210mm`、描述序号 `2.` 都会被当 cm 吞进 `size.*_cm`；`build_facts` 已加量级/单位校验（1–150 cm、mm 未 ÷10 即置 null），存量用 `fix_size_fields.py` 回填，原值留在 `_meta.size_fix`。
7. **图源问题要早查**：`AXNJCPS300` 01.jpg 只有 562×1200，主图非 1:1 且短边 <800 → 上架会被打回；图片检查要在生成前跑，不要等上架。

