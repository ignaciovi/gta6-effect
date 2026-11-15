"""Steam concurrent users (Valve's public 48h chart) + GTA V players."""
from common import session, now_ms
from config import GTAV_STEAM_APPID, HISTORY_START_S


def fetch():
    series = {}
    r = session.get("https://store.steampowered.com/stats/userdata.json", timeout=30)
    r.raise_for_status()
    for s in r.json():
        label = s["label"].lower()
        key = "logged_in" if "logged" in label else ("in_game" if "game" in label else label.replace(" ", "_"))
        series[key] = [[int(t), int(v)] for t, v in s["data"]]

    r = session.get(
        "https://api.steampowered.com/ISteamUserStats/GetNumberOfCurrentPlayers/v1/",
        params={"appid": GTAV_STEAM_APPID}, timeout=30)
    r.raise_for_status()
    series["gtav_players"] = [[now_ms(), r.json()["response"]["player_count"]]]

    # Hourly GTA V history from SteamCharts (third party), so the chart has a
    # baseline from day one. Optional: Valve's live count above still works without it.
    try:
        r = session.get(f"https://steamcharts.com/app/{GTAV_STEAM_APPID}/chart-data.json",
                        headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
        r.raise_for_status()
        cutoff = HISTORY_START_S * 1000
        series["gtav_players"] = [[int(t), int(v)] for t, v in r.json() if t >= cutoff] + series["gtav_players"]
    except Exception:
        pass
    return {"mode": "merge", "series": series}
