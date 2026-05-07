# data/fetcher.py
import os
import json
import logging
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd
import requests

from config import settings

logger = logging.getLogger(__name__)

TWELVEDATA_URL = 'https://api.twelvedata.com/time_series'


def _normalize_candles(df: pd.DataFrame) -> pd.DataFrame:
    df = df.rename(columns={
        'datetime': 'timestamp',
        'open': 'open',
        'high': 'high',
        'low': 'low',
        'close': 'close',
        'volume': 'volume'
    })
    df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
    df = df.sort_values('timestamp').reset_index(drop=True)
    return df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]


def fetch_candles_twelvedata(symbol: str, interval: str, n_bars: int) -> pd.DataFrame:
    api_key = os.environ.get('TWELVEDATA_API_KEY')
    if not api_key:
        raise RuntimeError('Twelvedata API key not found in TWELVEDATA_API_KEY')

    params = {
        'symbol': symbol,
        'interval': interval,
        'outputsize': n_bars,
        'apikey': api_key
    }
    logger.info('Twelvedata API call: %s %s %s', symbol, interval, n_bars)
    response = requests.get(TWELVEDATA_URL, params=params, timeout=30)
    response.raise_for_status()
    payload = response.json()

    if 'values' not in payload:
        raise RuntimeError(f'Twelvedata response missing values: {payload}')

    df = pd.DataFrame(payload['values'])
    if df.empty:
        raise RuntimeError('Twelvedata returned empty candle data')

    df = _normalize_candles(df)
    return df


def fetch_candles_mt5(symbol: str, timeframe: str, n_bars: int) -> pd.DataFrame:
    try:
        import MetaTrader5 as mt5
    except ImportError as exc:
        raise RuntimeError('MetaTrader5 package is unavailable') from exc

    if timeframe == '1H':
        mt5_timeframe = mt5.TIMEFRAME_H1
    elif timeframe == 'M15':
        mt5_timeframe = mt5.TIMEFRAME_M15
    else:
        raise ValueError(f'Unsupported timeframe for MT5: {timeframe}')

    if not mt5.initialize():
        raise RuntimeError('MetaTrader5 initialization failed')

    rates = mt5.copy_rates_from_pos('XAUUSD', mt5_timeframe, 0, n_bars)
    mt5.shutdown()
    if rates is None or len(rates) == 0:
        raise RuntimeError('MT5 returned no candle data')

    df = pd.DataFrame(rates)
    df['timestamp'] = pd.to_datetime(df['time'], unit='s', utc=True)
    df = df.rename(columns={
        'open': 'open',
        'high': 'high',
        'low': 'low',
        'close': 'close',
        'real_volume': 'volume'
    })
    df = df.sort_values('timestamp').reset_index(drop=True)
    return df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]


def get_candles(symbol: str, interval: str, n_bars: int) -> pd.DataFrame:
    try:
        return fetch_candles_twelvedata(symbol, interval, n_bars)
    except Exception as exc:
        logger.warning('DATA SOURCE: Twelvedata failed — switched to MT5 bridge. %s', exc)
        return fetch_candles_mt5(symbol, interval, n_bars)


def load_parquet(path: str) -> pd.DataFrame:
    return pd.read_parquet(path)


def save_parquet(df: pd.DataFrame, path: str) -> None:
    df.to_parquet(path, index=False)


def validate_candles(df: pd.DataFrame) -> bool:
    required = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
    if not all(col in df.columns for col in required):
        logger.error('validate_candles: missing required columns')
        return False

    if df[required].isna().any().any():
        logger.error('validate_candles: NaN values found in OHLCV columns')
        return False

    if not df['timestamp'].is_monotonic_increasing:
        logger.error('validate_candles: timestamps are not sorted ascending')
        return False

    if (df['high'] < df['low']).any():
        logger.error('validate_candles: high < low on one or more rows')
        return False

    timestamp_diffs = df['timestamp'].diff().dropna()
    if not timestamp_diffs.empty:
        expected = int(timestamp_diffs.mode().iloc[0].total_seconds())
        if expected <= 0:
            expected = int(timestamp_diffs.median().total_seconds())
        if expected <= 0:
            expected = 60

        consecutive_missing = 0
        max_consecutive_missing = 0
        for diff in timestamp_diffs:
            missing_bars = int(round(diff.total_seconds() / expected)) - 1
            if missing_bars > 0:
                consecutive_missing += missing_bars
                max_consecutive_missing = max(max_consecutive_missing, consecutive_missing)
            else:
                consecutive_missing = 0

        if max_consecutive_missing > settings.PARITY_MAX_GAP_CANDLES:
            logger.error('validate_candles: more than %s consecutive missing bars detected', settings.PARITY_MAX_GAP_CANDLES)
            return False

    return True
