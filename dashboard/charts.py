"""Build chart payloads from SQLite history for the HTML report."""
import json
from typing import Dict, List

import pandas as pd

from .sparkline import panel_svg
from .storage import latest_series


def _pairs(df: pd.DataFrame, max_points: int = 2500) -> List[List]:
    if df is None or df.empty:
        return []
    s = df["value"].dropna()
    if len(s) > max_points:
        step = max(1, len(s) // max_points)
        s = s.iloc[::step]
    return [[idx.strftime("%Y-%m-%d"), float(v)] for idx, v in s.items()]


def _yoy_pairs(df: pd.DataFrame, periods: int = 12) -> List[List]:
    if df is None or df.empty:
        return []
    s = df["value"].dropna().pct_change(periods).dropna() * 100.0
    return [[idx.strftime("%Y-%m-%d"), float(v)] for idx, v in s.items()]


def _scaled_pairs(df: pd.DataFrame, factor: float) -> List[List]:
    if df is None or df.empty:
        return []
    s = df["value"].dropna() * factor
    return [[idx.strftime("%Y-%m-%d"), float(v)] for idx, v in s.items()]


def build() -> Dict[str, List[Dict]]:
    p: Dict[str, List[Dict]] = {}

    p["gdp"] = []
    for label, sid in [("US Real GDP QoQ SAAR (%)", "A191RL1Q225SBEA"),
                        ("Atlanta Fed GDPNow (%)", "GDPNOW")]:
        s = latest_series(f"FRED:{sid}")
        if not s.empty:
            p["gdp"].append({"label": label, "data": _pairs(s)})

    p["credit"] = []
    for label, sid in [("IG OAS (%)", "BAMLC0A0CM"),
                        ("BBB OAS (%)", "BAMLC0A4CBBB"),
                        ("HY OAS (%)", "BAMLH0A0HYM2"),
                        ("CCC OAS (%)", "BAMLH0A3HYC")]:
        s = latest_series(f"FRED:{sid}")
        if not s.empty:
            p["credit"].append({"label": label, "data": _pairs(s)})

    p["move"] = []
    for label, key in [("MOVE (Yahoo ^MOVE)", "YF:^MOVE:CLOSE"),
                        ("MOVE (Bloomberg)", "BBG:MOVE Index:PX_LAST"),
                        ("MOVE (manual CSV)", "CSV:move_index")]:
        s = latest_series(key)
        if not s.empty:
            p["move"].append({"label": label, "data": _pairs(s)})

    p["inflation_yoy"] = []
    for label, sid in [("Headline CPI YoY (%)", "CPIAUCSL"),
                        ("Core CPI YoY (%)", "CPILFESL"),
                        ("Headline PCE YoY (%)", "PCEPI"),
                        ("Core PCE YoY (%)", "PCEPILFE")]:
        s = latest_series(f"FRED:{sid}")
        if not s.empty:
            p["inflation_yoy"].append({"label": label, "data": _yoy_pairs(s, 12)})

    p["expectations"] = []
    for label, sid in [("5y breakeven (%)", "T5YIE"),
                        ("10y breakeven (%)", "T10YIE"),
                        ("5y5y forward (%)", "T5YIFR"),
                        ("UMich 1y expectation (%)", "MICH")]:
        s = latest_series(f"FRED:{sid}")
        if not s.empty:
            p["expectations"].append({"label": label, "data": _pairs(s)})

    p["liquidity"] = []
    fed = latest_series("FRED:WALCL")
    if not fed.empty:
        p["liquidity"].append({"label": "Fed BS ($bn)", "data": _scaled_pairs(fed, 1 / 1000.0)})
    rrp = latest_series("FRED:RRPONTSYD")
    if not rrp.empty:
        p["liquidity"].append({"label": "Fed ON RRP ($bn)", "data": _pairs(rrp)})
    tga = latest_series("TREAS:TGA_BAL")
    if not tga.empty:
        p["liquidity"].append({"label": "TGA ($bn, DTS)", "data": _scaled_pairs(tga, 1 / 1000.0)})
    else:
        tga_fred = latest_series("FRED:WTREGEN")
        if not tga_fred.empty:
            p["liquidity"].append({"label": "TGA ($bn, FRED WTREGEN)", "data": _pairs(tga_fred)})
    ecb = latest_series("FRED:ECBASSETSW")
    if not ecb.empty:
        p["liquidity"].append({"label": "ECB total assets (€bn)", "data": _scaled_pairs(ecb, 1 / 1000.0)})
    m2 = latest_series("FRED:M2SL")
    if not m2.empty:
        p["liquidity"].append({"label": "US M2 ($bn)", "data": _pairs(m2)})

    p["sentiment"] = []
    pc = latest_series("CBOE:EQUITY_PC")
    if not pc.empty:
        p["sentiment"].append({"label": "CBOE equity put/call", "data": _pairs(pc)})
    pc_yf = latest_series("YF:^CPC:CLOSE")
    if not pc_yf.empty:
        p["sentiment"].append({"label": "CBOE total put/call (^CPC)", "data": _pairs(pc_yf)})
    vix = latest_series("FRED:VIXCLS")
    if not vix.empty:
        p["sentiment"].append({"label": "VIX", "data": _pairs(vix)})

    p["sectors"] = []
    sector_etfs = ["XLK", "XLF", "XLE", "XLY", "XLP", "XLI", "XLV", "XLB", "XLU", "XLRE", "XLC", "SPY"]
    for t in sector_etfs:
        s = latest_series(f"YF:{t}:CLOSE")
        if not s.empty:
            base = s["value"].dropna()
            if len(base) >= 2:
                base_val = float(base.iloc[0])
                norm = base / base_val * 100.0
                pairs = [[idx.strftime("%Y-%m-%d"), float(v)] for idx, v in norm.items()]
                p["sectors"].append({"label": t, "data": pairs})

    p["asset_classes"] = []
    asset_etfs = ["SPY", "IWM", "IEF", "TLT", "LQD", "HYG", "DBC", "GLD", "USO", "UUP"]
    for t in asset_etfs:
        s = latest_series(f"YF:{t}:CLOSE")
        if not s.empty:
            base = s["value"].dropna()
            if len(base) >= 2:
                base_val = float(base.iloc[0])
                norm = base / base_val * 100.0
                pairs = [[idx.strftime("%Y-%m-%d"), float(v)] for idx, v in norm.items()]
                p["asset_classes"].append({"label": t, "data": pairs})

    return p


def to_json(payload: Dict) -> str:
    return json.dumps(payload, separators=(",", ":"))


PANEL_TITLES = {
    "gdp": "GDP nowcasts & QoQ SAAR (%)",
    "credit": "Corporate OAS (%)",
    "move": "Rate volatility — MOVE",
    "inflation_yoy": "Inflation YoY (%)",
    "expectations": "Inflation expectations (%)",
    "liquidity": "Liquidity ($bn / €bn)",
    "sentiment": "Sentiment",
    "sectors": "Sector ETFs (rebased=100)",
    "asset_classes": "Asset-class ETFs (rebased=100)",
}


def to_svgs(payload: Dict) -> Dict[str, str]:
    """Render each chart panel to an inline SVG. Keys with no data are omitted."""
    out: Dict[str, str] = {}
    for key, series in payload.items():
        if not series:
            continue
        out[key] = panel_svg(series, title=PANEL_TITLES.get(key, key))
    return out


def to_individual_svgs(payload: Dict) -> Dict[str, List[Dict[str, str]]]:
    """Render every series as its own inline SVG so each data point has a chart.

    Returns {section_key: [{label, svg}, ...]}. Sections with no data are omitted.
    """
    out: Dict[str, List[Dict[str, str]]] = {}
    for key, series in payload.items():
        if not series:
            continue
        out[key] = [
            {"label": s.get("label", ""),
             "svg": panel_svg([s], title=s.get("label", ""), width=560, height=200)}
            for s in series
        ]
    return out
