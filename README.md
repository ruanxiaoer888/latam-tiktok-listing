# listing-pipeline｜拉美 TikTok Shop Listing 生产流水线

> 2026-10-30 · v2.0：**Pattern 化 + 交付闭环 + 事实一致性门禁**
> 前身是 Gemini GEM 那套「内容标准」，现在是一条带确定性闸门的批量生产线。
> **新手先看 `新手怎么用.md`（零命令）。** 本文剩下的是给技术和维护者看的。

## 身份

**一个技能（`SKILL.md`）+ 一套规则包 + 两个 Pattern + 三个脚本 + 一套确定性校验器 + 评测基线。**

- **技能入口**：`SKILL.md`（DSH / Claude Code / Codex 可识别）
- **全局安装**：`%USERPROFILE%\.agents\skills\latam-tiktok-listing\`（DSH 自动加载）
- **主本**：本目录。改规则只改这里，改完跑 **`sync-all.cmd`**（同步两个技能 + SHA256 校验）
- **版本库**：本目录就是 git 仓库根（`origin` = GitHub 私有库）
- **交接**：`HANDOFF.md`；设计取舍见 `fabric对照分析-20261029.md`

## 快速导航

- **要上架**：只看 `output\批次YYYYMMDD\<SKU>\`（标题 / 描述 / 图片 / 上架信息一个文件夹）
- **跑流水线 / 改提示词**：`patterns\README.md`
- **改规则**：`skill\`；**改校验**：`qa\`；**类目字段**：`kb\_schemas\`
- **采集新商品**：`采集怎么用.md`

## 当前状态（2026-10-30，跑命令为准）

| 项 | 数值 | 取数命令 |
|---|---|---|
| 输入 SKU | 113 | `Get-ChildItem input -Directory` |
| 事实卡：verified / draft / quarantined | 84 / 16 / 13 | `python qa\check_facts.py` |
| 已出稿（批次20261022-v2） | 81 | `Get-ChildItem output\批次20261022-v2 -Directory` |
| 首批已上架 | 8 | 运营侧 |
| 黄金集（已确认） | 20 | `eval\golden\manifest.json` |
| 成稿校验 | P0=0 / P1=0 / P2=0 | `python qa\run_batch.py ...` |
| 图片 P0 | 55 条 / 40 SKU | `python qa\check_images.py --input-root input` |
| 认证阻断（双站口径） | 171 条 / 74 SKU（UN38.3 98 + NOM-003 73） | `python qa\check_certificates.py --input-root input --site ALL` |

> 文档里不抄死数字；以命令输出为准。

## 目录

```text
listing-pipeline\
├─ AGENTS.md                一句话生成规则（仓库副本；换机放到工作区根目录）
├─ SKILL.md                 技能入口（什么时候用、怎么用、硬约束）
├─ README.md                本文件
├─ HANDOFF.md               交接：现状 / 卡点 / 踩过的坑
├─ 项目结构.md              一页看懂目录角色
├─ 使用说明.md              日常四步（采集 → 事实卡 → 生成 → 校验）
├─ fabric对照分析-20261029.md  架构取舍与执行记录（含评估结论）
├─ 首批上架候选-20261029.md    首批筛选结果与依据
├─ patterns\                ★ 提示词 Pattern（listing_write / listing_fix / README）
├─ scripts\                 ★ render_prompt（组装）/ render_listing（JSON→纯文本）/ eval_pattern（打分）
├─ eval\golden\             ★ 黄金集 manifest（20 条，approved）
├─ skill\                   规则包：生成提示词 / 骨架 / 转化层 / 属性映射 / rules-mx|br / 类目 9 包
├─ qa\                      确定性校验与工具（见下）
├─ kb\                      _schemas\（类目字段）＋ _index\（脚本生成）
├─ collector\               美客多采集技能
├─ source-gemini\           V3.2 原始知识库（只读）
├─ input\<SKU>\             原料：input.json / item.json / img\ / facts.json / overrides.json
└─ output\
   ├─ 批次YYYYMMDD\<SKU>\    ★ 交付：标题.txt / 描述.txt / 上架信息.md / 图片\
   ├─ _prompts\              组装好的 prompt（带版本+sha256）
   ├─ _draft\                Agent 输出的 JSON 草稿
   ├─ _packs\                旧生成包（兼容保留，不再扩展）
   ├─ _eval\                 评测基线与历史
   ├─ _smoke\                每次 run_batch 的机器文件（不用看）
   └─ _backup\               图片/清洗前的原件（别删）
```

## 主流程（v2 推荐）

```powershell
# 1) 组装 prompt（只渲染，不调模型；可 diff、可版本化）
python scripts\render_prompt.py --sku ABU5000000 --site MX

# 2) Agent 按 output\_prompts\<SKU>.md 生成草稿 JSON -> output\_draft\<SKU>.json

# 3) JSON 渲染成可粘贴的纯文本（格式由代码保证，不靠模型自觉）
python scripts\render_listing.py --dir output\_draft --out-root output\批次20261030 --site MX

# 4) 门禁 + 映射 + 校验 + 出表（P0/P1 任一 >0 即 exit 3）
python qa\run_batch.py --input-root input --listing-dir output\批次20261030 --site MX

# 5) 打分并存基线（复用 check_listing，不调模型）
python scripts\eval_pattern.py --batch output\批次20261030 --pattern listing_write@1.0.0

# 6) 补上架信息 / 图片 / 批次 README
python qa\make_upload_pack.py --batch output\批次20261030 --site MX
```

**改稿闭环**（`run_batch` 发现违规时）：

```powershell
python scripts\render_prompt.py --sku <SKU> --site MX --pattern listing_fix `
  --findings output\_smoke\run_batch_<ts>\<日期>\明细_MX_check_verified_<ts>.csv `
  --batch output\批次20261030
# Agent 按 <SKU>-fix.md 输出改稿 JSON → 重跑 3–5，直到 P0/P1/P2=0
```

> 旧流程 `qa\make_listing_pack.py`（`_packs`）保留可用但不再扩展。

## （给技术同学）不依赖 DSH 的最小用法（任何电脑 / 任何模型）

> 新手请跳过本节，直接看 `新手怎么用.md`。

核心是 Python + Markdown，**不需要 DeepSeek Harness**。DSH 只负责「自动加载技能 + 一键跑」；
换任何电脑、任何模型都能用这套流程。

**环境**（一次）

```powershell
python -m pip install -r requirements.txt   # openpyxl + Pillow
```

不需要 API Key——脚本本身不调模型，生成那一步由你选任意模型完成。

**四步**（仓库根执行，Windows 示例；Mac/Linux 把 `\` 换成 `/`）

```powershell
# 1) 组装 prompt（把事实卡 + 站点规则 + 类目包 + pattern 压成一份）
python scripts\render_prompt.py --sku ABU5000000 --site MX
#    -> output\_prompts\ABU5000000.md

# 2) 把这份文件「整份」贴给任意模型（ChatGPT / Claude / Gemini / Codex），开头加一句：
#    按文件里的全部要求执行，只输出一个 JSON；不要代码块、不要解释。
#    把模型回复存成 output\_draft\ABU5000000.json

# 3) JSON → 可粘贴的纯文本（格式由代码保证，不靠模型自觉）
python scripts\render_listing.py --json output\_draft\ABU5000000.json --out-root output\批次20261030 --site MX

# 4) 门禁 + 校验（P0/P1 任一 >0 会报错并中止）
python qa\run_batch.py --input-root input --listing-dir output\批次20261030 --site MX
```

失败了就改稿，重复 2–4：

```powershell
python scripts\render_prompt.py --sku ABU5000000 --site MX --pattern listing_fix `
  --findings output\_smoke\run_batch_<ts>\<日期>\明细_MX_check_verified_<ts>.csv `
  --batch output\批次20261030
```

**仍然跟本机绑定的小地方**

- `.ps1/.cmd`（`sync-all`、`setup-new-pc`）只在 Windows 有效；其他系统只用上面的 Python 流程即可
- `run_batch` 在系统 Python 缺 `openpyxl` 时会尝试 DSH 自带 Python；装好依赖就用不到这条回退
- `check_images` 需要 `Pillow`，缺了会明确提示 `pip install Pillow`，不会静默跳过
- 生成质量取决于所选模型：优先选能稳定输出 JSON、指令跟随好的模型

## 校验能力（按环节）

| 脚本 | 查什么 | 阻断 |
|---|---|---|
| `qa\check_facts.py` | 事实卡必填/完整度（四态） | READY 才可生成 |
| `qa\check_facts_quality.py` | 字段间口径一致性（19 条） | `--strict` P0 → 3 |
| `qa\check_listing.py` | 合规 P0/P1 + 结构/转化 P2 | `--fail-on-p1` → 3 |
| `qa\check_consistency.py` | **facts ↔ 文案矛盾**（供电方向/瓦数/容量/认证） | `--strict` P0 → 3 |
| `qa\check_images.py` | 数量/尺寸/比例/格式/重复/白底 | 有 P0 → 3 |
| `qa\check_certificates.py` | NOM-003 / INMETRO / ANATEL / UN38.3 | `--strict` → 3（只挡上架） |
| `qa\run_batch.py` | 门禁 + 映射 + 上表四层 + 出表 | 任一步失败即中止 |

关键口径：

- **P0**（上架必失败）：中文残留、`[POR CONFIRMAR]`、标题超限、空标题/描述
- **P1**（违规/粘不进后台）：绝对化、医疗、虚假紧迫、站外导流、Markdown 残留、全角标点、混语
- **P2-结构 / P2-转化**：排版与必带信息 / 首屏、卖点排序、FAQ、权益
- 类目必带项**按 facts 可用性判断**：facts 没有的项不要求写（避免逼模型编造）
- 平台限制（标题区间、图片阈值）统一在 `qa\denylist.json`，脚本经 `qa\_limits.py` 读取

## 门禁（强制）

| 环节 | 命令 | 拦截 |
|---|---|---|
| 事实卡 | `python qa\check_facts.py` | 非 verified 不参与生成 |
| 批次 | `python qa\run_batch.py ...` | P0/P1 任一 >0 → exit 3；一致性 P0 → exit 3 |
| 图片 | `python qa\check_images.py --input-root input` | P0 → exit 3 |
| 认证 | `python qa\check_certificates.py --input-root input --strict` | 阻断项 → exit 3 |
| 提交前 | `.githooks\pre-commit` → `qa\selftest.py` | 回归失败阻止提交 |

## 已验证（2026-10-30）

| 项 | 结果 |
|---|---|
| `python qa\selftest.py` | **4/4 PASS**（0.4s） |
| 批次20261022-v2（81 条） | **P0=0 / P1=0 / P2-结构=0 / P2-转化=0** |
| 黄金集（20 条） | P0=0 / P1=0 / P2=0 |
| 事实一致性检查（81 条） | 0 命中；构造样本能抓 2 条 P0 |
| 主图修复 | `ATVMX18200` 1182×1182、`ABTL00000J` 1920×1920，均无 P0 |

## 待办

1. **27 个 SKU 出稿**：缺包装清单 / 电池电压（原始描述里也没有），需实物或供应商补
2. **图片 P0 55 条**：低分辨率需重拍；主图裁方可批量做（待确认）
3. **认证台账**：171 条阻断项待填证书号与有效期
4. **后台数据回灌**：上架 7 天后导曝光/点击/转化/退货，转化层才能定向优化
5. **BR 站**：规则已备但从未实测（INMETRO/ANATEL、110V/220V）
6. **一致性检查边界**：只查可结构化项（供电/瓦数/容量/认证），语义类仍需人工

## 注意

- 本机 shell 是 Windows PowerShell 5.1：`.ps1` 要么纯 ASCII、要么 UTF-8 带 BOM
- `output\` 里的图片**不进 git**（体积大），交付靠 `input\<SKU>\img` 现生成
- 批次根目录只放 `README.md` + SKU 文件夹；机器文件在 `output\_smoke\`
- 平台规则会变（标题上限、认证要求）：定期回后台核对 `denylist.json`
- 只做「生成 + 校验」，**不做自动上传**
- 文档数字容易过期：一律以命令输出为准，不要手抄
