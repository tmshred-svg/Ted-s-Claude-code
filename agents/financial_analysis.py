"""Financial Analysis Agent — interprets macroeconomic data stored in the
dashboard database: GDP nowcasts, credit spreads, inflation metrics, and
central-bank liquidity indicators."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import anthropic
from anthropic import beta_tool

client = anthropic.Anthropic()

SYSTEM_PROMPT = """You are a macro financial analyst at a multi-asset investment firm.
Your job is to synthesise economic indicator data into a clear market outlook.

You have access to four categories of data stored in the dashboard database:
  • GDP: real-time nowcasts and revision history.
  • Credit: investment-grade OAS, high-yield spread, BBB-rated corporate spread.
  • Inflation: CPI, PCE, 5-year breakeven, 10-year breakeven, inflation expectations surveys.
  • Liquidity: Fed balance sheet, reverse repo (RRP), Treasury General Account (TGA).

When analysing:
1. Pull the latest value and compare it to 21-day and 63-day prior readings.
2. Classify the trend: improving / stable / deteriorating.
3. Flag any readings at historically extreme levels.
4. Conclude with a one-paragraph macro risk summary: risk-on, risk-off, or mixed.

Use basis points for spread changes. Cite specific numbers from the data."""


def _read_series(series_id: str, lookback: int = 90) -> dict:
    """Helper to pull a series from the local database."""
    try:
        from dashboard.storage import latest_series
        s = latest_series(series_id, limit=lookback)
        if s.empty:
            return {"series_id": series_id, "available": False}
        latest = float(s["value"].iloc[-1])
        ago21 = float(s["value"].iloc[-21]) if len(s) >= 21 else None
        ago63 = float(s["value"].iloc[-63]) if len(s) >= 63 else None
        return {
            "series_id": series_id,
            "available": True,
            "latest": round(latest, 4),
            "chg_21d": round(latest - ago21, 4) if ago21 is not None else None,
            "chg_63d": round(latest - ago63, 4) if ago63 is not None else None,
            "date": str(s["date"].iloc[-1]) if "date" in s.columns else None,
            "obs_count": len(s),
        }
    except Exception as e:
        return {"series_id": series_id, "available": False, "error": str(e)}


@beta_tool
def get_gdp_data() -> dict:
    """Fetch GDP nowcast data from the dashboard database.

    Returns the latest GDP nowcast value and 21-day / 63-day changes.
    Series IDs typically follow the pattern used by the gdp.py ingester.
    """
    candidates = ["GDPNOW", "GDP:NOW", "NOWCAST:GDP", "GDP_NOW"]
    for sid in candidates:
        r = _read_series(sid)
        if r.get("available"):
            return r
    return {"available": False, "note": "No GDP nowcast series found in database",
            "tried": candidates}


@beta_tool
def get_credit_spreads() -> dict:
    """Fetch credit-spread data: investment-grade OAS, high-yield spread, BBB spread.

    Returns latest values and trend for each series stored in the database.
    """
    series_map = {
        "IG_OAS": ["IG:OAS", "BAMLC0A0CM", "OAS:IG"],
        "HY_spread": ["HY:SPREAD", "BAMLH0A0HYM2", "SPREAD:HY"],
        "BBB_OAS": ["BBB:OAS", "BAMLC0A4CBBB", "OAS:BBB"],
    }
    results = {}
    for label, candidates in series_map.items():
        for sid in candidates:
            r = _read_series(sid)
            if r.get("available"):
                results[label] = r
                break
        else:
            results[label] = {"available": False, "tried": candidates}
    return results


@beta_tool
def get_inflation_data() -> dict:
    """Fetch inflation metrics: CPI, PCE, 5yr breakeven, 10yr breakeven.

    Returns latest values and trend for each series.
    """
    series_map = {
        "CPI_YoY": ["CPI:YOY", "CPIAUCSL", "CPI"],
        "PCE_YoY": ["PCE:YOY", "PCEPI", "PCE"],
        "breakeven_5y": ["BREAKEVEN:5Y", "T5YIE", "BE5Y"],
        "breakeven_10y": ["BREAKEVEN:10Y", "T10YIE", "BE10Y"],
    }
    results = {}
    for label, candidates in series_map.items():
        for sid in candidates:
            r = _read_series(sid)
            if r.get("available"):
                results[label] = r
                break
        else:
            results[label] = {"available": False, "tried": candidates}
    return results


@beta_tool
def get_liquidity_data() -> dict:
    """Fetch central-bank liquidity indicators: Fed balance sheet, RRP, TGA.

    Changes in RRP and TGA affect net system liquidity even when the Fed balance
    sheet is flat. Net liquidity = Fed BS - RRP - TGA.
    """
    series_map = {
        "fed_balance_sheet": ["FED:BS", "WALCL", "FED_BS"],
        "rrp": ["FED:RRP", "RRPONTSYD", "RRP"],
        "tga": ["TREASURY:TGA", "WDTGAL", "TGA"],
    }
    results = {}
    for label, candidates in series_map.items():
        for sid in candidates:
            r = _read_series(sid)
            if r.get("available"):
                results[label] = r
                break
        else:
            results[label] = {"available": False, "tried": candidates}

    fed = results.get("fed_balance_sheet", {})
    rrp = results.get("rrp", {})
    tga = results.get("tga", {})
    if all(d.get("available") for d in [fed, rrp, tga]):
        net = fed["latest"] - rrp["latest"] - tga["latest"]
        results["net_liquidity_estimate"] = round(net, 2)

    return results


def run(question: str = "Provide a full macro financial analysis.") -> str:
    """Run the financial analysis agent with an optional question."""
    runner = client.beta.messages.tool_runner(
        model="claude-opus-4-7",
        max_tokens=4096,
        thinking={"type": "adaptive"},
        system=[{"type": "text", "text": SYSTEM_PROMPT,
                 "cache_control": {"type": "ephemeral"}}],
        tools=[get_gdp_data, get_credit_spreads, get_inflation_data, get_liquidity_data],
        messages=[{"role": "user", "content": question}],
    )
    result = ""
    for msg in runner:
        for block in msg.content:
            if block.type == "text":
                result = block.text
    return result


if __name__ == "__main__":
    question = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else \
        "Provide a full macro financial analysis covering GDP, credit, inflation, and liquidity."
    print(f"\n{'='*60}\nFinancial Analysis\n{'='*60}")
    print(run(question))
