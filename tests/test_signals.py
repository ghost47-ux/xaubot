from datetime import datetime, timezone

from signals.output import format_signal
from state.models import (
    Edge1Signal,
    Edge2Signal,
    RegimeState,
    TrendState,
    VolatilityState,
    SessionName,
    WeekdayName,
    BreakoutClass,
    CriticOutput,
    DriftState,
    DriftSeverity,
    DriftFlag,
    ParityState,
    ParityCheck,
    ParityStatus
)


def make_regime():
    return RegimeState(
        timestamp=datetime(2026, 5, 7, 12, 0, tzinfo=timezone.utc),
        trend_1h=TrendState.BULL,
        ema20_1h=100.0,
        ema50_1h=99.5,
        ema200_1h=99.0,
        atr_1h=0.5,
        volatility=VolatilityState.NORMAL,
        session=SessionName.LONDON_MAIN,
        weekday=WeekdayName.WED,
        hour_utc=12
    )


def make_edge1_signal():
    return Edge1Signal(
        timestamp=datetime(2026, 5, 7, 12, 0, tzinfo=timezone.utc),
        direction='LONG',
        entry_price=100.0,
        stop_loss=99.0,
        take_profit=101.5,
        stop_distance=1.0,
        dollar_risk=1.0,
        timeout_bar=72,
        ema20=100.0,
        ema50=99.5,
        ema200=99.0,
        atr=0.5,
        session='London_Main',
        weekday='WED',
        regime=make_regime()
    )


def make_critic_output():
    return CriticOutput(
        timestamp=datetime(2026, 5, 7, 12, 0, tzinfo=timezone.utc),
        critic_called=True,
        signal_type='TRADE',
        edge_source='EDGE 1',
        contradictions=['None.'],
        confirmations=['None.'],
        drift_flags_in_context=['None.'],
        parity_flags_in_context=['None.'],
        context_notes=['None.'],
        raw_critic_text='None.',
        tokens_used=0,
        output_bounded=True,
        decision_words_found=[]
    )


def test_format_trade_signal_contains_expected_blocks():
    signal = make_edge1_signal()
    result = format_signal('TRADE', signal, None, {'timeout_hours': 72, 'dollar_risk_adj': 1.0, 'account_risk_pct': 10.0, 'risk_flag': 'ACCEPTABLE'}, bot_state=None, drift_state=DriftState(
        timestamp=datetime(2026, 5, 7, 12, 0, tzinfo=timezone.utc),
        severity=DriftSeverity.NONE,
        e1_rolling_ev=0.3,
        e1_rolling_wr=0.5,
        e1_consecutive_losses=0,
        e1_trade_count=0,
        e2_rolling_ev=0.6,
        e2_rolling_wr=0.56,
        e2_consecutive_losses=0,
        e2_trade_count=0,
        atr_1h_current=0.5,
        atr_1h_mean_90d=0.4,
        atr_ratio=1.25,
        volatility_outside_backtest=False,
        regime_flip_count_14d=0,
        regime_choppy=False,
        e1_session_ev={'London_Main': 0.3},
        session_rotation_flag=False,
        active_flags=[]
    ),
    parity_state=ParityState(
        timestamp=datetime(2026, 5, 7, 12, 0, tzinfo=timezone.utc),
        status=ParityStatus.OK,
        ema20_check=None,
        ema50_check=None,
        ema200_check=None,
        atr_1h_check=None,
        atr_m15_check=None,
        swing_low_check=None,
        session_check=None,
        candles_checked=0,
        missing_candles_1h=0,
        missing_candles_m15=0,
        data_quality_ok=True,
        cumulative_ema20_drift=0.0,
        cumulative_atr_drift=0.0,
        parity_check_count=0,
        failed_checks=[]
    ),
    critic_output=make_critic_output())
    assert 'SIGNAL: XAU/USD' in result
    assert 'SYSTEM HEALTH' in result
    assert 'CRITIC LAYER OUTPUT' in result


def test_format_no_trade_signal_contains_reason():
    result = format_signal('NO_TRADE', None, None, None, bot_state=type('B', (), {'e1_reject_reason': 'Test', 'e2_reject_reason': 'Test'}))
    assert 'NO TRADE — XAU/USD' in result
    assert '[Edge 1]: ✗ Test' in result
    assert '[Edge 2]: ✗ Test' in result
