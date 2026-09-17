import yfinance as yf
import pandas as pd
from loguru import logger
import streamlit as st

@st.cache_data(ttl=360, show_spinner=False)
def _fetch_historical_prices_cached(ticker: str, period: str = "1mo", interval: str = "1d") -> pd.DataFrame:
    """
    Downloads historical data for a single ticker and caches it for 6 minutes (360 seconds).
    """
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period=period, interval=interval)
        if df is None or df.empty:
            logger.warning(f"No price data found for {ticker}")
            return pd.DataFrame()
        return df
    except Exception as e:
        logger.error(f"Error fetching historical prices for {ticker}: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=360, show_spinner=False)
def _fetch_batch_historical_prices_cached(tickers: tuple, period: str = "6mo", interval: str = "1d") -> dict:
    """
    Downloads historical data for multiple tickers in a SINGLE HTTP request.
    Caches the entire batch for 6 minutes (360 seconds).
    Returns a dict {ticker: DataFrame}.
    """
    if not tickers:
        return {}
    
    tickers_list = list(tickers)
    logger.info(f"Executing single batch download for {len(tickers_list)} tickers (period={period})...")
    
    try:
        data = yf.download(
            tickers=tickers_list,
            period=period,
            interval=interval,
            group_by='ticker',
            auto_adjust=True,
            threads=True,
            progress=False
        )
        
        result = {}
        if data is None or data.empty:
            logger.warning("Batch download returned an empty dataset from Yahoo Finance.")
            return result

        if len(tickers_list) == 1:
            t = tickers_list[0]
            clean_df = data.dropna(how='all')
            if not clean_df.empty:
                result[t] = clean_df
        else:
            for t in tickers_list:
                try:
                    if isinstance(data.columns, pd.MultiIndex):
                        if t in data.columns.levels[0]:
                            df_t = data[t].dropna(how='all')
                            if not df_t.empty:
                                result[t] = df_t
                    elif t in data:
                        df_t = data[t].dropna(how='all')
                        if not df_t.empty:
                            result[t] = df_t
                except Exception as ex:
                    logger.debug(f"Could not extract sub-dataframe for {t}: {ex}")
                    
        logger.info(f"Batch download successful: {len(result)}/{len(tickers_list)} tickers populated.")
        return result
    except Exception as e:
        logger.error(f"Error in batch download from Yahoo Finance: {e}")
        return {}

@st.cache_data(ttl=360, show_spinner=False)
def _fetch_company_info_cached(ticker: str) -> dict:
    """
    Fetches company info metadata with 6-minute cache.
    """
    try:
        stock = yf.Ticker(ticker)
        return stock.info
    except Exception as e:
        logger.error(f"Error fetching company info for {ticker}: {e}")
        return {}

class MarketDataClient:
    """
    Client for downloading market data using Yahoo Finance (free API)
    with Streamlit caching (6-minute TTL / ~10 times per hour) and batch execution.
    """
    def __init__(self):
        pass

    def get_historical_prices(self, ticker: str, period: str = "1mo", interval: str = "1d") -> pd.DataFrame:
        """
        Fetches historical price and volume data for a single ticker (cached for 6 min).
        """
        return _fetch_historical_prices_cached(ticker, period=period, interval=interval)

    def get_batch_historical_prices(self, tickers: list, period: str = "6mo", interval: str = "1d") -> dict:
        """
        Fetches historical prices for an entire list of tickers in ONE single network call (cached for 6 min).
        """
        if not tickers:
            return {}
        return _fetch_batch_historical_prices_cached(tuple(tickers), period=period, interval=interval)

    def get_company_info(self, ticker: str) -> dict:
        """
        Fetches general company info (sector, industry, market cap) (cached for 6 min).
        """
        return _fetch_company_info_cached(ticker)
