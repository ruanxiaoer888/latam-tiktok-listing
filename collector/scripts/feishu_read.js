// 飞书多维表格「商品链接」清单读取（页面内执行，复用浏览器登录态）
// 由 scripts/read_sheet.py 调用；也可人工核验时单独粘进控制台。
// 可覆盖参数：执行前设 window.__FEISHU = {appToken, table, view, recordLimit}
(async () => {
  const CFG = window.__FEISHU || {};
  const APP = CFG.appToken || "Nqxob1DmsalyjHs2E8YcSqaxnTe";
  const TBL = CFG.table || "tbl4wXgSNkfMYD1f";
  const VIEW = CFG.view || "vewkZbJc3v";
  const LIMIT = CFG.recordLimit || 500;

  const API = "/space/api/v1/bitable/" + APP + "/clientvars?tableID=" + TBL +
    "&viewID=" + VIEW + "&recordLimit=" + LIMIT +
    "&needBase=true&viewLazyLoad=true&ondemandVer=2&openType=0";

  const toText = v => {
    if (v === null || v === undefined) return "";
    if (typeof v === "string") return v;
    if (Array.isArray(v)) return v.map(toText).join(" | ");
    if (typeof v === "object") {
      if (v.text !== undefined) return String(v.text);
      if (v.name !== undefined) return String(v.name);
      if (v.value !== undefined) return toText(v.value);
      if (v.link !== undefined) return toText(v.link);
      return JSON.stringify(v).slice(0, 300);
    }
    return String(v);
  };

  try {
    const r = await fetch(API, { credentials: "include" });
    const j = await r.json();
    if (!j || !j.data || !j.data.table) {
      return "ERR:no_table " + JSON.stringify(j).slice(0, 400) +
        " （大概率是当前页面未登录飞书，或 table/view id 过期）";
    }
    // data.table 是 base64 的 gzip 数据块
    const bin = Uint8Array.from(atob(j.data.table), c => c.charCodeAt(0));
    const text = await new Response(
      new Blob([bin]).stream().pipeThrough(new DecompressionStream("gzip"))
    ).text();
    const t = JSON.parse(text);

    const fm = t.fieldMap || {};
    const id2name = {};
    for (const id of Object.keys(fm)) id2name[id] = fm[id].name;
    const findId = nm => Object.keys(fm).find(id => fm[id].name === nm);

    const F = {
      sku: findId("Tiktok商品SKU"),
      link: findId("商品链接"),
      mlTitle: findId("美客多标题"),
      itemId: findId("Item ID"),
      price: findId("美客多零售价"),
      note: findId("备注信息"),
    };
    const missingFields = Object.keys(F).filter(k => !F[k]);

    const rm = t.recordMap || {};
    const rows = [];
    for (const rid of Object.keys(rm)) {
      const c = rm[rid] || {};
      const g = fid => (fid && c[fid]) ? toText(c[fid].value).trim() : "";
      const sku = g(F.sku);
      rows.push({
        rid: rid,
        sku: sku,
        link: g(F.link),
        ml_title: g(F.mlTitle).slice(0, 120),
        item_id: g(F.itemId),
        price: g(F.price),
        note: g(F.note).slice(0, 60),
      });
    }
    rows.sort((a, b) => (a.sku < b.sku ? -1 : a.sku > b.sku ? 1 : 0));

    const out = JSON.stringify({
      app_token: APP, table: TBL, view: VIEW,
      fieldMap: id2name,
      missing_fields: missingFields,
      recordCount: rows.length,
      with_link: rows.filter(r => r.link).length,
      rows: rows,
    });
    window.__SHEET = rows;
    return "B64:" + btoa(unescape(encodeURIComponent(out)));
  } catch (e) {
    return "ERR:" + (e && e.message ? e.message : String(e));
  }
})()