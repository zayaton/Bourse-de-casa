"""
Exact port of the feature engineering in geminiML1.py, so the website's
model sees precisely the same signals your manual script does. (The MASI-
relative feature that used to live here has been removed for exact parity
— see README "Known rough edges" if you want to bring it back later.)
"""
import pandas as pd


def _rsi(series: pd.Series, period: int = 7) -> pd.Series:
    delta = series.diff()
    gain = delta.where(delta > 0, 0).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
    return 100 - (100 / (1 + (gain / (loss + 1e-10))))


def build_features(prices: pd.DataFrame) -> pd.DataFrame:
    """prices: columns [Date, Ticker, Open, High, Low, Close, Volume]"""
    df = prices.sort_values(['Ticker', 'Date']).copy()

    df['vol_ma_5'] = df.groupby('Ticker')['Volume'].transform(lambda x: x.rolling(5).mean())
    df['vol_spike'] = df['Volume'] / (df['vol_ma_5'] + 1)

    df['ret_1d'] = df.groupby('Ticker')['Close'].pct_change()
    df['ret_3d'] = df.groupby('Ticker')['Close'].pct_change(3)

    df['std_10'] = df.groupby('Ticker')['Close'].transform(lambda x: x.rolling(10).std())
    df['ma_10'] = df.groupby('Ticker')['Close'].transform(lambda x: x.rolling(10).mean())
    df['bb_width'] = (df['std_10'] * 2) / df['ma_10']

    df['rsi'] = df.groupby('Ticker')['Close'].transform(_rsi)

    return df.dropna(subset=['vol_spike', 'ret_1d', 'ret_3d', 'bb_width', 'rsi'])


FEATURE_COLUMNS = ['vol_spike', 'ret_1d', 'ret_3d', 'bb_width', 'rsi']
