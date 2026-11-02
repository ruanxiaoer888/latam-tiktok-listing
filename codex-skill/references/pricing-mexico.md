# TikTok Shop Mexico Price Recommendation

Use when Mexico price fields or pricing advice are in scope. Follow [SKILL.md](../SKILL.md) for output language, pending values and task boundaries; do not activate pricing just because a wording-only task includes a source price.

## Scope

A complete Listing includes a regular retail-price field per applicable SKU. Preserve a user-set shop price; otherwise recommend a supported price or leave the field pending. Only a recommendation needs a brief basis/caveat in the sales table. Campaign selection, coupon examples, promotion calculations, and detailed profitability output below apply only when the user asks for them or the supplied form requires them. A request for a complete Listing does not activate campaign planning.

## Identify the Price Role First

- **User-set shop price:** preserve the value and currency unless the user requests repricing. Do not replace it with a competitor price, label it as an assistant recommendation, or imply validated profit.
- **Reference retail price:** identify the source platform, date, currency and exact variant/offer. A comparable reference can anchor a test recommendation; preserve its source label rather than calling every reference Mercado Libre.
- **Procurement cost:** use only as a cost input. If it is the only price and fees, fulfillment and the pricing objective are missing, leave retail price pending; do not apply an invented markup or copy cost into the retail field.
- **Conditional or alternate amount:** distinguish installment amounts, crossed-out prices, coupon payments, shipping charges and funded discounts from an unconditional item retail price.

If a price's role is ambiguous, flag it instead of selecting whichever interpretation makes a recommendation possible.

## Currency and Source

- Treat a price from a confirmed Mercado Libre Mexico listing as Mexican pesos (`MXN`), unless the source explicitly states another currency.
- Preserve reference prices exactly. Use `Precio de referencia en Mercado Libre` / `美客多参考零售价` only for that source; name any other source accurately. Labels follow the selected output language.
- Read the actual price structure: a legacy `price` field may be replaced by `pricing.discount_price`, `original_price`, and `installment`. Use a clearly identified current item sale price as the reference, even when discounted; keep the crossed-out original separate. A conditionally subsidized or coupon-only buyer payment is not an unconditional item price. If that distinction is unclear, flag the reference basis instead of inventing a normal price.
- Bind each source price to its documented variant and capture time. Do not spread a selected variant's price across other variants as confirmed pricing. A proposed common test price must be explicitly a recommendation, not an observed source price; if its basis is insufficient, leave the other variants pending.
- If the price source or currency is uncertain, mark it `[POR CONFIRMAR]` / `[待确认]` instead of calculating a recommendation.

## Default Recommendation

When a recommendation is needed, no user-set shop price should be preserved, and cost/fee/margin inputs are incomplete:

1. Use a comparable reference retail price with the same currency and documented offer/variant; state its capture date when available and do not imply a live recheck.
2. Without a defensible adjustment reason, retain that reference as a clearly labeled test-price recommendation. Do not apply a fixed percentage band or invent a markup.
3. Change the price or its ending only for a stated commercial reason or user preference; an `x9` or `x99` ending alone is not evidence of better performance.
4. Only when promotion planning is requested, provide one defensible plan conditional on margin, eligibility, duration, and current platform rules.
5. Do not recommend a price below an unknown break-even point as if it were safe.

Label the regular recommendation `market-anchored test price` / `市场锚定测试价`, not `profit-validated price` / `利润已验证价格`. For campaigns only, label a proposal `conditional campaign price` / `条件性活动价` and state that the campaign must not be activated until costs, fees, funding, stacking, and post-promotion seller proceeds are confirmed. Do not add campaign activation warnings to regular-price-only output.

## Cost-Aware Recommendation

Calculate only the requested scenario. For regular-price economics, use the applicable costs, fees and tax treatment; missing campaign eligibility, stacking or subsidy details must not block an otherwise complete regular-price calculation. For campaign economics, additionally resolve the campaign inputs that affect that result. Mark only dependent results pending and identify the missing basis; do not block unrelated calculations. Never present gross buyer payment as net seller revenue.

Use a consistent currency, per-order basis and tax treatment. Let `C` be the included landed product cost plus fixed fulfillment/shipping/handling costs and return allowance, `r` the variable fee rate charged on the same selling-price base, and `P` the selling price on that base. If actual fees or taxes use different bases, model them explicitly rather than putting incompatible rates into `r`.

- `break-even price for included costs = C / (1 - r)`
- `price for target contribution margin = C / (1 - r - m)`, where `m` is the user's specified target contribution margin.
- `contribution profit at P = P * (1 - r) - C`
- `contribution margin at P = contribution profit at P / P`, for `P > 0`.

The break-even calculation uses a zero contribution target by definition; it does not assume the user wants zero profit. Do not invent `m`. If a target was not supplied, calculate supported break-even or profit-at-price results when requested, leaving only the target-price result unresolved. Treat target margin as contribution profit divided by selling price unless the user defines another basis; do not confuse margin with markup on cost.

Check `1 - r > 0` for break-even and `1 - r - m > 0` for a target price. If a denominator is zero or negative, stop only that calculation and flag its inputs. A target-price calculation can be invalid while break-even is still computable. Preserve precision until the displayed-price step and recheck any rounded price against its claimed threshold.

Track included costs, excluded costs, tax treatment and assumptions internally; show the breakdown when detailed analysis is requested. Label break-even as applying to the included costs, not as a guarantee of overall business profitability. Compare a proposed price with the applicable thresholds: below break-even means a negative contribution under the stated model; below a positive target-margin price but above break-even means the target is missed, not that the order loses money.

For a seller-funded promotion, account for the seller-funded discount and campaign-specific charges on the appropriate settlement/fee bases. Do not subtract the same discount twice if it is already reflected in the price used. If discounts stack, evaluate the supported combination rather than each discount in isolation. Do not count platform subsidies as seller proceeds unless funding and settlement are confirmed.

For requested detailed analysis, show only applicable results: break-even for included costs, price for a supplied target margin, recommended regular price, requested campaign price or coupon structure, and contribution profit/margin at a stated price. Distinguish campaign break-even from campaign target-margin pricing as well. Missing campaign inputs limit campaign results only; applicable unresolved cost or tax inputs still limit regular-price results.

## Promotion Decision

Apply this section only when promotion planning is in scope. Do not add campaigns to a regular-price-only response.

Choose one principal promotion rather than listing multiple unsupported alternatives:

- Recommend `Oferta relámpago` / `秒杀活动` when the goal is a short traffic or conversion push, the seller can limit the duration or quantity, and the proposed price is supportable by known costs or is clearly labeled conditional on margin confirmation.
- Recommend `Cupón para nuevos clientes` / `新人满减券` when the goal is first-order acquisition, the product price can support a clear threshold, and the threshold does not pressure buyers into an unsuitable quantity. State the threshold, discount, and expected payment for the intended basket.
- If cost, fee, or eligibility information is too incomplete to choose safely, still show a conditional planning example when useful, but label it `[POR CONFIRMAR]` / `[待确认]` and list the missing inputs. Do not describe it as profit-safe.

Identify who funds the promotion as `seller-funded`, `platform-funded`, or `shared` only when supported by the supplied campaign terms. If unknown, mark it `[POR CONFIRMAR]` / `[待确认]`. Buyer payment is not the same as seller revenue; never infer seller proceeds from the buyer-facing discount alone.

For a single-item flash sale, calculate and show:

`discount amount = regular price - campaign buyer payment`

`discount rate = discount amount / regular price × 100%`

For a new-customer threshold coupon, calculate against the qualifying basket, not automatically against one item's regular price:

`coupon discount rate = coupon discount / qualifying basket amount × 100%`

`expected basket payment = qualifying basket amount - coupon discount`

Show a single-item buyer payment only when one unit by itself meets the threshold. If the coupon requires multiple units or other products, state the example basket quantity and subtotal; do not attribute the full coupon discount to one item unless allocation is explicitly requested. If allocation is requested, state the allocation method.

Round only at the final displayed-price step. Do not treat a platform-funded subsidy as a seller-funded discount unless funding is verified.

## Output

In the SKU table, show the preserved shop price, a supported recommendation, or a pending field according to the price-role decision. For recommendations, identify the reference/date or cost basis briefly and state when profit remains unverified. Omit a separate pricing report.

For explicitly requested detailed pricing or promotion analysis, show the applicable items in a pricing block using the selected output language(s):

- Reference retail price and its actual source (MXN), if supplied.
- Recommended TikTok Shop regular retail price (MXN).
- Recommended promotion type and commercial objective.
- Flash-sale price, or new-customer coupon threshold and discount, plus expected buyer payment (MXN).
- Promotion funding source when known, otherwise a confirmation flag.
- Flash-sale discount amount and rate versus regular price, or coupon discount rate versus the qualifying basket amount.
- Difference from an available comparable reference in MXN and percent.
- Short basis and only the unresolved inputs needed for the requested calculation; do not flag an absent target margin when only break-even or profit at a stated price was requested.
- Break-even for included costs, price for a supplied target contribution margin, and profit/margin at a stated price, each only when its own required inputs are complete.

The price field is numeric. Labels, explanations and pending notes follow the language selection in SKILL.md, including Spanish-only requests.
