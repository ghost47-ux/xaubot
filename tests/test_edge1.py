# tests/test_edge1.py
from datetime import datetime, timezone

import pandas as pd

from edges.edge1.detector import detect_edge1
from state.models import RegimeState, TrendState, VolatilityState, SessionName, WeekdayName


class DummyBotState:
    def __init__(self, e1_trades_today=0):
        self.e1_trades_today = e1_trades_today


def test_detect_edge1_passes_all_gates():
    timestamps = pd.date_range('2026-05-01 00:00', periods=15, freq='h', tz='UTC')
    close = pd.Series([100 + i * 0.1 for i in range(15)])
    high = close + 0.5
    low = close - 0.5
    open_ = close.shift(1).fillna(close.iloc[0])
    df = pd.DataFrame({'timestamp': timestamps, 'open': open_, 'high': high, 'low': low, 'close': close, 'volume': 1})

    regime = RegimeState(
        timestamp=datetime(2026, 5, 4, 9, 0, tzinfo=timezone.utc),
        trend_1h=TrendState.BULL,
        ema20_1h=101.0,
        ema50_1h=100.5,
        ema200_1h=100.0,
        atr_1h=0.5,
        volatility=VolatilityState.NORMAL,
        session=SessionName.LONDON_MAIN,
        weekday=WeekdayName.TUE,
        hour_utc=9
    )
    bot_state = DummyBotState()
    signal = detect_edge1(df, 14, regime, bot_state)

    assert signal is not None
    assert signal.direction == 'LONG'
    assert signal.entry_price == df.iloc[14]['close']
    assert signal.stop_loss < signal.entry_price


def test_detect_edge1_rejects_wrong_session():
    timestamps = pd.date_range('2026-05-01 00:00', periods=15, freq='h', tz='UTC')
    close = pd.Series([100 + i * 0.1 for i in range(15)])
    high = close + 0.5
    low = close - 0.5
    open_ = close.shift(1).fillna(close.iloc[0])
    df = pd.DataFrame({'timestamp': timestamps, 'open': open_, 'high': high, 'low': low, 'close': close, 'volume': 1})

    regime = RegimeState(
        timestamp=datetime(2026, 5, 4, 18, 0, tzinfo=timezone.utc),
        trend_1h=TrendState.BULL,
        ema20_1h=101.0,
        ema50_1h=100.5,
        ema200_1h=100.0,
        atr_1h=0.5,
        volatility=VolatilityState.NORMAL,
        session=SessionName.OFF,
        weekday=WeekdayName.TUE,
        hour_utc=18
    )
    bot_state = DummyBotState()
    signal = detect_edge1(df, 14, regime, bot_state)

    assert signal is None
