# 批次 BRIEF v2 · TikTok Shop 墨西哥站上架稿

> 目标：给新店「上架阶段」用的 Listing。**商品卡上要有人点，点进来要能自己做决定。**
> 本文件是唯一格式标准；三个金标准样例在同目录：`listing-AMU0000003.txt`、`listing-ATVMX09400.txt`、`listing-MBU6000001.txt`（先读，照这个质量写）。

## 1. 必读（按顺序，读完再动笔）

1. `skill\骨架.md`（结构与排版）
2. `skill\转化层.md`（首屏/卖点排序/疑虑/权益）
3. `skill\rules-mx.md`（es-MX、禁用词、127V、认证）
4. 你的类目包：`skill\类目\01-五金工具.md` / `02-汽车摩托.md` / `07-家电.md` / `04-运动户外.md`
5. 本 SKU 场景卡：`output\_batch\scene\<SKU>.md` ← **场景 / 痛点 / 差异点 / 包装 / 注意事项的唯一依据**
6. 本 SKU 事实卡：`input\<SKU>\facts.json` ← **参数/包装/价格的唯一依据**
7. 三个金标准样例

**不要读** `input\<SKU>\input.json`、`item.json`、`img\`：原文是机翻，读了会把机翻腔抄进文案。

## 2. 写作标准（这决定“好不好卖”）

每篇都要回答三个问题：
1. 这东西**是什么、给谁用**（标题 + 首屏第 1 行）
2. 它**解决什么具体麻烦**（第一条卖点）
3. 我**能不能用 / 里面有什么 / 还要另外买什么**（FAQ）

## 3. 标题（硬格式）

- 结构：**核心词 + 关键规格 + `para` 用途 + `|` 次卖点 + 品牌（句尾）**
- 长度：**60–80 字符**（汽车摩托 **80–120**）；`para` 尽量落在前 30 字符
- 核心词用当地叫法（`lijadora`、`gato hidráulico`、`hidrolavadora`…），核心词片段必须齐全（校验器会查）
- 只放**一个**可验证规格（功率/容量/尺寸/件数选一个）
- 禁：Emoji、全大写、促销词、价格、包邮、绝对化、无授权品牌

## 4. 描述（逐字照这个结构）

```
<首屏钩子：具体场景/痛点，≤60 字符>

⭐ **卖点1（最痛的利益）**：一句解释
（每条卖点之间空一行）
⭐ **卖点2**
⭐ **卖点3**
⭐ **卖点4（差异化：和普通款差在哪）**
⭐ **卖点5（可选，连带/易用）**

📋 Especificaciones Técnicas:
- 参数: 值 单位
（每行一个，≤8 行）

📦 Contenido del Paquete:
- 件 x数量
（逐件列全；不含的写 **NO incluidas**）

💡 Preguntas Frecuentes (FAQ):
- ¿问题？ 回答。
（固定 3 条，顺序：能不能用在我这 → 含什么/怎么用 → 隐藏成本）
- ...
- ...

<CTA 一行：Compra segura con pago dentro de TikTok Shop + 一句核对建议>
```

细则：

- **首屏钩子**：必须来自场景卡的场景/痛点；≤60 字符；同一执行者的稿件里**问句不超过 60%**，其余用陈述式场景（`Para quien…` / `Con…`）。
- **卖点 4–5 条**，第一条讲最痛的利益、**不许以参数开头**；每条 = 利益 + 证据（数字/材质/结构/附带件），没有证据的形容词删掉。
- **第 4 条必须写差异化**（铜芯电机 / 双头 / 6 档 / 含 6 个替换碳刷 / 加宽底板…），从场景卡的「卖点/差异化」里提炼，禁止贬低竞品。
- **至少一条“决策信息”**：哪种砂纸用于哪一步、哪种料用哪个头、含不含耗材、要不要另买配件。这是“帮客户做决策”的核心。
- **规格**：facts 有的必须照 facts；facts 没有而场景卡原文有明确数值的可以写（电压一律用 facts，冲突时 facts 优先）；没数值的不要编。
- **包装清单**：facts.package.included 逐件（去掉 `*1,` 这类残渣，写成 `x1`）；`not_included` 有的必须写 `**NO incluidas**`。
- **FAQ 3 条**：兼容/场景 → 含什么/怎么用 → 隐藏成本（耗材、配件、保养）。答不出来就写“revisa…”的安全建议，不要编。
- **CTA**：一句，不承诺物流/时效/保修。

## 5. 语言与合规（违反即作废）

- 全文 es-MX；禁中文、禁葡语、禁英文混排。
- 禁 `Compra protegida`、`envío gratis`、`entrega inmediata`、`pago contra entrega`、`solo por hoy`、`última pieza`、`100%`（材质语境除外）、绝对化、医疗宣称、站外导流（WhatsApp/Facebook/Amazon/Mercado Libre）。
- 禁出现 `NOM` / `NOM-003` / `INMETRO` / `ANATEL` / `UN38.3`（本批认证 missing）。
- 禁写价格（后台字段）、禁编赠品/保修/包邮。
- 数字与单位之间留空格（`650 W`、`21V`、`125 mm`）；公制；inch 只在括号里作补充。
- 禁结构标签（`标题：`、`Gancho:`、`Características:`）。

## 6. 自检（每写完一个文件跑一次）

```powershell
python -c "import sys;t=open(sys.argv[1],encoding='utf-8').read().splitlines();n=[x for x in t if x.strip()];print('title',len(t[0]),'hook',len(n[1]),'stars',sum(1 for x in t if x.startswith('⭐')),'chars',len(chr(10).join(t)))" output\批次20261022-v2\listing-<SKU>.txt
```

必须满足：标题长度在区间、hook ≤60、stars 4–5、全文 ≥900 字符、无中文、三段标题齐全。

## 7. 交付

- 文件：`output\批次20261022-v2\listing-<SKU>.txt`（UTF-8，**标题是第一行**，行间空行照样例）
- 只写你名单里的 SKU；写完一个落盘一个，文件名大小写与 SKU 完全一致
- 不碰别人的文件、不改 `input\` / `skill\` / `qa\`、不跑 git
- 全部写完后汇报：完成 N 个 / 你判断有风险的 SKU（数据缺失、参数冲突、材质只有原文推断）
