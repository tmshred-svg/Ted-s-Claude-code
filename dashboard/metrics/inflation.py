from typing import Dict, List

from ..sources import fred
from ..storage import latest_series
from ..roc import pct_change, diff, trend_slope
from ._common import Cell


CPI = "CPIAUCSL"
CORE_CPI = "CPILFESL"
PCE = "PCEPI"
CORE_PCE = "PCEPILFE"
BREAKEVEN_5Y = "T5YIE"
BREAKEVEN_10Y = "T10YIE"
FORWARD_5Y5Y = "T5YIFR"
UMICH_INFL_1Y = "MICH"


def _ingest_safe(fn, *a, **k):
    try:
        return f"ok ({fn(*a, **k)} rows)"
    except Exception as e:
        return f"err: {type(e).__name__}: {e}"


def collect() -> Dict:
    log = {}
    for s in [CPI, CORE_CPI, PCE, CORE_PCE, BREAKEVEN_5Y, BREAKEVEN_10Y, FORWARD_5Y5Y, UMICH_INFL_1Y]:
        log[s] = _ingest_safe(fred.ingest, s)

    cells: List[Cell] = []

    for label, sid in [("Headline CPI YoY", CPI), ("Core CPI YoY", CORE_CPI),
                        ("Headline PCE YoY", PCE), ("Core PCE YoY", CORE_PCE)]:
        s = latest_series(f"FRED:{sid}")
        if s.empty:
            cells.append(Cell(label=label, note="FRED not configured"))
            continue
        yoy = pct_change(s["value"], 12)
        mom = pct_change(s["value"], 1)
        slope = trend_slope(s["value"].pct_change(12).dropna(), 6)
        cells.append(Cell(
            label=label, value=yoy, unit="%",
            asof=s.index[-1].date().isoformat(), source=f"FRED:{sid}",
            series_id=f"FRED:{sid}",
            extra={"mom": mom, "yoy_slope_6m": slope},
        ))

    for label, sid in [("5y breakeven", BREAKEVEN_5Y), ("10y breakeven", BREAKEVEN_10Y),
                        ("5y5y forward inflation", FORWARD_5Y5Y), ("UMich 1y inflation expectation", UMICH_INFL_1Y)]:
        s = latest_series(f"FRED:{sid}")
        if s.empty:
            cells.append(Cell(label=label, note="FRED not configured"))
            continue
        v = s["value"].iloc[-1]
        d5 = diff(s["value"], 5)
        d21 = diff(s["value"], 21) if len(s) >= 21 else None
        slope = trend_slope(s["value"], 21)
        cells.append(Cell(
            label=label, value=v / 100.0, unit="%",
            asof=s.index[-1].date().isoformat(), source=f"FRED:{sid}",
            series_id=f"FRED:{sid}",
            extra={"5d_chg_bp": None if d5 is None else d5 * 100,
                   "21d_chg_bp": None if d21 is None else d21 * 100,
                   "21d_slope": slope},
        ))

    return {"cells": cells, "log": log}
