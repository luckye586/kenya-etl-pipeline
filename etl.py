"""Kenya development indicators: World Bank API -> pandas -> SQLite.

Run:  python etl.py
Output: data/kenya.db  (table: indicators_long, views from sql/views.sql)
"""
from __future__ import annotations

import logging
import sqlite3
from datetime import date
from pathlib import Path

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

API_URL = "https://api.worldbank.org/v2/country/{country}/indicator/{indicator}"
COUNTRY = "KEN"
INDICATORS = {
    "SP.POP.TOTL": "population",
    "NY.GDP.MKTP.CD": "gdp_usd",
    "SL.UEM.TOTL.ZS": "unemployment_pct",
    "SE.PRM.ENRR": "primary_enrolment_pct",
}
DB_PATH = Path("data/kenya.db")
VIEWS_SQL = Path("sql/views.sql")

log = logging.getLogger("kenya_etl")


class DataQualityError(Exception):
    """Raised when a data quality check fails."""


def make_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(total=4, backoff_factor=1, status_forcelist=(429, 500, 502, 503, 504))
    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session


# ---------- Extract ----------
def extract(session: requests.Session, indicator: str, country: str = COUNTRY) -> list[dict]:
    """Fetch every page of one indicator and return the raw records."""
    records: list[dict] = []
    page = 1
    while True:
        resp = session.get(
            API_URL.format(country=country, indicator=indicator),
            params={"format": "json", "per_page": 200, "page": page},
            timeout=30,
        )
        resp.raise_for_status()
        payload = resp.json()
        if not isinstance(payload, list) or len(payload) < 2 or payload[1] is None:
            raise DataQualityError(f"Unexpected API response for {indicator}: {str(payload)[:200]}")
        meta, rows = payload
        records.extend(rows)
        if page >= meta["pages"]:
            break
        page += 1
    log.info("Extracted %s rows for %s", len(records), indicator)
    return records


# ---------- Transform ----------
def transform(records: list[dict]) -> pd.DataFrame:
    """Flatten raw API records into a tidy long table."""
    df = pd.DataFrame(
        {
            "country_code": [r["countryiso3code"] for r in records],
            "indicator_code": [r["indicator"]["id"] for r in records],
            "year": [r["date"] for r in records],
            "value": [r["value"] for r in records],
        }
    )
    df["year"] = pd.to_numeric(df["year"], errors="coerce").astype("Int64")
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df["indicator_name"] = df["indicator_code"].map(INDICATORS)
    before = len(df)
    df = df.dropna(subset=["year", "value"]).drop_duplicates(
        subset=["country_code", "indicator_code", "year"]
    )
    log.info("Dropped %s empty/duplicate rows", before - len(df))
    return df.sort_values(["indicator_code", "year"]).reset_index(drop=True)


def check_quality(df: pd.DataFrame) -> None:
    """Fail loudly instead of loading bad data."""
    if df.empty:
        raise DataQualityError("No rows to load")
    if df.duplicated(subset=["country_code", "indicator_code", "year"]).any():
        raise DataQualityError("Duplicate (country, indicator, year) rows found")
    if not df["year"].between(1960, date.today().year).all():
        raise DataQualityError("Year outside the expected range")
    non_negative = df["indicator_name"].isin(["population", "gdp_usd"])
    if (df.loc[non_negative, "value"] < 0).any():
        raise DataQualityError("Negative population or GDP value found")
    missing = set(INDICATORS) - set(df["indicator_code"])
    if missing:
        raise DataQualityError(f"Indicators missing from result: {sorted(missing)}")
    log.info("Quality checks passed (%s rows)", len(df))


# ---------- Load ----------
def load(df: pd.DataFrame, db_path: Path = DB_PATH, views_sql: Path = VIEWS_SQL) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        df.to_sql("indicators_long", conn, if_exists="replace", index=False)
        if views_sql.exists():
            conn.executescript(views_sql.read_text())
    log.info("Loaded %s rows into %s", len(df), db_path)


def run() -> None:
    session = make_session()
    frames = [transform(extract(session, code)) for code in INDICATORS]
    df = pd.concat(frames, ignore_index=True)
    check_quality(df)
    load(df)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run()
