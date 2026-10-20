# 规则包 · 巴西站（pt-BR）v1.0

> 说明：**这份不是把墨西哥包机翻过来的**。巴西的供电、插头、认证、语言习惯、促销节点都和墨西哥不同，硬套 MX 包会得到"西语混葡语"的废稿。
> 结构对齐 `rules-mx.md`，机器校验版本见 `qa/denylist.json`。

---

## 1. 语言与语气

- 语言：**pt-BR（巴西葡语）**，不是葡萄牙葡语。禁用 es-MX 词（`envío`、`celular` 可用但 `computadora`→`computador`、`refacción`→`peça`）
- 人称：**você**（不是 tu，也不是 o senhor）
- 标点：**没有倒标点**（不要 `¡...!` / `¿...?`，那是西语）
- 首字母大写，正文不用全大写强调
- 重音符号必须写对（`elétrico`、`indução`、`não`）——影响搜索匹配，也影响可信度
- 俚语（`top`、`maravilhoso`、`trem bom`）：**只用于视频脚本**，商品描述不用

## 2. 度量衡与货币

- 强制公制：inch → cm，lb → kg，oz → ml，°F → °C
- 价格必须带币种：`R$ 199,90`（逗号小数、点千分位，**别写成 199.90**）
- 电压写法：`127V / 60Hz` 或 `220V / 60Hz`，**必须写清具体电压**
- 巴西 127V / 220V 分地区供电（同一城市都可能不一样）→ 这是退货和差评的头号来源

## 3. 可用本地化词（安全区）

| 场景 | 可用表达 | 备注 |
|---|---|---|
| 好评 | `Ótimo custo-benefício` / `Muito prático` | 稳妥 |
| 性价比 | `Preço justo` / `Vale cada centavo` | |
| 分期 | `Parcele em até 3x sem juros` | 仅在真支持时写 |
| 干活/修车 | `Para a oficina` / `Item essencial na caixa de ferramentas` | 五金汽配专用 |
| 家居 | `Deixa sua casa mais organizada` | |
| 运动 | `Treino em casa ou na academia` | |
| 宠物 | `Seu pet vai amar` | |
| 配件 | `O toque final no seu look` | |
| CTA | `Toque na sacolinha laranja` / `clique no carrinho laranja` | 两种都有人用，二选一保持一致 |

## 4. CTA 与信任词（安全版）

| 可用 | 条件 |
|---|---|
| `Compra segura` | 随时可用 |
| `Proteção ao comprador` | 随时可用 |
| `Garantia de devolução` | 店铺真有退货政策 |
| `Selo INMETRO`（如属实） | 只在产品真有认证时写 |

| **禁用** | 原因 |
|---|---|
| `Compra garantida` | **美客多巴西的品牌词**，借用即误导 |
| `100% garantido` | 绝对化 |
| `Frete grátis` / `Envio grátis` / `Entrega imediata` | 物流承诺必须有履约能力，默认关闭 |
| `Pague na entrega` | 仅真支持货到付款时写 |

## 5. 标签（可选，默认关闭）

A/B 验证前不作为标准。若必须用，取 3–5 个：

- 通用：`#TikTokShopBrasil` `#TikTokMeFezComprar` `#Achadinhos`
- 五金汽配：`#Ferramentas` `#Mecanica` `#Oficina` `#Moto`
- 家居厨房：`#Casa` `#Cozinha` `#Eletrodomesticos`
- 运动：`#Academia` `#Treino`

## 6. 消费节点

| 节点 | 时间 | 可用表达（仅当促销真实存在） |
|---|---|---|
| Carnaval | 2 月 | 场景联想为主 |
| Dia do Consumidor | 3 月 15 日 | `Oferta do Dia do Consumidor` |
| Dia dos Namorados | 6 月 12 日 | `Ideal para presentear` |
| Dia das Crianças | 10 月 12 日 | 儿童/宠物用品可蹭 |
| Black Friday | 11 月最后一周五 | `Oferta de Black Friday` |
| Natal | 12 月 | `Presente de Natal` |

## 7. 禁用词与违规宣称

| 类型 | 禁用 |
|---|---|
| 绝对化 | `o melhor do mundo`、`milagroso`、`100% garantido` |
| 医疗 | `cura`、`tratamento médico`、`perda de peso rápida`、`elimina a dor` |
| 虚假紧迫 | `só hoje`、`última peça`、`por tempo limitado` |
| 站外导流 | `WhatsApp`、`Facebook`、`Instagram`、`Amazon`、`Mercado Livre`、`telefone` |
| 未验证物流/信任 | `frete grátis`、`envio grátis`、`entrega imediata`、`compra garantida` |

**`100%` 判定同 MX**：`100% aço inox`（材质）放行；`100% seguro`（保证）拦截。

## 8. 认证与硬合规（巴西比墨西哥更严，这是硬门槛）

| 品类 | 巴西要求 |
|---|---|
| 家电 | **INMETRO 强制认证**；大家电另有 PBE 能效标签；插头 **N 型**（NBR 14136） |
| 电动工具 / 电工 | INMETRO（部分品类强制）；锂电池 UN38.3 |
| 无线（WiFi / 蓝牙） | **ANATEL 认证**（无认证不得销售） |
| 汽摩配 | 头盔 **INMETRO 强制**；灯具/刹车类法规更严；无线加 ANATEL |
| 厨房/食品接触 | 材料合规 + ANVISA（接触食品器具） |
| 宠物电子 | 电池 + ANATEL（含无线时） |
| 通用 | 葡语说明书与标签；TikTok Shop 特殊类目上架前需提交证书 |

## 9. 常见坑

1. 电压只写 `Bivolt` 不写实际范围 → 买家装不上就退
2. 插头照搬美规/欧规 → 巴西是 N 型（三圆孔）
3. 价格写成 `199.90` → 巴西人读成 19990
4. 用西语词（`envío`、`gratis`）→ 立刻暴露"外国人开店"
5. 认证没到手就上架 → 被下架还影响店铺分
6. 把 MX 的促销节点（Buen Fin）用到巴西 → 完全不同市场

## 10. 和 MX 包的差异速查

| 项 | MX | BR |
|---|---|---|
| 人称 | Tú | você |
| 倒标点 | 必须 | 禁止 |
| 货币 | `$299 MXN` | `R$ 199,90` |
| 电压 | 127V | 127V / 220V（必须写清） |
| 插头 | A/B | N |
| 认证 | NOM-003 | INMETRO / ANATEL / ANVISA / PBE |
| 信任词 | Compra segura | Compra segura（**不是** Compra garantida） |
| 大促 | Buen Fin 11月 | Black Friday 11月 |
