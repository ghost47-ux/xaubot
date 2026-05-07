# tests/test_risk.py
from datetime import datetime, timezone

from risk.engine import assess_risk
from state.models import Edge1Signal, RegimeState, TrendState, VolatilityState, SessionName, WeekdayName


def make_edge1_signal(stop_distance, sizing_factor=1.0):
    return Edge1Signal(
        timestamp=datetime(2026, 5, 4, 9, 0, tzinfo=timezone.utc),
        direction='LONG',
        entry_price=100.0,
        stop_loss=100.0 - stop_distance,
        take_profit=100.0 + 1.5 * stop_distance,
        stop_distance=stop_distance,
        dollar_risk=stop_distance,
        timeout_bar=200,
        ema20=100.0,
        ema50=99.5,
        ema200=99.0,
        atr=0.5,
        session='London_Main',
        weekday='TUE',
        regime=RegimeState(
            timestamp=datetime(2026, 5, 4, 9, 0, tzinfo=timezone.utc),
            trend_1h=TrendState.BULL,
            ema20_1h=100.0,
            ema50_1h=99.5,
            ema200_1h=99.0,
            atr_1h=0.5,
            volatility=VolatilityState.NORMAL,
            session=SessionName.LONDON_MAIN,
            weekday=WeekdayName.TUE,
            hour_utc=9
        ),
        sizing_factor=sizing_factor
    )


def test_assess_risk_flags():
    signal = make_edge1_signal(stop_distance=1.0, sizing_factor=1.0)
    result = assess_risk(signal, None)
    assert result['dollar_risk_raw'] == 1.0
    assert result['dollar_risk_adj'] == 1.0
    assert result['risk_flag'] == 'ACCEPTABLE'
    assert result['timeout_hours'] == 72


def test_assess_risk_elevated_flag():
    signal = make_edge1_signal(stop_distance=3.0, sizing_factor=1.0)
    result = assess_risk(signal, None)
    assert result['risk_flag'] == 'ELEVATED'
