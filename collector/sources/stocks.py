"""Stock prices from Yahoo Finance's public chart endpoint (no key).
30-minute bars over the last 5 trading days, plus today's % change."""
from common import session
from config import TICKERS

API = "https://query1.finance.yahoo.com/v8/finance/chart/{sym}"
HEADERS = {"User-Agent": "Mozilla/5.0"}  # Yahoo rejects non-browser user agents


def _chart(sym, rng, interval):
    r = session.get(API.format(sym=sym), params={"range": rng, "interval": interval},
                    headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.json()["chart"]["result"][0]


def fetch():
    series, meta = {}, {}
    for sym in TICKERS:
        bars = _chart(sym, "5d", "30m")
        closes = bars["indicators"]["quote"][0]["close"]
        series[f"{sym}:price"] = [[int(t) * 1000, round(c, 2)]
                                  for t, c in zip(bars["timestamp"], closes) if c is not None]
        today = _chart(sym, "1d", "5m")["meta"]  # chartPreviousClose = yesterday's close
        price, prev = today["regularMarketPrice"], today["chartPreviousClose"]
        ts = int(today["regularMarketTime"]) * 1000
        series[f"{sym}:price"].append([ts, round(price, 2)])
        series[f"{sym}:pct"] = [[ts, round(100 * (price / prev - 1), 2)]]
        meta[sym] = {"prev_close": prev, "currency": today.get("currency")}
    return {"mode": "merge", "series": series, "meta": meta}
