# tests/test_regime.py
from datetime import datetime, timezone

import pandas as pd

from regimes.engine import classify_regime
from state.models import TrendState, VolatilityState, SessionName, WeekdayName


def test_classify_regime_bullish():
    timestamps = pd.date_range('2026-05-01 00:00', periods=220, freq='h', tz='UTC')
    close = pd.Series([100 + i * 0.1 for i in range(220)])
    high = close + 0.5
    low = close - 0.5
    df = pd.DataFrame({'timestamp': timestamps, 'open': close.shift(1).fillna(close.iloc[0]), 'high': high, 'low': low, 'close': close, 'volume': 1})

    current_bar = 219
    current_datetime = datetime(2026, 5, 11, 13, 15, tzinfo=timezone.utc)
    regime = classify_regime(df, current_bar, current_datetime)

    assert regime.trend_1h == TrendState.BULL
    assert regime.volatility == VolatilityState.NORMAL
    assert regime.session == SessionName.NY_MAIN
    assert regime.weekday == WeekdayName.MON
