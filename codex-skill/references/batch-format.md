# Batch Listing Format

Use for requested CSV/XLSX imports or exports, multiple products, or bulk rewrites. Several variants of one product in an ordinary chat response use the compact SKU table in SKILL.md instead.

## Review Workbook or Platform Import

Follow [SKILL.md](../SKILL.md) for task scope, target market, language and source review. Distinguish the requested artifact:

- **Review workbook:** use readable fields and permitted reference translations; keep pending explanations in a compact notes column. The suggested schema below is for review, not a platform import specification.
- **Platform import:** use the actual target-market/category template and its sheet names, exact column names/order, data types, row structure and accepted values. Do not add translation, source or audit columns unless the template supports them. Keep necessary review notes outside the import data.
- Without an actual template or a verified import schema, create a clearly labeled review draft if useful and request the template for conversion. Do not claim the draft is ready to import or invent a platform schema.
- Missing required values, unverified required category/option values or unresolved SKU mappings prevent an import-ready designation. Keep affected records in a review draft or separate review output; do not silently drop them or mark them ready.

## Data Handling

- Preserve the input row order and stable identifiers such as product ID, parent SKU, and seller SKU.
- Never merge products or variants merely because their names are similar.
- Keep one parent product's shared content separate from variant-specific fields.
- In review workbooks, retain source columns unless a reduced output is requested. In platform imports, include only template-supported columns; keep the source available separately.
- In review workbooks, use one notes column for uncertainty; add separate review columns only for requested audits. For import sheets, use the template's accepted blank/null representation, never pending text in numeric fields.
- For a review table, use one row per purchasable SKU combination when price, package data or inventory differs. For an import, follow the template's parent/variant row structure. Keep shared content stable and per-SKU facts separate.
- Preserve SKU, GTIN and other identifiers as text, including leading zeros and long digit strings. Set XLSX identifier cells to text; for CSV, preserve literal strings and verify a text-preserving re-read. CSV quoting alone does not control spreadsheet type inference. Reopen the generated artifact to verify identifiers, row counts, variant mappings and missing numeric values.
- In requested audit exports, use evidence status values `CONFIRMED`, `IMAGE_READ`, `RECOMMENDED`, and `TO_CONFIRM` for critical fields when provenance is not otherwise obvious.
- In those exports, use compliance action values `PASS`, `NEEDS_EVIDENCE`, `REWRITE`, and `REMOVE` separately from evidence status. Do not add these audit columns to routine compact imports.

## Suggested Output Columns

For a review workbook, adapt to the user's requested columns. Without a template, use only the entry fields needed: seller SKU, applicable variant names/options, title and description in the selected output language(s), category, brand, inventory, required product identifier, regular price in the target currency, packaged weight, labeled height/width/length and units, and warranty fields when requested. Mark missing values in a compact notes column. Do not invent or add campaign, SEO, or audit columns by default.

The expanded schema below is an optional Mexico review/analysis example. Select requested, applicable columns; adapt language/currency suffixes for other markets. For imports, use only the actual template's schema:

`source_platform`, `source_url`, `source_product_id`, `source_title`, `source_variant`, `source_current_price_mxn`, `source_original_price_mxn`, `source_observed_date`, `product_id`, `parent_sku`, `seller_sku`, `inventory`, `target_market`, `title_es_mx`, `title_zh_cn`, `category_es_mx`, `category_zh_cn`, `category_id`, `category_verification_status`, `brand`, `brand_evidence_status`, `selling_point_1_es_mx` through `selling_point_5_es_mx`, `selling_point_1_zh_cn` through `selling_point_5_zh_cn`, `description_es_mx`, `description_zh_cn`, `search_keywords_es_mx`, `normalized_attributes_es_mx`, `normalized_attributes_zh_cn`, `variant_1_name_es_mx`, `variant_1_name_zh_cn`, `variant_1_option_es_mx`, `variant_1_option_zh_cn`, `variant_2_name_es_mx`, `variant_2_name_zh_cn`, `variant_2_option_es_mx`, `variant_2_option_zh_cn`, `package_weight`, `package_weight_unit`, `package_length`, `package_width`, `package_height`, `package_dimension_unit`, `package_data_evidence_status`, `regular_price_mxn`, `promotion_type`, `campaign_eligibility_status`, `promotion_stackable_status`, `promotion_funding_source`, `promotion_threshold_mxn`, `promotion_discount_mxn`, `qualifying_basket_mxn`, `campaign_buyer_payment_mxn`, `compliance_action`, `missing_information_es_mx`, `missing_information_zh_cn`, `compliance_flags_es_mx`, `compliance_flags_zh_cn`, `review_status`

Add further numbered variant-name and option columns only when the current platform template and source data support more dimensions. Keep unit conversions traceable in the review/source data without adding unsupported columns to an import template.

Use ISO `YYYY-MM-DD` for `source_observed_date`. Preserve both the source current price and crossed-out/original price without treating the latter as the actual selling price. Category fields must match the actual import template's language and accepted values; translated Chinese or Spanish paths are only suggestions until verified. Never copy another marketplace's category ID into TikTok's category field.

Use these controlled values where applicable:

- `category_verification_status`: `VERIFIED` or `TO_CONFIRM`.
- `campaign_eligibility_status`: `ELIGIBLE`, `NOT_ELIGIBLE`, or `TO_CONFIRM`.
- `promotion_stackable_status`: `STACKABLE`, `NOT_STACKABLE`, or `TO_CONFIRM`.
- `promotion_funding_source`: `SELLER`, `PLATFORM`, `SHARED`, or `TO_CONFIRM`.
- Unknown numeric values remain blank, never zero. Explain them in the review notes using the selected language(s); for platform imports, follow the readiness rules above.

For review/audit outputs, use `review_status` values:

- `READY` — review content is complete based on provided facts; this is not an import-readiness or platform-approval claim.
- `REVIEW` — non-critical facts, category, or policy details need confirmation.
- `BLOCKED` — critical product, compliance, or variant information is missing or risky.

## Batch Summary

For routine batches, identify the artifact as review or import, report total products/rows and only material blockers. If import data excludes blocked records, account for every excluded record in a separate review output. For requested audit exports, also report counts by review status, common missing fields, and repeated compliance risks. Do not claim that `READY` means approved by TikTok Shop.
