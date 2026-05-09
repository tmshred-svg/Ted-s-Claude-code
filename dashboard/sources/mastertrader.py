"""Master Trader adapter (pending credentials). Mirrors VectorVest pattern."""
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Tuple

from ..config import CFG
from ..storage import upsert_observations


class NotConfigured(RuntimeError):
    pass


def _csv(sheet: str) -> Path:
    return Path(CFG.data_dir) / "manual" / f"mastertrader_{sheet}.csv"


def fetch(sheet: str) -> List[Tuple[str, float]]:
    p = _csv(sheet)
    if p.exists():
        from . import csv_drop
        return csv_drop.read(f"mastertrader_{sheet}")
    if CFG.mastertrader_user and CFG.mastertrader_pass:
        raise NotConfigured(
            "Master Trader credentials present but live ingestion adapter not yet implemented; "
            "drop a CSV at " + str(p)
        )
    raise NotConfigured("Master Trader not configured (no credentials, no CSV)")


def ingest(sheet: str) -> int:
    try:
        rows = fetch(sheet)
    except NotConfigured:
        return 0
    if not rows:
        return 0
    return upsert_observations(
        series_id=f"MT:{sheet}",
        rows=rows,
        source="MasterTrader",
        fetched_at=datetime.now(timezone.utc).isoformat(),
    )
