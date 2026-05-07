import os
import time
import logging
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd
import requests

logger = logging.getLogger(__name__)

# Try to import Streamlit (optional, only used in dashboard)
try:
    import streamlit as st
    STREAMLIT_AVAILABLE = True
except ImportError:
    STREAMLIT_AVAILABLE = False
    st = None

# Try to import Twelve Data
try:
    from twelvedata import TDClient
    TWELVEDATA_AVAILABLE = True
except ImportError:
    TWELVEDATA_AVAILABLE = False
    TDClient = None

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

def _fetch_from_api(symbol: str, interval: str, n_bars: int) -> pd.DataFrame:
    """Fetch candles from Twelve Data API."""
    if not TWELVEDATA_AVAILABLE:
        logger.warning('Twelve Data package not available')
        return pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])

    try:
        api_key = None
        
        # Try Streamlit secrets first, then env
        if STREAMLIT_AVAILABLE:
            try:
                api_key = st.secrets.get("TWELVE_DATA_API_KEY")
            except:
                pass
        
        if not api_key:
            api_key = os.environ.get('TWELVE_DATA_API_KEY') or os.environ.get('TWELVEDATA_API_KEY')
        
        if not api_key:
            logger.error('Twelve Data API key not found')
            return pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])

        client = TwelveDataClient(api_key)
        return client.fetch_candles(symbol, interval, n_bars)
    except Exception as exc:
        logger.error('API fetch failed: %s', exc)
        return pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])


# Conditional caching: only use Streamlit cache if available
if STREAMLIT_AVAILABLE:
    @st.cache_data(ttl=300)
    def get_cached_candles(symbol: str, interval: str, n_bars: int) -> pd.DataFrame:
        """Cached wrapper for candle fetching (Streamlit context)."""
        return _fetch_from_api(symbol, interval, n_bars)
else:
    def get_cached_candles(symbol: str, interval: str, n_bars: int) -> pd.DataFrame:
        """Non-cached wrapper for candle fetching (regular Python context)."""
        return _fetch_from_api(symbol, interval, n_bars)

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


def load_candles(symbol: str, interval: str, n_bars: int) -> pd.DataFrame:
    """Main function to load candles, preferring cache but falling back to API."""
    # Try to load from local cache first
    cache_path = f"data/candles/{symbol.replace('/', '')}_{interval}.parquet"
    if os.path.exists(cache_path):
        try:
            df = pd.read_parquet(cache_path)
            if len(df) >= n_bars:
                logger.info('Loaded %d candles from cache for %s %s', len(df), symbol, interval)
                return df.tail(n_bars)  # Return latest n_bars
        except Exception as e:
            logger.warning('Failed to load cached candles: %s', e)

    # Fetch from API
    df = get_cached_candles(symbol, interval, n_bars)
    if not df.empty:
        # Save to cache
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        df.to_parquet(cache_path, index=False)
    return df