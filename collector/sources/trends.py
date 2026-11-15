"""US Google Trends, hourly over the last 7 days.

Talks to the same two endpoints the Trends website uses (explore -> token,
widgetdata/multiline -> series) instead of the unmaintained pytrends package.
Google re-normalises the series on every request, so the whole window is
replaced each run. The data is hourly, so we only fetch once an hour; on
failure the last good file is left untouched.
"""
import json
import time
from pathlib import Path

from common import session, Fresh
from config import HISTORY_START_ISO, TRENDS_BATCHES

BASE = "https://trends.google.com"
DATA_FILE = Path(__file__).resolve().parents[2] / "data" / "trends.json"
MIN_INTERVAL_S = 55 * 60
DAILY_INTERVAL_S = 6 * 3600  # daily series since HISTORY_START: refresh every 6h


def _json(text):
    # responses are prefixed with ")]}'" (and sometimes a comma) to block JSON hijacking
    return json.loads(text[text.index("{"):])


def _series(terms, geo="US", timeframe="now 7-d"):
    req = {"comparisonItem": [{"keyword": t, "geo": geo, "time": timeframe} for t in terms],
           "category": 0, "property": ""}
    r = session.get(f"{BASE}/trends/api/explore",
                    params={"hl": "en-US", "tz": 0, "req": json.dumps(req)}, timeout=30)
    r.raise_for_status()
    widget = next(w for w in _json(r.text)["widgets"] if w["id"] == "TIMESERIES")
    r = session.get(f"{BASE}/trends/api/widgetdata/multiline",
                    params={"hl": "en-US", "tz": 0, "req": json.dumps(widget["request"]),
                            "token": widget["token"]}, timeout=30)
    r.raise_for_status()
    rows = [row for row in _json(r.text)["default"]["timelineData"] if not row.get("isPartial")]
    if not rows:
        raise RuntimeError(f"empty timeline for {terms}")
    return {t: [[int(row["time"]) * 1000, int(row["value"][i])] for row in rows]
            for i, t in enumerate(terms)}


def fetch():
    try:
        daily_updated = json.loads(DATA_FILE.read_text()).get("meta", {}).get("daily_updated", 0)
    except (FileNotFoundError, ValueError):
        daily_updated = 0
    try:
        updated = json.loads(DATA_FILE.read_text()).get("updated")
        if updated and time.time() - time.mktime(time.strptime(updated, "%Y-%m-%dT%H:%M:%SZ")) + time.timezone < MIN_INTERVAL_S:
            raise Fresh("fetched within the last hour")
    except (FileNotFoundError, ValueError):
        pass
    session.get(f"{BASE}/?geo=US", timeout=30)  # sets the NID cookie the API expects
    series = {}
    for i, (batch, terms) in enumerate(TRENDS_BATCHES.items()):
        if i:
            time.sleep(5)
        for term, pts in _series(terms).items():
            series[f"{batch}:{term}"] = pts
    meta = {"batches": TRENDS_BATCHES}
    # Longer windows only come back at daily resolution (separately normalised by Google).
    if time.time() - daily_updated > DAILY_INTERVAL_S:
        window = f"{HISTORY_START_ISO[:10]} {time.strftime('%Y-%m-%d', time.gmtime())}"
        for batch, terms in TRENDS_BATCHES.items():
            time.sleep(5)
            for term, pts in _series(terms, timeframe=window).items():
                series[f"{batch}:{term}:daily"] = pts
        meta["daily_updated"] = int(time.time())
    return {"mode": "replace", "series": series, "meta": meta}
