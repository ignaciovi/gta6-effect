"""Worldwide share of most-popular YouTube videos that are GTA 6 related
(matched by title), averaged over 10 big markets, overall and in Gaming."""
from common import session, env, now_ms, is_gta6, Skip
from config import YOUTUBE_REGIONS

API = "https://www.googleapis.com/youtube/v3/videos"


def chart(key, n, region, **extra):
    items, token = [], None
    while len(items) < n:
        p = {"part": "snippet", "chart": "mostPopular", "regionCode": region,
             "maxResults": 50, "key": key, **extra}
        if token:
            p["pageToken"] = token
        r = session.get(API, params=p, timeout=30)
        r.raise_for_status()
        j = r.json()
        items += j.get("items", [])
        token = j.get("nextPageToken")
        if not token:
            break
    return items[:n]


def hits(items):
    # Title only: descriptions and tags are often keyword-stuffed (false positives).
    return [v for v in items if is_gta6(v["snippet"]["title"])]


def fetch():
    key = env("YOUTUBE_API_KEY")
    if not key:
        raise Skip("YOUTUBE_API_KEY not set")
    ts = now_ms()
    per_region, gaming_shares, videos = {}, [], {}
    for region in YOUTUBE_REGIONS:
        items = chart(key, 100, region)
        if not items:
            continue
        h = hits(items)
        per_region[region] = round(100 * len(h) / len(items), 1)
        for v in h:
            e = videos.setdefault(v["id"], {"title": v["snippet"]["title"][:90],
                                            "channel": v["snippet"]["channelTitle"], "regions": []})
            e["regions"].append(region)
        try:  # the Gaming chart isn't available in every region
            g = chart(key, 100, region, videoCategoryId="20")
            if g:
                gaming_shares.append(100 * len(hits(g)) / len(g))
        except Exception:
            pass
    if not per_region:
        raise RuntimeError("no YouTube charts returned")
    world = round(sum(per_region.values()) / len(per_region), 1)
    top = sorted(videos.values(), key=lambda v: -len(v["regions"]))[:6]
    series = {"world_top100_share": [[ts, world]]}
    if gaming_shares:
        series["world_gaming_share"] = [[ts, round(sum(gaming_shares) / len(gaming_shares), 1)]]
    return {"mode": "merge", "series": series,
            "meta": {"per_region": per_region, "top_gta6_videos": top, "regions": YOUTUBE_REGIONS}}
