// 美客多商品页批量抓取（页面内执行，同源 fetch + credentials:include）
// 必须在 mercadolibre.com.mx 页面上下文里执行（否则跨域被 CORS 拦）。
// 前置：执行前先设 window.__URLS = [{sku, url}, ...]（单批 <= 24 个）
// 由 scripts/ml_batch.py 调用；也可人工核验时单独使用。
(async () => {
  const ITEMS = window.__URLS || [];
  if (!ITEMS.length) return "ERR:no_urls 先设置 window.__URLS = [{sku, url}, ...]";

  function parseNordic(html) {
    const key = "__NORDIC_RENDERING_CTX__";
    const i = html.indexOf(key);
    if (i < 0) return null;
    const gt = html.indexOf(">", i);
    if (gt < 0) return null;
    let start = html.indexOf("=", gt);
    if (start < 0) return null;
    start += 1;
    let depth = 0, inStr = false, esc = false, end = -1;
    for (let p = start; p < html.length; p++) {
      const c = html[p];
      if (inStr) { if (esc) esc = false; else if (c === "\\") esc = true; else if (c === '"') inStr = false; }
      else { if (c === '"') inStr = true; else if (c === "{") depth++; else if (c === "}") { depth--; if (depth === 0) { end = p + 1; break; } } }
    }
    if (end < 0) return null;
    try { return JSON.parse(html.slice(start, end)); } catch (e) { return { __parseError: String(e) }; }
  }

  function collectSpecs(node, out) {
    if (!node || typeof node !== "object") return;
    if (Array.isArray(node)) { node.forEach(function (n) { collectSpecs(n, out); }); return; }
    if (node.type === "technical_specifications" && Array.isArray(node.specs)) {
      for (const g of node.specs) {
        const title = g.title || "";
        const attrs = (g.attributes || []).map(function (a) {
          return { name: a.id || a.name || "", value: (a.text !== undefined ? a.text : a.value) };
        });
        out.push({ group: title, attributes: attrs });
      }
    }
    for (const k in node) { const v = node[k]; if (v && typeof v === "object") collectSpecs(v, out); }
  }

  function collectKV(node, out) {
    if (!node || typeof node !== "object") return;
    if (Array.isArray(node)) { node.forEach(function (n) { collectKV(n, out); }); return; }
    if (node.type === "key_value" && node.title && node.title.values) {
      const vals = node.title.values;
      const kk = vals.key && vals.key.text;
      const vv = vals.value && vals.value.text;
      if (kk && vv) out.push({ key: kk.replace(/:\s*$/, ""), value: vv });
    }
    for (const k in node) { const v = node[k]; if (v && typeof v === "object") collectKV(v, out); }
  }

  const results = [];
  for (const it of ITEMS) {
    const rec = { sku: it.sku, url: it.url };
    try {
      const r = await fetch(it.url, { credentials: "include" });
      rec.http_status = r.status;
      rec.resolved_url = r.url;
      const html = await r.text();
      rec.html_len = html.length;

      // 风控/失效的早期信号（不要在这里重试，交给 build_input 判性质）
      if (/account-verification|\/gz\/|captcha/i.test(rec.resolved_url)) { rec.blocked = "wall"; results.push(rec); continue; }
      if (r.status === 404) { rec.blocked = "404"; results.push(rec); continue; }
      if (/\/listado|#redirectedFromVip/i.test(rec.resolved_url)) { rec.blocked = "delisted"; results.push(rec); continue; }

      const root = parseNordic(html);
      if (!root || root.__parseError) {
        rec.error = "nordic parse: " + ((root && root.__parseError) || "missing");
        rec.blocked = "wall";
        results.push(rec); continue;
      }
      const is = root.appProps.pageProps.initialState || {};
      const comp = is.components || {};
      const gal = comp.gallery || {};
      const pc = gal.picture_config || {};
      const fill = function (tpl, pic) {
        return tpl ? tpl.replace("{id}", pic.id).replace("{sanitizedTitle}", pic.sanitized_title || "") : null;
      };
      const varOf = function (w) {
        const v = (pc.template_variants || []).find(function (x) { return x.width === String(w); });
        return v ? v.template : null;
      };
      const pictures = (gal.pictures || []).map(function (p, idx) {
        return {
          index: idx + 1, id: p.id, alt: p.alt || null, width: p.width, height: p.height,
          url_original: fill(pc.template_zoom, p),
          url_w800: fill(varOf(800), p),
          url_w1200: fill(varOf(1200), p),
          url_thumb: fill(pc.template_thumbnail, p)
        };
      });
      const ev = (is.track && is.track.melidata_event && is.track.melidata_event.event_data) || {};
      const bc = comp.breadcrumb || is.breadcrumb || null;

      rec.item_id = is.id || null;
      rec.canonical_url = (is.metadata && is.metadata.url_canonical) || null;
      rec.title = (comp.header && comp.header.title) || comp.title || null;
      rec.subtitle = (comp.header && comp.header.subtitle) || null;
      rec.reviews = (comp.header && comp.header.reviews) || null;
      rec.price = comp.price && comp.price.price ? {
        value: comp.price.price.value, currency_symbol: comp.price.price.currency_symbol,
        currency_id: comp.price.price.currency_id, original_value: comp.price.price.original_value || null
      } : null;
      rec.price_state = (comp.price && comp.price.state) || null;
      rec.category_id = ev.category_id || null;
      rec.category_path = ev.category_path || null;
      rec.item_status = ev.item_status || null;
      rec.item_condition = ev.item_condition || null;
      rec.listing_type_id = ev.listing_type_id || null;
      rec.seller_id = ev.seller_id || null;
      rec.status_message = comp.item_status_message
        ? ((comp.item_status_message.body && comp.item_status_message.body.text) || null) : null;

      const groups = [];
      const kvs = [];
      const chosen = [];
      for (const node of [comp.highlighted_specs_attrs, comp.highlighted_specs_attrs_swap]) {
        if (!node) continue;
        const g0 = []; const k0 = [];
        collectSpecs(node, g0); collectKV(node, k0);
        if (g0.length || k0.length) {
          chosen.push({
            which: node === comp.highlighted_specs_attrs ? "highlighted_specs_attrs" : "highlighted_specs_attrs_swap",
            groups: g0.length, kvs: k0.length
          });
        }
        for (const g of g0) groups.push(g);
        for (const k of k0) kvs.push(k);
      }
      rec.spec_source = chosen;
      const seenG = {};
      const specGroups = groups.filter(function (g) { if (seenG[g.group]) return false; seenG[g.group] = 1; return true; });
      const seenKV = {};
      const hkv = kvs.filter(function (k) {
        const t = k.key + "\u0000" + k.value;
        if (seenKV[t]) return false; seenKV[t] = 1; return true;
      });
      rec.spec_groups = specGroups;
      rec.highlighted_kv = hkv;
      const flat = {};
      for (const g of specGroups) for (const a of g.attributes) if (a.name && !(a.name in flat)) flat[a.name] = a.value;
      rec.attributes_raw = flat;
      rec.is_attributes = is.attributes || null;
      rec.variations = (comp.variations && comp.variations.length) ? comp.variations.length : ((is.variations && is.variations.length) || 0);
      rec.description_title = comp.description ? comp.description.title : null;
      rec.description_text = comp.description ? comp.description.content : null;
      rec.breadcrumb = bc;
      rec.seller_data = comp.seller_data ? JSON.stringify(comp.seller_data).slice(0, 4000) : null;
      rec.pictures = pictures;
      rec.pic_count = pictures.length;

      // item 级 = item id（MLM+数字）；catalog 级 = 目录产品 id（MLMU…）或不足价
      const idStr = String(rec.item_id || "");
      rec.data_level = (idStr === "" || idStr.indexOf("MLMU") === 0) ? "catalog" : "item";
      if (rec.data_level === "catalog") rec.availability = rec.price_state || "OutOfStock";
      if (!rec.title) rec.blocked = "empty";
    } catch (e) { rec.error = String(e); }
    results.push(rec);
  }

  window.__RESULT = results;
  return btoa(unescape(encodeURIComponent(JSON.stringify(results))));
})()