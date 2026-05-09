from typing import Dict, List

from ..sources import fred, csv_drop, bloomberg
from ..storage import latest_series, revision_count
from ..roc import diff, trend_slope
from ._common import Cell


US_REAL_GDP_LEVEL = "GDPC1"
US_REAL_GDP_QOQ_SAAR = "A191RL1Q225SBEA"
US_GDP_NOWCAST_ATL = "GDPNOW"
GLOBAL_GDP_NOWCAST_BBG = "WLDGDPNW Index"


def _ingest_safe(fn, *args, **kw) -> str:
    try:
        n = fn(*args, **kw)
        return f"ok ({n} rows)"
    except Exception as e:
        return f"err: {type(e).__name__}: {e}"


def collect() -> Dict[str, List[Cell]]:
    log = {}
    log[US_REAL_GDP_LEVEL] = _ingest_safe(fred.ingest, US_REAL_GDP_LEVEL)
    log[US_REAL_GDP_QOQ_SAAR] = _ingest_safe(fred.ingest, US_REAL_GDP_QOQ_SAAR)
    log[US_GDP_NOWCAST_ATL] = _ingest_safe(fred.ingest, US_GDP_NOWCAST_ATL)
    log["GlobalGDP_BBG"] = _ingest_safe(bloomberg.ingest, GLOBAL_GDP_NOWCAST_BBG)
    log["GlobalGDP_CSV"] = _ingest_safe(csv_drop.ingest, "global_gdp_nowcast")

    cells: List[Cell] = []

    qoq = latest_series(f"FRED:{US_REAL_GDP_QOQ_SAAR}")
    if not qoq.empty:
        last = qoq["value"].iloc[-1]
        prev = qoq["value"].iloc[-2] if len(qoq) >= 2 else None
        slope = trend_slope(qoq["value"], 8)
        cells.append(Cell(
            label="US Real GDP, QoQ SAAR (latest)",
            value=last / 100.0, unit="%",
            asof=qoq.index[-1].date().isoformat(), source="FRED:A191RL1Q225SBEA",
            series_id=f"FRED:{US_REAL_GDP_QOQ_SAAR}",
        ))
        if prev is not None:
            cells.append(Cell(
                label="US Real GDP QoQ — change vs prior print",
                value=(last - prev) / 100.0, unit="%",
                asof=qoq.index[-1].date().isoformat(), source="FRED",
            ))
        cells.append(Cell(
            label="US Real GDP QoQ — 8q linear slope",
            value=slope, unit="",
            asof=qoq.index[-1].date().isoformat(), source="FRED",
            note="positive=accelerating",
        ))
    else:
        cells.append(Cell(label="US Real GDP, QoQ SAAR", note="FRED not configured"))

    revs = revision_count(f"FRED:{US_REAL_GDP_LEVEL}")
    if not revs.empty:
        revised = int((revs["revs"] > 0).sum())
        total = int(len(revs))
        ratio = revised / total if total else None
        cells.append(Cell(
            label="US GDP revision ratio (locally observed prints)",
            value=ratio, unit="ratio",
            asof=revs.index[-1].date().isoformat(), source="FRED (local history)",
            note=f"{revised}/{total} prints revised since first capture",
        ))
    else:
        cells.append(Cell(label="US GDP revision ratio", note="need >=2 captures to compute"))

    nowcast = latest_series(f"FRED:{US_GDP_NOWCAST_ATL}")
    if not nowcast.empty:
        cells.append(Cell(
            label="Atlanta Fed GDPNow nowcast",
            value=nowcast["value"].iloc[-1] / 100.0, unit="%",
            asof=nowcast.index[-1].date().isoformat(), source="FRED:GDPNOW",
            series_id=f"FRED:{US_GDP_NOWCAST_ATL}",
        ))
    else:
        cells.append(Cell(label="Atlanta Fed GDPNow", note="FRED not configured"))

    g_bbg = latest_series(f"BBG:{GLOBAL_GDP_NOWCAST_BBG}:PX_LAST")
    g_csv = latest_series("CSV:global_gdp_nowcast")
    g = g_bbg if not g_bbg.empty else g_csv
    if not g.empty:
        cells.append(Cell(
            label="Global GDP nowcast",
            value=g["value"].iloc[-1] / 100.0, unit="%",
            asof=g.index[-1].date().isoformat(),
            source="Bloomberg" if not g_bbg.empty else "manual_csv",
        ))
    else:
        cells.append(Cell(
            label="Global GDP nowcast",
            note="Bloomberg disabled and no CSV at data/manual/global_gdp_nowcast.csv",
        ))

    return {"cells": cells, "log": log}
