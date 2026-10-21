# HANDOFF｜交接文档

> 最后更新：2026-10-21 20:50（家里电脑；v1.3 转化层 + 生成前事实门禁）
> 仓库：https://github.com/ruanxiaoer888/listing-pipeline （private）
> 本文件位置 = 仓库根目录 = 流水线主本

---

## 0. 如果只看三件事

1. **目标别跑偏**：这一切的最终目的只有一个——**在合规前提下，写出能提高转化率的 Listing**。校验器、事实库、门禁都是手段，不是目的。
2. **环境**：公司电脑 clone → 覆盖 `input` → 双击 `setup-new-pc.cmd`，看到 `ALL DONE.` 即可开工。
3. **成本**：白天（峰时）只做零模型成本的活（脚本校验、核事实、改规则）；批量生成留到夜间谷时。
4. **现在的卡点**：门禁建好了，但 **15 个 SKU 里 0 个 `verified`** → 按规则一个都不能生成。先人工核验（2–3 分钟/条）再跑批量。

---

## 1. 当前任务

**核心目的**：生产**高转化率**的 TikTok Shop 商品 Listing，前提是**安全合规**。
- 转化率 = 流量精准度 × 承接效率 × 价格/信任。Listing 只负责中间那段「承接效率」。
- 所以 **Listing 需要满足的不只是「不违规」，还要「被看懂、被相信、被推一把」**。
- 合规 ≠ 保守 ≠ 低转化：同样合规的两种写法转化能差几倍，转化层全在红线内操作。

**工程主线**：拉美 TikTok Shop（墨西哥 5 店 + 巴西 6 店，全部本土店，运营团队在国内）的 Listing 生产流水线，从「能生成」推进到「能批量、能校验、能投产」。

**当前所处的阶段**：
- 合规层 + 转化层 + 工具链已成型（v1.3），MX 站跑通 15 个商品批次；
- **2026-10-21 公司电脑补了两件事**：① 事实层落地（`kb/` + 15 份 `facts.json`，生成立唯一事实来源）；② 生成前三道门禁（事实卡 / 口径 / 认证），4 个疑点 SKU 已隔离；
- 还差一样东西：**后台真实数据**（曝光/点击/转化/退货），没有它只能做下限提升，做不了定向优化。
- BR 站还没实际跑过（所有验证都是 MX）。

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
| 换机脚本 | `setup-new-pc.cmd/.ps1`、`sync-to-skill.cmd/.ps1`、`迁移到新电脑.md` | ✅ |

### 2.2 事实层（2026-10-21 公司电脑新增）

| 项 | 内容 |
|---|---|
| 事实卡 | `input\<SKU>\facts.json` × 15：品牌/供电/电压/功率/尺寸/包装/兼容/认证/图片哈希/门禁 |
| 图片清单 | `input\<SKU>\img_manifest.csv`：哈希、主图、重复组 |
| 人工确认 | `input\<SKU>\overrides.json` × 4：按点路径覆盖 + 解除阻断 + 加警告 + 隔离；重建自动重放 |
| 字段字典 | `kb\_schemas\_fields.md` + 3 个类目 schema（五金工具/汽摩/家电） |
| 状态机 | `draft`（待核）→ `verified`（可生成）/ `quarantined`（移出生成集）/ `blocked`（硬伤） |
| 版本库 | `facts.json`、`overrides.json`、`img_manifest.csv` **进 git**；`input.json`/`item.json`/`img/` 不进 |
| 构建/门禁 | `qa\build_facts.py`（`--check` 只报告不写）/ `check_facts.py` / `index_kb.py` / `verify_facts.py` |
| 数据质量哨兵 | `qa\check_facts_quality.py`：品牌/型号冲突、电池 vs 充电器电压、电压口径、功率物理、单位、价格币种、属性键值错位 |
| 认证卡口 | `qa\check_certificates.py` + `qa\certifications.json` + `认证台账说明.md` + 飞书导入模板 |
| 生成摘要 | `qa\source_digest.py`：`input.json` → `output\_batch\digest.md`（省去反复读图/长描述） |

**认证规则**：NOM-003（MX 电动类，阻断）、INMETRO（BR，范围待确认→只提醒）、ANATEL（只认 bluetooth/wifi/2.4G/radio，`inalámbrico` 不算）、UN38.3（含锂电池即需要）。

**当前隔离 4 个**（不进本批生成，事实卡和 overrides 都保留）：
- `ATVMX11700`：6800W / 127V ≈ 54A，与家庭电路矛盾，拿不到铭牌；
- `AMR3000002`：电池电压 18V 只是口述估计，无标签；
- `BKU0000000`：包装清单是推断（是否含充电器未核对）；
- `MMV2000000`：电池 18V / 整机标称 21V 口径未确认。

**干净候选 11 个**：`ABTL000006`、`ABU5000000`、`ABU6000008`、`ABU600000T`、`AHR6C50002`、`AMU0000003`、`AMU3CI0000`、`AMU6000005`、`ATVMX18200`、`MBU6000001`、`ZK2604270H`。

### 2.3 换机与版本管理

| 项 | 结果 |
|---|---|
| 仓库根目录 | 就是本目录（`listing-pipeline`），外层 `Tiktok` 只是资料文件夹 |
| GitHub | 私有库 `ruanxiaoer888/listing-pipeline`，**93 个文件，7 个提交** |
| remote | SSH：`git@github.com:ruanxiaoer888/listing-pipeline.git` |
| 提交邮箱 | `203290839+ruanxiaoer888@users.noreply.github.com`（GH007 规避） |
| 忽略规则 | `.gitignore` 排除 `input\*`（图 49MB，但放行 facts/overrides/manifest）、`output\*`（除黄金样例）、`qa\报告\`、`kb\_index\`、缓存 |

### 2.4 已验证结果（都可重跑）

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

| # | 问题 | 影响 | 需要谁 |
|---|---|---|---|
| 1 | **15 个 SKU 全 `draft`，0 个 `verified`** | 门禁下无法生成任何一条 | 人工核验后跑 `verify_facts.py` |
| 2 | **认证台账 `certificates: []` 是空的** | 14 条 NOM-003 / UN38.3 全部 `未登记`，上架必卡 | 向供应商/认证机构拿证书号 + 有效期 |
| 3 | ATVMX11700 功率 6800W/127V 不可信 | 已隔离，补齐铭牌才能恢复 | 铭牌/规格书 |
| 4 | AMR3000002 电池电压仅口述 | 已隔离 | 电池标签照片 |
| 5 | BKU0000000 包装清单是推断 | 已隔离 | 实物/包装核对 |
| 6 | MMV2000000 18V vs 21V | 已隔离 | 确认电池平台 |
| 7 | 15 个商品里 6 个电池工具属性写 `Voltaje:127V`（那是充电器输入） | 已由 `state_power` / `charger_v` 区分，别直接抄 | 已进 facts，生成时读 facts |
| 8 | 3 个类目 schema 只覆盖本批（五金/汽摩/家电） | 下一批碰到家居建材等会报「缺少类目 schema」 | 扩 schema |
| 9 | **没有后台转化数据**（曝光/点击率/转化率/退货率） | 只能做「下限提升」，做不了定向优化 | 从 TikTok 后台导出 15 个 SKU 的 7 天数据 |
| 10 | 后台搜索词数据拿不到（只有下拉和竞品标题） | L1 关键词靠猜 | 能导则导 |
| 11 | 转化层规则未 A/B 验证 | 只是「按经验该更好」 | 挑 2 个商品各投 7 天 |
| 12 | `采集清单.md` 未接进批次核对 | 漏做商品不会被发现 | 可选 |
| 13 | TikTok 后台批量模板列名未提供 | 不能直接出「上传就绪」表格 | 后台导一份空模板 |

> 生成仍由 Agent 按规则完成，**刻意不接模型 API**：规则还在每天变，过早自动化会固化错误。

---

## 4. 下一步计划

### 今晚（谷时）
- [x] 事实门禁接入 skill（`SKILL.md` 加三道门 + facts 唯一事实源；同步脚本补 `kb/`；修 2 个误报）
- [ ] **人工核验 11 个干净 SKU** → `python qa\verify_facts.py <ID...> --by "<你的名字>"`
- [ ] 核完 `python qa\check_facts.py`，看到 `READY=11` 再动手
- [ ] 按新规则生成这 11 条（老批次 9 条标题缺用途词、5 条首条卖点是参数）

### 明天（公司，白天）
- [ ] 环境自检（不花模型钱）：`cd qa; python check_listing.py --demo --site MX` → 0/4/9/14
- [ ] 新门禁自检三条：`check_facts.py` / `check_facts_quality.py --strict` / `check_certificates.py --strict`
- [ ] 用 1–2 个商品做生成验证（别批量），重点看标题 `para…`、首行痛点、首条卖点是利益
- [ ] **导后台数据**：15 个 SKU 的曝光 / 点击率 / 转化率 / 退货率

### 本周
- [ ] 认证台账填第一批证书（哪怕先填 2–3 个 SKU 的）
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
# 换电脑一次性安装 + 自检
powershell -NoProfile -ExecutionPolicy Bypass -File .\setup-new-pc.ps1 -FullCheck

# 改完规则后同步到全局技能（DSH 才会加载新规则）
.\sync-to-skill.cmd

# —— 生成前三道门（零模型成本，先跑这个）——
python qa\check_facts.py                                        # READY 才可生成
python qa\check_facts_quality.py --input-root input --strict    # P0 时退出码 3
python qa\check_certificates.py --input-root input --strict     # 上架卡口，阻断退出码 3

# 事实卡维护
python qa\build_facts.py --check                 # 只看不写
python qa\verify_facts.py ABU5000000 --by "名字"  # 人工核完置 verified
python qa\index_kb.py                            # 汇总索引
python qa\source_digest.py                       # 生成用摘要

# 合规 + 转化回归（9 黄金案例，退出码 0 = 通过）
cd qa
python check_listing.py --demo --site MX         # 应为 P0=0 P1=4 P2-结构=9 P2-转化=14

# 跑一个批次（纯脚本）
python run_batch.py --input-root ..\input --listing-dir ..\output\批次YYYYMMDD --site MX

# 提交推送
git add -A; git commit -m "说明"; git pull; git push
```

---

## 7. 目录地图

```
listing-pipeline\            ← git 仓库根目录
├─ SKILL.md                  技能入口（三道门 + facts 唯一事实源）
├─ README.md                 身份、目录、V3.2 整合对照表、校验能力、认证卡口
├─ HANDOFF.md                本文件
├─ 迁移到新电脑.md            换机 6 步 + 坑
├─ setup-new-pc.cmd/.ps1     新电脑安装 + 自检
├─ sync-to-skill.cmd/.ps1    工作区主本 → 全局技能（含 kb）
├─ skill\                    规则：骨架/转化层/站点包/8 类目/属性映射/案例库/脚本库
├─ kb\                       事实库：_schemas\（3 类目 + 字段字典）、_index\（脚本生成，不进 git）
├─ qa\                       校验器 + 事实工具 + 认证台账 + 批次脚本 + denylist + 报告
├─ source-gemini\            V3.2 原始四份（只读存档）
├─ input\<SKU>\              商品：facts.json / overrides.json / img_manifest.csv 进 git；图与原始 json 不进
└─ output\                   生成结果（不进 git，黄金样例除外）
   ├─ 批次20261020\          15 个商品：旧规则产出（对照基准）
   ├─ 批次20261021\          ABU5000000 转化层重写版（单条前后对照）
   └─ _归档\示例商品001…\    黄金对照样例（A/B 两版）
```

---

## 8. 对外依赖（换人接手要知道）

- **TikTok Shop 后台**：无 API 对接，Listing 靠人工/批量模板上传；
- **MercadoLibre**：只作为历史数据来源，本流水线不读写它；
- **DSH**：技能加载与生成环境，版本不影响规则文件（纯文本 + Python）；
- **Python**：3.9+，xlsx 输出需要 openpyxl（DSH 自带环境里有）。
