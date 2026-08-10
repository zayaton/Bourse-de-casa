"""
Entrypoint for one pipeline run.

Live mode (what the scheduled job uses):
  python run_daily.py --mode live
  -> resolves any pending pick whose target_date has arrived, then
     predicts the pick for the next trading day and saves it.

Backtest mode (the "test a random day" feature):
  python run_daily.py --mode backtest --target-date 2026-06-15
  -> runs the pipeline as if standing on the evening before that date,
     prints the result, and does NOT touch the database.
"""
import argparse
import pandas as pd

from pipeline import run_for_target_date, next_trading_day
from scraper import get_stock_history
from db import get_client, upsert_pick, get_pending_picks, resolve_pick
from model import POP_THRESHOLD


def resolve_pending(client, as_of_date: str):
    pending = get_pending_picks(client)
    today = pd.Timestamp(as_of_date)

    for pick in pending:
        target_date = pd.Timestamp(pick["target_date"])
        if target_date > today:
            continue  # outcome not knowable yet

        history = get_stock_history(pick["ticker"], as_of_date)
        if history is None:
            print(f"Could not fetch price to resolve {pick['ticker']} on {pick['target_date']}")
            continue

        # investing.com dates come back as strings; normalize before comparing
        history["Date"] = pd.to_datetime(history["Date"])
        row = history[history["Date"] == target_date]
        if row.empty:
            print(f"No price row for {pick['ticker']} on {pick['target_date']} yet")
            continue

        actual_close = float(row.iloc[0]["Close"])
        pct_change = (actual_close - pick["reference_close"]) / pick["reference_close"]
        hit = pct_change >= POP_THRESHOLD

        resolve_pick(client, pick["id"], actual_close, round(pct_change, 4), hit)
        print(f"Resolved {pick['ticker']} for {pick['target_date']}: "
              f"{pct_change:+.2%} ({'hit' if hit else 'miss'})")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["live", "backtest"], default="live")
    parser.add_argument("--target-date", default=None,
                         help="Backtest mode: the day to predict for. Defaults to the next trading day for live mode.")
    args = parser.parse_args()

    if args.mode == "live":
        client = get_client()
        today = pd.Timestamp.today().normalize()
        resolve_pending(client, today.strftime('%Y-%m-%d'))

        target_date = args.target_date or next_trading_day(today).strftime('%Y-%m-%d')
        result = run_for_target_date(target_date)

        if result["top_pick"] is None:
            print(f"No candidate cleared the {50}% confidence bar for {target_date}.")
            return

        pick = result["top_pick"]
        upsert_pick(client, {
            "prediction_date": result["prediction_date"],
            "target_date": result["target_date"],
            "ticker": pick["ticker"],
            "confidence": pick["confidence"],
            "reference_close": pick["reference_close"],
        })
        print(f"Saved pick for {target_date}: {pick['ticker']} ({pick['confidence']:.0%} confidence)")

    else:
        if not args.target_date:
            parser.error("--target-date is required in backtest mode")
        result = run_for_target_date(args.target_date)
        if result["top_pick"] is None:
            print(f"No candidate cleared the confidence bar for {args.target_date}.")
        else:
            pick = result["top_pick"]
            print(f"Backtest for {args.target_date} (as of {result['prediction_date']}):")
            print(f"  Top pick: {pick['ticker']} — {pick['confidence']:.0%} confidence")
            print("  (Not saved — backtests are sandboxed and never touch the live results.)")


if __name__ == "__main__":
    main()
