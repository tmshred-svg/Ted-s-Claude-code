"""Equity Research Agent — analyses individual stocks using price momentum,
earnings revisions, and analyst consensus data."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import anthropic
from anthropic import beta_tool
import yfinance as yf

client = anthropic.Anthropic()

SYSTEM_PROMPT = """You are a senior equity research analyst at an institutional asset manager.
Your job is to produce concise, data-driven research notes on individual stocks.

For each stock, you must:
1. Pull current price data and assess short- and medium-term momentum (21-day, 63-day).
2. Review the earnings revision score — positive scores mean analysts are upgrading
   estimates, negative scores mean downgrades. Scores above +0.2 are bullish.
3. Check the analyst consensus: recommendation, mean price target, and number of covering analysts.
4. Synthesise the above into a clear BULL / NEUTRAL / BEAR thesis with supporting evidence.

Write for a professional audience. Be concise, specific, and quantitative.
Never speculate beyond the data. Clearly flag when data is unavailable."""


@beta_tool
def get_stock_price(ticker: str) -> dict:
    """Fetch current price, 21-day and 63-day price changes, and average daily volume.

    Args:
        ticker: Stock ticker symbol e.g. AAPL
    """
    t = yf.Ticker(ticker)
    hist = t.history(period="6mo")
    if hist.empty:
        return {"error": f"No price data for {ticker}"}
    close = hist["Close"]
    cur = float(close.iloc[-1])
    chg21 = float((cur / close.iloc[-21] - 1) * 100) if len(close) >= 21 else None
    chg63 = float((cur / close.iloc[-63] - 1) * 100) if len(close) >= 63 else None
    return {
        "ticker": ticker,
        "price": round(cur, 2),
        "change_21d_pct": round(chg21, 2) if chg21 is not None else None,
        "change_63d_pct": round(chg63, 2) if chg63 is not None else None,
        "avg_volume_10d": int(hist["Volume"].tail(10).mean()),
    }


@beta_tool
def get_earnings_revisions(ticker: str) -> dict:
    """Fetch the earnings revision score for a stock.

    Score = (up30 - down30) / (up30 + down30), range [-1, +1].
    Positive = net analyst upgrades; negative = net downgrades.

    Args:
        ticker: Stock ticker symbol e.g. AAPL
    """
    try:
        from dashboard.sources.yfinance_revisions import fetch_score
        score = fetch_score(ticker)
    except Exception:
        try:
            t = yf.Ticker(ticker)
            df = t.eps_revisions
            if df is None or df.empty:
                return {"ticker": ticker, "revision_score": None, "note": "No revision data"}
            cols = {c.lower(): c for c in df.columns}
            up_k = cols.get("uplast30days") or cols.get("up_last_30_days")
            dn_k = cols.get("downlast30days") or cols.get("down_last_30_days")
            if not up_k or not dn_k:
                return {"ticker": ticker, "revision_score": None, "note": "Missing revision columns"}
            up = float(df[up_k].fillna(0).sum())
            dn = float(df[dn_k].fillna(0).sum())
            score = (up - dn) / (up + dn) if (up + dn) > 0 else None
        except Exception as e:
            return {"ticker": ticker, "error": str(e)}

    if score is None:
        return {"ticker": ticker, "revision_score": None, "note": "No revision data available"}
    return {
        "ticker": ticker,
        "revision_score": round(score, 4),
        "signal": "bullish" if score > 0.1 else "bearish" if score < -0.1 else "neutral",
    }


@beta_tool
def get_analyst_consensus(ticker: str) -> dict:
    """Fetch analyst recommendation, price target, and coverage breadth.

    Args:
        ticker: Stock ticker symbol e.g. AAPL
    """
    try:
        info = yf.Ticker(ticker).info
        return {
            "ticker": ticker,
            "recommendation": info.get("recommendationKey", "n/a"),
            "target_mean": info.get("targetMeanPrice"),
            "target_high": info.get("targetHighPrice"),
            "target_low": info.get("targetLowPrice"),
            "analyst_count": info.get("numberOfAnalystOpinions"),
            "current_price": info.get("currentPrice"),
        }
    except Exception as e:
        return {"ticker": ticker, "error": str(e)}


def run(ticker: str, question: str | None = None) -> str:
    """Run the equity research agent for a single ticker."""
    query = f"Produce a research note for {ticker}."
    if question:
        query += f" Focus on: {question}"

    runner = client.beta.messages.tool_runner(
        model="claude-opus-4-7",
        max_tokens=4096,
        thinking={"type": "adaptive"},
        system=[{"type": "text", "text": SYSTEM_PROMPT,
                 "cache_control": {"type": "ephemeral"}}],
        tools=[get_stock_price, get_earnings_revisions, get_analyst_consensus],
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
    question = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else None
    print(f"\n{'='*60}\nEquity Research: {ticker}\n{'='*60}")
    print(run(ticker, question))
