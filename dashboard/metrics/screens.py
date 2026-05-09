"""Stock/sector screens.

Inputs:
  - universe CSV at SCREEN_UNIVERSE_FILE: columns ticker,sector,sector_etf
  - daily closes for each ticker, sector ETF, and benchmark (Yahoo)
  - optional earnings revisions per ticker:
      data/manual/revisions_<TICKER>.csv with date,value
      where value = (# upward revisions - # downward) over trailing 4w / total

Rules (deterministic):
  - 63d relative strength of each ticker vs benchmark
  - Sector strength = 63d return of sector ETF minus benchmark 63d return
  - "Strong sectors": top tercile by sector strength
  - "Weak sectors": bottom tercile by sector strength
  - "Earnings revisions improving": last value > value 21 trading days ago
  - HH+HL on weekly RSI(14) of sector ETF computed from daily closes
"""
import csv
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from ..config import CFG
from ..sources import yfinance_src, csv_drop
from ..storage import latest_series
from ..roc import pct_change, rsi, higher_highs_higher_lows, relative_strength
from ._common import Cell


def _load_universe() -> pd.DataFrame:
    p = Path(CFG.universe_file)
    if not p.exists():
        return pd.DataFrame(columns=["ticker", "sector", "sector_etf"])
    df = pd.read_csv(p)
    df.columns = [c.strip().lower() for c in df.columns]
    for col in ("ticker", "sector", "sector_etf"):
        if col not in df.columns:
            df[col] = ""
    df["ticker"] = df["ticker"].astype(str).str.upper().str.strip()
    df["sector_etf"] = df["sector_etf"].astype(str).str.upper().str.strip()
    return df[df["ticker"] != ""]


def _ingest_safe(fn, *a, **k):
    try:
        return f"ok ({fn(*a, **k)} rows)"
    except Exception as e:
        return f"err: {type(e).__name__}: {e}"


def collect() -> Dict:
    log = {}
    universe = _load_universe()
    if universe.empty:
        return {
            "log": {"universe": f"missing or empty: {CFG.universe_file}"},
            "strong_in_strong": [],
            "strong_in_weak": [],
            "sector_strength": [],
            "note": (f"Provide a universe CSV at {CFG.universe_file} with columns "
                     "ticker,sector,sector_etf to enable screens."),
        }

    tickers = sorted(set(universe["ticker"]))
    for t in tickers:
        log[f"YF:{t}"] = _ingest_safe(yfinance_src.ingest_close, t, "1y")
    for t in sorted(set(universe["sector_etf"])):
        if t:
            log[f"YF:{t}"] = _ingest_safe(yfinance_src.ingest_close, t, "1y")
    for t in tickers:
        csv_drop.ingest(f"revisions_{t}")

    bench = latest_series(f"YF:{CFG.benchmark}:CLOSE")
    if bench.empty:
        return {"log": log, "strong_in_strong": [], "strong_in_weak": [],
                "sector_strength": [], "note": "Benchmark price unavailable."}
    bench_close = bench["value"]

    sector_strength = []
    sector_rs_map: Dict[str, float] = {}
    for sector_etf in sorted({s for s in universe["sector_etf"] if s}):
        s = latest_series(f"YF:{sector_etf}:CLOSE")
        if s.empty:
            continue
        rs63 = relative_strength(s["value"], bench_close, 63)
        rsi14 = rsi(s["value"], 14)
        hh_hl = higher_highs_higher_lows(rsi14, lookback=20, pivots=2)
        sector_rs_map[sector_etf] = rs63 if rs63 is not None else float("nan")
        sector_strength.append({
            "etf": sector_etf,
            "rs_63d": rs63,
            "rsi14_last": float(rsi14.dropna().iloc[-1]) if not rsi14.dropna().empty else None,
            "rsi_hh_hl_20d": bool(hh_hl),
        })

    if not sector_strength:
        return {"log": log, "strong_in_strong": [], "strong_in_weak": [],
                "sector_strength": [], "note": "No sector ETF prices ingested."}

    rs_sorted = sorted(
        [s for s in sector_strength if s["rs_63d"] is not None],
        key=lambda x: x["rs_63d"], reverse=True,
    )
    n = len(rs_sorted)
    cut = max(1, n // 3)
    strong_etfs = {s["etf"] for s in rs_sorted[:cut]}
    weak_etfs = {s["etf"] for s in rs_sorted[-cut:]}

    rows = []
    for _, u in universe.iterrows():
        t, etf = u["ticker"], u["sector_etf"]
        s = latest_series(f"YF:{t}:CLOSE")
        if s.empty:
            continue
        rs63 = relative_strength(s["value"], bench_close, 63)
        rs21 = relative_strength(s["value"], bench_close, 21)
        revs = latest_series(f"CSV:revisions_{t}")
        rev_last = float(revs["value"].iloc[-1]) if not revs.empty else None
        rev_chg21 = None
        if not revs.empty and len(revs) >= 2:
            rev_chg21 = float(revs["value"].iloc[-1] - revs["value"].iloc[max(0, len(revs) - 22)])
        rows.append({
            "ticker": t,
            "sector": u["sector"],
            "sector_etf": etf,
            "rs_63d": rs63,
            "rs_21d": rs21,
            "revisions_last": rev_last,
            "revisions_chg_21d": rev_chg21,
        })

    df = pd.DataFrame(rows)
    if df.empty:
        return {"log": log, "strong_in_strong": [], "strong_in_weak": [],
                "sector_strength": sector_strength, "note": "No ticker prices ingested."}

    rs_thresh = df["rs_63d"].dropna().quantile(0.75) if df["rs_63d"].dropna().size else 0.0

    sis = df[
        (df["sector_etf"].isin(strong_etfs))
        & (df["rs_63d"] >= rs_thresh)
        & (df["revisions_chg_21d"].fillna(-1e9) > 0)
    ].sort_values("rs_63d", ascending=False)

    weak_with_hh_hl = {s["etf"] for s in sector_strength if s["etf"] in weak_etfs and s["rsi_hh_hl_20d"]}
    siw = df[
        (df["sector_etf"].isin(weak_with_hh_hl))
        & (df["rs_63d"] >= rs_thresh)
    ].sort_values("rs_63d", ascending=False)

    return {
        "log": log,
        "sector_strength": sector_strength,
        "strong_etfs": sorted(strong_etfs),
        "weak_etfs": sorted(weak_etfs),
        "weak_with_hh_hl": sorted(weak_with_hh_hl),
        "rs_threshold_p75": float(rs_thresh) if rs_thresh == rs_thresh else None,
        "strong_in_strong": sis.to_dict(orient="records"),
        "strong_in_weak": siw.to_dict(orient="records"),
        "universe_size": int(len(df)),
    }
