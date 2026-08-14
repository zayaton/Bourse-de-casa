"""
Pulls daily OHLCV price history from investing.com, for every stock in
tickers.py plus the MASI index, up to whatever cutoff date you pass in.
This is your original scraperV1.py, split into reusable functions and
parametrized so the same code serves the daily job, manual backtests,
and the July backfill.
"""
from curl_cffi import requests
import pandas as pd
import time

from tickers import STOCK_IDS, MASI_INDEX_ID

BASE_URL = "https://de.api.investing.com/api/financialdata/historical/"
START_DATE = "2016-01-01"  # far enough back for the model to have history

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Referer': 'https://www.investing.com/',
    'domain-id': 'de',
    'x-requested-with': 'OpenAPI',
}

COLS = {
    'rowDate': 'Date', 'last_openRaw': 'Open', 'last_maxRaw': 'High',
    'last_minRaw': 'Low', 'last_closeRaw': 'Close', 'volumeRaw': 'Volume',
}


def _fetch(instrument_id: str, end_date: str, start_date: str = START_DATE) -> pd.DataFrame | None:
    url = f"{BASE_URL}{instrument_id}"
    params = {
        'start-date': start_date, 'end-date': end_date,
        'time-frame': 'Daily', 'add-missing-rows': 'false',
    }
    try:
        resp = requests.get(url, params=params, headers=HEADERS, impersonate="chrome120", timeout=15)
        if resp.status_code != 200:
            print(f"Error {resp.status_code} for instrument {instrument_id}")
            return None
        data = resp.json().get('data', [])
        if not data:
            return None
        df = pd.DataFrame(data)[list(COLS.keys())].rename(columns=COLS)

        # investing.com sometimes sends these as JSON strings (e.g. "1234.50")
        # instead of numbers. Force them to real numbers here, once, so nothing
        # downstream (features.py doing division, etc.) can silently choke on text.
        numeric_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')

        # investing.com sends dates as day-first text (e.g. "05.08.2026").
        # Convert once, here, so every caller (stocks AND the MASI index)
        # gets a real date back instead of text -- this used to only happen
        # for stock prices, which is why merging with the index broke.
        df['Date'] = pd.to_datetime(df['Date'], dayfirst=True, errors='coerce')

        return df
    except Exception as e:
        print(f"Failed to fetch {instrument_id}: {e}")
        return None


def get_stock_history(ticker: str, cutoff_date: str) -> pd.DataFrame | None:
    stock_id = STOCK_IDS.get(ticker)
    if not stock_id:
        print(f"Unknown ticker {ticker}, skipping")
        return None
    df = _fetch(stock_id, cutoff_date)
    if df is not None:
        df['Ticker'] = ticker
    return df


def get_masi_history(cutoff_date: str) -> pd.DataFrame | None:
    if not MASI_INDEX_ID:
        print("MASI_INDEX_ID is not set in tickers.py — skipping index data. "
              "The model will run without market-relative features until this is filled in.")
        return None
    df = _fetch(MASI_INDEX_ID, cutoff_date)
    if df is not None:
        df = df.rename(columns={'Close': 'MASI_Close'})[['Date', 'MASI_Close']]
    return df


def get_all_stock_history(cutoff_date: str, pause_seconds: float = 2.0) -> pd.DataFrame:
    """Fetches every ticker in tickers.py, capped at cutoff_date, and fills
    in any weekdays investing.com skips (its 0%-change-day gaps)."""
    frames = []
    for ticker in STOCK_IDS:
        print(f"Scraping {ticker}...")
        df = get_stock_history(ticker, cutoff_date)
        if df is not None:
            frames.append(df)
        time.sleep(pause_seconds)  # be polite to the API

    if not frames:
        raise RuntimeError("No stock data scraped — check your network/headers/IDs.")

    combined = pd.concat(frames, ignore_index=True)
    combined['Date'] = pd.to_datetime(combined['Date'], errors='coerce')
    combined = combined.dropna(subset=['Date'])
    combined = combined[combined['Date'] <= pd.Timestamp(cutoff_date)]

    all_weekdays = pd.bdate_range(start=combined['Date'].min(), end=cutoff_date, freq='B')
    filled = []
    for ticker, group in combined.groupby('Ticker'):
        idx = pd.DataFrame({'Date': all_weekdays, 'Ticker': ticker})
        merged = idx.merge(group, on=['Date', 'Ticker'], how='left')
        for col in ['Open', 'High', 'Low', 'Close']:
            merged[col] = merged[col].ffill()
        merged['Volume'] = merged['Volume'].fillna(0)
        filled.append(merged)

    return pd.concat(filled, ignore_index=True)