from typing import Dict, List

from ..sources import fred, treasury, csv_drop, bloomberg
from ..storage import latest_series
from ..roc import diff, pct_change, trend_slope
from ._common import Cell


FED_BS = "WALCL"          # millions
RRP = "RRPONTSYD"         # billions
M2 = "M2SL"
ECB_BS_FRED = "ECBASSETSW"  # ECB total assets, millions EUR
BOJ_BS_BBG = "BJACTOTL Index"
PBOC_BS_BBG = "PBCRTOTA Index"


def _ingest_safe(fn, *a, **k):
    try:
        return f"ok ({fn(*a, **k)} rows)"
    except Exception as e:
        return f"err: {type(e).__name__}: {e}"


def collect() -> Dict:
    log = {}
    log[FED_BS] = _ingest_safe(fred.ingest, FED_BS)
    log[RRP] = _ingest_safe(fred.ingest, RRP)
    log[M2] = _ingest_safe(fred.ingest, M2)
    log[ECB_BS_FRED] = _ingest_safe(fred.ingest, ECB_BS_FRED)
    log["TGA"] = _ingest_safe(treasury.ingest_tga)
    log["BOJ_BBG"] = _ingest_safe(bloomberg.ingest, BOJ_BS_BBG)
    log["PBOC_BBG"] = _ingest_safe(bloomberg.ingest, PBOC_BS_BBG)
    log["BOJ_CSV"] = _ingest_safe(csv_drop.ingest, "boj_balance_sheet")
    log["PBOC_CSV"] = _ingest_safe(csv_drop.ingest, "pboc_balance_sheet")

    cells: List[Cell] = []

    fed = latest_series(f"FRED:{FED_BS}")
    rrp = latest_series(f"FRED:{RRP}")
    tga = latest_series("TREAS:TGA_BAL")

    if not fed.empty:
        v = fed["value"].iloc[-1] * 1e6
        c4 = pct_change(fed["value"], 4)
        c13 = pct_change(fed["value"], 13)
        slope = trend_slope(fed["value"], 13)
        cells.append(Cell(
            label="Fed balance sheet (WALCL)",
            value=v, unit="$bn",
            asof=fed.index[-1].date().isoformat(), source="FRED:WALCL",
            extra={"4w_chg": c4, "13w_chg": c13, "13w_slope": slope},
        ))
    else:
        cells.append(Cell(label="Fed balance sheet", note="FRED not configured"))

    if not rrp.empty:
        v = rrp["value"].iloc[-1] * 1e9
        d5 = diff(rrp["value"], 5)
        cells.append(Cell(
            label="Fed ON RRP balance",
            value=v, unit="$bn",
            asof=rrp.index[-1].date().isoformat(), source="FRED:RRPONTSYD",
            extra={"5d_chg_$bn": None if d5 is None else d5},
        ))
    else:
        cells.append(Cell(label="Fed ON RRP", note="FRED not configured"))

    if not tga.empty:
        v = tga["value"].iloc[-1] * 1e6
        d5 = diff(tga["value"], 5)
        cells.append(Cell(
            label="Treasury General Account (TGA)",
            value=v, unit="$bn",
            asof=tga.index[-1].date().isoformat(), source="USTreasury",
            extra={"5d_chg_$mm": None if d5 is None else d5},
        ))
    else:
        cells.append(Cell(label="TGA", note="Treasury fetch failed"))

    if not fed.empty and not rrp.empty and not tga.empty:
        idx = fed.index.intersection(tga.index).intersection(rrp.index)
        if len(idx) >= 2:
            net = (fed.loc[idx, "value"] * 1e6
                   - rrp.loc[idx, "value"] * 1e9
                   - tga.loc[idx, "value"] * 1e6)
            v = float(net.iloc[-1])
            d5 = diff(net, 5)
            slope = trend_slope(net, 21)
            cells.append(Cell(
                label="US net liquidity (Fed BS - RRP - TGA)",
                value=v, unit="$bn",
                asof=idx[-1].date().isoformat(), source="derived",
                extra={"5d_chg_$": d5, "21d_slope": slope},
            ))

    ecb = latest_series(f"FRED:{ECB_BS_FRED}")
    if not ecb.empty:
        v = ecb["value"].iloc[-1] * 1e6
        c4 = pct_change(ecb["value"], 4)
        cells.append(Cell(
            label="ECB total assets",
            value=v, unit="$bn",
            asof=ecb.index[-1].date().isoformat(), source="FRED:ECBASSETSW",
            note="EUR not USD",
            extra={"4w_chg": c4},
        ))
    else:
        cells.append(Cell(label="ECB total assets", note="FRED not configured"))

    for label, key, csv_id in [("BOJ balance sheet", f"BBG:{BOJ_BS_BBG}:PX_LAST", "boj_balance_sheet"),
                                ("PBOC balance sheet", f"BBG:{PBOC_BS_BBG}:PX_LAST", "pboc_balance_sheet")]:
        s = latest_series(key)
        if s.empty:
            s = latest_series(f"CSV:{csv_id}")
        if s.empty:
            cells.append(Cell(label=label, note=f"Bloomberg disabled and no CSV at data/manual/{csv_id}.csv"))
            continue
        cells.append(Cell(
            label=label, value=float(s["value"].iloc[-1]), unit="",
            asof=s.index[-1].date().isoformat(), source="Bloomberg/CSV",
            extra={"4w_chg": pct_change(s["value"], 4)},
        ))

    return {"cells": cells, "log": log}
