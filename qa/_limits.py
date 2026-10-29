# -*- coding: utf-8 -*-
r"""平台限制的唯一读取入口。

数据源：`qa/denylist.json` 的 `sites.<SITE>.title / description`（已经是平台口径的单一源）。
本模块只负责「按站点 + 类目」取区间，避免各脚本各自写死 60–80 / 80–120。

用法：
  from _limits import title_range, title_ok, site_title, site_desc, AUTOPARTS_CATS
  lo, hi = title_range("MX", "汽车摩托")   # -> (80, 120)
  title_ok("MX", "Gato ...", "汽车摩托")    # -> True/False
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DENY = ROOT / "qa" / "denylist.json"

# 标题建议区间更宽的类目（汽配要放适配车型/年款/位置，骨架规定 80–120）
AUTOPARTS_CATS = {"汽车摩托", "autoparts", "automotriz"}

_cache = {}


def rules():
    if "rules" not in _cache:
        _cache["rules"] = json.loads(DENY.read_text(encoding="utf-8"))
    return _cache["rules"]


def site_cfg(site):
    sites = rules()["sites"]
    if site not in sites:
        raise KeyError(f"站点 {site} 不在 denylist.json；可用：{', '.join(sites)}")
    return sites[site]


def site_title(site):
    return site_cfg(site)["title"]


def site_desc(site):
    return site_cfg(site)["description"]


def title_range(site, category=""):
    """返回建议区间 (lo, hi)：汽配用 autoparts，其余用 recommended。"""
    t = site_title(site)
    if category in AUTOPARTS_CATS and t.get("autoparts"):
        return tuple(t["autoparts"])
    return tuple(t["recommended"])


def title_ok(site, title, category=""):
    lo, hi = title_range(site, category)
    return lo <= len(title) <= hi
