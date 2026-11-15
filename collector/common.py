"""Shared helpers: HTTP session, time utilities, GTA 6 classifier."""
import os
import re
import time

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config import USER_AGENT

session = requests.Session()
session.headers["User-Agent"] = USER_AGENT
_retry = Retry(total=4, backoff_factor=3, status_forcelist=[429, 500, 502, 503, 504],
               allowed_methods=None, respect_retry_after_header=True)
session.mount("https://", HTTPAdapter(max_retries=_retry))

GTA6_RE = re.compile(r"\b(gta\s?-?\s?(6|vi)|grand\s+theft\s+auto\s+(6|vi))\b", re.I)


def is_gta6(*texts) -> bool:
    return any(t and GTA6_RE.search(t) for t in texts)


def now_ms() -> int:
    return int(time.time() * 1000)


def hour_floor_ms(ts_s: float) -> int:
    return int(ts_s // 3600 * 3600 * 1000)


def iso(ts_s: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts_s))


def env(name: str):
    """Return an env var or None (sources skip themselves when keys are missing)."""
    v = os.environ.get(name, "").strip()
    return v or None


class Skip(Exception):
    """Raised by a source that can't run (e.g. missing API key)."""


class Fresh(Skip):
    """Raised when a source's data is still fresh and needn't be refetched."""
