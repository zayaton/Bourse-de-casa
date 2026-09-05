-- Run this once in Supabase: Project > SQL Editor > New query > paste > Run

create table if not exists daily_picks (
  id bigserial primary key,

  -- prediction_date = the day the model stood on (reference close = "buy" price)
  -- target_date     = the last day of the 3-trading-day window the pick is
  --                    given to pop within (i.e. window_end_date) — the
  --                    outcome isn't knowable until this date has passed
  prediction_date date not null,
  target_date date not null,

  ticker text not null,
  confidence numeric not null,        -- model's predicted probability, 0-1
  reference_close numeric,            -- stock's close price on prediction_date (what you'd buy at)

  -- filled in once target_date has passed and the outcome is known
  actual_close numeric,               -- best close reached anywhere in the window
  pct_change numeric,
  hit boolean,                        -- true if pct_change > TARGET_PCT (see scripts/model.py)

  status text not null default 'pending',  -- 'pending' -> 'resolved'
  created_at timestamptz not null default now(),

  unique (target_date, ticker)
);

-- Lets the dashboard read this table with the public anon key (read-only)
alter table daily_picks enable row level security;
create policy "Public read access" on daily_picks
  for select using (true);
