import os
import time
import logging
from datetime import datetime, timedelta
from typing import Optional
import streamlit as st

import pandas as pd
import requests
try:
    from twelvedata import TDClient
    TWELVEDATA_AVAILABLE = True
except ImportError:
    TWELVEDATA_AVAILABLE = False
    TDClient = None

from config import settings

logger = logging.getLogger(__name__)

class TwelveDataClient:
    def __init__(self, api_key: str):
        if not TWELVEDATA_AVAILABLE:
            raise RuntimeError('twelvedata package not installed. Install with: pip install twelvedata')
        self.api_key = api_key
        self.client = TDClient(apikey=api_key)
        self.last_call_time = 0
        self.rate_limit_delay = 1.0  # 1 second between calls for free tier

    def _rate_limit_wait(self):
        """Enforce rate limiting."""
        elapsed = time.time() - self.last_call_time
        if elapsed < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - elapsed)
        self.last_call_time = time.time()

    def fetch_candles(self, symbol: str, interval: str, n_bars: int) -> pd.DataFrame:
        """Fetch candles with rate limiting and error handling."""
        try:
            self._rate_limit_wait()
            logger.info('Fetching %d %s candles for %s from Twelve Data', n_bars, interval, symbol)

            # Use twelvedata SDK
            ts = self.client.time_series(
                symbol=symbol,
                interval=interval,
                outputsize=n_bars
            )

            df = ts.as_pandas()
            if df.empty:
                logger.warning('Twelve Data returned empty data for %s %s', symbol, interval)
                return pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])

            # Normalize to UTC timestamps
            df.index = pd.to_datetime(df.index, utc=True)
            df = df.reset_index()
            df = df.rename(columns={
                'index': 'timestamp',
                'open': 'open',
                'high': 'high',
                'low': 'low',
                'close': 'close',
                'volume': 'volume'
            })
            df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
            df = df.sort_values('timestamp').reset_index(drop=True)

            logger.info('Fetched %d candles for %s %s', len(df), symbol, interval)
            return df

        except Exception as exc:
            logger.error('Twelve Data fetch failed: %s', exc)
            # Return empty DataFrame to prevent crashes
            return pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])

@st.cache_data(ttl=300)  # Cache for 5 minutes
def get_cached_candles(symbol: str, interval: str, n_bars: int) -> pd.DataFrame:
    """Cached wrapper for candle fetching."""
    # Try Streamlit secrets first, then env
    api_key = None
    try:
        api_key = st.secrets.get("TWELVE_DATA_API_KEY")
    except:
        pass
    if not api_key:
        api_key = os.environ.get('TWELVE_DATA_API_KEY') or os.environ.get('TWELVEDATA_API_KEY')
    if not api_key:
        raise RuntimeError('Twelve Data API key not found. Set TWELVE_DATA_API_KEY in secrets or environment.')

    client = TwelveDataClient(api_key)
    return client.fetch_candles(symbol, interval, n_bars)

def validate_candles(df: pd.DataFrame) -> bool:
    """Validate candle DataFrame has required columns and is well-formed."""
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

    return True