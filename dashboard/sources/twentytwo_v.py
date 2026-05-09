"""22V Research adapter (pending credentials). Mirrors VectorVest pattern."""
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Tuple

from ..config import CFG
from ..storage import upsert_observations


class NotConfigured(RuntimeError):
    pass


def _csv(sheet: str) -> Path:
    return Path(CFG.data_dir) / "manual" / f"22v_{sheet}.csv"


def fetch(sheet: str) -> List[Tuple[str, float]]:
    p = _csv(sheet)
    if p.exists():
        from . import csv_drop
        return csv_drop.read(f"22v_{sheet}")
    if CFG.twentytwov_user and CFG.twentytwov_pass:
        raise NotConfigured(
            "22V credentials present but live ingestion adapter not yet implemented; "
            "drop a CSV at " + str(p)
        )
    raise NotConfigured("22V not configured (no credentials, no CSV)")


def ingest(sheet: str) -> int:
    try:
        rows = fetch(sheet)
    except NotConfigured:
        return 0
    if not rows:
        return 0
    return upsert_observations(
        series_id=f"22V:{sheet}",
        rows=rows,
        source="22V",
        fetched_at=datetime.now(timezone.utc).isoformat(),
    )
