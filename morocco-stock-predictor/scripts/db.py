"""
Thin wrapper around the Supabase client. Credentials come from environment
variables so they're never hardcoded in the repo:

  SUPABASE_URL  - your project URL (Settings > API)
  SUPABASE_KEY  - the service_role key (Settings > API) — NOT the anon key.
                  The service_role key is needed because the daily job writes
                  to the table; the dashboard, which only reads, uses the
                  public anon key separately (see dashboard/index.html).

Locally, put these in a .env file (never commit it). In GitHub Actions,
they come from repo secrets (see .github/workflows/daily.yml).
"""
import os
from supabase import create_client, Client


def get_client() -> Client:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if not url or not key:
        raise RuntimeError(
            "Missing SUPABASE_URL / SUPABASE_KEY environment variables. "
            "Set them in a local .env file or as GitHub Actions secrets."
        )
    return create_client(url, key)


def upsert_pick(client: Client, pick: dict):
    """Insert a new prediction, or update it if one already exists for
    that (target_date, ticker) pair — makes re-running a day safe."""
    return client.table("daily_picks").upsert(pick, on_conflict="target_date,ticker").execute()


def get_pending_picks(client: Client):
    """Picks that haven't had their outcome logged yet."""
    return client.table("daily_picks").select("*").eq("status", "pending").execute().data


def resolve_pick(client: Client, pick_id: int, actual_close: float, pct_change: float, hit: bool):
    return client.table("daily_picks").update({
        "actual_close": actual_close,
        "pct_change": pct_change,
        "hit": hit,
        "status": "resolved",
    }).eq("id", pick_id).execute()
