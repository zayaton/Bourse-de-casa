# Casablanca Sniper

Predicts which Moroccan (Casablanca Stock Exchange) stock is most likely
to close 2.5%+ above today's price at some point in the next 3 trading
days, using price momentum, volatility, volume, and RSI — the exact same
target, threshold, and features as `geminiML1.py`. Runs automatically
every weekday after market close via GitHub Actions, saves the pick to
Supabase, and a static dashboard shows it plus a running predicted-vs-actual
track record.

## Changing the strategy

Everything that defines the strategy lives in one place:
`scripts/model.py`, top of the file:

```python
TARGET_PCT = 0.025            # the "pop" size that counts as a win (2.5%)
TARGET_WINDOW_DAYS = 3        # within how many trading days
CONFIDENCE_THRESHOLD = 0.60   # only act on picks above this predicted probability
```

Change any of the three and nothing else needs to change — the training
label, the backtest CLI, the daily job, and the dashboard's resolution
logic all read from these.

## One-time setup

1. **Create the Supabase table**: open your Supabase project's SQL Editor
   and run `sql/schema.sql`. (If you already ran the old version of this
   file, you don't need to re-run it — the table structure is unchanged,
   only comments were updated.)

2. **Set secrets**: in this repo's Settings > Secrets and variables >
   Actions, add `SUPABASE_URL` and `SUPABASE_KEY` (the **service_role**
   key — Settings > API in Supabase).

3. **Wire up the dashboard**: `dashboard/index.html` already has your
   project's public anon key and URL in it — nothing to fill in unless
   you rotate keys. Deploy the `dashboard/` folder on Vercel (or any
   static host).

4. **Run the backfill once, locally**, so the dashboard isn't empty:
   ```
   cd scripts
   pip install -r ../requirements.txt
   export SUPABASE_URL=...
   export SUPABASE_KEY=...
   python backfill.py
   ```
   This recomputes what the model would have picked every trading day
   since July 1, 2026, and saves the resolved results. It'll take a
   while — there's a deliberate pause between requests to stay polite to
   investing.com.

After that, the GitHub Actions workflow (`.github/workflows/daily.yml`)
takes over automatically on weekdays.

## Testing a random day (backtest / sandbox mode)

From the Actions tab, run the "Daily stock pick" workflow manually and
fill in the `target_date` input. This predicts as if standing on the
evening before that date — using only data available up to that point —
and prints the result in the workflow log. Nothing is saved, so it never
affects your real track record.

You can also run it locally without touching Supabase at all:
```
cd scripts
python run_daily.py --mode backtest --target-date 2026-06-15
```

## Known rough edges (worth knowing about before you push)

- **Holiday calendar isn't modeled** — `previous_trading_day` /
  `next_trading_day` only skip weekends, not Moroccan market holidays.
  Good enough to start; worth revisiting if picks land on holidays.
- **The bad-tick guard in `scraper.py`** discards a 0-volume day's price
  if it deviates from the last real trade by more than 20% (`BAD_TICK_DEVIATION`
  in `scraper.py`). This is a heuristic, not a certainty — if a stock ever
  has a real, legitimate 20%+ move on a day with genuinely zero recorded
  volume (unusual, but not impossible for the most illiquid names), this
  guard would incorrectly discard it. Worth an occasional spot-check of
  the "discarded ... as bad ticks" log lines the scraper prints.
- **The MASI-relative feature was removed** so the website matches
  `geminiML1.py` exactly. `tickers.py` still has `MASI_INDEX_ID` filled
  in if you want to bring a market-relative feature back later.
- **GitHub Actions cron jobs auto-disable after 60 days with zero commits**
  to the repo's default branch (not 60 days without a *run* — pushing
  anything resets the clock). Not currently a risk here, just worth
  knowing if this repo ever goes quiet for a couple of months.
