"""
Generate reference snapshots for parity monitoring.

This script creates baseline indicator values that the live system
compares against to ensure byte-for-byte identical calculations.

The reference engine must export these snapshots from backtest data.
In production, this should be updated periodically with the latest backtest results.
"""

import os
import logging
from pathlib import Path
import pandas as pd
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

REFERENCE_PATH = os.path.join(os.path.dirname(__file__), 'backtest_ref', 'reference.parquet')


def generate_reference_snapshot(df_1h: pd.DataFrame, df_m15: pd.DataFrame) -> pd.DataFrame:
    """
    Generate reference snapshot from candle data.
    
    This function calculates indicators on the provided dataframes
    and returns a dataframe suitable for storage as the reference baseline.
    
    Args:
        df_1h: DataFrame with 1H candles (timestamp, open, high, low, close, volume)
        df_m15: DataFrame with M15 candles
    
    Returns:
        DataFrame with reference indicator values and metadata
    """
    from indicators.core import ema, atr, swing_low, classify_session
    from state.models import SessionName, WeekdayName
    
    if df_1h.empty:
        logger.warning('generate_reference_snapshot: df_1h is empty')
        return pd.DataFrame()
    
    # Calculate indicators on 1H bars
    ema20_series = ema(df_1h['close'], 20)
    ema50_series = ema(df_1h['close'], 50)
    ema200_series = ema(df_1h['close'], 200)
    atr_1h_series = atr(df_1h, 14)
    
    # Swing low on 1H
    swing_low_10 = swing_low(df_1h, 10)
    
    # ATR on M15
    atr_m15_series = atr(df_m15, 14) if not df_m15.empty else pd.Series([None] * len(df_1h))
    
    # Create reference dataframe
    reference_data = []
    for idx in range(len(df_1h)):
        if pd.isna(ema20_series.iloc[idx]) or pd.isna(ema50_series.iloc[idx]):
            continue
        
        ts = df_1h.iloc[idx]['timestamp']
        session = classify_session(ts.hour, ts.minute)
        weekday = ts.weekday()
        
        # Find matching M15 bar for ATR
        m15_atr = None
        if not df_m15.empty:
            # M15 bars for this hour: 4 bars (0, 15, 30, 45 minutes)
            matching_m15 = df_m15[
                (df_m15['timestamp'] >= ts) & 
                (df_m15['timestamp'] < ts + timedelta(hours=1))
            ]
            if not matching_m15.empty:
                # Use the last M15 bar in this hour
                m15_atr = atr_m15_series.iloc[len(df_m15) - len(df_m15[df_m15['timestamp'] > matching_m15.iloc[-1]['timestamp']])]
        
        reference_data.append({
            'timestamp': ts,
            'ema20_1h': ema20_series.iloc[idx],
            'ema50_1h': ema50_series.iloc[idx],
            'ema200_1h': ema200_series.iloc[idx],
            'atr_1h': atr_1h_series.iloc[idx],
            'atr_m15': m15_atr,
            'swing_low_10': swing_low_10.iloc[idx],
            'swing_high_10': df_1h['high'].rolling(10).max().iloc[idx],
            'session': session.value,
            'weekday': weekday,
        })
    
    return pd.DataFrame(reference_data)


def save_reference_snapshot(df_snapshot: pd.DataFrame, path: str = REFERENCE_PATH) -> None:
    """Save reference snapshot to parquet file."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    df_snapshot.to_parquet(path, index=False)
    logger.info(f'Reference snapshot saved to {path} ({len(df_snapshot)} bars)')


def load_reference_snapshot(timestamp: datetime, path: str = REFERENCE_PATH) -> dict:
    """Load a single reference record by timestamp."""
    if not os.path.exists(path):
        return None
    
    ref = pd.read_parquet(path)
    match = ref[ref['timestamp'] == timestamp]
    if match.empty:
        return None
    
    return match.iloc[0].to_dict()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    print('Reference snapshot generation utility loaded.')
    print('Use: from data.generate_reference_snapshot import generate_reference_snapshot, save_reference_snapshot')
