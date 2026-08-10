"""
Turns raw price history into the signals the model trains on. Same core
ideas as your original geminiML1.py, plus a MASI-relative return (is
this stock beating the market, or just riding it up).
"""
import pandas as pd


def _rsi(series: pd.Series, period: int = 7) -> pd.Series:
    delta = series.diff()
    gain = delta.where(delta > 0, 0).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
    return 100 - (100 / (1 + (gain / (loss + 1e-10))))


def build_features(prices: pd.DataFrame, masi: pd.DataFrame | None) -> pd.DataFrame:
    """
    prices: columns [Date, Ticker, Open, High, Low, Close, Volume]
    masi:   columns [Date, MASI_Close], or None if not available yet
    """
    df = prices.sort_values(['Ticker', 'Date']).copy()

    # Belt-and-suspenders: force these to real numbers again right here, no
    # matter what dtype they arrived as. Something upstream (the scraper's
    # merge step that fills in missing weekdays) can still let these come
    # through as text in some cases, and this is the last point before any
    # math happens on them.
    for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    df['vol_ma_5'] = df.groupby('Ticker')['Volume'].transform(lambda x: x.rolling(5).mean())
    df['vol_spike'] = df['Volume'] / (df['vol_ma_5'] + 1)

    df['ret_1d'] = df.groupby('Ticker')['Close'].pct_change()
    df['ret_3d'] = df.groupby('Ticker')['Close'].pct_change(3)

    df['std_10'] = df.groupby('Ticker')['Close'].transform(lambda x: x.rolling(10).std())
    df['ma_10'] = df.groupby('Ticker')['Close'].transform(lambda x: x.rolling(10).mean())
    df['bb_width'] = (df['std_10'] * 2) / df['ma_10']

    df['rsi'] = df.groupby('Ticker')['Close'].transform(_rsi)

    if masi is not None:
        masi = masi.sort_values('Date').copy()
        masi['masi_ret_1d'] = masi['MASI_Close'].pct_change()
        df = df.merge(masi[['Date', 'masi_ret_1d']], on='Date', how='left')
        df['masi_rel_ret'] = df['ret_1d'] - df['masi_ret_1d']
    else:
        df['masi_rel_ret'] = 0.0  # neutral until MASI_INDEX_ID is filled in

    return df.dropna(subset=['vol_spike', 'ret_1d', 'ret_3d', 'bb_width', 'rsi'])


FEATURE_COLUMNS = ['vol_spike', 'ret_1d', 'ret_3d', 'bb_width', 'rsi', 'masi_rel_ret']