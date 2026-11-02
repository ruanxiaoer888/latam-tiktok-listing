---
name: latam-tiktok-listing
description: "拉美 TikTok Shop（墨西哥 MX / 巴西 BR）商品 Listing 生成、转化率优化与合规校验。当需要根据商品图片和描述生成或优化 Listing（标题/描述/卖点/规格/包装清单/FAQ）、想提高 Listing 的点击率与转化率、给标题定关键词结构、按决策权重排卖点，或批量检查已上架 Listing 的违禁词、字符数、中文残留、西葡混用、未验证承诺时使用。内置事实卡门禁（`facts.json` 为唯一事实来源）、认证台账卡口（NOM-003 / INMETRO / ANATEL / UN38.3）、9 个类目包（五金工具、汽车摩托、家居建材、运动户外、宠物、厨房、家电、时尚配件、服装）、转化层手册（首屏钩子/卖点排序/疑虑前置/权益写实）与可执行的合规+转化扫描脚本。"
---

# 拉美 TikTok Shop Listing 生成、转化与合规校验

> **命名说明**：本文件是 Skill ID `/latam-tiktok-listing` 的源码母版。
> -   DSH 调用名：`/latam-tiktok-listing`（全局技能目录 `C:\Users\Michael\.agents\skills\latam-tiktok-listing\SKILL.md`）
> -   源码位置：`D:\Michael\DSHProjects\skills\latam-tiktok-listing\SKILL.md`（即本文件）
> -   两者是同一套东西的"运行时副本"和"开发母版"，通过 `sync-all.cmd` 同步。
> -   工作区根目录名 `skills/latam-tiktok-listing` = 这个 Skill 的源码仓库 + 数据仓库（input/output/qa）。
> -   **注意**：本 Skill (`/latam-tiktok-listing`) 与 Codex 版 `/tiktok-shop-listing` 是两个独立的 Skill，前者负责工程化执行（门禁+校验+批量），后者负责知识组织和决策框架（SEO 证据、合规审计、定价模型）。两者互补，不互相覆盖。

## 什么时候用

- 根据商品图片（5–6 张）+ 原描述，生成或重写 MX / BR 站 Listing
- **想让 Listing 卖得更好**：标题没搜索量、点击进来不买、转化率低、退货多
- 批量检查已上架 Listing：违禁词、绝对化宣传、未验证物流/信任承诺、中文残留、西葡混用、标题超长
- 给标题定结构、给描述定骨架、按类目补必带信息与 FAQ、按决策权重排卖点

**不适用**：自动上传、商品抓取、广告投放、店铺注册。

**两层目标（缺一层都是残品）**：合规层 = 不违规（`rules-*` + 类目包 + `qa\denylist.json`）；转化层 = 卖得动（`skill\转化层.md`）。合规是地板，转化是地板之上的高度。

## 目录（相对本文件）

```
skill\骨架.md            输出结构与排版硬规范
skill\转化层.md          转化率手册（关键词三层/首屏两行/卖点排序/疑虑前置/权益写实/替代表达/6 条自检）
skill\生成提示词.md      模型无关的生成 prompt 模板（角色/工作流/硬约束/模块开关）
skill\rules-mx.md        墨西哥规则包（es-MX）
skill\rules-br.md        巴西规则包（pt-BR）
skill\类目\01..09-*.md   9 个类目包（双站标题公式/必带信息/FAQ/合规/坑；09 = 服装：外套/风衣/衬衫外套）
skill\案例库索引.md      9 条案例的类目映射、盲区、few-shot 使用规则
skill\短视频脚本.md      可选模块 B（Hook 库/CTA 库/15-30 秒结构），默认不生成
skill\属性映射.md        ML 属性 → TikTok 槽位映射规则（电池电压 vs 充电器电压等）
skill\references\        模块化参考文档（按需加载，不塞进主提示词）
  seo-evidence.md        SEO 证据分级规范（observed/inferred/fallback 三级标注）
  compliance-audit.md    合规审计框架（数据来源状态 + 合规动作分级 + 严重度）
  pricing-mx.md          墨西哥站定价决策框架（存档备用，未集成进生成流程）
kb\_schemas\             5 个类目事实 schema（五金工具/汽车摩托/家电/运动户外/服装）+ _fields.md（字段字典，含 evidence_status 规范）
                         **没有 schema 的类目（如「时尚配件」）不许生成**，见硬约束
kb\README.md             事实库状态机（draft/verified/quarantined/blocked）+ 命令
input\<SKU>\facts.json   事实卡：生成的唯一事实来源（verified 才可生成）
qa\build_facts.py        input.json + overrides.json → facts.json
qa\check_facts.py        事实卡门禁（必填/完整度 → kb\_index\完整度报告.md）；--fail-on-skip 有跳过即 exit 3
qa\check_facts_quality.py 数据质量哨兵（品牌/电压/功率/单位口径，--strict 有 P0 退出 3）
qa\check_certificates.py 认证卡口（NOM-003 / INMETRO / ANATEL / UN38.3；只挡上架不挡生成）
qa\certifications.json   认证台账主本（规则 + 证书明细）
qa\source_digest.py      input.json → output\_batch\digest.md（原始摘要）
qa\facts_digest.py       facts.json → 生成用摘要（默认只输出 verified）
qa\run_batch.py          批次卡口：门禁 + 映射 + 校验 + 出表（非 verified 默认拒绝，exit 3）
qa\selftest.py           一键回归（4 组基线断言；pre-commit 调它）
qa\denylist.json         机器可判规则（MX/BR 两套 + 8 类目必带信息）
qa\check_listing.py      合规校验脚本（标准库，无第三方依赖）
qa\check_images.py       图片合规检查（数量/尺寸/比例/格式/重复/白底；上架前，P0 → exit 3）
qa\fix_size_fields.py    尺寸回填：不可信尺寸置 null（默认 dry-run，--apply 才写；原值留在 _meta.size_fix）
qa\测试样例.csv          回归用例（含 核心词 / 类目 两列）
qa\报告\<日期>\          扫描输出（check_listing / check_images 单独跑时写这里）
output\_smoke\           每次 run_batch 的校验明细（run_batch_<时间戳>_<pid>\，不入库）
source-gemini\           V3.2 原始知识库
sync-all.ps1 / .cmd      一次同步两个技能 → 全局技能目录 + SHA256 校验 + 三处状态表
```

## 使用步骤

1. **先定站点**：MX 或 BR。**两站规则不通用，禁止混用**（西语倒标点、você/Tú、R$/MXN、127V/220V、NOM/INMETRO 全不同）。
2. **先过三道门（生成前，零模型成本）**：
   - `python qa\check_facts.py` → 看 `READY`。**只有 `verified` 且无硬伤才允许生成**；`quarantined` / `blocked` / `draft` 一律不生成。
   - `python qa\check_facts.py --fail-on-skip` → 有 SKU 因类目 schema 未登记被跳过，退出码 3 → **该 SKU 不许生成**。
   - `python qa\check_facts_quality.py --input-root input --strict` → 有 P0 先修（品牌冲突、电压口径、功率物理不可能）。`--strict` 返回 3 表示不许生成。
   - `python qa\check_certificates.py --input-root input --strict` → 认证缺登记/过期/待确认，**"上架"会卡在这里，"生成"不受它约束**（本批台账为空，全部 `missing` 是事实）。
   - `python qa\facts_digest.py` → 批量生成前读这份摘要（默认只输出 `verified`）；要排查时才加 `--status all --include-pending`。
   - **上架前再加两道**：`python qa\check_certificates.py --strict`（认证，只挡上架）+ `python qa\check_images.py --input-root input`（图片：5–9 张、短边 ≥800px、±3% 比例、无重复图；**P0 → exit 3**；文字/水印需人工核对）。
3. **读数（顺序固定）**：
   - **事实**：只读 `input\<SKU>\facts.json`。**不读原始描述、不读图片、不猜参数**——`power.state_power=false` 时不许写瓦数，`certification.status=missing` 时不许写 NOM/INMETRO/ANATEL。
   - **规则**：`skill\生成提示词.md`（模板，含窄编辑模式）+ `skill\骨架.md` + `skill\转化层.md` + `skill\rules-<站点>.md` + `skill\类目\<最贴近的类目>.md`；要 few-shot 就按 `skill\案例库索引.md` 取同类目案例。
   - **参考文档（按需）**：SEO 证据分级 → `skill\references\seo-evidence.md`；合规审计 → `skill\references\compliance-audit.md`；定价建议 → `skill\references\pricing-mx.md`。常规生成不需要加载，仅在对应场景触发时读取。
4. **生成**（二选一）：
   - 单条：按规则直接产出纯文本，**不要**输出"以下是您的 Listing"、不要结构标签、不要引用标记。
   - 批量：`input\<商品ID>\facts.json`（+ 需要时 `output\_batch\digest.md`）喂进去，逐条产出到 `output\`。
   - 顺序别乱：核事实 → 定关键词（L1/L2/L3）→ 定标题 → 写首屏两行 → 排卖点 → 规格/清单/FAQ → 权益 → 自检
5. **校验**：`cd qa` 后 `python check_listing.py --input 结果.csv --site MX`（或 `--site BR`）。
   - 加 `--category 家电`（或行内带"类目"列）会额外检查该类目的必带信息
   - 输入带"核心词"列时，会检查核心词是否落在标题前 30 字符
   - `--fail-on-p0` 让脚本在出现 P0 时返回非 0，便于接自动化
   - 报告分四档：`P0` / `P1` / `P2-结构` / `P2-转化`
6. **交付门槛**：P0 与 P1 必须清零；**P2-转化 优先清**（直接关联转化率），P2-结构 记入备注排期。
7. **缺参数不阻断**：资料里没有的参数**不写进正文、不推测**，列进中文备注「待确认清单」；属性与描述冲突时**以属性为准**并写明冲突点。只有后台必填字段才在字段层标 `[POR CONFIRMAR]`。**禁止**为了凑排版而编参数。
8. **转化自检 6 条**（`skill\转化层.md` §8）：标题有 L1+L2？第 1 行是具体痛点？第一条卖点是利益不是参数？卖点 3–5 条按决策权重？三问疑虑答了且 FAQ ≥2？每项权益后台真实存在？

## 硬约束（违反即不交付）

- 语言纯净：全部 es-MX 或 pt-BR；**禁止中文残留、禁止西葡混用**
- 标题 60–80 字符（汽摩配 80–120），核心搜索词在前 30 字符，禁 Emoji、禁促销词
- **标题必须含 `para…` 用途词**（只写品类词丢掉一半搜索）
- **描述第 1 行必须是具体场景/痛点**，禁 `alta calidad` / `excelente calidad` / `perfecto para` 这类空泛开场
- **第一条卖点讲最痛的利益，不讲参数**；参数一律进规格区
- 描述 ≤10000 字符、建议 ≥300；必须含 `📋 规格` / `📦 包装清单` / `💡 FAQ` 三段，FAQ ≥2 条
- 禁 `Compra protegida`（MX）、`Compra garantida`（BR）——都是美客多品牌词
- `100%` 只允许出现在材质成分语境（`100% acero inoxidable`），保证/效果语境一律禁
- 物流与信任承诺（包邮、极速、货到付款）没有实际履约能力不得写；促销/折扣词只在后台活动真实存在时写
- 事实只取 `facts.json`：**`status` 不是 `verified` 的 SKU 一律禁止生成**（`draft` / `quarantined` / `blocked` 都不行；`run_batch.py` 默认拒绝并 exit 3，`--allow-unverified` 只供调试）；**类目未登记 schema 的 SKU（被 `check_facts.py` 跳过的，如「服装」）同样禁止生成**——无门禁 = 不许出稿。`power.state_power=false` 时**禁止写瓦数**；属性与描述冲突以属性为准并备注；不确定的参数一律进「待确认清单」，不许编
- 家电/电动工具/汽摩配/无线产品：先跑 `python qa\check_certificates.py --strict`；台账 `missing` 时**禁止**出现 NOM / INMETRO / ANATEL / UN38.3 字样（可写「uso seguro en casa」这类通用表达）。**认证只挡上架、不挡生成**；NOM-003 仅适用 127V 市电产品（12V 直流车充不触发）

## 输出

- `output\<批次>.xlsx`：列名对齐 TikTok 后台批量上架模板
- `output\_smoke\run_batch_<时间戳>_<pid>\`：`run_batch.py` 每次校验的明细（独立目录、不入库）
- `qa\报告\<日期>\`：`check_listing.py` 单独跑时的 md 报告 + csv 明细（含命中位置与修改建议）

## 改规则之后

- 跑 **`sync-all.cmd`**（一次同步两个技能 + SHA256 校验 + 三处状态表；老的 `sync-to-skill.cmd` 仍可用），否则 DSH 读到的还是旧规则；
- 跑 **`python qa\selftest.py`**（4 组基线断言，全 PASS 才算没改坏）；提交时 `.githooks/pre-commit` 会自动跑一次。

## 边界

- **不做自动上传**：上传有副作用，留人工
- **不做数据抓取**：美客多优先走官方 API
- 参数与图片一致性、证书真伪、适配表准确性：由人工终审，脚本只做词与结构判断
