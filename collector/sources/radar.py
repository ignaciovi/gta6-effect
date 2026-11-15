"""US internet traffic (Cloudflare Radar netflows), hourly, last 14 days.
Normalised by Cloudflare per request, so the window is replaced every run."""
from datetime import datetime

from common import session, env, Skip


def fetch():
    tok = env("CLOUDFLARE_RADAR_TOKEN")
    if not tok:
        raise Skip("CLOUDFLARE_RADAR_TOKEN not set")
    r = session.get("https://api.cloudflare.com/client/v4/radar/netflows/timeseries",
                    params={"location": "US", "dateRange": "14d", "aggInterval": "1h",
                            "normalization": "MIN0_MAX", "format": "json"},
                    headers={"Authorization": f"Bearer {tok}"}, timeout=30)
    r.raise_for_status()
    s = r.json()["result"]["serie_0"]
    pts = [[int(datetime.fromisoformat(t.replace("Z", "+00:00")).timestamp() * 1000), float(v)]
           for t, v in zip(s["timestamps"], s["values"])]
    return {"mode": "replace", "series": {"us_netflows": pts}}
