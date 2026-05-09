from datetime import datetime, timezone
from typing import List, Tuple

from ..config import CFG
from ..storage import upsert_observations


class NotConfigured(RuntimeError):
    pass


def fetch(ticker: str, field: str = "PX_LAST", start: str = "2000-01-01") -> List[Tuple[str, float]]:
    """Bloomberg adapter. Requires `blpapi` and a licensed terminal/BPipe.
    Returns [(YYYY-MM-DD, value)]. Raises NotConfigured if unavailable."""
    if not CFG.bloomberg_enabled:
        raise NotConfigured("BLOOMBERG_ENABLED!=1")
    try:
        import blpapi  # type: ignore
        from xbbg import blp  # type: ignore
    except ImportError as e:
        raise NotConfigured(f"blpapi/xbbg not installed: {e}")

    df = blp.bdh(tickers=ticker, flds=field, start_date=start)
    if df is None or df.empty:
        return []
    s = df[(ticker, field)] if (ticker, field) in df.columns else df.iloc[:, 0]
    return [(d.strftime("%Y-%m-%d"), float(v)) for d, v in s.dropna().items()]


def ingest(ticker: str, field: str = "PX_LAST", start: str = "2000-01-01") -> int:
    rows = fetch(ticker, field=field, start=start)
    return upsert_observations(
        series_id=f"BBG:{ticker}:{field}",
        rows=rows,
        source="Bloomberg",
        fetched_at=datetime.now(timezone.utc).isoformat(),
    )
