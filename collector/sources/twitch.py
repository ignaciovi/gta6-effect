"""Share of the top 100 live Twitch streams (by viewers) that are GTA 6 related.
Computed globally and for English-language streams (US proxy)."""
from common import session, env, now_ms, is_gta6, Skip


def token(cid, secret):
    r = session.post("https://id.twitch.tv/oauth2/token", params={
        "client_id": cid, "client_secret": secret, "grant_type": "client_credentials"}, timeout=30)
    r.raise_for_status()
    return r.json()["access_token"]


def share(headers, **params):
    r = session.get("https://api.twitch.tv/helix/streams",
                    params={"first": 100, **params}, headers=headers, timeout=30)
    r.raise_for_status()
    streams = r.json()["data"]
    hits = [s for s in streams if is_gta6(s.get("game_name"), s.get("title"))]
    playing = [s for s in streams if is_gta6(s.get("game_name"))]
    total_v = sum(s["viewer_count"] for s in streams) or 1
    hit_v = sum(s["viewer_count"] for s in hits)
    top = [{"user": s["user_name"], "viewers": s["viewer_count"], "title": s["title"][:90],
            "playing": s in playing} for s in hits[:5]]
    play_share = 100 * len(playing) / max(len(streams), 1)
    return 100 * len(hits) / max(len(streams), 1), 100 * hit_v / total_v, top, play_share


def fetch():
    cid, secret = env("TWITCH_CLIENT_ID"), env("TWITCH_CLIENT_SECRET")
    if not (cid and secret):
        raise Skip("TWITCH_CLIENT_ID / TWITCH_CLIENT_SECRET not set")
    headers = {"Client-Id": cid, "Authorization": f"Bearer {token(cid, secret)}"}
    ts = now_ms()
    g_s, g_v, g_top, g_p = share(headers)
    e_s, e_v, e_top, e_p = share(headers, language="en")
    return {"mode": "merge", "series": {
        "global_stream_share": [[ts, round(g_s, 1)]],
        "global_viewer_share": [[ts, round(g_v, 2)]],
        "en_stream_share": [[ts, round(e_s, 1)]],
        "en_viewer_share": [[ts, round(e_v, 2)]],
        "global_playing_share": [[ts, round(g_p, 1)]],
        "en_playing_share": [[ts, round(e_p, 1)]],
    }, "meta": {"top_gta6_streams_en": e_top, "top_gta6_streams_global": g_top}}
