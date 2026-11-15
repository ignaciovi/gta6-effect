"""Human (non-bot) edits per hour on English Wikipedia."""
import time

from common import session, hour_floor_ms, iso

API = "https://en.wikipedia.org/w/api.php"


def count_hour(start_s):
    p = dict(action="query", list="recentchanges", rctype="edit|new", rcshow="!bot",
             rcprop="timestamp", rclimit="max", format="json",
             rcstart=iso(start_s + 3599), rcend=iso(start_s), maxlag=5)
    n = 0
    while True:
        r = session.get(API, params=p, timeout=30)
        r.raise_for_status()
        j = r.json()
        n += len(j["query"]["recentchanges"])
        if "continue" not in j:
            return n
        p.update(j["continue"])
        time.sleep(1)


def fetch(hours=2, end_s=None):
    end_s = end_s or int(time.time() // 3600 * 3600)
    pts = []
    for h in range(hours, 0, -1):
        start = end_s - h * 3600
        pts.append([hour_floor_ms(start), count_hour(start)])
    return {"mode": "merge", "series": {"human_edits_per_hour": pts}}
