"""
Entrypoint for one pipeline run.

Live mode (what the scheduled job uses):
  python run_daily.py --mode live
  -> resolves any pending pick whose 3-day window has fully closed, then
     predicts today's pick (standing on today's close) and saves it.

Backtest mode (the "test a random day" feature):
  python run_daily.py --mode backtest --target-date 2026-06-15
  -> runs the pipeline as if standing on the evening before that date,
     prints the result, and does NOT touch the database.
"""
import argparse
import pandas as pd

from pipeline import run_for_prediction_date, previous_trading_day
from scraper import get_stock_history
from db import get_client, upsert_pick, get_pending_picks, resolve_pick
from model import POP_THRESHOLD, CONFIDENCE_THRESHOLD


def resolve_pending(client, as_of_date: str):
    """A pick's outcome is only knowable once its full 3-day window has
    closed — checking early would risk calling a false "miss" on a stock
    that still had a day or two left to pop."""
    pending = get_pending_picks(client)
    today = pd.Timestamp(as_of_date)

    for pick in pending:
        window_end = pd.Timestamp(pick["target_date"])
        if window_end > today:
            continue  # window not fully closed yet — outcome not knowable

        history = get_stock_history(pick["ticker"], as_of_date)
        if history is None:
            print(f"Could not fetch price to resolve {pick['ticker']} (window ending {pick['target_date']})")
            continue

        # investing.com dates come back as strings; normalize before comparing
        history["Date"] = pd.to_datetime(history["Date"])
        prediction_date = pd.Timestamp(pick["prediction_date"])
        window = history[(history["Date"] > prediction_date) & (history["Date"] <= window_end)]
        if window.empty:
            print(f"No price rows yet in the resolution window for {pick['ticker']} (window ending {pick['target_date']})")
            continue

        # Best close reached anywhere in the window — mirrors how the
        # target label itself is built (rolling max over the window).
        actual_close = float(window["Close"].max())
        pct_change = (actual_close - pick["reference_close"]) / pick["reference_close"]
        hit = pct_change > POP_THRESHOLD

        resolve_pick(client, pick["id"], actual_close, round(pct_change, 4), hit)
        print(f"Resolved {pick['ticker']} (window ending {pick['target_date']}): "
              f"best move {pct_change:+.2%} ({'hit' if hit else 'miss'})")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["live", "backtest"], default="live")
    parser.add_argument("--target-date", default=None,
                         help="Backtest mode: predict as if standing on the evening before this date.")
    args = parser.parse_args()

    if args.mode == "live":
        client = get_client()
        today = pd.Timestamp.today().normalize()
        # If this ever runs on a non-trading day (e.g. a manual dispatch on
        # a weekend), fall back to the last real trading day instead of
        # trying to predict for a day with no fresh close.
        prediction_date = today if today.weekday() < 5 else previous_trading_day(today)
        prediction_date_str = prediction_date.strftime('%Y-%m-%d')

        # Resolving OLD picks and predicting TODAY's pick are independent —
        # a failure in one (e.g. a transient network blip talking to
        # Supabase) should never prevent the other. This is what silently
        # cost entire days in October: an unrelated resolve_pending crash
        # was taking down the whole run before it ever reached the scraper.
        try:
            resolve_pending(client, prediction_date_str)
        except Exception as e:
            print(f"Warning: resolving pending picks failed, continuing to today's prediction anyway: {e!r}")

        result = run_for_prediction_date(prediction_date_str)

        if result["top_pick"] is None:
            print(f"No candidate cleared the {CONFIDENCE_THRESHOLD:.0%} confidence bar for {prediction_date_str}.")
            return

        pick = result["top_pick"]
        upsert_pick(client, {
            "prediction_date": result["prediction_date"],
            "target_date": result["target_date"],
            "ticker": pick["ticker"],
            "confidence": pick["confidence"],
            "reference_close": pick["reference_close"],
        })
        print(f"Saved pick as of {prediction_date_str}: {pick['ticker']} "
              f"({pick['confidence']:.0%} confidence, window ends {result['target_date']})")

    else:
        if not args.target_date:
            parser.error("--target-date is required in backtest mode")
        prediction_date_str = previous_trading_day(pd.Timestamp(args.target_date)).strftime('%Y-%m-%d')
        result = run_for_prediction_date(prediction_date_str)
        if result["top_pick"] is None:
            print(f"No candidate cleared the {CONFIDENCE_THRESHOLD:.0%} confidence bar as of {prediction_date_str}.")
        else:
            pick = result["top_pick"]
            print(f"Backtest as of {result['prediction_date']} (window ends {result['target_date']}):")
            print(f"  Top pick: {pick['ticker']} — {pick['confidence']:.0%} confidence")
            print("  (Not saved — backtests are sandboxed and never touch the live results.)")


if __name__ == "__main__":
    main()
