from datetime import datetime, timezone
from typing import List, Tuple

import requests

from ..storage import upsert_observations


BASE = "https://api.fiscaldata.treasury.gov/services/api/fiscal_service"


def fetch_tga(days: int = 1500) -> List[Tuple[str, float]]:
    """Operating Cash Balance — Treasury General Account.

    The Treasury API has used several different account_type labels over the
    years ('Federal Reserve Account', 'Treasury General Account (TGA)',
    'Treasury General Account (TGA) Opening Balance',
    'Treasury General Account (TGA) Closing Balance'). We pull all rows and
    filter by substring match in Python so the adapter survives schema
    changes.
    """
    url = f"{BASE}/v1/accounting/dts/operating_cash_balance"
    params = {
        "fields": "record_date,open_today_bal,close_today_bal,account_type",
        "sort": "-record_date",
        "page[size]": str(days),
    }
    r = requests.get(url, params=params, timeout=60,
                     headers={"User-Agent": "metrics-dashboard"})
    r.raise_for_status()
    by_date: dict = {}
    for row in r.json().get("data", []):
        acct = (row.get("account_type") or "").lower()
        if "treasury general account" not in acct and "federal reserve account" not in acct:
            continue
        if "opening" in acct:
            continue
        date_iso = row.get("record_date")
        for v_field in ("close_today_bal", "open_today_bal"):
            v = row.get(v_field)
            if v in (None, "", "null"):
                continue
            try:
                by_date[date_iso] = float(v)
                break
            except (ValueError, TypeError):
                continue
    return sorted(by_date.items())


def ingest_tga() -> int:
    rows = fetch_tga()
    return upsert_observations(
        series_id="TREAS:TGA_BAL",
        rows=rows,
        source="USTreasury",
        fetched_at=datetime.now(timezone.utc).isoformat(),
    )
