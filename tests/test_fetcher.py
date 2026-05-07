# tests/test_fetcher.py
import pandas as pd
from datetime import datetime, timedelta, timezone

from data.fetcher import validate_candles


def test_validate_candles_accepts_clean_dataframe():
    timestamps = [datetime(2026, 5, 7, 0, 0, tzinfo=timezone.utc) + timedelta(minutes=15 * i) for i in range(4)]
    df = pd.DataFrame({
        'timestamp': timestamps,
        'open': [1.0, 1.1, 1.2, 1.3],
        'high': [1.2, 1.3, 1.4, 1.5],
        'low': [0.9, 1.0, 1.1, 1.2],
        'close': [1.1, 1.2, 1.3, 1.4],
        'volume': [10, 12, 14, 16]
    })
    assert validate_candles(df)


def test_validate_candles_rejects_missing_values():
    timestamps = [datetime(2026, 5, 7, 0, 0, tzinfo=timezone.utc) + timedelta(minutes=15 * i) for i in range(4)]
    df = pd.DataFrame({
        'timestamp': timestamps,
        'open': [1.0, None, 1.2, 1.3],
        'high': [1.2, 1.3, 1.4, 1.5],
        'low': [0.9, 1.0, 1.1, 1.2],
        'close': [1.1, 1.2, 1.3, 1.4],
        'volume': [10, 12, 14, 16]
    })
    assert not validate_candles(df)


def test_validate_candles_rejects_high_low_inverted():
    timestamps = [datetime(2026, 5, 7, 0, 0, tzinfo=timezone.utc) + timedelta(minutes=15 * i) for i in range(4)]
    df = pd.DataFrame({
        'timestamp': timestamps,
        'open': [1.0, 1.1, 1.2, 1.3],
        'high': [1.0, 1.0, 1.0, 1.0],
        'low': [1.1, 1.0, 1.1, 1.2],
        'close': [1.1, 1.2, 1.3, 1.4],
        'volume': [10, 12, 14, 16]
    })
    assert not validate_candles(df)


def test_validate_candles_rejects_large_gaps():
    timestamps = [datetime(2026, 5, 7, 0, 0, tzinfo=timezone.utc),
                  datetime(2026, 5, 7, 0, 15, tzinfo=timezone.utc),
                  datetime(2026, 5, 7, 1, 15, tzinfo=timezone.utc),
                  datetime(2026, 5, 7, 1, 30, tzinfo=timezone.utc)]
    df = pd.DataFrame({
        'timestamp': timestamps,
        'open': [1.0, 1.1, 1.2, 1.3],
        'high': [1.2, 1.3, 1.4, 1.5],
        'low': [0.9, 1.0, 1.1, 1.2],
        'close': [1.1, 1.2, 1.3, 1.4],
        'volume': [10, 12, 14, 16]
    })
    assert not validate_candles(df)
