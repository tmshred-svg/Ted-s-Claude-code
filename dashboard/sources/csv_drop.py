import csv
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Tuple

from ..config import CFG
from ..storage import upsert_observations


def read(series_id: str) -> List[Tuple[str, float]]:
    path = Path(CFG.data_dir) / "manual" / f"{series_id}.csv"
    if not path.exists():
        return []
    out = []
    with path.open() as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                d = row["date"].strip()
                v = float(row["value"])
            except (KeyError, ValueError):
                continue
            out.append((d, v))
    out.sort()
    return out


def ingest(series_id: str) -> int:
    rows = read(series_id)
    if not rows:
        return 0
    return upsert_observations(
        series_id=f"CSV:{series_id}",
        rows=rows,
        source="manual_csv",
        fetched_at=datetime.now(timezone.utc).isoformat(),
    )
