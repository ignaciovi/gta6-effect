"""PRs and issues opened on GitHub per hour (global developer activity).

Re-queries the last 3 full hours each run because the search index lags.
"""
import time

from common import session, env, hour_floor_ms, iso

HOURS = 3


def count(kind, start_s, end_s, headers):
    q = f"type:{kind} created:{iso(start_s)}..{iso(end_s - 1)}"
    for _ in range(4):
        r = session.get("https://api.github.com/search/issues",
                        params={"q": q, "per_page": 1}, headers=headers, timeout=30)
        if r.status_code not in (403, 429):
            break
        # rate limited: wait for the window to reset (Retry-After or X-RateLimit-Reset)
        wait = int(r.headers.get("Retry-After") or
                   max(5, int(r.headers.get("X-RateLimit-Reset", time.time() + 60)) - time.time()))
        time.sleep(min(wait + 2, 90))
    r.raise_for_status()
    return r.json()["total_count"]


def fetch(hours=HOURS, end_s=None):
    headers = {"Accept": "application/vnd.github+json"}
    if env("GITHUB_TOKEN"):
        headers["Authorization"] = f"Bearer {env('GITHUB_TOKEN')}"
    end_s = end_s or int(time.time() // 3600 * 3600)
    series = {"prs_per_hour": [], "issues_per_hour": []}
    for h in range(hours, 0, -1):
        start = end_s - h * 3600
        ts = hour_floor_ms(start)
        series["prs_per_hour"].append([ts, count("pr", start, start + 3600, headers)])
        series["issues_per_hour"].append([ts, count("issue", start, start + 3600, headers)])
        if not env("GITHUB_TOKEN"):
            time.sleep(6.5)  # unauthenticated search limit: 10/min
    return {"mode": "merge", "series": series}
