# tests/test_indicators.py
import pandas as pd
import pytest

from indicators.core import ema, atr, body_ratio, classify_session


def test_ema_manual_calculation():
    data = pd.Series([10.0, 11.0, 12.0, 11.0, 13.0])
    result = ema(data, 5)

    # Manual EMA calculation for 5-period with alpha=2/(span+1)=1/3
    alpha = 2 / (5 + 1)
    expected = [10.0]
    prev = expected[0]
    for value in data[1:]:
        prev = (value - prev) * alpha + prev
        expected.append(prev)

    assert pytest.approx(result.iloc[-1], rel=1e-9) == expected[-1]


def test_atr_wilder_smoothing():
    df = pd.DataFrame({
        'high': [1.0, 2.0, 3.0, 4.0],
        'low': [0.5, 1.5, 2.5, 3.5],
        'close': [0.75, 1.75, 2.75, 3.75]
    })
    result = atr(df, period=2)

    tr = pd.Series([0.5, 1.25, 1.25, 1.25])
    expected = tr.ewm(alpha=1/2, adjust=False).mean()
    assert pytest.approx(result.iloc[-1], rel=1e-9) == expected.iloc[-1]


def test_body_ratio_zero_range_returns_zero():
    candle = {'open': 1.0, 'high': 1.0, 'low': 1.0, 'close': 1.0}
    assert body_ratio(candle) == 0.0


def test_classify_session_boundaries():
    assert classify_session(0, 0).value == 'Asian'
    assert classify_session(6, 59).value == 'Asian'
    assert classify_session(7, 0).value == 'London_Open'
    assert classify_session(8, 59).value == 'London_Open'
    assert classify_session(9, 0).value == 'London_Main'
    assert classify_session(12, 59).value == 'London_Main'
    assert classify_session(13, 0).value == 'NY_Main'
    assert classify_session(17, 30).value == 'NY_Main'
    assert classify_session(17, 31).value == 'Off'
