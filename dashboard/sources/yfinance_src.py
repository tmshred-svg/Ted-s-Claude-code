from datetime import datetime, timezone
from typing import Dict

import pandas as pd

from ..storage import upsert_observations


def fetch_history(tickers, period: str = "2y", interval: str = "1d") -> Dict[str, pd.DataFrame]:
    import yfinance as yf
    if isinstance(tickers, str):
        tickers = [tickers]
    data = yf.download(
        tickers=" ".join(tickers),
        period=period,
        interval=interval,
        auto_adjust=True,
        progress=False,
        group_by="ticker",
        threads=True,
    )
    out: Dict[str, pd.DataFrame] = {}
    if isinstance(data.columns, pd.MultiIndex):
        for t in tickers:
            if t in data.columns.get_level_values(0):
                out[t] = data[t].dropna(how="all")
    else:
        out[tickers[0]] = data.dropna(how="all")
    return out


def ingest_close(ticker: str, period: str = "2y") -> int:
    frames = fetch_history(ticker, period=period)
    df = frames.get(ticker)
    if df is None or df.empty or "Close" not in df.columns:
        return 0
    rows = [(d.strftime("%Y-%m-%d"), float(v)) for d, v in df["Close"].dropna().items()]
    return upsert_observations(
        series_id=f"YF:{ticker}:CLOSE",
        rows=rows,
        source="Yahoo",
        fetched_at=datetime.now(timezone.utc).isoformat(),
    )
