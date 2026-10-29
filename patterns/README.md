# patterns｜提示词按 fabric 的 Pattern 规范组织

一个 pattern = 一个目录：`system.md`（只写流程与硬约束）+ `meta.json`（版本/上下文/输出契约）。
规则本体在 `skill/`，由 meta.json 的 contexts 引用，**不复制**。

## 现有 pattern

| pattern | 作用 | 输出 |
|---|---|---|
| `listing_write` | 初稿：标题 / 首屏 / 卖点 / 规格 / 包装 / FAQ / CTA | `listing_draft/v1` JSON |
| `listing_fix` | 按 `check_listing` 的违规清单改稿：只改被点名的项 | `listing_draft/v1` JSON + `changes` |

## 主流程

```powershell
# 1) 组装 prompt（不调模型，可 diff）
python scripts\render_prompt.py --sku ABU5000000 --site MX

# 2) Agent 按 output\_prompts\<SKU>.md 生成草稿 JSON
#    -> output\_draft\<SKU>.json

# 3) JSON 渲染成可粘贴的纯文本（格式由代码保证）
python scripts\render_listing.py --dir output\_draft --out-root output\批次20261030 --site MX

# 4) 门禁 + 校验 + 出表（P0/P1 任一 >0 即阻断）
python qa\run_batch.py --input-root input --listing-dir output\批次20261030 --site MX

# 5) 评分并存基线
python scripts\eval_pattern.py --batch output\批次20261030 --pattern listing_write@1.0.0 `
  --baseline output\_eval\listing_write@1.0.0.json
```

## 改稿闭环（listing_fix）

```powershell
# 1) 上一步 run_batch 会在 output\_smoke\run_batch_<ts>\ 里产出明细 CSV
#    用明细生成改稿 prompt（会自动带上当前成稿 + 违规清单）
python scripts\render_prompt.py --sku <SKU> --site MX --pattern listing_fix `
  --findings output\_smoke\run_batch_<ts>\<日期>\明细_MX_check_verified_<ts>.csv `
  --batch output\批次20261030

# 2) Agent 按 output\_prompts\<SKU>-fix.md 输出改稿 JSON -> output\_draft\<SKU>.json
# 3) 重跑 render_listing + run_batch，直到 P0/P1=0
```

## 黄金集（回归基准）

- 清单：`eval/golden/manifest.json`（20 条候选，`status=pending_human_review`）。
- 人工确认后把 `status` 改成 `approved`，这套就是「不许变差」的固定样本。
- 评测：`python scripts\eval_pattern.py --batch <批次> --golden eval\golden\manifest.json`

## 三条纪律

1. **规则只有一份**：meta.json 的 contexts 指向 `skill/`；平台限制统一从 `qa/denylist.json` 读（`qa/_limits.py`），不要在脚本里写死 60–80。
2. **生成包带版本**：`output/_prompts/*.md` 头部有 pattern 版本 + renderer 版本 + sha256，过期包一眼能看出来。
3. **改提示词必须评测**：与 `output/_eval/<pattern>@<version>.json` 比，变差就回滚。

## 与旧流程的关系

- `qa/make_listing_pack.py`（旧的 `_packs`）保留可用，但**不再扩展**；新批次走 `render_prompt`。
- `qa/normalize_listing.py` 只用于清洗存量成稿（新流程不需要）。
