-- Run this once in Supabase: Project > SQL Editor > New query > paste > Run

create table if not exists daily_picks (
  id bigserial primary key,

  -- prediction_date = the day the data was as-of (day before target_date)
  -- target_date     = the day being predicted for (the pick is meant to pop on this day)
  prediction_date date not null,
  target_date date not null,

  ticker text not null,
  confidence numeric not null,        -- model's predicted probability, 0-1
  reference_close numeric,            -- stock's close price on prediction_date (what you'd buy at)

  -- filled in the day after target_date, once the outcome is known
  actual_close numeric,
  pct_change numeric,
  hit boolean,                        -- true if pct_change >= 0.015

  status text not null default 'pending',  -- 'pending' -> 'resolved'
  created_at timestamptz not null default now(),

  unique (target_date, ticker)
);

-- Lets the dashboard read this table with the public anon key (read-only)
alter table daily_picks enable row level security;
create policy "Public read access" on daily_picks
  for select using (true);
