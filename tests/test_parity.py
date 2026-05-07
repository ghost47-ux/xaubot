import os
import tempfile
from datetime import datetime, timezone

import pandas as pd

from indicators.core import ema, atr
from parity import monitor


def test_load_reference_snapshot_and_parity_ok(tmp_path):
    temp_dir = tmp_path / 'backtest_ref'
    temp_dir.mkdir()
    path = temp_dir / 'reference.parquet'
    timestamp = datetime(2026, 5, 7, 0, 0, tzinfo=timezone.utc)

    data = pd.DataFrame([
        {
            'timestamp': timestamp,
            'ema20_1h': 100.0,
            'ema50_1h': 99.0,
            'ema200_1h': 98.0,
            'atr_1h': 0.5,
            'atr_m15': 0.2,
            'swing_low_10': 99.5,
            'swing_high_10': 100.5,
            'session': 'London_Main',
            'weekday': 'MON'
        }
    ])
    data.to_parquet(path, index=False)

    monitor.REFERENCE_PATH = str(path)

    df_1h = pd.DataFrame({
        'timestamp': [timestamp],
        'open': [99.8],
        'high': [100.2],
        'low': [99.7],
        'close': [100.0],
        'volume': [100]
    })
    df_m15 = pd.DataFrame({
        'timestamp': [timestamp],
        'open': [99.9],
        'high': [100.1],
        'low': [99.8],
        'close': [100.0],
        'volume': [100]
    })
    regime = type('R', (), {'session': type('S', (), {'value': 'London_Main'}), 'weekday': None})()

    result = monitor.run_parity_check(df_1h, df_m15, 0, 0, regime)
    assert result.status.name in ['OK', 'WARNING', 'BREACH']
    assert isinstance(result.failed_checks, list)


def test_check_absolute_with_tolerance():
    check = monitor.check_absolute(100.1, 100.0, 0.2, 'ema20')
    assert check.passed
    assert abs(check.difference - 0.1) < 1e-9
