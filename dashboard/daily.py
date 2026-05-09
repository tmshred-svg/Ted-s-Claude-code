import shutil
from datetime import date, datetime, timezone
from pathlib import Path

from .config import CFG
from .metrics import gdp, credit, inflation, liquidity, flows, sentiment, screens
from .sources import vectorvest, mastertrader, twentytwo_v
from .storage import init_db, log_run
from .report import render, write, fmt_log


def _bootstrap_universe() -> None:
    target = Path(CFG.universe_file)
    if target.exists():
        return
    src = Path(__file__).resolve().parent.parent / "examples" / "universe.default.csv"
    if not src.exists():
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(src, target)


def _account_status(name: str, user: str) -> str:
    if user:
        return f"credentials present; live ingestion adapter pending. Drop CSVs at data/manual/{name}_*.csv to ingest now."
    p = list(Path(CFG.data_dir, "manual").glob(f"{name}_*.csv"))
    if p:
        return f"using {len(p)} manual CSV(s): " + ", ".join(x.name for x in p)
    return "not configured (no credentials, no CSV)"


def main() -> int:
    init_db()
    _bootstrap_universe()
    g = gdp.collect()
    cr = credit.collect()
    inf = inflation.collect()
    liq = liquidity.collect()
    fl = flows.collect()
    se = sentiment.collect()
    sc = screens.collect()

    for sheet in ("watchlist", "rt_rv_vst", "stops"):
        vectorvest.ingest(sheet)
    for sheet in ("watchlist", "trade_log"):
        mastertrader.ingest(sheet)
    for sheet in ("positioning", "macro_view"):
        twentytwo_v.ingest(sheet)

    personal = {
        "vectorvest": _account_status("vectorvest", CFG.vectorvest_user),
        "mastertrader": _account_status("mastertrader", CFG.mastertrader_user),
        "twentytwov": _account_status("22v", CFG.twentytwov_user),
    }

    ctx = {
        "run_date": date.today().isoformat(),
        "run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "gdp": g, "credit": cr, "inflation": inf, "liquidity": liq,
        "flows": fl, "sentiment": se, "screens": sc, "personal": personal,
        "ingest_log": fmt_log(
            ("gdp", g.get("log", {})),
            ("credit", cr.get("log", {})),
            ("inflation", inf.get("log", {})),
            ("liquidity", liq.get("log", {})),
            ("flows", fl.get("log", {})),
            ("sentiment", se.get("log", {})),
            ("screens", sc.get("log", {})),
        ),
    }
    html = render(ctx)
    out = write(html)
    log_run(notes=f"wrote {out}")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
