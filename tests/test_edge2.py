# tests/test_edge2.py
from datetime import datetime, timezone

import pandas as pd

from edges.edge2.detector import detect_compression_zones, detect_edge2
from state.models import BreakoutClass, Edge2Signal, RegimeState, TrendState, VolatilityState, SessionName, WeekdayName


class DummyBotState:
    def __init__(self, e2_trades_today=0):
        self.e2_trades_today = e2_trades_today


def test_detect_compression_zones_finds_zone():
    timestamps = pd.date_range('2026-05-01 00:00', periods=21, freq='15min', tz='UTC')
    open_ = [100.1] * 20 + [100.1]
    close = [100.4] * 20 + [100.6]
    high = [100.5] * 20 + [100.7]
    low = [100.0] * 20 + [100.0]
    volume = [10] * 21
    df = pd.DataFrame({'timestamp': timestamps, 'open': open_, 'high': high, 'low': low, 'close': close, 'volume': volume})

    zones = detect_compression_zones(df.iloc[:20])
    assert len(zones) >= 1
    assert zones[-1].start_bar == 0
    assert zones[-1].end_bar == 19


def test_detect_edge2_builds_signal():
    timestamps = pd.date_range('2026-05-01 00:00', periods=21, freq='15min', tz='UTC')
    open_ = [100.1] * 20 + [100.1]
    close = [100.4] * 20 + [100.6]
    high = [100.5] * 20 + [100.7]
    low = [100.0] * 20 + [100.0]
    volume = [10] * 21
    df = pd.DataFrame({'timestamp': timestamps, 'open': open_, 'high': high, 'low': low, 'close': close, 'volume': volume})

    zones = detect_compression_zones(df.iloc[:20])
    regime = RegimeState(
        timestamp=datetime(2026, 5, 4, 9, 0, tzinfo=timezone.utc),
        trend_1h=TrendState.BULL,
        ema20_1h=100.4,
        ema50_1h=100.2,
        ema200_1h=100.0,
        atr_1h=0.5,
        volatility=VolatilityState.NORMAL,
        session=SessionName.LONDON_MAIN,
        weekday=WeekdayName.TUE,
        hour_utc=9
    )
    bot_state = DummyBotState()
    signal = detect_edge2(df, 20, regime, bot_state, zones)

    assert isinstance(signal, Edge2Signal)
    assert signal.direction == 'LONG'
    assert signal.breakout_class in [BreakoutClass.A, BreakoutClass.B]
    assert signal.entry_price == 100.6


def test_detect_edge2_rejects_when_no_zone():
    timestamps = pd.date_range('2026-05-01 00:00', periods=21, freq='15min', tz='UTC')
    open_ = [100.1] * 21
    close = [100.4] * 21
    high = [100.5] * 21
    low = [100.0] * 21
    volume = [10] * 21
    df = pd.DataFrame({'timestamp': timestamps, 'open': open_, 'high': high, 'low': low, 'close': close, 'volume': volume})

    zones = detect_compression_zones(df)
    regime = RegimeState(
        timestamp=datetime(2026, 5, 4, 9, 0, tzinfo=timezone.utc),
        trend_1h=TrendState.BULL,
        ema20_1h=100.4,
        ema50_1h=100.2,
        ema200_1h=100.0,
        atr_1h=0.5,
        volatility=VolatilityState.NORMAL,
        session=SessionName.LONDON_MAIN,
        weekday=WeekdayName.TUE,
        hour_utc=9
    )
    bot_state = DummyBotState()
    signal = detect_edge2(df, 20, regime, bot_state, zones)

    assert signal is None
