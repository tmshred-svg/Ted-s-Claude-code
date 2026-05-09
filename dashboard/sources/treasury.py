from datetime import datetime, timezone
from typing import List, Tuple

import requests

from ..storage import upsert_observations


BASE = "https://api.fiscaldata.treasury.gov/services/api/fiscal_service"


_LAST_DEBUG = {"distinct_account_types": [], "row_count": 0, "sample_keys": []}


def last_debug() -> dict:
    return dict(_LAST_DEBUG)


def fetch_tga(days: int = 1500) -> List[Tuple[str, float]]:
    """Operating Cash Balance — TGA closing balance.

    Returns sorted (date, value_in_millions). The DTS API has used several
    different account_type labels and field names over the years; we filter
    by substring match and probe known value-field names. Diagnostic info
    is kept in last_debug() but is not required for downstream metric
    rendering — FRED:WTREGEN is the production fallback.
    """
    url = f"{BASE}/v1/accounting/dts/operating_cash_balance"
    params = {
        "fields": "record_date,open_today_bal,close_today_bal,today_amt,account_type",
        "sort": "-record_date",
        "page[size]": str(days),
    }
    r = requests.get(url, params=params, timeout=45,
                     headers={"User-Agent": "metrics-dashboard"})
    r.raise_for_status()
    rows = r.json().get("data", [])
    seen_accts = sorted({(row.get("account_type") or "").strip()
                         for row in rows if row.get("account_type")})
    _LAST_DEBUG["distinct_account_types"] = seen_accts[:30]
    _LAST_DEBUG["row_count"] = len(rows)

    by_date: dict = {}
    for row in rows:
        acct = (row.get("account_type") or "").lower()
        if "treasury general account" not in acct:
            continue
        if "opening" in acct or "deposit" in acct or "withdrawal" in acct:
            continue
        date_iso = row.get("record_date")
        if not date_iso:
            continue
        for v_field in ("close_today_bal", "today_amt", "open_today_bal"):
            v = row.get(v_field)
            if v in (None, "", "null"):
                continue
            try:
                fv = float(v)
            except (ValueError, TypeError):
                continue
            if fv == 0:
                continue
            by_date[date_iso] = fv
            break
    return sorted(by_date.items())


def ingest_tga() -> int:
    rows = fetch_tga()
    return upsert_observations(
        series_id="TREAS:TGA_BAL",
        rows=rows,
        source="USTreasury",
        fetched_at=datetime.now(timezone.utc).isoformat(),
    )
