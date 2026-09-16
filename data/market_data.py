import yfinance as yf
import pandas as pd
from loguru import logger

class MarketDataClient:
    """
    Client for downloading market data using Yahoo Finance (free API).
    """
    def __init__(self):
        logger.info("MarketDataClient initialized")

    def get_historical_prices(self, ticker: str, period: str = "1mo", interval: str = "1d") -> pd.DataFrame:
        """
        Fetches historical price and volume data.
        """
        try:
            stock = yf.Ticker(ticker)
            df = stock.history(period=period, interval=interval)
            if df.empty:
                logger.warning(f"No price data found for {ticker}")
                return pd.DataFrame()
            return df
        except Exception as e:
            logger.error(f"Error fetching historical prices for {ticker}: {e}")
            return pd.DataFrame()

    def get_company_info(self, ticker: str) -> dict:
        """
        Fetches general company info (sector, industry, market cap).
        """
        try:
            stock = yf.Ticker(ticker)
            return stock.info
        except Exception as e:
            logger.error(f"Error fetching company info for {ticker}: {e}")
            return {}
