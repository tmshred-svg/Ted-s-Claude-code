"""FRED adapter.

Uses the keyed JSON API when FRED_API_KEY is set, otherwise falls back to the
public CSV endpoint at fred.stlouisfed.org/graph/fredgraph.csv which does not
require authentication.
"""
import csv
import io
import time
from datetime import datetime, timezone
from typing import List, Tuple

import requests

from ..config import CFG
from ..storage import upsert_observations


JSON_BASE = "https://api.stlouisfed.org/fred/series/observations"
CSV_BASE = "https://fred.stlouisfed.org/graph/fredgraph.csv"
UA = "Mozilla/5.0 (compatible; metrics-dashboard/1.0; +https://github.com/tmshred-svg/Ted-s-Claude-code)"


class NotConfigured(RuntimeError):
    pass


def _http_get(url: str, params: dict, timeout: int = 60, retries: int = 3) -> requests.Response:
    last_exc = None
    for attempt in range(retries):
        try:
            r = requests.get(url, params=params, timeout=timeout,
                             headers={"User-Agent": UA, "Accept": "*/*"})
            if r.status_code == 429 or r.status_code >= 500:
                raise requests.HTTPError(f"{r.status_code}", response=r)
            r.raise_for_status()
            return r
        except (requests.Timeout, requests.HTTPError, requests.ConnectionError) as e:
            last_exc = e
            time.sleep(2 ** attempt)
    raise last_exc


def _fetch_json(series_id: str, start: str) -> List[Tuple[str, float]]:
    params = {
        "series_id": series_id,
        "api_key": CFG.fred_api_key,
        "file_type": "json",
        "observation_start": start,
    }
    r = _http_get(JSON_BASE, params=params)
    out = []
    for o in r.json().get("observations", []):
        v = o.get("value")
        if v in (None, ".", ""):
            continue
        try:
            out.append((o["date"], float(v)))
        except ValueError:
            continue
    return out


def _fetch_csv(series_id: str, start: str) -> List[Tuple[str, float]]:
    params = {"id": series_id, "cosd": start}
    r = _http_get(CSV_BASE, params=params)
    out = []
    rdr = csv.reader(io.StringIO(r.text))
    rows = list(rdr)
    if not rows:
        return out
    header = [h.strip().upper() for h in rows[0]]
    try:
        date_i = header.index("DATE")
        val_i = header.index(series_id.upper())
    except ValueError:
        if len(header) >= 2:
            date_i, val_i = 0, 1
        else:
            return out
    for row in rows[1:]:
        if len(row) <= max(date_i, val_i):
            continue
        v = row[val_i].strip()
        if v in (".", "", "NA"):
            continue
        try:
            out.append((row[date_i].strip(), float(v)))
        except ValueError:
            continue
    return out


def fetch(series_id: str, start: str = "2000-01-01") -> List[Tuple[str, float]]:
    if CFG.fred_api_key:
        return _fetch_json(series_id, start)
    return _fetch_csv(series_id, start)


def ingest(series_id: str, start: str = "2000-01-01") -> int:
    rows = fetch(series_id, start=start)
    return upsert_observations(
        series_id=f"FRED:{series_id}",
        rows=rows,
        source="FRED" if CFG.fred_api_key else "FRED-CSV",
        fetched_at=datetime.now(timezone.utc).isoformat(),
    )
