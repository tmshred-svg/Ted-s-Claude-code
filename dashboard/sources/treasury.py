from datetime import datetime, timezone
from typing import List, Tuple

import requests

from ..storage import upsert_observations


BASE = "https://api.fiscaldata.treasury.gov/services/api/fiscal_service"


def fetch_tga(days: int = 1500) -> List[Tuple[str, float]]:
    """Operating Cash Balance — Treasury General Account."""
    url = f"{BASE}/v1/accounting/dts/operating_cash_balance"
    params = {
        "fields": "record_date,open_today_bal,account_type",
        "filter": "account_type:eq:Treasury General Account (TGA) Closing Balance",
        "sort": "-record_date",
        "page[size]": str(days),
    }
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    out = []
    for row in r.json().get("data", []):
        try:
            out.append((row["record_date"], float(row["open_today_bal"])))
        except (ValueError, KeyError, TypeError):
            continue
    out.sort()
    return out


def ingest_tga() -> int:
    rows = fetch_tga()
    return upsert_observations(
        series_id="TREAS:TGA_BAL",
        rows=rows,
        source="USTreasury",
        fetched_at=datetime.now(timezone.utc).isoformat(),
    )
