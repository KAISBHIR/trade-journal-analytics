from __future__ import annotations

from typing import Dict

import pandas as pd


REQUIRED_COLUMNS = {"Ticket", "Symbol", "OpenTime", "CloseTime", "Profit"}


def load_csv(file_path: str, sep: str = ",") -> pd.DataFrame:
    """Load a CSV and coerce time fields to datetime."""

    df = pd.read_csv(file_path, sep=sep, on_bad_lines="skip")
    for col in ("OpenTime", "CloseTime"):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
    return df


def analyze_trades(df: pd.DataFrame) -> Dict[str, float]:
    """Return a couple of high level metrics resilient to missing data."""

    if df is None or df.empty:
        return {"total_trades": 0, "profit_factor": 0.0, "net_profit": 0.0}

    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"DataFrame missing required columns: {', '.join(sorted(missing))}")

    total_trades = len(df)
    net_profit = float(df["Profit"].sum())
    gross_profit = float(df.loc[df["Profit"] > 0, "Profit"].sum())
    gross_loss = float(df.loc[df["Profit"] < 0, "Profit"].sum())

    profit_factor = gross_profit / abs(gross_loss) if gross_loss != 0 else float("inf") if gross_profit > 0 else 0.0

    return {
        "total_trades": total_trades,
        "net_profit": net_profit,
        "profit_factor": profit_factor,
    }
