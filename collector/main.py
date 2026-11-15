"""Run every source and merge results into data/<source>.json.

Each source module exposes fetch() -> {"series": {key: [[ts_ms, value], ...]},
"mode": "merge" | "replace", "meta": {...}}.

  merge   - new points overwrite same-timestamp points; history is kept
  replace - the source returns its full (re-normalised) window every run
"""
import argparse
import importlib
import json
import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

# Load a local .env for development (GitHub Actions passes secrets as env vars).
_env = Path(__file__).resolve().parent.parent / ".env"
if _env.exists():
    import os
    for _line in _env.read_text().splitlines():
        if "=" in _line and not _line.lstrip().startswith("#"):
            _k, _v = _line.split("=", 1)
            if _v.strip():
                os.environ.setdefault(_k.strip(), _v.strip())

from common import Fresh, Skip, iso  # noqa: E402
from config import FULL_RES_DAYS, LAUNCH_ISO, RETENTION_DAYS  # noqa: E402

SOURCES = [
    "steam", "github", "wikiedits", "trends", "trending", "appstore",
    "twitch", "youtube", "tomtom", "radar", "stocks",
]

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def load(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def thin(points, full_res_ms):
    """Keep every point newer than full_res_ms; older ones, the first per hour."""
    out, seen = [], set()
    for t, v in points:
        if t < full_res_ms:
            h = t // 3_600_000
            if h in seen:
                continue
            seen.add(h)
        out.append([t, v])
    return out


def merge_points(old, new, cutoff_ms, full_res_ms=0):
    by_ts = {int(t): v for t, v in (old or [])}
    by_ts.update({int(t): v for t, v in new})
    return thin([[t, by_ts[t]] for t in sorted(by_ts) if t >= cutoff_ms], full_res_ms)


def write(name: str, result: dict):
    path = DATA_DIR / f"{name}.json"
    doc = load(path)
    cutoff = int((time.time() - RETENTION_DAYS * 86400) * 1000)
    full_res = int((time.time() - FULL_RES_DAYS * 86400) * 1000)
    series = doc.get("series", {})
    for key, pts in result.get("series", {}).items():
        if result.get("mode") == "replace":
            series[key] = thin([[int(t), v] for t, v in pts if int(t) >= cutoff], full_res)
        else:
            series[key] = merge_points(series.get(key), pts, cutoff, full_res)
    doc["series"] = series
    doc["meta"] = {**doc.get("meta", {}), **result.get("meta", {})}
    doc["updated"] = iso(time.time())
    path.write_text(json.dumps(doc, separators=(",", ":")))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="print, don't write")
    ap.add_argument("--only", nargs="*", help="run only these sources")
    args = ap.parse_args()

    DATA_DIR.mkdir(exist_ok=True)
    status = load(DATA_DIR / "status.json")
    names = args.only or SOURCES
    failures = 0

    for name in names:
        t0 = time.time()
        entry = status.get(name, {})
        try:
            mod = importlib.import_module(f"sources.{name}")
            result = mod.fetch()
            n = sum(len(v) for v in result.get("series", {}).values())
            if args.dry_run:
                preview = {k: v[-3:] for k, v in result["series"].items()}
                print(f"[ok]   {name}: {n} pts  {json.dumps(preview)[:600]}")
            else:
                write(name, result)
            entry.update(state="ok", last_ok=iso(time.time()), error=None)
            print(f"[ok]   {name} ({n} pts, {time.time()-t0:.1f}s)")
        except Fresh as e:
            print(f"[keep] {name}: {e}")
        except Skip as e:
            entry.update(state="skipped", error=str(e))
            print(f"[skip] {name}: {e}")
        except Exception as e:  # one source never breaks the run
            failures += 1
            entry.update(state="error", error=f"{type(e).__name__}: {e}"[:300])
            print(f"[err]  {name}: {e}")
            traceback.print_exc(limit=2)
        entry["last_run"] = iso(time.time())
        status[name] = entry

    if not args.dry_run:
        (DATA_DIR / "status.json").write_text(json.dumps(status, indent=1))
        (DATA_DIR / "meta.json").write_text(json.dumps(
            {"launch": LAUNCH_ISO, "generated": iso(time.time())}))
    print(f"done: {len(names)} sources, {failures} errors")


if __name__ == "__main__":
    main()
