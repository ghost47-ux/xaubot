# edges/edge1/detector.py
import logging
from typing import Optional

import pandas as pd

from config import settings
from indicators.core import swing_low
from state.models import Edge1Signal, RegimeState, TrendState

logger = logging.getLogger(__name__)


def detect_edge1(df_1h: pd.DataFrame, current_bar: int, regime: RegimeState, bot_state) -> Optional[Edge1Signal]:
    bot_state.e1_reject_reason = ''
    current_row = df_1h.iloc[current_bar]
    current_open = current_row['open']
    current_close = current_row['close']
    current_low = current_row['low']
    ema20 = regime.ema20_1h
    ema50 = regime.ema50_1h
    atr_value = regime.atr_1h

    if bot_state.e1_trades_today >= settings.MAX_DAILY_TRADES_E1:
        bot_state.e1_reject_reason = 'Daily limit reached'
        logger.info('E1 rejected — daily limit reached: %s', bot_state.e1_trades_today)
        return None

    if regime.weekday.value not in settings.E1_VALID_WEEKDAYS:
        bot_state.e1_reject_reason = f'Weekday {regime.weekday.name} not valid'
        logger.info('E1 rejected — weekday %s not valid', regime.weekday.name)
        return None

    if regime.session.value not in settings.E1_VALID_SESSIONS:
        bot_state.e1_reject_reason = f'Session {regime.session.value} not valid'
        logger.info('E1 rejected — session %s not valid', regime.session.value)
        return None

    if regime.trend_1h != TrendState.BULL:
        bot_state.e1_reject_reason = f'Trend not BULL: {regime.trend_1h.value}'
        logger.info('E1 rejected — trend not BULL: %s', regime.trend_1h.value)
        return None

    pullback_valid = (current_low <= ema20) and (current_low >= ema50 * 0.998)
    if not pullback_valid:
        bot_state.e1_reject_reason = f'Pullback invalid: low={current_low} ema20={ema20} ema50*0.998={ema50 * 0.998}'
        logger.info('E1 rejected — pullback invalid: low=%s ema20=%s ema50*0.998=%s', current_low, ema20, ema50 * 0.998)
        return None

    if current_close <= current_open:
        bot_state.e1_reject_reason = f'Continuation invalid: open={current_open} close={current_close}'
        logger.info('E1 rejected — continuation invalid: open=%s close=%s', current_open, current_close)
        return None

    if current_bar < settings.E1_SL_SWING_LOOKBACK - 1:
        bot_state.e1_reject_reason = 'Insufficient history for swing low'
        logger.info('E1 rejected — insufficient history for swing low')
        return None

    swing_sl = swing_low(df_1h.iloc[current_bar - settings.E1_SL_SWING_LOOKBACK + 1: current_bar + 1], settings.E1_SL_SWING_LOOKBACK).iloc[-1]
    stop_loss = swing_sl - (settings.E1_SL_ATR_BUFFER * atr_value)
    stop_distance = current_close - stop_loss
    if stop_distance <= 0:
        bot_state.e1_reject_reason = f'Non-positive stop distance: {stop_distance}'
        logger.info('E1 rejected — non-positive stop distance: %s', stop_distance)
        return None

    dollar_risk = stop_distance * settings.USD_PER_POINT
    if dollar_risk > settings.MAX_SINGLE_TRADE_RISK_USD:
        bot_state.e1_reject_reason = f'Dollar risk too high: {dollar_risk}'
        logger.info('E1 rejected — dollar risk too high: %s', dollar_risk)
        return None

    take_profit = current_close + (settings.E1_RR * stop_distance)
    timeout_bar = current_bar + settings.E1_TIMEOUT_BARS

    return Edge1Signal(
        timestamp=current_row['timestamp'],
        direction=settings.E1_DIRECTION,
        entry_price=current_close,
        stop_loss=stop_loss,
        take_profit=take_profit,
        stop_distance=stop_distance,
        dollar_risk=dollar_risk,
        timeout_bar=timeout_bar,
        ema20=ema20,
        ema50=ema50,
        ema200=regime.ema200_1h,
        atr=atr_value,
        session=regime.session.value,
        weekday=regime.weekday.name,
        regime=regime,
        sizing_factor=1.0,
        adjusted_risk=0.0,
        overlap_active=False
    )
