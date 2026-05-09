from datetime import datetime, timezone
from typing import List, Tuple

import requests

from ..config import CFG
from ..storage import upsert_observations


BASE = "https://api.bls.gov/publicAPI/v2/timeseries/data/"


class NotConfigured(RuntimeError):
    pass


def fetch(series_id: str, start_year: int = 2000) -> List[Tuple[str, float]]:
    if not CFG.bls_api_key:
        raise NotConfigured("BLS_API_KEY not set")
    payload = {
        "seriesid": [series_id],
        "startyear": str(start_year),
        "endyear": str(datetime.utcnow().year),
        "registrationkey": CFG.bls_api_key,
    }
    r = requests.post(BASE, json=payload, timeout=30)
    r.raise_for_status()
    data = r.json()
    out = []
    for s in data.get("Results", {}).get("series", []):
        for d in s.get("data", []):
            period = d.get("period", "")
            if not period.startswith("M") or period == "M13":
                continue
            month = int(period[1:])
            year = int(d["year"])
            iso = f"{year:04d}-{month:02d}-01"
            try:
                out.append((iso, float(d["value"])))
            except (ValueError, KeyError):
                continue
    out.sort()
    return out


def ingest(series_id: str, start_year: int = 2000) -> int:
    rows = fetch(series_id, start_year=start_year)
    return upsert_observations(
        series_id=f"BLS:{series_id}",
        rows=rows,
        source="BLS",
        fetched_at=datetime.now(timezone.utc).isoformat(),
    )
