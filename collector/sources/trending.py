"""Google's official 'Trending Now' RSS feeds for 10 countries: how many of the
~100 trending slots worldwide are searches about GTA 6."""
import re
import xml.etree.ElementTree as ET

from common import session, now_ms, is_gta6
from config import TRENDING_GEOS

FEED = "https://trends.google.com/trending/rss"
HT = "{https://trends.google.com/trending/rss}"


def _traffic(s):
    m = re.sub(r"[^\d]", "", s or "")
    return int(m) if m else 0


def fetch():
    per_geo, gta_items, slots, total_traffic, gta_traffic = {}, [], 0, 0, 0
    for geo in TRENDING_GEOS:
        try:
            r = session.get(FEED, params={"geo": geo}, timeout=30)
            r.raise_for_status()
        except Exception:
            continue
        items = [(it.findtext("title") or "", _traffic(it.findtext(f"{HT}approx_traffic")))
                 for it in ET.fromstring(r.content).iter("item")]
        # Only the search term itself counts; attached news often mentions GTA 6 in passing.
        hits = [(t, v) for t, v in items if is_gta6(t)]
        per_geo[geo] = {"hits": len(hits), "items": len(items), "top": items[0][0] if items else None}
        gta_items += [{"geo": geo, "title": t, "traffic": v} for t, v in hits]
        slots += len(items)
        total_traffic += sum(v for _, v in items)
        gta_traffic += sum(v for _, v in hits)
    if not slots:
        raise RuntimeError("no trending feeds returned")
    ts = now_ms()
    return {"mode": "merge", "series": {
        "world_gta6_items": [[ts, len(gta_items)]],
        "world_slot_share": [[ts, round(100 * len(gta_items) / slots, 1)]],
        "world_traffic_share": [[ts, round(100 * gta_traffic / max(total_traffic, 1), 1)]],
    }, "meta": {"per_geo": per_geo, "gta6_items": sorted(gta_items, key=lambda i: -i["traffic"]),
                "slots": slots, "geos": TRENDING_GEOS}}
