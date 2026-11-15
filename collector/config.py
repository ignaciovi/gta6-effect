"""Static configuration for the collector."""

USER_AGENT = "gta6-launch-tracker/0.1 (unofficial fan project; github.com)"

# Launch marker used by the site (also exported to data/meta.json).
# Midnight US Eastern on release day.
LAUNCH_ISO = "2026-11-19T05:00:00Z"

# Keep at most this many days of history per series.
RETENTION_DAYS = 180

# Backfill history from here where sources allow it.
HISTORY_START_ISO = "2026-11-01T00:00:00Z"
HISTORY_START_S = 1793491200  # same instant, as a unix timestamp
# Points older than this are thinned to one per hour (keeps sub-hourly series,
# e.g. Steam's ~5-min chart, small while preserving full detail for the last week).
FULL_RES_DAYS = 7

# --- Google Trends (US). Values are relative *within* a batch, so related
# terms of similar volume are grouped together.
TRENDS_BATCHES = {
    "sick": ["call in sick", "sick day"],
    "food": ["DoorDash", "Uber Eats", "pizza delivery", "Domino's"],
}

# --- US App Store top-free ranks. key -> name prefix to match.
APPSTORE_APPS = {
    "doordash": "DoorDash",
    "ubereats": "Uber Eats",
    "dominos": "Domino's",
    "mcdonalds": "McDonald's",
    "tacobell": "Taco Bell",
    "playstation": "PlayStation App",
    "xbox": "Xbox",
    "discord": "Discord",
    "twitch": "Twitch",
    "indeed": "Indeed",
}

# --- TomTom flow sample points: two freeway points per metro.
METROS = {
    "nyc": ("New York", [(40.6955, -73.9875), (40.8445, -73.9030)]),
    "la": ("Los Angeles", [(34.1260, -118.4740), (34.0985, -118.3330)]),
    "chicago": ("Chicago", [(41.9180, -87.6935), (41.8750, -87.7000)]),
    "houston": ("Houston", [(29.7400, -95.4560), (29.7840, -95.5600)]),
    "dallas": ("Dallas", [(32.8000, -96.8200), (32.8700, -96.7700)]),
    "atlanta": ("Atlanta", [(33.7700, -84.3880), (33.9100, -84.3500)]),
    "sf": ("SF Bay Area", [(37.8250, -122.2900), (37.6000, -122.3900)]),
    "seattle": ("Seattle", [(47.6300, -122.3230), (47.6000, -122.1860)]),
    "miami": ("Miami", [(25.8000, -80.2050), (25.8000, -80.3300)]),
    "dc": ("Washington DC", [(38.9900, -77.1200), (38.8500, -77.0600)]),
}

TICKERS = ["TTWO", "SONY", "MSFT"]

GTAV_STEAM_APPID = 271590

# --- Worldwide attention share: big markets queried individually and combined.
YOUTUBE_REGIONS = ["US", "GB", "DE", "FR", "ES", "BR", "MX", "JP", "IN", "KR"]
TRENDING_GEOS = ["US", "GB", "CA", "AU", "IN", "DE", "FR", "BR", "MX", "JP"]
