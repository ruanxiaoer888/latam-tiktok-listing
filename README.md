# listing-pipeline｜拉美 TikTok Shop Listing 生产流水线

> 2026-10-20 建立，v1.2。把 Gemini GEM 那套「内容标准」搬进可批量、可校验的运行环境。

## 身份

**一个技能（SKILL.md）+ 一套规则包 + 一个校验脚本 + 一份案例索引。** 不依赖任何平台：

- **技能入口**：`SKILL.md`（DSH / Claude Code / Codex 可识别）
- **全局安装**：`%USERPROFILE%\.agents\skills\latam-tiktok-listing\`（副本，DSH 自动加载）
- **主本**：本目录。改规则只改这里，改完跑 `sync-to-skill.cmd`
- **版本库**：本目录就是 git 仓库根目录（`origin` = GitHub 私有库）；换电脑 / 迁移步骤见 `迁移到新电脑.md`

## 目录

```
listing-pipeline\
├─ SKILL.md               技能入口（什么时候用、怎么用、硬约束）
├─ sync-to-skill.cmd      ← 双击同步（.ps1 也可，但要带 -ExecutionPolicy Bypass）
├─ source-gemini\         V3.2 四份原始文件副本（只读）
├─ skill\
│  ├─ 生成提示词.md       模型无关 prompt 模板（角色/工作流/硬约束/模块开关）
│  ├─ 骨架.md             Listing 输出结构 + 排版硬规范
│  ├─ rules-mx.md         墨西哥规则包（es-MX）
│  ├─ rules-br.md         巴西规则包（pt-BR，重写非机翻）
│  ├─ 类目\               8 个类目包
│  ├─ 案例库索引.md       9 条案例 → 类目映射、盲区、few-shot 规则
│  └─ 短视频脚本.md       可选模块 B（Hook/CTA/结构），默认不生成
├─ qa\
│  ├─ denylist.json       违规词 + 结构规则 + 8 类目必带信息（MX/BR）
│  ├─ check_listing.py    合规校验器 v1.2
│  ├─ map_attributes.py   ML 属性 → TikTok 槽位映射（电池工具电压口径等）
│  ├─ build_batch_csv.py  批量：input + listing → 校验用 CSV
│  ├─ make_batch_xlsx.py  批量：校验结果 + 备注 → 批次结果.xlsx
│  ├─ 测试样例.csv        回归用例（含 核心词 / 类目 两列）
│  └─ 报告\<日期>\        扫描输出
├─ input\                 待处理商品（一个商品一个子目录）
└─ output\                生成结果
```

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

```powershell
cd E:\AUSU\DSHProjects\Tiktok\listing-pipeline\qa

python check_listing.py --input 导出.csv --site MX                 # 基本扫描
python check_listing.py --input 导出.csv --site MX --category 家电  # 加类目必带信息
python check_listing.py --input 导出.csv --site BR                 # 巴西（会拦"混入西语"）
python check_listing.py --input 导出.csv --site MX --fail-on-p0    # P0 时退出码 3
python check_listing.py --demo --site MX                           # 回归自检
python check_listing.py --input 测试样例.csv --site MX

# 6) 属性映射（ML 属性 → TikTok 槽位；需带 openpyxl 的 Python）
python map_attributes.py --input-root ..\input --out ..\output\批次20261020\属性映射.xlsx

# 7) 一条命令跑完 属性映射 + 校验 + 出表（生成仍由 Agent 完成）
python run_batch.py --input-root ..\input --listing-dir ..\output\批次20261020 --site MX
```

**可选列**（有就用，没有跳过）：`核心词/keyword`（检查前 30 字符）、`类目/category`（按行套类目检查）、`SKU/商品ID`（报告区分条目）。

## 校验能力（v1.2）

**P0（上架必失败）**：中文残留、`[POR CONFIRMAR]` 占位、标题超平台上限、描述超 10000、**空标题/空描述**

**P1（违规/误导）**：绝对化、医疗宣称、虚假紧迫、站外导流、未验证物流/信任承诺、`100%` 上下文、跨语言混入

**P2（影响转化）**：标题不在 60–80、核心词不在前 30、标题重复词堆砌、描述过短、缺 📋📦💡 分段、单行 Emoji >2、模型腔结构标签残留、标签过多、**类目必带信息缺失**、**英制单位未换算**、**价格未标币种**

**查不了**：参数与图/原文是否一致、证书真伪、汽配适配表准确性（需事实卡 + 人工）

## 已验证结果

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

## 待办

1. **扫真实存量**：导出 200–500 条已上架 Listing 跑一遍，出命中率（>10% 说明必须进流程）
2. **接生成端**：`input\商品ID\`（图片 + input.json）→ 事实卡 facts.json → 按 `生成提示词.md` 生成 → 过校验 → 出 `output\批次.xlsx`
3. **汽配适配表结构化**（退货最大头）
4. **补 BR 案例**：现在 0 条葡语案例，规则有了但缺锚点
5. **认证台账**：证书编号/有效期，上架前卡口

## 注意

- 平台规则会变（标题上限、认证要求）：建议 `denylist.json` 加 `verified_at`，每季度回后台核一次
- 只做"生成 + 校验"，**不做自动上传**
- `output\` 结构：`批次<日期>\` 是正式产出；`_归档\` 放示例与中间产物，可随时删。`input\output` 里**以下划线开头的目录/文件不参与批次**（脚本自动跳过）
- `E:\工作资料\Gemini` 原目录未改动，本目录全是副本
- 本机 shell 是 Windows PowerShell 5.1：`.ps1` 要么纯 ASCII、要么存成带 BOM 的 UTF-8，否则中文注释会让脚本语法报错
- **暂不接模型 API 跑生成**：规则还在迭代（每批都会暴露新的源数据坑），先让 Agent 按 skill 生成、人工校准 2–3 批再自动化；`run_batch.py` 只封装"映射 + 校验 + 出表"这段确定性工作
