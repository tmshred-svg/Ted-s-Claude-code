import sqlite3
from contextlib import contextmanager
from datetime import date
from typing import Iterable, Optional

import pandas as pd

from .config import CFG


SCHEMA = """
CREATE TABLE IF NOT EXISTS observations (
    series_id TEXT NOT NULL,
    obs_date  TEXT NOT NULL,
    value     REAL,
    source    TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    revision_n INTEGER DEFAULT 0,
    PRIMARY KEY (series_id, obs_date, revision_n)
);
CREATE INDEX IF NOT EXISTS ix_obs_series ON observations(series_id, obs_date);

CREATE TABLE IF NOT EXISTS run_log (
    run_at TEXT PRIMARY KEY,
    notes  TEXT
);
"""


@contextmanager
def conn():
    c = sqlite3.connect(CFG.db_path)
    try:
        yield c
        c.commit()
    finally:
        c.close()


def init_db() -> None:
    with conn() as c:
        c.executescript(SCHEMA)


def upsert_observations(
    series_id: str,
    rows: Iterable[tuple],
    source: str,
    fetched_at: str,
) -> int:
    """rows: iterable of (obs_date_iso, value).
    Stores a new revision_n if the value for an existing date changed."""
    init_db()
    n = 0
    with conn() as c:
        for obs_date_iso, value in rows:
            if value is None:
                continue
            cur = c.execute(
                "SELECT value, MAX(revision_n) FROM observations "
                "WHERE series_id=? AND obs_date=? GROUP BY series_id, obs_date",
                (series_id, obs_date_iso),
            )
            row = cur.fetchone()
            if row is None:
                c.execute(
                    "INSERT OR REPLACE INTO observations VALUES (?,?,?,?,?,0)",
                    (series_id, obs_date_iso, float(value), source, fetched_at),
                )
                n += 1
            else:
                last_value, last_rev = row
                if last_value is None or abs(float(last_value) - float(value)) > 1e-12:
                    c.execute(
                        "INSERT OR REPLACE INTO observations VALUES (?,?,?,?,?,?)",
                        (series_id, obs_date_iso, float(value), source, fetched_at, (last_rev or 0) + 1),
                    )
                    n += 1
    return n


def latest_series(series_id: str) -> pd.DataFrame:
    init_db()
    with conn() as c:
        df = pd.read_sql_query(
            "SELECT obs_date, value, source, fetched_at, revision_n "
            "FROM observations WHERE series_id=? "
            "ORDER BY obs_date ASC, revision_n DESC",
            c, params=(series_id,),
        )
    if df.empty:
        return df
    df = df.drop_duplicates(subset=["obs_date"], keep="first")
    df["obs_date"] = pd.to_datetime(df["obs_date"])
    return df.set_index("obs_date").sort_index()


def revision_count(series_id: str) -> pd.DataFrame:
    """Number of revisions per obs_date; ratio of revised observations to total."""
    init_db()
    with conn() as c:
        df = pd.read_sql_query(
            "SELECT obs_date, MAX(revision_n) AS revs FROM observations "
            "WHERE series_id=? GROUP BY obs_date ORDER BY obs_date ASC",
            c, params=(series_id,),
        )
    if df.empty:
        return df
    df["obs_date"] = pd.to_datetime(df["obs_date"])
    return df.set_index("obs_date")


def log_run(notes: str = "") -> None:
    init_db()
    with conn() as c:
        c.execute(
            "INSERT OR REPLACE INTO run_log VALUES (?, ?)",
            (date.today().isoformat(), notes),
        )
