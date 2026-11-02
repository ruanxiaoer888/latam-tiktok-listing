---
name: mercadolibre-listing-collector
description: "美客多（Mercado Libre）商品 Listing 批量采集与增量续采。当需要从飞书多维表格的「商品链接」列批量抓取美客多商品页、把商品详情（全部原图 + 标题／价格／类目／规格属性／西语原文描述）落成 latam-tiktok-listing 的 `input/<SKU>/` 目录结构、续采上次被风控拦截或抓取失败的 SKU、核对哪些 SKU 还没采到、生成采集清单或交付压缩包时使用。也适用于换一台电脑继续采集。内置飞书表读取、美客多页面数据提取路径（`__NORDIC_RENDERING_CTX__`）、反爬拦截与失效 SKU 排查、目录产物与命名规范，以及读表／建目录／生成清单／打包校验的可执行脚本。"
---

# 美客多 Listing 采集（飞书表 → 美客多商品页 → `input/<SKU>/`）

## 什么时候用

- 从飞书多维表格「商品链接」列批量采集美客多商品页，落盘成 `input/<SKU>/`
- **续采**：上一轮被风控拦截、404、链接失效的 SKU，现在要补
- **增量采集**：表里新增了 SKU，只采新的（已采的不重抓）
- 生成／刷新采集清单，打包交付（给下游 Listing 生成用）
- 换电脑继续采（家里 ↔ 公司）

**不适用**：Listing 文案生成与合规校验（那是 `latam-tiktok-listing` 技能）、自动上传后台、店铺注册。

**与 `latam-tiktok-listing` 的分工**：本技能是**上游**——只管把原始素材（图 + 原文 + 属性）落到
`input/<SKU>/`；下游跑 `qa\build_facts.py` 生成 `facts.json` 再生成 Listing。
**不要在本流程里生成或改写 Listing 文案。**

## 三条硬前提（缺一条就采不到，先过这三关）

| 前提 | 判定 | 不满足会怎样 |
|---|---|---|
| **非机房网络出口**（墨西哥住宅 IP） | 商品页能正常打开，不出现安全验证页 | 出现「安全验证／正在验证你」页 → 见 `references/03-风控与失效排查.md`，**先解决出口再采**，硬试只会把整个会话标记 |
| **浏览器通道可用** | `dumate-browser-cli --version` 有输出；`init` 成功 | 页面数据必须带登录态在同源下读取，通道不可用就取不到数 |
| **飞书已登录** | 浏览器里打开的多维表格能读到行 | 读不到「商品链接」列，采集清单为空 |

> 出口这一条是本流程的**唯一决定性变量**。本机跑通时的形态：FlClash 类客户端 + Windows
> 系统代理 `127.0.0.1:7890`，出口为墨西哥住宅 IP（实测 `189.253.199.238` / AS8151 Uninet）。
> **换到公司电脑时必须自带同样的住宅出口**，否则第一关就卡住。

## 目录（相对本文件）

```
SKILL.md                        本文件
references\
  01-飞书表读取.md               内部接口 / 列名映射 / gzip 解码 / 排错
  02-美客多页面提取.md            数据路径表、规格属性、图片 URL 模板、判定信号
  03-风控与失效排查.md            验证码墙根因与解法、失效 SKU 判定、已试错的路径清单
  04-产物与命名规范.md            input/<SKU>/ 结构、字段口径、命名与跳过铁律
scripts\
  feishu_read.js                页面内：读飞书表 → 返回 B64(JSON)
  ml_extract.js                 页面内：批量抓美客多商品页 → 返回 B64(JSON)
  catalog_extract.js            页面内：读已打开的目录产品页 DOM
  bridge.py                     浏览器桥（init/goto/eval/解码 B64）
  read_sheet.py                 读表 → <work>/_sheet_rows.json
  ml_batch.py                   分批抓 item 级 → <work>/raw_<tag>.json
  ml_catalog.py                 逐个抓目录级 → <work>/raw_catalog.json
  build_input.py                抓取结果 → input/<SKU>/{input.json,item.json,img/}
  gen_manifest.py               增量规划（--plan）+ 生成 采集清单.md
  pack_and_verify.py            打包 zip + 逐条校验包内内容
```

## 使用步骤

### 0. 定位参数（每次都先做）

| 参数 | 含义 | 默认 |
|---|---|---|
| `--input-root` | 落盘根目录 | env `MLP_INPUT_ROOT`，否则 `<collector 上一级>/input` |
| `--work` | 中间结果目录 | `<collector>/_work`（`_` 开头，自动跳过） |
| `app_token` / `table` / `view` | 飞书表三个 id | 见 `references/01-飞书表读取.md`，换表时改那里 |

**把这两条路径先记下来**（下文示例用 `<工作区>` 和 `<技能>` 代替）：

```
<工作区> = 你的技能仓库根（clone 出来的那一层，随机器变化，不要写死盘符）
<技能>   = 本 collector 目录，例如 <工作区>\collector
```

> **技能装到 `%USERPROFILE%\.agents\skills\` 或本机技能目录后，脚本位置已不在工作区里**——
> 那时 `<collector 上一级>` 不再是仓库根，默认值会指错。**必须给每条命令显式写
> `--input-root`**（或先设环境变量 `MLP_INPUT_ROOT`）。下文示例一律写成显式参数，照抄即可。

### 1. 拿全量清单（飞书表）

```bash
python "<技能>\scripts\read_sheet.py" --work "<工作区>\collector\_work"
```

产出 `<工作区>\collector\_work\_sheet_rows.json`：每行含 `sku / link / ml_title / item_id /
price / note`。**这是本次采集的权威清单**；`missing_fields` 非空说明列名对不上，按
`references/01-飞书表读取.md` 处理。

### 2. 算增量（关键：已采的不重抓）

```bash
python "<技能>\scripts\gen_manifest.py" --input-root "<工作区>\input" --work "<工作区>\collector\_work" --plan
```

只打印三类：**已采（跳过）／待采（新增）／需补采（上次失败）**。
顺手写出可直接喂 `ml_batch.py` 的待采清单：

```bash
python "<技能>\scripts\gen_manifest.py" --input-root "<工作区>\input" --work "<工作区>\collector\_work" \
    --plan --pending-out "<工作区>\collector\_work\pending.json"
```

**只对「待采 + 需补采」动手**；已落盘目录默认不覆盖（除非显式 `--force` 并确认）。

### 3. 分批抓取

item 级（常规）：

```bash
python "<技能>\scripts\ml_batch.py" --items "<工作区>\collector\_work\pending.json" --tag b01 \
    --work "<工作区>\collector\_work"
```

- 自动分批（**单批 ≤ 24 个 URL**）、批间串行 + 停顿，结果合并写 `<work>\raw_b01.json`
- 需要按批留档时加 `--tag-field`（写 `raw_b01_01.json` …）
- 每批实时打印成功率与拦截计数；末批出现 `wall` 警告时**停下来先换出口**，不要就地重试

目录级（原 item 停售，链接会跳到 `/up/MLMU...`）：把这类 SKU 单独写成 `[{sku,url}]` 后：

```bash
python "<技能>\scripts\ml_catalog.py" --items "<工作区>\collector\_work\catalog_items.json" --work "<工作区>\collector\_work"
```

### 4. 建目录 + 下图

```bash
python "<技能>\scripts\build_input.py" --raw "<工作区>\collector\_work\raw_b01.json" \
    --input-root "<工作区>\input" --work "<工作区>\collector\_work" --proxy 127.0.0.1:7890
```

产出每个 SKU：`input.json` + `item.json` + `img\01.jpg…`（原图，保留原始格式与尺寸）。
脚本行为：

- 目录已存在且含 `input.json` → **跳过**（`--force` 才重建）
- 图片按 `url_original`（最高分辨率 `-OO`）下载，失败重试 3 次并记进 `item.json.images[].error`
- 自动判定 `category`（中文类目）与 `core_keyword`，判定规则在脚本内，可事后核对
- 风控/404/下架记录**不建目录**，只写进 `<work>\build_report.json`（供下一步判「需补采」）

### 5. 处理没采到的（别急着重试）

按 `references/03-风控与失效排查.md` 判性质：

| 现象 | 性质 | 动作 |
|---|---|---|
| 返回验证码墙／重定向到 `gz/account-verification` | 网络出口被拦 | 换住宅出口后**整批**重采 |
| 链接跳到 `…/listado…/#redirectedFromVip=…`（类目浏览页） | 商品已下架／删除 | **不重试**，记入清单「未采到」 |
| 404 | 商品已删除 | **不重试**，记入清单「未采到」 |
| 跳到同商品的目录产品页（`data_level: catalog`、`availability: OutOfStock`） | 原 item 停售，同商品仍在 | 走第 3 步的 `ml_catalog.py`，价格置 `null` |

### 6. 生成清单

```bash
python "<技能>\scripts\gen_manifest.py" --input-root "<工作区>\input" --work "<工作区>\collector\_work" \
    --out "<工作区>\采集清单.md" --zip ml-listing-input-<N>sku.zip
```

产出：汇总表 + 按采集日期的逐 SKU 明细 + 「未采到」表 + 异常说明。
**清单是交付物的一部分，必须与实际目录一致。**

### 7. 打包 + 校验

```bash
python "<技能>\scripts\pack_and_verify.py" --input-root "<工作区>\input" \
    --out "<工作区>\ml-listing-input-<N>sku.zip" --manifest "<工作区>\采集清单.md"
```

同一命令先打包再**直接验包内**内容：SKU 目录数、`input.json` 必填字段、图片声明数与实际数、
图片能否打开、标题与描述非空、有无冗余 `description.json`。
**校验不过会以非 0 退出码结束——按提示回第 4 步修，再重跑，不要带着问题交付。**

## 硬约束（违反即不交付）

- **已采目录默认不覆盖**：增量采集只写新目录；覆盖必须显式 `--force`，且覆盖前确认
- **描述保留西语原文，不翻译、不截断**；图片保留原始格式与尺寸，文件名 `01.jpg` 起两位顺序编号
- **不并发抓取**：串行分批，单批 ≤ 24 个；触发风控不是「再试一次」，而是先换出口
- **失败 SKU 先判性质再决定是否重试**：已下架／404 属美客多侧数据缺失，重试无意义，只记缺口
- **`_` 开头目录不参与采集／统计／打包**
- 落盘目录结构与字段名必须与 `references/04-产物与命名规范.md` 一致——下游 `qa\build_facts.py`
  直接吃这份结构，字段少一个就断链
- 不把密钥、cookie、代理口令写进任何落盘文件

## 输出

| 产物 | 位置 |
|---|---|
| 商品目录（每条一个） | `<工作区>\input\<SKU>\{input.json, item.json, img\}` |
| 采集清单 | `<工作区>\采集清单.md` |
| 交付压缩包 | `<工作区>\ml-listing-input-<N>sku.zip`（含 `input/**` + 采集清单） |
| 中间结果 | `<工作区>\collector\_work\`（`raw_*.json`、`_sheet_rows.json`、`build_report.json`、`pending.json`，不进交付） |

## 安装与换机

- 两个技能（本技能 + 下游 `latam-tiktok-listing`）都在同一个仓库里，
  一次 clone 全拿到；仓库根的 `迁移到新电脑.md` / `setup-new-pc.cmd` 是换机入口
- 技能运行位置二选一：DSH 全局 `%USERPROFILE%\.agents\skills\<技能名>\`，
  或本机 DuMate 技能目录 `...\data\skills\user\<技能名>\`
- 采集必备的**住宅出口**不在仓库里（也不该进仓库）——换机后第一件事就是按
  `references/03-风控与失效排查.md` 第三节过那三道检查

## 边界

- **不做 Listing 生成／改写**：那是下游 `latam-tiktok-listing` 技能
- **不做自动上传**：上传有副作用，留人工
- **不绕过风控**：不伪造 UA／cookie／打码服务；拦截只通过网络出口解决
- **不虚构数据**：页面没有的价格、卖家、属性一律留空并标注原因，不用飞书登记值冒充页面值