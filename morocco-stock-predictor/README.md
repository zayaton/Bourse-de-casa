# Casablanca Sniper

Predicts which Moroccan (Casablanca Stock Exchange) stock is most likely
to close up 1.5%+ the next trading day, using price momentum, volatility,
volume, and MASI-relative strength. Runs automatically
every weekday after market close via GitHub Actions, saves the pick to
Supabase, and a static dashboard shows it plus a running predicted-vs-actual
track record.

## One-time setup

1. **Fill in `scripts/tickers.py`**: set `MASI_INDEX_ID` (see the comment
   in that file for how to find it).

2. **Create the Supabase table**: open your Supabase project's SQL Editor
   and run `sql/schema.sql`.

3. **Set secrets**: in this repo's Settings > Secrets and variables >
   Actions, add `SUPABASE_URL` and `SUPABASE_KEY` (the **service_role**
   key — Settings > API in Supabase).

4. **Wire up the dashboard**: in `dashboard/index.html`, replace
   `YOUR_SUPABASE_URL` and `YOUR_SUPABASE_ANON_KEY` with your project's
   URL and **anon** key (a different, public-safe key from the one above).
   Deploy the `dashboard/` folder on Vercel (or any static host).

5. **Run the backfill once, locally**, so the dashboard isn't empty:
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

## Known rough edges (worth knowing about before you push)

- **MASI_INDEX_ID** needs to be found manually (see `tickers.py`) —
  without it the model still runs, just without the market-relative
  feature.
- **Holiday calendar isn't modeled** — `previous_trading_day` /
  `next_trading_day` only skip weekends, not Moroccan market holidays.
  Good enough to start; worth revisiting if picks land on holidays.
