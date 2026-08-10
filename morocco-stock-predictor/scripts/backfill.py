"""
One-time script: recomputes what the model would have picked for every
trading day from BACKFILL_START onward, and saves each one as a resolved
(or pending, if too recent) row — so your dashboard has a real track
record the first time you open it, instead of an empty chart.

Run this once, locally, after your Supabase table exists:
  python backfill.py
"""
import time
import pandas as pd

from pipeline import run_for_target_date, next_trading_day
from scraper import get_stock_history
from db import get_client, upsert_pick, resolve_pick
from model import POP_THRESHOLD

BACKFILL_START = "2026-07-01"


def business_days(start: str, end: str):
    return pd.bdate_range(start=start, end=end, freq='B')


def main():
    client = get_client()
    today = pd.Timestamp.today().normalize()
    target_dates = business_days(BACKFILL_START, today.strftime('%Y-%m-%d'))

    for target_date in target_dates:
        target_str = target_date.strftime('%Y-%m-%d')
        print(f"\n--- Backfilling {target_str} ---")

        result = run_for_target_date(target_str)
        if result["top_pick"] is None:
            print("  No candidate cleared the confidence bar, skipping.")
            continue

        pick = result["top_pick"]
        row = {
            "prediction_date": result["prediction_date"],
            "target_date": result["target_date"],
            "ticker": pick["ticker"],
            "confidence": pick["confidence"],
            "reference_close": pick["reference_close"],
        }
        upsert_pick(client, row)

        # Resolve immediately if the outcome is already in the past
        if target_date < today:
            history = get_stock_history(pick["ticker"], today.strftime('%Y-%m-%d'))
            if history is not None:
                history["Date"] = pd.to_datetime(history["Date"])
                outcome_row = history[history["Date"] == target_date]
                if not outcome_row.empty:
                    actual_close = float(outcome_row.iloc[0]["Close"])
                    pct_change = (actual_close - pick["reference_close"]) / pick["reference_close"]
                    hit = pct_change >= POP_THRESHOLD

                    saved = client.table("daily_picks").select("id") \
                        .eq("target_date", target_str).eq("ticker", pick["ticker"]).execute()
                    if saved.data:
                        resolve_pick(client, saved.data[0]["id"], actual_close, round(pct_change, 4), hit)
                        print(f"  {pick['ticker']}: {pct_change:+.2%} ({'hit' if hit else 'miss'})")

        time.sleep(1)  # ease up on investing.com between days

    print("\nBackfill complete.")


if __name__ == "__main__":
    main()
