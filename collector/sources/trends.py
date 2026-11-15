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
from config import HISTORY_START_S, TRENDS_BATCHES

BASE = "https://trends.google.com"
DATA_FILE = Path(__file__).resolve().parents[2] / "data" / "trends.json"
MIN_INTERVAL_S = 55 * 60
DAILY_INTERVAL_S = 6 * 3600  # earlier hourly windows since HISTORY_START: refresh every 6h


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


def _overlap_ratio(newer, older, terms):
    """Scale factor mapping `older` onto `newer`, from the batch totals on shared hours."""
    nt = {ts: sum(v for t in terms for tt, v in newer[t] if tt == ts) for ts, _ in newer[terms[0]]}
    num = den = 0
    for ts, _ in older[terms[0]]:
        if ts in nt:
            num += nt[ts]
            den += sum(v for t in terms for tt, v in older[t] if tt == ts)
    return num / den if den else None


def fetch():
    try:
        daily_updated = json.loads(DATA_FILE.read_text()).get("meta", {}).get("early_updated", 0)
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
    # Hourly history before the current week: Google serves hourly data for any
    # 7-day window, but scales each window separately. Fetch windows back to
    # HISTORY_START, each overlapping the next by a day, and rescale them onto
    # the current week. The overlap day is kept so the site can re-match the
    # scale against each newer hourly fetch.
    if time.time() - daily_updated > DAILY_INTERVAL_S:
        for batch, terms in TRENDS_BATCHES.items():
            newer = {t: series[f"{batch}:{t}"] for t in terms}
            early = {t: [] for t in terms}
            start = min(newer[terms[0]])[0] // 1000
            while start > HISTORY_START_S:
                end = start + 86400
                begin = max(HISTORY_START_S, end - 7 * 86400)
                tf = f"{time.strftime('%Y-%m-%dT%H', time.gmtime(begin))} {time.strftime('%Y-%m-%dT%H', time.gmtime(end))}"
                time.sleep(5)
                win = _series(terms, timeframe=tf)
                ratio = _overlap_ratio(newer, win, terms)
                if ratio is None:
                    break
                scaled = {t: [[ts, v * ratio] for ts, v in win[t]] for t in terms}
                for t in terms:
                    # keep the overlap day only for the newest window (site re-matches on it)
                    cut = None if not early[t] else min(early[t])[0]
                    early[t] = [p for p in scaled[t] if cut is None or p[0] < cut] + early[t]
                newer, start = scaled, begin
            for t in terms:
                series[f"{batch}:{t}:early"] = [[ts, round(v, 2)] for ts, v in early[t]]
        meta["early_updated"] = int(time.time())
    return {"mode": "replace", "series": series, "meta": meta}
