# risk/engine.py
import logging
from typing import Dict

from config import settings
from state.models import Edge1Signal, Edge2Signal

logger = logging.getLogger(__name__)


def assess_risk(signal, bot_state) -> Dict[str, float]:
    dollar_risk_raw = signal.stop_distance * settings.USD_PER_POINT
    dollar_risk_adj = dollar_risk_raw * signal.sizing_factor
    dollar_target = signal.stop_distance * 1.5 * settings.USD_PER_POINT
    account_risk_pct = (dollar_risk_adj / settings.ACCOUNT_BALANCE) * 100
    rr = 1.5

    if dollar_risk_adj <= 2.00:
        risk_flag = 'ACCEPTABLE'
    elif dollar_risk_adj <= 3.50:
        risk_flag = 'ELEVATED'
    elif dollar_risk_adj <= 5.00:
        risk_flag = 'HIGH'
    else:
        risk_flag = 'REJECTED'

    if isinstance(signal, Edge1Signal):
        timeout_hours = settings.E1_TIMEOUT_BARS
    else:
        timeout_hours = int(settings.E2_TIMEOUT_BARS * 0.25)

    logger.info(
        'At $10 with 0.01 lot fixed: $%s stop = $%s risk = %s%% of account.',
        signal.stop_distance,
        dollar_risk_adj,
        round(account_risk_pct, 2)
    )

    return {
        'dollar_risk_raw': dollar_risk_raw,
        'dollar_risk_adj': dollar_risk_adj,
        'dollar_target': dollar_target,
        'account_risk_pct': account_risk_pct,
        'rr': rr,
        'risk_flag': risk_flag,
        'sizing_factor': signal.sizing_factor,
        'overlap_active': signal.overlap_active,
        'timeout_hours': timeout_hours
    }
