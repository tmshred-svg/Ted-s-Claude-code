from datetime import datetime, timezone
from typing import List, Tuple

from ..config import CFG
from ..storage import upsert_observations


class NotConfigured(RuntimeError):
    pass


def fetch(ric: str, field: str = "TR.PriceClose", start: str = "2000-01-01") -> List[Tuple[str, float]]:
    if not CFG.refinitiv_app_key:
        raise NotConfigured("REFINITIV_APP_KEY not set")
    try:
        import refinitiv.data as rd  # type: ignore
    except ImportError as e:
        raise NotConfigured(f"refinitiv-data not installed: {e}")
    rd.open_session(app_key=CFG.refinitiv_app_key)
    try:
        df = rd.get_history(universe=ric, fields=[field], start=start)
    finally:
        rd.close_session()
    if df is None or df.empty:
        return []
    s = df.iloc[:, 0].dropna()
    return [(d.strftime("%Y-%m-%d"), float(v)) for d, v in s.items()]


def ingest(ric: str, field: str = "TR.PriceClose", start: str = "2000-01-01") -> int:
    rows = fetch(ric, field=field, start=start)
    return upsert_observations(
        series_id=f"RFN:{ric}:{field}",
        rows=rows,
        source="Refinitiv",
        fetched_at=datetime.now(timezone.utc).isoformat(),
    )
