"""Estimate the hourly share of big Twitch channels streaming about GTA VI over
the last 7 days, reconstructed from past broadcasts (VODs).

Method
  1. Panel: channels in the top ~1,000 live streams worldwide right now.
  2. For each channel, fetch its archived broadcasts (title, start, duration).
  3. For every hour: live = panel channels with a broadcast covering that hour;
     share = live channels whose broadcast title matches GTA VI / live channels.

This is an approximation of the live "top 100" metric, not the same thing:
the panel is fixed (no historical viewer counts exist to rank channels), each
broadcast keeps a single title, and channels without saved VODs are invisible.

  python collector/twitch_backfill.py            # writes data/twitch_vod.json
"""
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import main  # noqa: E402,F401  (loads .env)
from common import env, is_gta6, iso, session  # noqa: E402
from sources.twitch import token  # noqa: E402

DAYS = 7
PANEL_PAGES = 10  # 10 x 100 live streams
OUT = Path(__file__).resolve().parent.parent / "data" / "twitch_vod.json"


def parse_duration(s):
    h, m, sec = (int(x or 0) for x in re.fullmatch(r"(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?", s).groups())
    return h * 3600 + m * 60 + sec


def get(path, headers, **params):
    for _ in range(5):
        r = session.get(f"https://api.twitch.tv/helix/{path}", params=params, headers=headers, timeout=30)
        if r.status_code == 429:  # rate limited: wait for the bucket to refill
            time.sleep(max(1, int(r.headers.get("Ratelimit-Reset", time.time() + 5)) - time.time()))
            continue
        r.raise_for_status()
        return r.json()
    raise RuntimeError(f"rate limited on {path}")


def main_():
    cid, secret = env("TWITCH_CLIENT_ID"), env("TWITCH_CLIENT_SECRET")
    headers = {"Client-Id": cid, "Authorization": f"Bearer {token(cid, secret)}"}

    # 1. panel
    panel, cursor = {}, None
    for _ in range(PANEL_PAGES):
        params = {"first": 100, **({"after": cursor} if cursor else {})}
        j = get("streams", headers, **params)
        for s in j["data"]:
            panel[s["user_id"]] = s["user_name"]
        cursor = j.get("pagination", {}).get("cursor")
        if not cursor:
            break
    print(f"panel: {len(panel)} channels", flush=True)

    # 2. broadcasts in the window
    now = time.time()
    start_window = now - DAYS * 86400
    spans = []  # (start_s, end_s, is_gta)
    no_vods = 0
    for i, uid in enumerate(panel):
        j = get("videos", headers, user_id=uid, type="archive", first=100)
        vids = j["data"]
        if not vids:
            no_vods += 1
        for v in vids:
            st = datetime.fromisoformat(v["created_at"].replace("Z", "+00:00")).timestamp()
            en = st + parse_duration(v["duration"])
            if en >= start_window:
                spans.append((st, en, is_gta6(v["title"])))
        if i % 100 == 99:
            print(f"  {i + 1}/{len(panel)} channels", flush=True)

    # 3. hourly timeline (sample at half past each hour)
    pts = []
    h = int(start_window // 3600 * 3600)
    while h + 1800 < now:
        t = h + 1800
        live = [g for st, en, g in spans if st <= t < en]
        if live:
            pts.append([h * 1000, round(100 * sum(live) / len(live), 2), len(live)])
        h += 3600

    doc = {
        "updated": iso(now),
        "series": {"panel_gta_share": [[t, v] for t, v, _ in pts],
                   "panel_live": [[t, n] for t, _, n in pts]},
        "meta": {"panel_size": len(panel), "channels_without_vods": no_vods, "broadcasts": len(spans),
                 "method": "Share of a fixed panel of big channels (top ~1,000 live now) whose past broadcast "
                           "titles mention GTA VI, hour by hour. Estimate, not the live top-100 metric."},
    }
    OUT.write_text(json.dumps(doc, separators=(",", ":")))
    print(f"wrote {len(pts)} hourly points; {len(spans)} broadcasts; {no_vods} channels without VODs")


if __name__ == "__main__":
    main_()
