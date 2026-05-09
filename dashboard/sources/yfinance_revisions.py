"""Earnings revision snapshots via yfinance.

yfinance exposes Ticker.eps_revisions as a current snapshot of analyst
revision counts (upLast7days, upLast30days, downLast7days, downLast30days)
keyed by reporting period. We compute a single daily score:

    score = (up30 - down30) / max(1, up30 + down30)

and write it to the time series with today's date. The "improving revisions"
filter in screens.py compares the current score to the score 21 trading days
ago; until 21 days of history exist locally, the screen will simply find no
matches (rule, not guess).
"""
from datetime import date, datetime, timezone
from typing import List, Tuple

from ..storage import upsert_observations


def fetch_score(ticker: str) -> float | None:
    import yfinance as yf
    try:
        t = yf.Ticker(ticker)
        df = t.eps_revisions
    except Exception:
        return None
    if df is None or df.empty:
        return None
    cols = {c.lower(): c for c in df.columns}
    up_key = cols.get("uplast30days") or cols.get("up_last_30_days")
    dn_key = cols.get("downlast30days") or cols.get("down_last_30_days")
    if not up_key or not dn_key:
        return None
    try:
        up = float(df[up_key].fillna(0).sum())
        dn = float(df[dn_key].fillna(0).sum())
    except Exception:
        return None
    denom = up + dn
    if denom <= 0:
        return 0.0
    return (up - dn) / denom


def ingest(ticker: str) -> int:
    score = fetch_score(ticker)
    if score is None:
        return 0
    today = date.today().isoformat()
    return upsert_observations(
        series_id=f"REVS:{ticker}",
        rows=[(today, score)],
        source="Yahoo:eps_revisions",
        fetched_at=datetime.now(timezone.utc).isoformat(),
    )
