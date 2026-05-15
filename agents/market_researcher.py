"""Market Researcher Agent — surveys broad market conditions: sector-level
price momentum, investor sentiment (put/call, AAII), and asset-class flows."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import anthropic
from anthropic import beta_tool
import yfinance as yf

client = anthropic.Anthropic()

SYSTEM_PROMPT = """You are a market research analyst at a macro hedge fund.
Your job is to build a top-down market outlook by combining three data sources:

  1. Sector performance: which sectors lead and lag the broad market over 21 and 63 days.
  2. Sentiment: put/call ratios and the AAII/II survey — contrarian signals when extreme.
  3. Flows: net flows into equities, bonds, and money-market funds — confirm or deny price trends.

Structure your output as:
  • Market Breadth & Leadership: which sectors are strong, which are weak.
  • Sentiment Positioning: are investors too bullish (risk) or too bearish (opportunity)?
  • Flow Confirmation: do flows support or contradict the price trends?
  • Overall Market Stance: risk-on, risk-off, or selective — with a one-line rationale.

Rely on data. Flag when data is sparse or only partially available."""


SECTOR_ETFS = ["XLK", "XLV", "XLF", "XLY", "XLC", "XLI",
               "XLP", "XLE", "XLU", "XLRE", "XLB"]

SECTOR_NAMES = {
    "XLK": "Technology", "XLV": "Healthcare", "XLF": "Financials",
    "XLY": "Consumer Discretionary", "XLC": "Communication Services",
    "XLI": "Industrials", "XLP": "Consumer Staples", "XLE": "Energy",
    "XLU": "Utilities", "XLRE": "Real Estate", "XLB": "Materials",
}


@beta_tool
def get_sector_performance(benchmark: str = "SPY") -> dict:
    """Fetch 21-day and 63-day return for all 11 S&P 500 sector ETFs vs the benchmark.

    Returns a ranked table from strongest to weakest relative performance.

    Args:
        benchmark: Benchmark ticker, default SPY
    """
    tickers = SECTOR_ETFS + [benchmark]
    try:
        data = yf.download(tickers, period="6mo", progress=False, auto_adjust=True)
        closes = data["Close"] if "Close" in data.columns else data.xs("Close", axis=1, level=0)
        bench = closes[benchmark].dropna()

        rows = []
        for etf in SECTOR_ETFS:
            if etf not in closes.columns:
                continue
            s = closes[etf].dropna()
            ret21 = float(s.iloc[-1] / s.iloc[-21] - 1) if len(s) >= 21 else None
            ret63 = float(s.iloc[-1] / s.iloc[-63] - 1) if len(s) >= 63 else None
            b21 = float(bench.iloc[-1] / bench.iloc[-21] - 1) if len(bench) >= 21 else None
            b63 = float(bench.iloc[-1] / bench.iloc[-63] - 1) if len(bench) >= 63 else None
            rows.append({
                "etf": etf,
                "sector": SECTOR_NAMES.get(etf, etf),
                "return_21d_pct": round(ret21 * 100, 2) if ret21 is not None else None,
                "return_63d_pct": round(ret63 * 100, 2) if ret63 is not None else None,
                "vs_benchmark_21d": round((ret21 - b21) * 100, 2)
                    if ret21 is not None and b21 is not None else None,
                "vs_benchmark_63d": round((ret63 - b63) * 100, 2)
                    if ret63 is not None and b63 is not None else None,
            })

        rows.sort(key=lambda r: r["vs_benchmark_63d"] or float("-inf"), reverse=True)
        n = len(rows)
        cut = max(1, n // 3)
        for i, r in enumerate(rows):
            r["tier"] = "strong" if i < cut else "weak" if i >= n - cut else "neutral"

        return {"benchmark": benchmark, "sectors": rows, "count": n}
    except Exception as e:
        return {"error": str(e)}


@beta_tool
def get_sentiment_data() -> dict:
    """Fetch sentiment indicators from the dashboard database.

    Covers put/call ratio and AAII/Investors Intelligence bull-bear spreads.
    Extreme readings are contrarian signals.
    """
    def read(series_id: str) -> dict:
        try:
            from dashboard.storage import latest_series
            s = latest_series(series_id, limit=63)
            if s.empty:
                return {"available": False}
            latest = float(s["value"].iloc[-1])
            avg = float(s["value"].mean())
            return {
                "available": True,
                "latest": round(latest, 4),
                "63d_avg": round(avg, 4),
                "vs_avg": round(latest - avg, 4),
            }
        except Exception:
            return {"available": False}

    candidates = {
        "put_call_ratio": ["CBOE:PCR", "PCR", "PUT_CALL"],
        "aaii_bull_bear": ["AAII:BULL_BEAR", "AAII", "SENTIMENT:AAII"],
        "ii_bull_bear": ["II:BULL_BEAR", "II", "SENTIMENT:II"],
    }
    results = {}
    for label, ids in candidates.items():
        for sid in ids:
            r = read(sid)
            if r.get("available"):
                results[label] = {**r, "series_id": sid}
                break
        else:
            results[label] = {"available": False, "tried": ids}

    return results


@beta_tool
def get_flow_data() -> dict:
    """Fetch asset-class flow data from the dashboard database.

    Covers equity, bond, and money-market fund flows. Positive = inflows.
    """
    def read(series_id: str) -> dict:
        try:
            from dashboard.storage import latest_series
            s = latest_series(series_id, limit=63)
            if s.empty:
                return {"available": False}
            latest = float(s["value"].iloc[-1])
            cumulative_4w = float(s["value"].tail(4).sum())
            return {
                "available": True,
                "latest": round(latest, 2),
                "cumulative_4w": round(cumulative_4w, 2),
            }
        except Exception:
            return {"available": False}

    candidates = {
        "equity_flows": ["FLOWS:EQUITY", "EQUITY:FLOW", "ICI:EQUITY"],
        "bond_flows": ["FLOWS:BOND", "BOND:FLOW", "ICI:BOND"],
        "money_market_flows": ["FLOWS:MMF", "MMF:FLOW", "ICI:MMF"],
    }
    results = {}
    for label, ids in candidates.items():
        for sid in ids:
            r = read(sid)
            if r.get("available"):
                results[label] = {**r, "series_id": sid}
                break
        else:
            results[label] = {"available": False, "tried": ids}

    return results


@beta_tool
def get_market_breadth(index: str = "SPY") -> dict:
    """Fetch broad market price trend data for the main index.

    Returns 21-day, 63-day, and 252-day returns to characterise the trend.

    Args:
        index: Index ETF ticker, default SPY
    """
    try:
        hist = yf.Ticker(index).history(period="2y")
        if hist.empty:
            return {"error": f"No data for {index}"}
        close = hist["Close"]
        cur = float(close.iloc[-1])
        ret = lambda n: round(float(cur / close.iloc[-n] - 1) * 100, 2) if len(close) >= n else None
        return {
            "index": index,
            "price": round(cur, 2),
            "return_21d_pct": ret(21),
            "return_63d_pct": ret(63),
            "return_252d_pct": ret(252),
            "trend": ("uptrend" if (ret(21) or 0) > 0 and (ret(63) or 0) > 0
                      else "downtrend" if (ret(21) or 0) < 0 and (ret(63) or 0) < 0
                      else "mixed"),
        }
    except Exception as e:
        return {"error": str(e)}


def run(question: str = "Provide a comprehensive market research overview.") -> str:
    """Run the market researcher agent."""
    runner = client.beta.messages.tool_runner(
        model="claude-opus-4-7",
        max_tokens=4096,
        thinking={"type": "adaptive"},
        system=[{"type": "text", "text": SYSTEM_PROMPT,
                 "cache_control": {"type": "ephemeral"}}],
        tools=[get_sector_performance, get_sentiment_data, get_flow_data, get_market_breadth],
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
        "Provide a comprehensive market research overview covering sector leadership, sentiment, and flows."
    print(f"\n{'='*60}\nMarket Researcher\n{'='*60}")
    print(run(question))
