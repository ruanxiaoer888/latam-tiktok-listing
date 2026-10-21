# 事实卡字段字典（facts/v1）

> 一个 SKU 一份 `input/<SKU>/facts.json`。**生成 Listing 只读这份文件，不读原始描述、不读图片、不猜参数。**
> 状态：`draft`（草稿，待人工核）/ `verified`（可生成）/ `quarantined`（已隔离，移出生成集）/ `blocked`（有硬伤，禁止生成）。
> 规则：缺失写 `null`，不补、不猜；同一槽位多值冲突 → `blocked`。

## 1. 标识

| 路径 | 类型 | 说明 |
|---|---|---|
| `product_id` | string | 与目录名一致，如 `ABU5000000` |
| `category` | string | 8 类目之一 |
| `status` | string | `draft` / `verified` / `blocked` |
| `identity.brand` | string | 品牌（属性 `Marca`） |
| `identity.brand_aliases` | string[] | 同公司可并列的品牌（如 `["Fanny"]`） |
| `identity.model` | string | 型号 |
| `identity.title_raw` | string | 原平台标题（仅留档，不直接用于生成） |

## 2. 供电与功率（最容易错，门禁最严）

| 路径 | 类型 | 说明 |
|---|---|---|
| `power.type` | enum | `corded`（插电）/ `battery`（电池）/ `manual`（手动/液压） |
| `power.voltage_v` | number | 插电类额定电压；110/115/120 一律归一为 127 并留 warning |
| `power.battery_v` | number | **电池工具的工作电压**（不是充电器电压） |
| `power.charger_v` | number | 充电器/额定输入电压（MX 通常 127V）；未确认写 `null` |
| `power.w` | number | **可写进 Listing 的功率**；不可信时写 `null` |
| `power.claimed_w` | number | 供应商标称的最大功率（只留档） |
| `power.rated_claimed_w` | number | 供应商标称的额定功率（只留档） |
| `power.claims_w` | number[] | 资料里出现过的所有功率值（用于发现冲突） |
| `power.state_power` | bool | 是否允许在 Listing 里写具体瓦数 |
| `power.listing_policy` | string | `state_verified_only` / `do_not_state_power` |
| `power.basis` | string | 功率来源：`attribute` / `description` / `supplier_claim` |
| `power.device_v` | number | 整机标称电压（如标 21V 但电池 18V） |
| `power.listing_voltage_v` | number | **Listing 实际要写的电压**（一般=电池实际电压） |
| `power.battery_v_basis` | string | `user_confirmed` / `user_estimate` / null |

**门禁**：插电类 `w >= 3500`（127V 下 >27A）或电池类 `w >= 600` → `state_power=false`，Listing 不写瓦数；要写必须先有铭牌/书面证据。

## 3. 规格

| 路径 | 类型 | 说明 |
|---|---|---|
| `size.length_cm` / `width_cm` / `height_cm` / `diameter_cm` | number | 厘米；缺写 `null` |
| `size.raw` | string[] | 无法结构化的尺寸原文（如起升范围） |
| `weight_kg` | number | 整机重量 |
| `capacity` | string | 容量/承载（`15 L`、`3 toneladas`、`1.5 Ah`） |
| `pieces` | number | 件数（套装） |
| `material` | string[] | 材质（`acero`、`aluminio`…） |
| `extras.lift_range_mm` | number[2] | 千斤顶起升范围 [min, max]（mm） |

## 4. 包装与兼容

| 路径 | 类型 | 说明 |
|---|---|---|
| `package.included` | string[] | 包装清单（逐件） |
| `package.not_included` | string[] | 明确不含的（电池/充电器） |
| `package.source` | string | `attribute` / `description` |
| `compatibility` | object[] | 汽配适配（车型/年款/位置）；通用件为空数组 |
| `certification.status` | string | `available` / `missing` / `not_applicable` |
| `certification.nom` / `inmetro` / `anatel` | string/null | 认证编号（有才写） |

## 5. 卖点素材

| 路径 | 类型 | 说明 |
|---|---|---|
| `features` | string[] | 可从属性 `Con …=Sí` 提取的功能点 |
| `usage` | string[] | 用途/场景（属性 `Usos recomendados`） |
| `specs` | object | 选定的西班牙语规格键值（用于规格段） |
| `raw_attributes` | object | 原始 ML 属性全量留档（只读，不直接生成） |

## 6. 站点与图片

| 路径 | 类型 | 说明 |
|---|---|---|
| `site_profiles.MX.price` | number | 原价（MXN） |
| `site_profiles.MX.currency` | string | `MXN` |
| `site_profiles.MX.plug` | string | `A/B`（BR 为 `N`） |
| `site_profiles.MX.nominal_v` | number | 127 |
| `images[].file` | string | `img/01.jpg` |
| `images[].sha256` | string | 图片哈希（查重/完整性） |
| `images[].main` | bool | 主图（01 为 true） |

## 7. 元数据与门禁

| 路径 | 类型 | 说明 |
|---|---|---|
| `_meta.rules_version` | string | 生成时使用的规则版本（当前 `v1.3`） |
| `_meta.built_at` | string | 事实卡生成时间 |
| `_meta.built_from` | string[] | 来源文件（input.json / item.json） |
| `_meta.source_sha256` | object | 来源文件哈希（可复现） |
| `_meta.verified_by` / `verified_at` | string/null | 人工核验人与时间 |
| `_meta.quarantine` | object/null | 隔离记录：`reason` / `by` / `at`；非空即移出生成集 |
| `gates.hard_blocks` | string[] | 硬伤（非空 → 必须 `blocked`） |
| `gates.warnings` | string[] | 需人工确认，但不阻断 |

## 8. 生成门禁（check_facts.py）

- `status != verified` → 不生成。
- `gates.hard_blocks` 非空 → 不生成。
- 按类目 `required` 检查必填；缺 → 不生成。
- 图片 <5 张 / 无主图 → 警告或阻断（按类目）。
- 认证 `missing` → 不得写 NOM/INMETRO/ANATEL。

## 9. 人工确认覆盖（overrides.json）

不要手改 `facts.json` 的业务字段——重建会覆盖。人工确认写进 `input/<SKU>/overrides.json`，`build_facts.py` 每次重建自动重放：

```json
{
  "source": "用户确认 2026-10-21：电池电压 18V；整机标称 21V",
  "set": {
    "power.battery_v": 18,
    "power.device_v": 21,
    "power.listing_voltage_v": 18,
    "power.battery_v_basis": "user_confirmed"
  },
  "resolve_blocks": ["电池电压多值冲突"],
  "remove_warnings": ["未找到电池电压"],
  "add_warnings": ["电池 18V / 整机标称 21V：Listing 写 18V，不写 21V"],
  "brand_aliases": ["Fanny"]
}
```

- `set`：按点路径覆盖字段；
- `resolve_blocks` / `remove_warnings`：按子串删除构建器产生的阻断/警告；
- `add_warnings`：保留人工确认的注意事项；
- `quarantine`：隔离（移出生成集），格式 `{"reason": "...", "by": "...", "at": "..."}`；补到证据后删除该键即恢复；
- `source`：写清谁、何时、依据什么确认（审计用）。
