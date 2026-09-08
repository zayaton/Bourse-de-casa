"""
Pulls daily OHLCV price history from investing.com, for every stock in
tickers.py, up to whatever cutoff date you pass in. This is your original
scraperV1.py, split into reusable functions and parametrized so the same
code serves the daily job, manual backtests, and the July backfill.

Also guards against a real data-quality bug we found in your CSV: on some
0-volume days (nothing actually traded), investing.com occasionally
returns a stale/bad reference price wildly different from the last real
trade — e.g. MNG jumping from 63 to 772 for three straight 0-volume days
in 2016, then snapping back to 78 the moment trading resumed. That's not
a real price move and it was poisoning both training labels and backtest
results with fake 50%+ "pops". See `_clean_bad_ticks` below.
"""
from curl_cffi import requests
import pandas as pd
import time

from tickers import STOCK_IDS

BASE_URL = "https://de.api.investing.com/api/financialdata/historical/"
START_DATE = "2016-01-01"  # far enough back for the model to have history

# A 0-volume day (nothing traded) whose Close deviates from the last real
# trade by more than this is treated as a bad tick, not a real price move.
BAD_TICK_DEVIATION = 0.20  # 20%

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

# Columns that must be real numbers before any arithmetic (bad-tick check,
# ret_1d/ret_3d features, model input, etc.) touches them.
NUMERIC_COLS = ['Open', 'High', 'Low', 'Close', 'Volume']


def _fetch(instrument_id: str, end_date: str, start_date: str = START_DATE, tries: int = 3) -> pd.DataFrame | None:
    url = f"{BASE_URL}{instrument_id}"
    params = {
        'start-date': start_date, 'end-date': end_date,
        'time-frame': 'Daily', 'add-missing-rows': 'false',
    }
    last_err = None
    for attempt in range(1, tries + 1):
        try:
            resp = requests.get(url, params=params, headers=HEADERS, impersonate="chrome120", timeout=15)
            if resp.status_code != 200:
                # Not a transient network issue — retrying won't help.
                print(f"Error {resp.status_code} for instrument {instrument_id}")
                return None
            data = resp.json().get('data', [])
            if not data:
                return None
            df = pd.DataFrame(data)[list(COLS.keys())].rename(columns=COLS)
            # investing.com's "Raw" fields aren't guaranteed to arrive as
            # real JSON numbers — sometimes they come back as strings.
            # Force numeric here, once, at the source, so every downstream
            # consumer (bad-tick guard, features, model) can trust these
            # are floats. Anything that can't be parsed becomes NaN rather
            # than silently poisoning arithmetic later.
            for col in NUMERIC_COLS:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            return df
        except Exception as e:
            last_err = e
            if attempt < tries:
                print(f"  Network hiccup fetching {instrument_id} (attempt {attempt}/{tries}): {e!r}; retrying...")
                time.sleep(3)
    print(f"Failed to fetch {instrument_id} after {tries} attempts: {last_err!r}")
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


def _clean_bad_ticks(df: pd.DataFrame, deviation: float = BAD_TICK_DEVIATION) -> pd.DataFrame:
    """Walks each ticker's real (scraped) rows in date order. On any
    0-volume day whose OHLC deviates from the last real (volume>0) close
    by more than `deviation`, blank the OHLC out so the weekday-fill step
    in get_all_stock_history carries the last good price forward instead
    — exactly what should have happened on a genuine no-trade day."""
    df = df.sort_values(['Ticker', 'Date']).copy()
    cleaned = []
    for ticker, group in df.groupby('Ticker'):
        group = group.copy()
        last_good_close = None
        flags = []
        for _, row in group.iterrows():
            is_bad = (
                last_good_close is not None
                and row['Volume'] == 0
                and pd.notna(row['Close'])
                and abs(row['Close'] - last_good_close) / last_good_close > deviation
            )
            flags.append(is_bad)
            if not is_bad and pd.notna(row['Close']):
                last_good_close = row['Close']
        group.loc[flags, ['Open', 'High', 'Low', 'Close']] = None
        n_bad = sum(flags)
        if n_bad:
            print(f"  {ticker}: discarded {n_bad} suspect zero-volume price(s) as bad ticks")
        cleaned.append(group)
    return pd.concat(cleaned, ignore_index=True)


def get_all_stock_history(cutoff_date: str, pause_seconds: float = 2.0) -> pd.DataFrame:
    """Fetches every ticker in tickers.py, capped at cutoff_date, strips
    out bad ticks (see _clean_bad_ticks), and fills in any weekdays
    investing.com skips (its 0%-change-day gaps)."""
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
    combined = _clean_bad_ticks(combined)

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
