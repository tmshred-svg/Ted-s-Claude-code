import csv
import io
from datetime import datetime, timezone
from typing import List, Tuple

import requests

from ..storage import upsert_observations


URL = "https://cdn.cboe.com/api/global/us_indices/daily_prices/PCRATIOS.csv"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"


def fetch() -> List[Tuple[str, float]]:
    """CBOE total equity put/call ratio (daily)."""
    r = requests.get(URL, timeout=30, headers={
        "User-Agent": UA,
        "Accept": "text/csv,*/*;q=0.8",
        "Referer": "https://www.cboe.com/",
    })
    r.raise_for_status()
    text = r.text
    out = []
    rdr = csv.reader(io.StringIO(text))
    rows = list(rdr)
    header_idx = None
    for i, row in enumerate(rows):
        if row and row[0].strip().upper() == "DATE":
            header_idx = i
            break
    if header_idx is None:
        return out
    header = [h.strip().upper() for h in rows[header_idx]]
    try:
        date_i = header.index("DATE")
        eq_i = header.index("EQUITY PUT/CALL RATIO")
    except ValueError:
        return out
    for row in rows[header_idx + 1:]:
        if len(row) <= max(date_i, eq_i):
            continue
        try:
            d = datetime.strptime(row[date_i].strip(), "%m/%d/%Y").date().isoformat()
            v = float(row[eq_i])
        except (ValueError, IndexError):
            continue
        out.append((d, v))
    out.sort()
    return out


def ingest() -> int:
    rows = fetch()
    return upsert_observations(
        series_id="CBOE:EQUITY_PC",
        rows=rows,
        source="CBOE",
        fetched_at=datetime.now(timezone.utc).isoformat(),
    )
