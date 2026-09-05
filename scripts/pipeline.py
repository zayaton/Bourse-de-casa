"""
The one pipeline every run goes through, whether it's the scheduled daily
job, a manual "test some random day" run, or the initial backfill.

Vocabulary used throughout:
  prediction_date  - the day the model stands on. Its close is the
                      reference price ("what you'd buy at"). All scraped
                      data is capped here — nothing later ever reaches the
                      model, which is what makes a backtest honest.
  window_end_date  - the last of the TARGET_WINDOW_DAYS trading days after
                      prediction_date. The pick "hits" if the stock ever
                      closes TARGET_PCT above the reference price on or
                      before this date. This is what gets stored as
                      target_date in the database (the day the outcome is
                      finally knowable), and what the dashboard shows as
                      the pick's deadline.
"""
import pandas as pd

from scraper import get_all_stock_history
from features import build_features
from model import add_target, train, rank_candidates, TARGET_WINDOW_DAYS


def previous_trading_day(date: pd.Timestamp) -> pd.Timestamp:
    d = date - pd.Timedelta(days=1)
    while d.weekday() >= 5:  # Sat/Sun — doesn't account for market holidays
        d -= pd.Timedelta(days=1)
    return d


def next_trading_day(date: pd.Timestamp) -> pd.Timestamp:
    d = date + pd.Timedelta(days=1)
    while d.weekday() >= 5:
        d += pd.Timedelta(days=1)
    return d


def trading_days_after(date: pd.Timestamp, n: int) -> pd.Timestamp:
    """The n-th trading day strictly after `date`."""
    d = date
    for _ in range(n):
        d = next_trading_day(d)
    return d


def run_for_prediction_date(prediction_date: str) -> dict:
    """Runs the full pipeline standing on the evening of `prediction_date`
    and returns the top pick (or None if nothing cleared the confidence
    bar). Does not write to the database — callers decide whether/how to
    persist the result."""
    prediction_date = pd.Timestamp(prediction_date)
    cutoff_str = prediction_date.strftime('%Y-%m-%d')
    window_end_date = trading_days_after(prediction_date, TARGET_WINDOW_DAYS)

    prices = get_all_stock_history(cutoff_str)
    features_df = build_features(prices)
    features_df = add_target(features_df)
    model = train(features_df)
    candidates = rank_candidates(model, features_df, prediction_date)

    base = {
        "prediction_date": prediction_date.date().isoformat(),
        "target_date": window_end_date.date().isoformat(),
    }

    if candidates.empty:
        return {**base, "top_pick": None}

    top = candidates.iloc[0]
    return {
        **base,
        "top_pick": {
            "ticker": top["Ticker"],
            "confidence": round(float(top["prob_jump"]), 4),
            "reference_close": float(top["Close"]),
        },
    }
