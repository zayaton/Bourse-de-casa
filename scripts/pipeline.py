"""
The one pipeline every run goes through, whether it's the scheduled daily
job, a manual "test some random day" run, or the initial backfill.

Vocabulary used throughout:
  target_date     - the day being predicted for (the pick is meant to pop
                     by the close of this day)
  prediction_date - the day the model is standing on when it makes that
                     call. Always the trading day right before target_date.
                     All scraped data (prices, MASI) is capped here
                     — nothing from target_date or later ever reaches the
                     model, which is what makes a backtest honest.
"""
import pandas as pd

from scraper import get_all_stock_history, get_masi_history
from features import build_features
from model import add_target, train, rank_candidates


def previous_trading_day(date: pd.Timestamp) -> pd.Timestamp:
    d = date - pd.Timedelta(days=1)
    while d.weekday() >= 5:  # Sat/Sun — doesn't account for MASI holidays
        d -= pd.Timedelta(days=1)
    return d


def next_trading_day(date: pd.Timestamp) -> pd.Timestamp:
    d = date + pd.Timedelta(days=1)
    while d.weekday() >= 5:
        d += pd.Timedelta(days=1)
    return d


def run_for_target_date(target_date: str) -> dict:
    """Runs the full pipeline for one target_date and returns the top pick
    (or None if nothing cleared the confidence bar). Does not write to the
    database — callers decide whether/how to persist the result."""
    target_date = pd.Timestamp(target_date)
    prediction_date = previous_trading_day(target_date)
    cutoff_str = prediction_date.strftime('%Y-%m-%d')

    prices = get_all_stock_history(cutoff_str)
    masi = get_masi_history(cutoff_str)

    features_df = build_features(prices, masi)
    features_df = add_target(features_df)
    model = train(features_df)
    candidates = rank_candidates(model, features_df, prediction_date)

    if candidates.empty:
        return {
            "target_date": target_date.date().isoformat(),
            "prediction_date": prediction_date.date().isoformat(),
            "top_pick": None,
        }

    top = candidates.iloc[0]
    return {
        "target_date": target_date.date().isoformat(),
        "prediction_date": prediction_date.date().isoformat(),
        "top_pick": {
            "ticker": top["Ticker"],
            "confidence": round(float(top["prob_jump"]), 4),
            "reference_close": float(top["Close"]),
        },
    }
