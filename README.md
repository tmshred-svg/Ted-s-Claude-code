# Economic Metrics Dashboard

Daily HTML report covering: global & US GDP (with revision ratios), credit spreads, MOVE, inflation & inflation expectations, global liquidity, sector/asset flows, sentiment (put/call, AAII/II), and screens for strong stocks in strong sectors and strong stocks in weak sectors.

Every value carries a source and timestamp. If a source is not configured or returns no data, the cell renders `n/a — source not configured`. Nothing is invented.

## Setup

```
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# fill in keys
```

## Run

```
python -m dashboard.daily
# writes reports/YYYY-MM-DD.html and reports/latest.html
```

## Schedule

See `cron.example`.

## Data sources

| Section | Source | Status |
|---|---|---|
| US GDP, CPI, PCE, breakevens, BBB/HY OAS, central-bank balance sheets, RRP, TGA | FRED | works with `FRED_API_KEY` |
| CPI/PPI detail | BLS | works with `BLS_API_KEY` |
| Treasury TGA, debt, auctions | US Treasury Fiscal Data API | works (no key) |
| Put/Call ratio | CBOE daily CSV | works (no key) |
| Sector ETF & stock prices, RSI, relative strength | Yahoo via `yfinance` | works (no key) |
| MOVE index, global GDP nowcast, earnings revisions, AAII/II raw | Bloomberg / Refinitiv / FactSet / Koyfin / YCharts | adapter present, requires license |
| Manual CSV drops | `data/manual/*.csv` | works |
| VectorVest, Master Trader, 22V | personal logins | adapters stubbed pending credentials |

## Manual CSV format

Drop files in `data/manual/<series_id>.csv` with two columns: `date,value` (ISO date). They are ingested as a fallback for any series whose primary source is unavailable.
