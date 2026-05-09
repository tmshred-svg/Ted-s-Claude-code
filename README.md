# Economic Metrics Dashboard

Daily HTML report covering: global & US GDP (with revision ratios), credit spreads, MOVE, inflation & inflation expectations, global liquidity, sector/asset flows, sentiment (put/call, AAII/II), and screens for strong stocks in strong sectors and strong stocks in weak sectors.

Every value carries a source and timestamp. If a source is not configured or returns no data, the cell renders `n/a — source not configured`. Nothing is invented.

## Setup

```
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # optional — keys not required for any free source
```

## Run

```
python -m dashboard.daily
# writes reports/YYYY-MM-DD.html and reports/latest.html
```

On first run a default cross-sector universe is copied from
`examples/universe.default.csv` to `data/manual/universe.csv`. Edit that file
to change which tickers the screens cover.

## Schedule

```
./install-cron.sh           # installs 17:30 Mon-Fri
SCHEDULE="0 22 * * 1-5" ./install-cron.sh    # override schedule
```

`crontab -l` to inspect; `crontab -l | grep -v '# metrics-dashboard' | crontab -` to remove.

## Data sources

| Section | Source | Status |
|---|---|---|
| US GDP, CPI, PCE, breakevens, BBB/HY OAS, central-bank balance sheets, RRP, TGA | FRED | works without a key (uses public CSV); `FRED_API_KEY` enables JSON API |
| CPI/PPI detail | BLS | works without a key (rate-limited); `BLS_API_KEY` raises the limit |
| Treasury TGA, debt, auctions | US Treasury Fiscal Data API | works (no key) |
| Put/Call ratio | CBOE daily CSV | works (no key) |
| Sector ETF & stock prices, RSI, relative strength | Yahoo via `yfinance` | works (no key) |
| MOVE index | Yahoo `^MOVE` if available, then Bloomberg, then manual CSV | works when Yahoo serves `^MOVE` |
| Earnings revisions per ticker | Yahoo `Ticker.eps_revisions` snapshotted daily | works (no key); 21d of history needed before "improving" filter activates |
| Global GDP nowcast, AAII/II raw | Bloomberg / manual CSV | adapter present, requires license or CSV |
| Manual CSV drops | `data/manual/*.csv` | works |
| VectorVest, Master Trader, 22V | personal logins | adapters stubbed pending credentials |

## Manual CSV format

Drop files in `data/manual/<series_id>.csv` with two columns: `date,value` (ISO date). They are ingested as a fallback for any series whose primary source is unavailable.
