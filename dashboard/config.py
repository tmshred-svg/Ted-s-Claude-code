import os
from dataclasses import dataclass
from pathlib import Path


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())


_load_dotenv(Path(".env"))


@dataclass(frozen=True)
class Config:
    fred_api_key: str = os.environ.get("FRED_API_KEY", "")
    bls_api_key: str = os.environ.get("BLS_API_KEY", "")
    bloomberg_enabled: bool = os.environ.get("BLOOMBERG_ENABLED", "0") == "1"
    refinitiv_app_key: str = os.environ.get("REFINITIV_APP_KEY", "")
    koyfin_api_key: str = os.environ.get("KOYFIN_API_KEY", "")
    ycharts_api_key: str = os.environ.get("YCHARTS_API_KEY", "")
    vectorvest_user: str = os.environ.get("VECTORVEST_USER", "")
    vectorvest_pass: str = os.environ.get("VECTORVEST_PASS", "")
    mastertrader_user: str = os.environ.get("MASTERTRADER_USER", "")
    mastertrader_pass: str = os.environ.get("MASTERTRADER_PASS", "")
    twentytwov_user: str = os.environ.get("TWENTYTWOV_USER", "")
    twentytwov_pass: str = os.environ.get("TWENTYTWOV_PASS", "")
    sector_etfs: tuple = tuple(
        s.strip() for s in os.environ.get(
            "SECTOR_ETFS", "XLK,XLF,XLE,XLY,XLP,XLI,XLV,XLB,XLU,XLRE,XLC"
        ).split(",") if s.strip()
    )
    benchmark: str = os.environ.get("BENCHMARK", "SPY")
    universe_file: str = os.environ.get("SCREEN_UNIVERSE_FILE", "data/manual/universe.csv")
    data_dir: str = os.environ.get("DATA_DIR", "data")
    report_dir: str = os.environ.get("REPORT_DIR", "reports")
    db_path: str = os.environ.get("DB_PATH", "data/dashboard.sqlite")


CFG = Config()
Path(CFG.data_dir).mkdir(parents=True, exist_ok=True)
Path(CFG.report_dir).mkdir(parents=True, exist_ok=True)
Path(CFG.data_dir, "manual").mkdir(parents=True, exist_ok=True)
