# tests/test_overlap.py
from datetime import datetime, timezone

from overlap.engine import apply_overlap_rules
from state.models import Edge1Signal, Edge2Signal, RegimeState, TrendState, VolatilityState, SessionName, WeekdayName, BreakoutClass


def make_dummy_edge1():
    return Edge1Signal(
        timestamp=datetime(2026, 5, 4, 9, 0, tzinfo=timezone.utc),
        direction='LONG',
        entry_price=100.0,
        stop_loss=99.0,
        take_profit=101.5,
        stop_distance=1.0,
        dollar_risk=1.0,
        timeout_bar=100,
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
        )
    )


def make_dummy_edge2(direction='LONG', breakout_class=BreakoutClass.A, dollar_risk=1.0):
    return Edge2Signal(
        timestamp=datetime(2026, 5, 4, 9, 0, tzinfo=timezone.utc),
        direction=direction,
        breakout_class=breakout_class,
        entry_price=100.0,
        stop_loss=99.0 if direction == 'LONG' else 101.0,
        take_profit=101.5 if direction == 'LONG' else 98.5,
        stop_distance=1.0,
        dollar_risk=dollar_risk,
        timeout_bar=100,
        compression_high=100.5,
        compression_low=99.5,
        atr=0.5,
        session='London_Main'
    )


class DummyBotState:
    def __init__(self):
        self.e2_trades_today = 0
        self.e2_oos_trade_count = 5


def test_overlap_both_active_sizing_reduction():
    e1 = make_dummy_edge1()
    e2 = make_dummy_edge2()
    bot_state = DummyBotState()

    e1_out, e2_out = apply_overlap_rules(e1, e2, bot_state)

    assert e1_out is not None
    assert e2_out is not None
    assert e1_out.sizing_factor == 0.7
    assert e2_out.sizing_factor == 0.7
    assert e1_out.overlap_active
    assert e2_out.overlap_active


def test_overlap_e2_short_suppressed():
    e1 = make_dummy_edge1()
    e2 = make_dummy_edge2(direction='SHORT', breakout_class=BreakoutClass.A)
    bot_state = DummyBotState()

    _, e2_out = apply_overlap_rules(e1, e2, bot_state)

    assert e2_out is not None
    assert e2_out.e2_short_suppressed


def test_overlap_combined_risk_over_limit_drops_lower_priority():
    e1 = make_dummy_edge1()
    e1.dollar_risk = 6.0
    e2 = make_dummy_edge2(direction='LONG', breakout_class=BreakoutClass.A, dollar_risk=6.0)
    bot_state = DummyBotState()

    e1_out, e2_out = apply_overlap_rules(e1, e2, bot_state)

    assert e1_out is not None
    assert e2_out is None
