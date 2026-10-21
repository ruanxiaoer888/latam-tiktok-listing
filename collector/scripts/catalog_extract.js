// 美客多「目录产品页」提取（读当前已打开页面，不做 fetch）
// 用途：原 item 已下架时，ML 会把链接重定向到同一商品的目录产品页
//       （URL 形如 .../xxx/up/MLMUxxxx，页面提示「Este producto no está disponible」）。
//       这种页面用 fetch 拿不稳，必须 goto 到该 URL 后读 DOM 里的 __NORDIC_RENDERING_CTX__。
// 由 scripts/ml_catalog.py 调用（goto → 执行本脚本）。
(() => {
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
        const attrs = (g.attributes || []).map(function (a) {
          return { name: a.id || a.name || "", value: (a.text !== undefined ? a.text : a.value) };
        });
        out.push({ group: g.title || "", attributes: attrs });
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

  try {
    const url = location.href;
    const html = document.documentElement.outerHTML;
    const root = parseNordic(html);
    if (!root || root.__parseError) {
      return "B64:" + btoa(unescape(encodeURIComponent(JSON.stringify({
        error: (root && root.__parseError) ? ("nordic parse: " + root.__parseError) : "no nordic",
        catalog_url: url
      }))));
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

    const groups = []; const kvs = [];
    for (const node of [comp.highlighted_specs_attrs, comp.highlighted_specs_attrs_swap]) {
      if (!node) continue;
      const g0 = []; const k0 = [];
      collectSpecs(node, g0); collectKV(node, k0);
      for (const g of g0) groups.push(g);
      for (const k of k0) kvs.push(k);
    }
    const seenG = {};
    const specGroups = groups.filter(function (g) { if (seenG[g.group]) return false; seenG[g.group] = 1; return true; });
    const seenKV = {};
    const hkv = kvs.filter(function (k) {
      const t = k.key + "\u0000" + k.value;
      if (seenKV[t]) return false; seenKV[t] = 1; return true;
    });
    const flat = {};
    for (const g of specGroups) for (const a of g.attributes) if (a.name && !(a.name in flat)) flat[a.name] = a.value;

    const rec = {
      data_level: "catalog",
      availability: "OutOfStock",
      catalog_url: url,
      catalog_id: is.id || null,
      canonical_url: (is.metadata && is.metadata.url_canonical) || null,
      title: (comp.header && comp.header.title) || comp.title || null,
      subtitle: (comp.header && comp.header.subtitle) || null,
      reviews: (comp.header && comp.header.reviews) || null,
      price: (comp.price && comp.price.price) ? {
        value: comp.price.price.value, currency_symbol: comp.price.price.currency_symbol,
        currency_id: comp.price.price.currency_id, original_value: comp.price.price.original_value || null
      } : null,
      price_state: (comp.price && comp.price.state) || null,
      category_id: ev.category_id || null,
      category_path: ev.category_path || null,
      breadcrumb: comp.breadcrumb || null,
      spec_groups: specGroups,
      highlighted_kv: hkv,
      attributes_raw: flat,
      description_title: comp.description ? comp.description.title : null,
      description_text: comp.description ? comp.description.content : null,
      seller_data: comp.seller_data ? JSON.stringify(comp.seller_data).slice(0, 4000) : null,
      pictures: pictures,
      pic_count: pictures.length,
      unavailable_text: (function () {
        const t = (document.body.innerText || "").replace(/\s+/g, " ");
        const m = t.match(/Este producto no est[^.]*\./i);
        return m ? m[0] : null;
      })(),
      html_len: html.length
    };
    return "B64:" + btoa(unescape(encodeURIComponent(JSON.stringify(rec))));
  } catch (e) {
    return "B64:" + btoa(unescape(encodeURIComponent(JSON.stringify({ error: String(e), catalog_url: location.href }))));
  }
})()