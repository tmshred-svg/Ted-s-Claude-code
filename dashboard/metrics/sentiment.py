from typing import Dict, List

from ..sources import cboe, csv_drop, fred
from ..storage import latest_series
from ..roc import diff, trend_slope
from ._common import Cell


VIX_FRED = "VIXCLS"


def _ingest_safe(fn, *a, **k):
    try:
        return f"ok ({fn(*a, **k)} rows)"
    except Exception as e:
        return f"err: {type(e).__name__}: {e}"


def collect() -> Dict:
    log = {}
    log["CBOE_PC"] = _ingest_safe(cboe.ingest)
    log["AAII"] = _ingest_safe(csv_drop.ingest, "aaii_sentiment")
    log["II"] = _ingest_safe(csv_drop.ingest, "investors_intelligence")
    log[VIX_FRED] = _ingest_safe(fred.ingest, VIX_FRED)

    cells: List[Cell] = []

    pc = latest_series("CBOE:EQUITY_PC")
    if not pc.empty:
        v = pc["value"].iloc[-1]
        d5 = diff(pc["value"], 5)
        slope = trend_slope(pc["value"], 21)
        cells.append(Cell(
            label="CBOE equity put/call ratio",
            value=v, unit="ratio",
            asof=pc.index[-1].date().isoformat(), source="CBOE",
            extra={"5d_chg": d5, "21d_slope": slope},
        ))
    else:
        cells.append(Cell(label="CBOE equity put/call", note="CBOE fetch failed"))

    vix = latest_series(f"FRED:{VIX_FRED}")
    if not vix.empty:
        v = vix["value"].iloc[-1]
        d5 = diff(vix["value"], 5)
        cells.append(Cell(
            label="VIX",
            value=v, unit="idx",
            asof=vix.index[-1].date().isoformat(), source="FRED:VIXCLS",
            series_id=f"FRED:{VIX_FRED}",
            extra={"5d_chg": d5},
        ))
    else:
        cells.append(Cell(label="VIX", note="FRED not configured"))

    aaii = latest_series("CSV:aaii_sentiment")
    if not aaii.empty:
        v = aaii["value"].iloc[-1]
        cells.append(Cell(
            label="AAII bull-bear spread (manual CSV)",
            value=v, unit="ratio",
            asof=aaii.index[-1].date().isoformat(), source="manual_csv",
        ))
    else:
        cells.append(Cell(label="AAII bull-bear spread", note="no CSV at data/manual/aaii_sentiment.csv"))

    ii = latest_series("CSV:investors_intelligence")
    if not ii.empty:
        v = ii["value"].iloc[-1]
        cells.append(Cell(
            label="Investors Intelligence bull-bear spread (manual CSV)",
            value=v, unit="ratio",
            asof=ii.index[-1].date().isoformat(), source="manual_csv",
        ))
    else:
        cells.append(Cell(label="Investors Intelligence", note="no CSV at data/manual/investors_intelligence.csv"))

    return {"cells": cells, "log": log}
