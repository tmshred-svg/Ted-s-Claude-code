"""Equity Reviewer Agent — scores stocks against the dashboard's quantitative
screens (relative strength, sector rank, earnings revisions) and delivers
a pass/fail verdict with supporting data."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import anthropic
from anthropic import beta_tool
import yfinance as yf
import numpy as np

client = anthropic.Anthropic()

SYSTEM_PROMPT = """You are a quantitative equity reviewer at a systematic hedge fund.
Your job is to evaluate stocks against three deterministic screens:

  1. Relative Strength (63-day): stock return vs benchmark return. Must be in
     the top quartile of the universe (≥75th percentile) to qualify.
  2. Sector Rank: the stock's sector ETF must rank in the top third of all
     sector ETFs by 63-day relative strength (a "strong sector").
  3. Earnings Revisions: the 30-day net revision score must have improved over
     the past 21 trading days (current score > score 21 days ago).

Return a structured verdict:
  - PASS: all three criteria met — candidate for long consideration.
  - PARTIAL (n/3): one or two criteria met — list which failed and why.
  - FAIL: none or only one criterion met.

Be precise about the numbers. Do not add qualitative opinion beyond the data."""


@beta_tool
def get_relative_strength(ticker: str, benchmark: str = "SPY", period: str = "6mo") -> dict:
    """Compute the 63-day price return of a ticker vs a benchmark.

    Args:
        ticker: Stock ticker symbol e.g. AAPL
        benchmark: Benchmark ticker, default SPY
        period: yfinance period string for historical data download
    """
    try:
        data = yf.download([ticker, benchmark], period=period, progress=False, auto_adjust=True)
        closes = data["Close"] if "Close" in data.columns else data.xs("Close", axis=1, level=0)
        if ticker not in closes.columns or benchmark not in closes.columns:
            return {"error": f"Missing data for {ticker} or {benchmark}"}
        t_close = closes[ticker].dropna()
        b_close = closes[benchmark].dropna()
        if len(t_close) < 63 or len(b_close) < 63:
            return {"ticker": ticker, "relative_strength_63d": None,
                    "note": f"Only {min(len(t_close), len(b_close))} days of data — need 63"}
        t_ret = float(t_close.iloc[-1] / t_close.iloc[-63] - 1)
        b_ret = float(b_close.iloc[-1] / b_close.iloc[-63] - 1)
        return {
            "ticker": ticker,
            "benchmark": benchmark,
            "stock_return_63d_pct": round(t_ret * 100, 2),
            "benchmark_return_63d_pct": round(b_ret * 100, 2),
            "relative_strength_63d": round(t_ret - b_ret, 4),
        }
    except Exception as e:
        return {"ticker": ticker, "error": str(e)}


@beta_tool
def get_sector_rank(sector_etf: str, benchmark: str = "SPY",
                    peer_etfs: list[str] | None = None) -> dict:
    """Rank a sector ETF against a peer set by 63-day relative strength.

    Args:
        sector_etf: The sector ETF to evaluate e.g. XLK
        benchmark: Benchmark ticker for relative-strength calc, default SPY
        peer_etfs: List of all sector ETFs to rank against. Defaults to the
                   11 S&P 500 sector ETFs.
    """
    if peer_etfs is None:
        peer_etfs = ["XLK", "XLV", "XLF", "XLY", "XLC", "XLI",
                     "XLP", "XLE", "XLU", "XLRE", "XLB"]
    all_tickers = list({sector_etf, benchmark} | set(peer_etfs))
    try:
        data = yf.download(all_tickers, period="6mo", progress=False, auto_adjust=True)
        closes = data["Close"] if "Close" in data.columns else data.xs("Close", axis=1, level=0)
        bench = closes[benchmark].dropna()
        rs_map = {}
        for etf in peer_etfs:
            if etf not in closes.columns:
                continue
            s = closes[etf].dropna()
            if len(s) >= 63 and len(bench) >= 63:
                rs_map[etf] = float(s.iloc[-1] / s.iloc[-63] - 1) - \
                               float(bench.iloc[-1] / bench.iloc[-63] - 1)
        if not rs_map:
            return {"error": "Insufficient data to rank sectors"}
        sorted_etfs = sorted(rs_map.items(), key=lambda x: x[1], reverse=True)
        n = len(sorted_etfs)
        rank = next((i + 1 for i, (e, _) in enumerate(sorted_etfs) if e == sector_etf), None)
        tercile_cut = max(1, n // 3)
        return {
            "sector_etf": sector_etf,
            "rank": rank,
            "total_peers": n,
            "rs_63d": round(rs_map.get(sector_etf, float("nan")), 4),
            "strong_sector": rank is not None and rank <= tercile_cut,
            "tercile_threshold": tercile_cut,
            "rankings": [{"etf": e, "rs_63d": round(v, 4)} for e, v in sorted_etfs],
        }
    except Exception as e:
        return {"sector_etf": sector_etf, "error": str(e)}


@beta_tool
def get_revision_trend(ticker: str) -> dict:
    """Check whether earnings revision score has improved over the past 21 trading days.

    Requires at least two data points from the local dashboard database.
    Falls back to a live yfinance snapshot if the database is unavailable.

    Args:
        ticker: Stock ticker symbol e.g. AAPL
    """
    try:
        from dashboard.storage import latest_series
        from dashboard.sources.yfinance_revisions import fetch_score as live_score
        revs = latest_series(f"REVS:{ticker}")
        if revs.empty:
            revs = latest_series(f"CSV:revisions_{ticker}")
        if revs.empty:
            score_now = live_score(ticker)
            return {
                "ticker": ticker,
                "current_score": round(score_now, 4) if score_now is not None else None,
                "score_21d_ago": None,
                "improving": None,
                "note": "Only live snapshot available — no 21-day history in database",
            }
        score_now = float(revs["value"].iloc[-1])
        score_21d = float(revs["value"].iloc[max(0, len(revs) - 22)])
        return {
            "ticker": ticker,
            "current_score": round(score_now, 4),
            "score_21d_ago": round(score_21d, 4),
            "change_21d": round(score_now - score_21d, 4),
            "improving": score_now > score_21d,
        }
    except Exception as e:
        return {"ticker": ticker, "error": str(e)}


def run(ticker: str, sector_etf: str | None = None) -> str:
    """Run the equity reviewer agent for a stock.

    Args:
        ticker: Stock ticker to review
        sector_etf: Optional sector ETF for the stock (e.g. XLK for tech)
    """
    query = f"Review {ticker}"
    if sector_etf:
        query += f" (sector ETF: {sector_etf})"
    query += (" against the three screens: relative strength, sector rank, "
              "and earnings revision trend. Return a PASS / PARTIAL / FAIL verdict.")

    runner = client.beta.messages.tool_runner(
        model="claude-opus-4-7",
        max_tokens=2048,
        thinking={"type": "adaptive"},
        system=[{"type": "text", "text": SYSTEM_PROMPT,
                 "cache_control": {"type": "ephemeral"}}],
        tools=[get_relative_strength, get_sector_rank, get_revision_trend],
        messages=[{"role": "user", "content": query}],
    )
    result = ""
    for msg in runner:
        for block in msg.content:
            if block.type == "text":
                result = block.text
    return result


if __name__ == "__main__":
    ticker = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
    sector_etf = sys.argv[2] if len(sys.argv) > 2 else None
    print(f"\n{'='*60}\nEquity Reviewer: {ticker}\n{'='*60}")
    print(run(ticker, sector_etf))
