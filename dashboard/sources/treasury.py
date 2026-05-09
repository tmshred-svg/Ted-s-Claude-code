from datetime import datetime, timezone
from typing import List, Tuple

import requests

from ..storage import upsert_observations


BASE = "https://api.fiscaldata.treasury.gov/services/api/fiscal_service"


_LAST_DEBUG = {"distinct_account_types": [], "row_count": 0, "sample_keys": []}


def last_debug() -> dict:
    return dict(_LAST_DEBUG)


_VALUE_FIELDS = (
    "close_today_bal",
    "open_today_bal",
    "today_amt",
    "amount",
    "amt",
)


def fetch_tga(days: int = 1500) -> List[Tuple[str, float]]:
    """Operating Cash Balance — Treasury General Account.

    Schema has changed several times; we request every field, match the row
    by account_type substring, then probe a list of known value fields. The
    distinct account_type values and the JSON keys of one matching row are
    surfaced in last_debug() for diagnostics.
    """
    url = f"{BASE}/v1/accounting/dts/operating_cash_balance"
    params = {
        "sort": "-record_date",
        "page[size]": str(days),
    }
    r = requests.get(url, params=params, timeout=60,
                     headers={"User-Agent": "metrics-dashboard"})
    r.raise_for_status()
    rows = r.json().get("data", [])
    seen_accts = sorted({(row.get("account_type") or "").strip()
                         for row in rows if row.get("account_type")})
    _LAST_DEBUG["distinct_account_types"] = seen_accts[:30]
    _LAST_DEBUG["row_count"] = len(rows)

    by_date: dict = {}
    sample_keys = []
    for row in rows:
        acct = (row.get("account_type") or "").lower()
        if "treasury general account" not in acct:
            continue
        if "opening" in acct or "deposit" in acct or "withdrawal" in acct:
            continue
        if not sample_keys:
            sample_keys = sorted(row.keys())
        date_iso = row.get("record_date")
        if not date_iso:
            continue
        for v_field in _VALUE_FIELDS:
            v = row.get(v_field)
            if v in (None, "", "null", "0", 0):
                continue
            try:
                by_date[date_iso] = float(v)
                break
            except (ValueError, TypeError):
                continue
    _LAST_DEBUG["sample_keys"] = sample_keys
    return sorted(by_date.items())


def ingest_tga() -> int:
    rows = fetch_tga()
    return upsert_observations(
        series_id="TREAS:TGA_BAL",
        rows=rows,
        source="USTreasury",
        fetched_at=datetime.now(timezone.utc).isoformat(),
    )
