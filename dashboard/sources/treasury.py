from datetime import datetime, timezone
from typing import List, Tuple

import requests

from ..storage import upsert_observations


BASE = "https://api.fiscaldata.treasury.gov/services/api/fiscal_service"


_LAST_DEBUG = {"distinct_account_types": [], "row_count": 0}


def last_debug() -> dict:
    return dict(_LAST_DEBUG)


def fetch_tga(days: int = 1500) -> List[Tuple[str, float]]:
    """Operating Cash Balance — Treasury General Account.

    The Treasury API has used several account_type labels over the years.
    We pull all rows and filter by substring match in Python so the adapter
    survives schema changes. We also record the distinct account_type values
    we saw in this fetch (accessible via last_debug()) for diagnostics.
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
    rows = r.json().get("data", [])
    seen_accts = sorted({(row.get("account_type") or "").strip() for row in rows if row.get("account_type")})
    _LAST_DEBUG["distinct_account_types"] = seen_accts[:30]
    _LAST_DEBUG["row_count"] = len(rows)

    by_date: dict = {}
    for row in rows:
        acct = (row.get("account_type") or "").lower()
        if not (
            "treasury general account" in acct
            or "federal reserve account" in acct
            or acct.strip() == "tga"
        ):
            continue
        if "opening" in acct:
            continue
        date_iso = row.get("record_date")
        if not date_iso:
            continue
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
