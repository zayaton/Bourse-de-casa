"""
One-time script: recomputes what the model would have picked for every
trading day from BACKFILL_START onward, and saves each one as a resolved
(or pending, if its 3-day window hasn't fully closed yet) row — so your
dashboard has a real track record the first time you open it, instead of
an empty chart.

Run this once, locally, after your Supabase table exists:
  python backfill.py
"""
import time
import pandas as pd

from pipeline import run_for_prediction_date, trading_days_after
from model import TARGET_WINDOW_DAYS, POP_THRESHOLD
from scraper import get_stock_history
from db import get_client, upsert_pick, resolve_pick

BACKFILL_START = "2026-07-01"


def business_days(start: str, end: str):
    return pd.bdate_range(start=start, end=end, freq='B')


def main():
    client = get_client()
    today = pd.Timestamp.today().normalize()
    prediction_dates = business_days(BACKFILL_START, today.strftime('%Y-%m-%d'))

    for prediction_date in prediction_dates:
        prediction_str = prediction_date.strftime('%Y-%m-%d')
        print(f"\n--- Backfilling as of {prediction_str} ---")

        result = run_for_prediction_date(prediction_str)
        if result["top_pick"] is None:
            print("  No candidate cleared the confidence bar, skipping.")
            continue

        pick = result["top_pick"]
        window_end_date = trading_days_after(prediction_date, TARGET_WINDOW_DAYS)
        row = {
            "prediction_date": result["prediction_date"],
            "target_date": result["target_date"],  # == window_end_date
            "ticker": pick["ticker"],
            "confidence": pick["confidence"],
            "reference_close": pick["reference_close"],
        }
        upsert_pick(client, row)

        # Resolve immediately if the window has already fully closed.
        # Wrapped so one flaky day (network blip) doesn't kill the whole
        # multi-hour backfill loop — you can always re-run backfill.py
        # later to pick up anything that failed to resolve.
        if window_end_date < today:
            try:
                history = get_stock_history(pick["ticker"], today.strftime('%Y-%m-%d'))
                if history is not None:
                    history["Date"] = pd.to_datetime(history["Date"])
                    window = history[
                        (history["Date"] > prediction_date) & (history["Date"] <= window_end_date)
                    ]
                    if not window.empty:
                        actual_close = float(window["Close"].max())
                        pct_change = (actual_close - pick["reference_close"]) / pick["reference_close"]
                        hit = pct_change > POP_THRESHOLD

                        saved = client.table("daily_picks").select("id") \
                            .eq("target_date", result["target_date"]).eq("ticker", pick["ticker"]).execute()
                        if saved.data:
                            resolve_pick(client, saved.data[0]["id"], actual_close, round(pct_change, 4), hit)
                            print(f"  {pick['ticker']}: best move {pct_change:+.2%} ({'hit' if hit else 'miss'})")
            except Exception as e:
                print(f"  Warning: could not resolve {pick['ticker']} for this day ({e!r}); "
                      f"re-run backfill.py later to pick it up.")

        time.sleep(1)  # ease up on investing.com between days

    print("\nBackfill complete.")


if __name__ == "__main__":
    main()
