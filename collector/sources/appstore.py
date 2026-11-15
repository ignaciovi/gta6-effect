"""US App Store top-free rank for food delivery / gaming / work apps.
Value is the rank (1-100) or None when outside the top 100."""
from common import session, now_ms
from config import APPSTORE_APPS

FEED = "https://rss.marketingtools.apple.com/api/v2/us/apps/top-free/100/apps.json"


def fetch():
    r = session.get(FEED, timeout=30)
    r.raise_for_status()
    names = [a["name"] for a in r.json()["feed"]["results"]]
    ts = now_ms()
    series = {}
    for key, prefix in APPSTORE_APPS.items():
        rank = next((i + 1 for i, n in enumerate(names) if n.lower().startswith(prefix.lower())), None)
        series[key] = [[ts, rank]]
    return {"mode": "merge", "series": series, "meta": {"apps": APPSTORE_APPS}}
