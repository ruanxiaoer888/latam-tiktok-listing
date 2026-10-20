# 规则包 · 墨西哥站（es-MX）v1.0

> 底本：`source-gemini/1_本地化词库与合规红线_V3.2.md` + `3_核心品类写作与脚本指南_V3.2.md`，2026-10-20 改造。
> 改动 5 处，清单在文末第 10 节。机器校验版本见 `qa/denylist.json`。

---

## 1. 语言与语气

- 人称：**Tú**（禁止 Usted，德式敬语会显得疏远）
- 标点：疑问 `¿...?`、感叹 `¡...!`，两边都要有倒标点
- 版本差异：es-MX，不是西班牙西语。墨西哥本地词优先（见第 3 节）
- 俚语（`chido`、`padrísimo`、`órale`、`talacha`）：**只允许出现在短视频脚本**，商品描述不用
- 数字与单位之间留空格：`21V`、`2 L`、`45 cm`、`4000mAh`

## 2. 度量衡与货币

- 强制公制：inch → cm，lb → kg，oz → ml，°F → °C
- 价格出现必须带币种：`$299 MXN`
- 电压写法：`127V / 60Hz`（墨西哥家用标称 127V，**别写 110V**，会被懂行买家挑刺）

## 3. 可用本地化词（安全区）

| 场景 | 可用表达 | 备注 |
|---|---|---|
| 好评 | `¡Excelente!` / `Súper práctico` | 稳妥 |
| 性价比 | `Súper precio` / `Excelente relación calidad-precio` | `Bueno, bonito y barato` 慎用：`barato` 拉低定位 |
| 分期 | `Meses sin intereses (MSI)` | 仅在店铺真支持时写 |
| 干活/修车 | `Para la talacha` / `Indispensable en tu cajuela` | 五金汽配专用 |
| 家居 | `Combina perfecto con tu hogar` | |
| 运动 | `Entrena en casa o donde sea` | |
| 宠物 | `Tu peludito lo amará` | |
| 配件 | `El toque final para tu outfit` | |

## 4. CTA 与信任词（安全版）

| 可用 | 条件 |
|---|---|
| `Compra segura` | 随时可用 |
| `Compra con protección al comprador` | 随时可用 |
| `Garantía de devolución` | 店铺真有退货政策 |
| `Garantía de calidad` | 真有售后承诺，否则删 |

| **禁用** | 原因 |
|---|---|
| `Compra protegida` | 美客多 / Mercado Pago 的品牌词，暗示 TikTok 未承诺的保障 |
| `Compra 100% segura` | 绝对化 |
| `Envío gratis` / `Entrega inmediata` / `Envíos rápidos a todo México` | 物流承诺必须有实际履约能力，默认关闭 |
| `Pago contra entrega` | 仅在该店铺真支持货到付款时写 |

## 5. 标签（可选，默认关闭）

A/B 验证前不作为标准。若必须用，从下列取 3–5 个：

- 通用：`#ComprasTikTok` `#TikTokMeHizoComprarlo`
- 五金汽配：`#Talacha` `#Herramientas` `#Mecanica`
- 家居：`#Hogar` `#Electrodomesticos`
- 运动：`#GymMexico` `#Entrenamiento`

> 注意：标签主要作用于视频/内容，对商品描述的搜索权重未经验证；且与自己「禁关键词堆砌」的规则冲突，先用 A/B 数据说话。

## 6. 消费节点

| 节点 | 时间 | 可用表达（仅当促销真实存在） |
|---|---|---|
| Hot Sale | 5 月 | `Oferta de Hot Sale` |
| El Buen Fin | 11 月 | `Oferta de Buen Fin` |
| Día de Muertos | 11 月初 | 仅做场景联想，不做折扣宣称 |
| Navidad / Reyes | 12 月 – 1 月 6 日 | `Ideal para regalo` |
| Día del Padre | 6 月第三个周日 | 五金汽配可蹭 |

## 7. 禁用词与违规宣称（机器校验见 `qa/denylist.json`）

| 类型 | 禁用 |
|---|---|
| 绝对化 | `el mejor del mundo`、`milagroso`、`100% garantizado` |
| 医疗 | `cura`、`tratamiento médico`、`pérdida de peso rápida`、`elimina el dolor` |
| 虚假紧迫 | `solo por hoy`、`última pieza`、`por tiempo limitado` |
| 站外导流 | `WhatsApp`、`Facebook`、`Instagram`、`Amazon`、`Mercado Libre`、`电话` |
| 未验证物流/信任 | `envío gratis`、`entrega inmediata`、`compra protegida`、`pago contra entrega`（未确认时） |

**`100%` 的判定规则（修正 V3.2 的一刀切）**

- 后面跟材质名词 → **放行**：`100% acero inoxidable`、`100% algodón`、`100% cobre`
- 后面跟保证/效果词 → **拦截**：`100% segura`、`100% garantizada`、`100% efectivo`
- 判定由 `qa/check_listing.py` 自动做

## 8. 认证与硬合规（比用词更要命）

| 品类 | 墨西哥要求 |
|---|---|
| 家电 / 电动工具 / 电工 | NOM-003-SCFI-2014；页面需标注 NOM 认证编码 |
| 无线（WiFi / 蓝牙） | NOM + 当地无线电要求 |
| 锂电池 | UN38.3 + 运输合规；说明书标电池规格 |
| 厨房/食品接触 | 材料合规，食品级宣称需有依据 |
| 玩具 / 儿童用品 | NOM-252 / COFEPRIS（涉及才需要） |
| 通用 | 127V / 60Hz，A/B 型插头，西语说明书与标签 |

## 9. 常见坑

1. 墨西哥买家不用 `110V` 说法 → 统一 `127V`
2. `barato` 会拉低定位，改用 `buen precio`
3. 用 `Bueno, bonito y barato` 描述五金工具会显得廉价
4. 价格不写 `MXN` 会被认为不可信
5. 促销节点词乱用 → 绑定"促销真实存在"这条闸

## 10. 相对 V3.2 改了什么

| # | 改动 | 原因 |
|---|---|---|
| 1 | `Compra protegida` → `Compra segura` | 前者是美客多品牌词 |
| 2 | `100%` 从一律禁 → 上下文判定 | 误杀 `100% acero inoxidable` 这类真实材质 |
| 3 | 标题 `\|` 明确允许 | V3.2 规则禁特殊符号，但 9 条案例全用 `\|`，自相矛盾 |
| 4 | 物流宣称（包邮/极速）从"话术"降为"需数据支撑，默认关闭" | 无履约能力就是虚假宣传 |
| 5 | 俚语限定只用于脚本 | 商品描述里偏轻浮，削弱五金/家电专业感 |
| 6 | 补入认证检查表 | V3.2 完全没有，而这是家电/工具/汽配的硬关卡 |
