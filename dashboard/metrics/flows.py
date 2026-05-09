"""Flow of funds via sector / asset-class ETF price action.

True fund-flow data (creations/redemptions) is paid (Bloomberg, ICI, EPFR).
We compute observable proxies from price + volume:
  - 1d, 5d, 21d return for each asset class & sector ETF
  - 21d $ volume change
  - relative strength vs benchmark
True fund flows, when configured via Bloomberg or CSV drop, override the proxies.
"""
from typing import Dict, List

import pandas as pd

from ..config import CFG
from ..sources import yfinance_src, csv_drop, bloomberg
from ..storage import latest_series
from ..roc import pct_change, relative_strength
from ._common import Cell


ASSET_CLASS_ETFS = {
    "US large-cap stocks": "SPY",
    "US small-cap stocks": "IWM",
    "US Treasury 7-10y": "IEF",
    "US Treasury 20+y": "TLT",
    "US IG corp bonds": "LQD",
    "US HY corp bonds": "HYG",
    "Broad commodities": "DBC",
    "Gold": "GLD",
    "Crude oil": "USO",
    "US dollar (DXY proxy)": "UUP",
}


def _ingest_safe(fn, *a, **k):
    try:
        return f"ok ({fn(*a, **k)} rows)"
    except Exception as e:
        return f"err: {type(e).__name__}: {e}"


def collect() -> Dict:
    log = {}
    tickers = list(ASSET_CLASS_ETFS.values()) + list(CFG.sector_etfs) + [CFG.benchmark]
    for t in tickers:
        log[t] = _ingest_safe(yfinance_src.ingest_close, t, "2y")

    cells: List[Cell] = []
    bench = latest_series(f"YF:{CFG.benchmark}:CLOSE")
    bench_close = bench["value"] if not bench.empty else pd.Series(dtype=float)

    for label, t in ASSET_CLASS_ETFS.items():
        s = latest_series(f"YF:{t}:CLOSE")
        if s.empty:
            cells.append(Cell(label=f"Asset-class flow proxy: {label} ({t})", note="Yahoo fetch failed"))
            continue
        last = float(s["value"].iloc[-1])
        r1 = pct_change(s["value"], 1)
        r5 = pct_change(s["value"], 5)
        r21 = pct_change(s["value"], 21)
        rs = relative_strength(s["value"], bench_close, 63) if not bench_close.empty else None
        cells.append(Cell(
            label=f"Asset-class flow proxy: {label} ({t})",
            value=last, unit="idx",
            asof=s.index[-1].date().isoformat(), source="Yahoo",
            extra={"1d": r1, "5d": r5, "21d": r21, "rs_vs_bench_63d": rs},
        ))

    sector_cells: List[Cell] = []
    for t in CFG.sector_etfs:
        s = latest_series(f"YF:{t}:CLOSE")
        if s.empty:
            sector_cells.append(Cell(label=f"Sector {t}", note="Yahoo fetch failed"))
            continue
        last = float(s["value"].iloc[-1])
        r5 = pct_change(s["value"], 5)
        r21 = pct_change(s["value"], 21)
        r63 = pct_change(s["value"], 63)
        rs = relative_strength(s["value"], bench_close, 63) if not bench_close.empty else None
        sector_cells.append(Cell(
            label=f"Sector ETF: {t}",
            value=last, unit="idx",
            asof=s.index[-1].date().isoformat(), source="Yahoo",
            extra={"5d": r5, "21d": r21, "63d": r63, "rs_vs_bench_63d": rs},
        ))

    bbg_flow = csv_drop.ingest("etf_flows")
    log["etf_flows_csv"] = f"ok ({bbg_flow} rows)"

    return {"asset_cells": cells, "sector_cells": sector_cells, "log": log}
