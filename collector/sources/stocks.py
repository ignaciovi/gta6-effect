"""Stock prices from Yahoo Finance's public endpoints (no key).
30-minute bars since HISTORY_START, the last session's % change, and shares
outstanding / market cap (used for the market-value counter)."""
import requests

from common import session
from config import HISTORY_START_S, TICKERS

API = "https://query1.finance.yahoo.com/v8/finance/chart/{sym}"
HEADERS = {"User-Agent": "Mozilla/5.0"}  # Yahoo rejects non-browser user agents


def _quotes(symbols):
    """Shares outstanding and market cap. The quote endpoint needs a cookie + crumb;
    optional: prices still work if this fails."""
    try:
        s = requests.Session()
        s.headers["User-Agent"] = HEADERS["User-Agent"]
        s.get("https://fc.yahoo.com", timeout=20)
        crumb = s.get("https://query2.finance.yahoo.com/v1/test/getcrumb", timeout=20).text.strip()
        r = s.get("https://query2.finance.yahoo.com/v7/finance/quote",
                  params={"symbols": ",".join(symbols), "crumb": crumb}, timeout=20)
        r.raise_for_status()
        return {q["symbol"]: q for q in r.json()["quoteResponse"]["result"]}
    except Exception:
        return {}


def _chart(sym, rng, interval):
    r = session.get(API.format(sym=sym), params={"range": rng, "interval": interval},
                    headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.json()["chart"]["result"][0]


def fetch():
    series, meta = {}, {}
    for sym in TICKERS:
        bars = _chart(sym, "1mo", "30m")  # Yahoo keeps 60 days of 30-min bars
        closes = bars["indicators"]["quote"][0]["close"]
        series[f"{sym}:price"] = [[int(t) * 1000, round(c, 2)]
                                  for t, c in zip(bars["timestamp"], closes)
                                  if c is not None and t >= HISTORY_START_S]
        today = _chart(sym, "1d", "5m")["meta"]  # chartPreviousClose = yesterday's close
        price, prev = today["regularMarketPrice"], today["chartPreviousClose"]
        ts = int(today["regularMarketTime"]) * 1000
        series[f"{sym}:price"].append([ts, round(price, 2)])
        series[f"{sym}:pct"] = [[ts, round(100 * (price / prev - 1), 2)]]
        meta[sym] = {"prev_close": prev, "currency": today.get("currency")}
    for sym, q in _quotes(TICKERS).items():
        if sym in meta and q.get("sharesOutstanding"):
            meta[sym].update(shares=q["sharesOutstanding"], market_cap=q.get("marketCap"))
    return {"mode": "merge", "series": series, "meta": meta}
