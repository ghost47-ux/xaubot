# edges/edge2/detector.py
import logging
from typing import List, Optional

import pandas as pd

from config import settings
from indicators.core import atr, rolling_range, body_ratio, wick_ratio, swing_point
from state.models import CompressionZone, Edge2Signal, BreakoutClass, RegimeState

logger = logging.getLogger(__name__)


def detect_compression_zones(df_m15: pd.DataFrame) -> List[CompressionZone]:
    atr_series = atr(df_m15, 14)
    range_series = rolling_range(df_m15, 20)
    zones: List[CompressionZone] = []

    for end_bar in range(19, len(df_m15)):
        atr_at_detection = atr_series.iloc[end_bar]
        range_value = range_series.iloc[end_bar]
        if pd.isna(atr_at_detection) or pd.isna(range_value):
            continue

        if range_value / atr_at_detection > settings.E2_COMPRESSION_MULT:
            continue

        window = df_m15.iloc[end_bar - 19:end_bar + 1]
        range_low = window['low'].min()
        range_high = window['high'].max()
        range_height = range_high - range_low

        if range_height < settings.E2_RANGE_MIN_ATR_MULT * atr_at_detection:
            continue
        if range_height > settings.E2_RANGE_MAX_ATR_MULT * atr_at_detection:
            continue

        zone = CompressionZone(
            start_bar=end_bar - 19,
            end_bar=end_bar,
            range_high=range_high,
            range_low=range_low,
            range_height=range_height,
            atr_at_detection=atr_at_detection
        )
        zones.append(zone)

    return zones


def classify_breakout(row: pd.Series, compression_zone: CompressionZone, direction: str) -> BreakoutClass:
    total_range = row['high'] - row['low']
    if total_range == 0:
        return BreakoutClass.FAKEOUT

    if body_ratio(row) < settings.E2_FAKEOUT_BODY_MIN or wick_ratio(row, direction) > settings.E2_FAKEOUT_WICK_RATIO:
        return BreakoutClass.FAKEOUT

    if direction == 'LONG':
        if (row['close'] - row['low']) / total_range >= settings.E2_CLASS_A_CLOSE_MULT:
            return BreakoutClass.A
    else:
        if (row['high'] - row['close']) / total_range >= settings.E2_CLASS_A_CLOSE_MULT:
            return BreakoutClass.A

    return BreakoutClass.B


def detect_edge2(df_m15: pd.DataFrame,
                 current_bar: int,
                 regime: RegimeState,
                 bot_state,
                 compression_zones: List[CompressionZone]) -> Optional[Edge2Signal]:
    bot_state.e2_reject_reason = ''
    current_row = df_m15.iloc[current_bar]
    current_close = current_row['close']
    atr_value = atr(df_m15, 14).iloc[current_bar]

    if bot_state.e2_trades_today >= settings.MAX_DAILY_TRADES_E2:
        bot_state.e2_reject_reason = 'Daily limit reached'
        logger.info('E2 rejected — daily limit reached: %s', bot_state.e2_trades_today)
        return None

    valid_zones = [z for z in compression_zones if z.end_bar < current_bar and not getattr(z, 'used', False)]
    if not valid_zones:
        bot_state.e2_reject_reason = 'No valid compression zone found'
        logger.info('E2 rejected — no valid compression zone found')
        return None

    zone = max(valid_zones, key=lambda z: z.end_bar)

    long_break = current_close > zone.range_high
    short_break = current_close < zone.range_low

    if not long_break and not short_break:
        logger.info('E2 rejected — no breakout detected: close=%s zone_high=%s zone_low=%s', current_close, zone.range_high, zone.range_low)
        return None

    direction = 'LONG' if long_break else 'SHORT'
    breakout_class = classify_breakout(current_row, zone, direction)
    if breakout_class == BreakoutClass.FAKEOUT:
        logger.info('E2 rejected — fakeout detected: direction=%s', direction)
        return None

    if current_bar < settings.E2_SL_SWING_LOOKBACK - 1:
        logger.info('E2 rejected — insufficient history for swing point')
        return None

    swing = swing_point(df_m15.iloc[current_bar - settings.E2_SL_SWING_LOOKBACK + 1: current_bar + 1], settings.E2_SL_SWING_LOOKBACK, 'long' if direction == 'LONG' else 'short').iloc[-1]
    if direction == 'LONG':
        stop_loss = swing - (settings.E2_SL_ATR_BUFFER * atr_value)
    else:
        stop_loss = swing + (settings.E2_SL_ATR_BUFFER * atr_value)

    stop_distance = abs(current_close - stop_loss)
    take_profit = current_close + (settings.E2_RR * stop_distance if direction == 'LONG' else -settings.E2_RR * stop_distance)
    timeout_bar = current_bar + settings.E2_TIMEOUT_BARS
    dollar_risk = stop_distance * settings.USD_PER_POINT

    zone.used = True

    return Edge2Signal(
        timestamp=current_row['timestamp'],
        direction=direction,
        breakout_class=breakout_class,
        entry_price=current_close,
        stop_loss=stop_loss,
        take_profit=take_profit,
        stop_distance=stop_distance,
        dollar_risk=dollar_risk,
        timeout_bar=timeout_bar,
        compression_high=zone.range_high,
        compression_low=zone.range_low,
        atr=atr_value,
        session=regime.session.value,
        sizing_factor=1.0,
        adjusted_risk=0.0,
        overlap_active=False,
        e2_short_suppressed=False
    )
