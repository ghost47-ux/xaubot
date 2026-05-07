# overlap/engine.py
import logging
from typing import Optional, Tuple

from config import settings
from state.models import Edge1Signal, Edge2Signal

logger = logging.getLogger(__name__)


def _signal_priority(e1_signal: Optional[Edge1Signal], e2_signal: Optional[Edge2Signal]) -> tuple:
    if e1_signal is not None:
        return (3, 'E1')
    if e2_signal is None:
        return (0, 'NONE')
    if e2_signal.direction == 'LONG' and e2_signal.breakout_class.name == 'A':
        return (2, 'E2_A')
    if e2_signal.direction == 'LONG' and e2_signal.breakout_class.name == 'B':
        return (1.5, 'E2_B')
    return (1, 'E2_OTHER')


def apply_overlap_rules(e1_signal: Optional[Edge1Signal],
                        e2_signal: Optional[Edge2Signal],
                        bot_state) -> Tuple[Optional[Edge1Signal], Optional[Edge2Signal]]:
    e2_oos_count = getattr(bot_state, 'e2_oos_trade_count', 0)
    bot_state.e2_oos_trade_count = e2_oos_count

    both_active = e1_signal is not None and e2_signal is not None
    if both_active:
        if e1_signal is not None:
            e1_signal.sizing_factor = 1.0 - settings.OVERLAP_SIZING_REDUCTION
            e1_signal.overlap_active = True
        if e2_signal is not None:
            e2_signal.sizing_factor = 1.0 - settings.OVERLAP_SIZING_REDUCTION
            e2_signal.overlap_active = True

    if e1_signal is not None and e2_signal is not None and e2_signal.direction == 'SHORT':
        e2_signal.e2_short_suppressed = True
        logger.info('OOS E2 SHORT during E1 active — strong prior until E2 OOS count = %s', settings.E2_MIN_OOS_TRADES_FOR_LOCK)

    if both_active:
        adjusted_risk_e1 = e1_signal.dollar_risk * e1_signal.sizing_factor
        adjusted_risk_e2 = e2_signal.dollar_risk * e2_signal.sizing_factor
        combined_adjusted_risk = adjusted_risk_e1 + adjusted_risk_e2
        if combined_adjusted_risk > settings.MAX_COMBINED_RISK_USD:
            _, winner = _signal_priority(e1_signal, e2_signal)
            if winner == 'E1':
                logger.info('Overlap combined risk %s > %s, dropping lower-priority E2 signal', combined_adjusted_risk, settings.MAX_COMBINED_RISK_USD)
                e2_signal = None
            else:
                logger.info('Overlap combined risk %s > %s, dropping lower-priority E1 signal', combined_adjusted_risk, settings.MAX_COMBINED_RISK_USD)
                e1_signal = None

    logger.info('Phase 11 caveat: E2 OOS trade count = %s. Locks at %s.', e2_oos_count, settings.E2_MIN_OOS_TRADES_FOR_LOCK)
    return e1_signal, e2_signal
