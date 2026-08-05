import pandas as pd
import re

def detect_strategy(comment, strategies):
    """Detect strategy from comment based on number prefix."""
    if not isinstance(comment, str):
        return "Unlabeled"
    comment = comment.strip().lower()
    for num, name in strategies.items():
        if not name.strip():
            continue
        if re.search(rf'\b{num}\b', comment):
            return name
    return "Unlabeled"

def process_trades(df: pd.DataFrame) -> pd.DataFrame:
    df = df.dropna(subset=['Symbol', 'OpenPrice', 'ClosePrice'])
    df = df.drop_duplicates(subset=['Ticket'])
    df['OpenTime'] = pd.to_datetime(df['OpenTime'], errors='coerce')
    df['CloseTime'] = pd.to_datetime(df['CloseTime'], errors='coerce')
    df['Dir'] = df['Type'].map({'BUY': 1, 'SELL': -1}).fillna(0)
    df['Duration_Hours'] = (df['CloseTime'] - df['OpenTime']).dt.total_seconds() / 3600
    df['Duration_Days'] = df['Duration_Hours'] / 24

    # simple trade outcome
    df['Result'] = df.apply(lambda row: 
        "Win" if "[tp]" in str(row['Comment']).lower() or row['Profit'] > 0
        else "Loss" if "[sl]" in str(row['Comment']).lower() or row['Profit'] < 0
        else "Neutral", axis=1
    )
    return df
