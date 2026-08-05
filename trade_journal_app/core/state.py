from __future__ import annotations

from dataclasses import dataclass, field
from threading import RLock
from typing import Dict, Optional

import pandas as pd


@dataclass
class JournalStore:
    """Thread-safe in-memory storage for the current upload lifecycle.

    This keeps the FastAPI request handlers and the Dash callbacks in sync
    without relying on bare module-level globals.
    """

    _strategies: Dict[int, str] = field(default_factory=lambda: {i: "" for i in range(1, 5)})
    _dataframe: Optional[pd.DataFrame] = None
    _lock: RLock = field(default_factory=RLock, init=False)
    _uploaded_filename: Optional[str] = None

    def set_strategies(self, strategies: Dict[int, str]) -> None:
        cleaned = {i: (strategies.get(i, "") or "").strip() for i in range(1, 5)}
        with self._lock:
            self._strategies = cleaned

    def get_strategies(self) -> Dict[int, str]:
        with self._lock:
            return dict(self._strategies)

    def set_dataframe(self, df: pd.DataFrame, filename: Optional[str] = None) -> None:
        with self._lock:
            self._dataframe = df.copy()
            if filename is not None:
                self._uploaded_filename = filename

    def get_dataframe(self) -> pd.DataFrame:
        with self._lock:
            if self._dataframe is None:
                return pd.DataFrame()
            return self._dataframe.copy()

    def get_uploaded_filename(self) -> Optional[str]:
        with self._lock:
            return self._uploaded_filename


def get_store_from_request(request) -> JournalStore:
    """Convenience accessor for FastAPI dependencies."""

    return request.app.state.journal_store
