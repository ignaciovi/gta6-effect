"""One-off: backfill hourly history for sources that only collect recent hours.

  python collector/backfill.py --days 7
"""
import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from main import write  # noqa: E402
from sources import github, wikiedits  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--only", nargs="*", default=["github", "wikiedits"])
    ap.add_argument("--skip-hours", type=int, default=0, help="start this many hours back (resume)")
    args = ap.parse_args()
    now_h = int(time.time() // 3600 * 3600) - args.skip_hours * 3600
    # Work backwards in 6-hour chunks, writing as we go so partial runs are useful.
    for name in args.only:
        mod = {"github": github, "wikiedits": wikiedits}[name]
        for chunk_end in range(now_h, int(time.time()) - args.days * 86400, -6 * 3600):
            try:
                res = mod.fetch(hours=6, end_s=chunk_end)
            except Exception as e:  # network blips: skip the chunk, keep going
                print(name, time.strftime("%m-%d %H:00", time.gmtime(chunk_end)), "FAILED", e, flush=True)
                continue
            write(name, res)
            print(name, time.strftime("%m-%d %H:00", time.gmtime(chunk_end)), "ok", flush=True)
            if name == "github":
                time.sleep(13)  # 12 queries per chunk; stay under 30/min


if __name__ == "__main__":
    main()
