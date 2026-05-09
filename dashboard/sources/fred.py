from datetime import datetime, timezone
from typing import List, Tuple

import requests

from ..config import CFG
from ..storage import upsert_observations


BASE = "https://api.stlouisfed.org/fred/series/observations"


class NotConfigured(RuntimeError):
    pass


def fetch(series_id: str, start: str = "2000-01-01") -> List[Tuple[str, float]]:
    if not CFG.fred_api_key:
        raise NotConfigured("FRED_API_KEY not set")
    params = {
        "series_id": series_id,
        "api_key": CFG.fred_api_key,
        "file_type": "json",
        "observation_start": start,
    }
    r = requests.get(BASE, params=params, timeout=30)
    r.raise_for_status()
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


def ingest(series_id: str, start: str = "2000-01-01") -> int:
    rows = fetch(series_id, start=start)
    return upsert_observations(
        series_id=f"FRED:{series_id}",
        rows=rows,
        source="FRED",
        fetched_at=datetime.now(timezone.utc).isoformat(),
    )
