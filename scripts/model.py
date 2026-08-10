"""
Same LightGBM approach as your geminiML1.py, with the two changes you
asked for: the target is now "closes up 1.5% or more TOMORROW" (not
+2.5% within any of the next 3 days), and the confidence bar to act on
a pick is 50% (not 60%).
"""
import lightgbm as lgb
from features import FEATURE_COLUMNS

POP_THRESHOLD = 0.015   # +1.5%
CONFIDENCE_THRESHOLD = 0.50


def add_target(df):
    df = df.copy()
    next_close = df.groupby('Ticker')['Close'].shift(-1)
    df['target'] = ((next_close - df['Close']) / df['Close'] > POP_THRESHOLD).astype(int)
    return df


def train(df_with_target):
    """Trains on every row that has a known outcome (i.e. not the most
    recent day per ticker, since tomorrow hasn't happened yet)."""
    train_df = df_with_target.dropna(subset=['target'] + FEATURE_COLUMNS)
    model = lgb.LGBMClassifier(
        n_estimators=300, learning_rate=0.03, num_leaves=20,
        random_state=42, verbose=-1,
    )
    model.fit(train_df[FEATURE_COLUMNS], train_df['target'])
    return model


def rank_candidates(model, df_with_target, as_of_date):
    """Returns tickers ranked by predicted probability of a pop, for the
    single day `as_of_date` — this is the day the pick would be acted on."""
    latest = df_with_target[df_with_target['Date'] == as_of_date].copy()
    if latest.empty:
        raise ValueError(f"No price rows found for {as_of_date} — did the scraper run for that date?")

    latest['prob_jump'] = model.predict_proba(latest[FEATURE_COLUMNS])[:, 1]
    candidates = latest[latest['prob_jump'] > CONFIDENCE_THRESHOLD].sort_values(
        'prob_jump', ascending=False
    )
    return candidates[['Ticker', 'Close', 'prob_jump']]
