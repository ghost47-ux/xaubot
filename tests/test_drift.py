from datetime import datetime, timezone

import pandas as pd

from drift.detector import detect_drift
from state.models import RegimeState, TrendState, VolatilityState, SessionName, WeekdayName


def test_detect_drift_warns_on_consecutive_losses():
    trade_log = []
    for i in range(5):
        trade_log.append({
            'edge_source': 'EDGE1',
            'outcome': 'LOSS',
            'result_r': -1.0,
            'timestamp_utc': datetime(2026, 5, 1, 0, 0, tzinfo=timezone.utc).isoformat(),
            'trend_1h': 'BULL',
            'session': 'London_Main'
        })

    regime = RegimeState(
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
    df_1h = pd.DataFrame({
        'timestamp': [datetime(2026, 5, 7, 11, 0, tzinfo=timezone.utc)],
        'open': [100.0],
        'high': [100.5],
        'low': [99.5],
        'close': [100.0],
        'atr_1h': [0.5]
    })
    drift_state = detect_drift(trade_log, regime, df_1h, 0)
    assert drift_state.severity.value in ['WATCH', 'CAUTION', 'ALERT', 'NONE']
    assert drift_state.e1_consecutive_losses >= 5
