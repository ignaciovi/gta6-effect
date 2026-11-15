"""US freeway congestion: 1 - currentSpeed/freeFlowSpeed (in %) averaged per metro."""
from common import session, env, now_ms, Skip
from config import METROS

API = "https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/6/json"  # zoom 6 snaps to freeways/major highways


def fetch():
    key = env("TOMTOM_API_KEY")
    if not key:
        raise Skip("TOMTOM_API_KEY not set")
    ts = now_ms()
    series, all_vals, errors = {}, [], 0
    for mkey, (_, points) in METROS.items():
        vals = []
        for lat, lon in points:
            try:
                r = session.get(API, params={"point": f"{lat},{lon}", "unit": "MPH", "key": key}, timeout=20)
                r.raise_for_status()
                f = r.json()["flowSegmentData"]
                if f.get("roadClosure") or not f.get("freeFlowSpeed") or f.get("frc") not in ("FRC0", "FRC1"):
                    continue
                vals.append(max(0.0, 1 - f["currentSpeed"] / f["freeFlowSpeed"]) * 100)
            except Exception:
                errors += 1
        if vals:
            v = round(sum(vals) / len(vals), 1)
            series[mkey] = [[ts, v]]
            all_vals.append(v)
    if not all_vals:
        raise RuntimeError(f"no TomTom data ({errors} errors)")
    series["us_avg"] = [[ts, round(sum(all_vals) / len(all_vals), 1)]]
    return {"mode": "merge", "series": series,
            "meta": {"metros": {k: v[0] for k, v in METROS.items()}}}
