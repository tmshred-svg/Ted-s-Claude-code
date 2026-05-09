"""VectorVest adapter.

Credentials will be supplied later. Until then this adapter:
  1. Looks for a manual CSV export at data/manual/vectorvest_<sheet>.csv.
  2. If a credentialed VECTORVEST_USER/VECTORVEST_PASS pair appears, raises
     NotConfigured with a clear message; we will not perform unauthenticated
     scraping.
"""
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Tuple

from ..config import CFG
from ..storage import upsert_observations


class NotConfigured(RuntimeError):
    pass


def _csv(sheet: str) -> Path:
    return Path(CFG.data_dir) / "manual" / f"vectorvest_{sheet}.csv"


def fetch(sheet: str) -> List[Tuple[str, float]]:
    p = _csv(sheet)
    if p.exists():
        from . import csv_drop
        return csv_drop.read(f"vectorvest_{sheet}")
    if CFG.vectorvest_user and CFG.vectorvest_pass:
        raise NotConfigured(
            "VectorVest credentials present but live ingestion adapter not yet implemented; "
            "drop a CSV at " + str(p)
        )
    raise NotConfigured("VectorVest not configured (no credentials, no CSV)")


def ingest(sheet: str) -> int:
    try:
        rows = fetch(sheet)
    except NotConfigured:
        return 0
    if not rows:
        return 0
    return upsert_observations(
        series_id=f"VV:{sheet}",
        rows=rows,
        source="VectorVest",
        fetched_at=datetime.now(timezone.utc).isoformat(),
    )
