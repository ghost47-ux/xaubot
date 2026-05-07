# regimes/engine.py
from datetime import datetime
from typing import Optional

import pandas as pd

from indicators.core import ema, atr, classify_volatility, classify_session
from state.models import RegimeState, TrendState, VolatilityState, SessionName, WeekdayName


def classify_regime(df_1h: pd.DataFrame, current_bar: int, current_datetime: datetime) -> RegimeState:
    ema20 = ema(df_1h['close'], 20).iloc[current_bar]
    ema50 = ema(df_1h['close'], 50).iloc[current_bar]
    ema200 = ema(df_1h['close'], 200).iloc[current_bar]

    if ema20 > ema50 > ema200:
        trend = TrendState.BULL
    elif ema20 < ema50 < ema200:
        trend = TrendState.BEAR
    else:
        trend = TrendState.MIXED

    atr_series = atr(df_1h, 14)
    atr_current = atr_series.iloc[current_bar]
    atr_mean_20 = atr_series.rolling(20).mean().iloc[current_bar]
    volatility = classify_volatility(atr_current, atr_mean_20)

    hour_utc = current_datetime.hour
    minute = current_datetime.minute
    session = classify_session(hour_utc, minute)
    weekday = WeekdayName(current_datetime.weekday())

    return RegimeState(
        timestamp=current_datetime,
        trend_1h=trend,
        ema20_1h=ema20,
        ema50_1h=ema50,
        ema200_1h=ema200,
        atr_1h=atr_current,
        volatility=volatility,
        session=session,
        weekday=weekday,
        hour_utc=hour_utc
    )
