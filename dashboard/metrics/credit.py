from typing import Dict, List

from ..sources import fred, csv_drop, bloomberg, yfinance_src
from ..storage import latest_series
from ..roc import diff, trend_slope
from ._common import Cell


SERIES = {
    "IG_OAS": "BAMLC0A0CM",
    "BBB_OAS": "BAMLC0A4CBBB",
    "HY_OAS": "BAMLH0A0HYM2",
    "CCC_OAS": "BAMLH0A3HYC",
}
MOVE_BBG = "MOVE Index"
MOVE_YF = "^MOVE"


def _ingest_safe(fn, *a, **k):
    try:
        return f"ok ({fn(*a, **k)} rows)"
    except Exception as e:
        return f"err: {type(e).__name__}: {e}"


def collect() -> Dict:
    log = {}
    for k, v in SERIES.items():
        log[v] = _ingest_safe(fred.ingest, v)
    log["MOVE_BBG"] = _ingest_safe(bloomberg.ingest, MOVE_BBG)
    log["MOVE_YF"] = _ingest_safe(yfinance_src.ingest_close, MOVE_YF, "2y")
    log["MOVE_CSV"] = _ingest_safe(csv_drop.ingest, "move_index")

    cells: List[Cell] = []
    for label, sid in SERIES.items():
        s = latest_series(f"FRED:{sid}")
        if s.empty:
            cells.append(Cell(label=f"{label} (BofA OAS)", note="FRED not configured"))
            continue
        v = s["value"].iloc[-1]
        d1 = diff(s["value"], 1)
        d5 = diff(s["value"], 5)
        d21 = diff(s["value"], 21)
        slope = trend_slope(s["value"], 21)
        cells.append(Cell(
            label=f"{label} (BofA OAS)",
            value=v / 100.0, unit="%",
            asof=s.index[-1].date().isoformat(), source=f"FRED:{sid}",
            series_id=f"FRED:{sid}",
            extra={
                "1d_chg_bp": None if d1 is None else d1 * 100,
                "5d_chg_bp": None if d5 is None else d5 * 100,
                "21d_chg_bp": None if d21 is None else d21 * 100,
                "21d_slope": slope,
            },
        ))

    move_bbg = latest_series(f"BBG:{MOVE_BBG}:PX_LAST")
    move_yf = latest_series(f"YF:{MOVE_YF}:CLOSE")
    move_csv = latest_series("CSV:move_index")
    if not move_bbg.empty:
        src_label, m = "Bloomberg", move_bbg
    elif not move_yf.empty:
        src_label, m = "Yahoo:^MOVE", move_yf
    else:
        src_label, m = "manual_csv", move_csv
    if not m.empty:
        v = m["value"].iloc[-1]
        d1 = diff(m["value"], 1)
        d5 = diff(m["value"], 5)
        d21 = diff(m["value"], 21)
        slope = trend_slope(m["value"], 21)
        cells.append(Cell(
            label="MOVE index (rate vol)",
            value=v, unit="idx",
            asof=m.index[-1].date().isoformat(), source=src_label,
            extra={"1d_chg": d1, "5d_chg": d5, "21d_chg": d21, "21d_slope": slope},
        ))
    else:
        cells.append(Cell(label="MOVE index", note="Bloomberg disabled, ^MOVE unavailable on Yahoo, and no CSV at data/manual/move_index.csv"))

    return {"cells": cells, "log": log}
