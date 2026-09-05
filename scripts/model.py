"""
Same LightGBM approach as your geminiML1.py. The three numbers below are
the entire definition of the strategy — change any of them to test
something else; nothing else in this file (or anywhere downstream) needs
to change.

Defaults match geminiML1.py exactly: does this stock close 2.5%+ above
today's close at any point in the next 3 trading days, with the model at
least 60% confident.
"""
import lightgbm as lgb
from features import FEATURE_COLUMNS

# ============================================================================
# CONFIG — edit these three to test a different strategy
# ============================================================================
TARGET_PCT = 0.025            # the "pop" size that counts as a win (2.5%)
TARGET_WINDOW_DAYS = 3         # within how many trading days
CONFIDENCE_THRESHOLD = 0.60    # only act on picks with predicted probability above this
# ============================================================================

# Kept as a plain alias — run_daily.py / backfill.py import this name for
# resolving outcomes, so it always reflects whatever TARGET_PCT is set to.
POP_THRESHOLD = TARGET_PCT


def add_target(df):
    """Label = 1 if the close ever reaches TARGET_PCT above today's close
    within the next TARGET_WINDOW_DAYS trading days (same rolling-max
    approach as geminiML1.py, generalized to any window length)."""
    df = df.copy()
    future_max = (
        df.groupby('Ticker')['Close']
          .transform(lambda x: x.shift(-TARGET_WINDOW_DAYS).rolling(TARGET_WINDOW_DAYS).max())
    )
    df['target'] = ((future_max - df['Close']) / df['Close'] > TARGET_PCT).astype(int)
    return df


def train(df_with_target):
    """Trains on every row with a known outcome (i.e. rows more than
    TARGET_WINDOW_DAYS from the end per ticker, since the label needs
    that many future days to exist)."""
    train_df = df_with_target.dropna(subset=['target'] + FEATURE_COLUMNS)
    model = lgb.LGBMClassifier(
        n_estimators=300, learning_rate=0.03, num_leaves=20,
        random_state=42, verbose=-1,
    )
    model.fit(train_df[FEATURE_COLUMNS], train_df['target'])
    return model


def rank_candidates(model, df_with_target, as_of_date):
    """Returns tickers ranked by predicted probability of a pop, as of
    `as_of_date` — this is the day the pick would be acted on (bought at
    that day's close)."""
    latest = df_with_target[df_with_target['Date'] == as_of_date].copy()
    if latest.empty:
        raise ValueError(f"No price rows found for {as_of_date} — did the scraper run for that date?")

    latest['prob_jump'] = model.predict_proba(latest[FEATURE_COLUMNS])[:, 1]
    candidates = latest[latest['prob_jump'] > CONFIDENCE_THRESHOLD].sort_values(
        'prob_jump', ascending=False
    )
    return candidates[['Ticker', 'Close', 'prob_jump']]
