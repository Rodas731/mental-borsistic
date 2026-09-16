from core.base_agent import BaseAgent
from loguru import logger
import pandas as pd
from data.market_data import MarketDataClient

class MacroAgent(BaseAgent):
    """
    Agent that analyzes the broad macroeconomic / market trend (using SPY as proxy).
    Instead of returning a standard signal (-1 to 1), it returns a 'multiplier' 
    (from 0.0 to 1.0) via the 'signal' field. This multiplier scales down all 
    autotrading activities if the market is crashing.
    """
    def __init__(self):
        super().__init__(
            name="Macro Analyst Agent",
            description="Analyzes broad market trends (SPY) to output a risk multiplier."
        )
        self.market_client = MarketDataClient()
        self.proxy_ticker = "SPY"

    def analyze(self, ticker: str = None, data: dict = None) -> dict:
        """
        The ticker is ignored because this agent always looks at SPY.
        """
        try:
            # Fetch SPY data
            df = self.market_client.get_historical_prices(self.proxy_ticker, period="3mo")
            if df.empty or len(df) < 20:
                logger.warning("MacroAgent: Not enough SPY data, defaulting multiplier to 1.0")
                return self._default_response()
                
            current_price = df['Close'].iloc[-1]
            sma_20 = df['Close'].rolling(window=20).mean().iloc[-1]
            
            # Simple RSI calculation for SPY
            delta = df['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs)).iloc[-1]
            
            multiplier = 1.0
            reasoning = "Mercato generale (SPY) in trend positivo o neutrale."
            
            if rsi < 35:
                multiplier = 0.0
                reasoning = "PANICO DI MERCATO: SPY in forte ipervenduto (RSI < 35). Autotrading bloccato."
            elif current_price < sma_20:
                multiplier = 0.5
                reasoning = "MERCATO DEBOLE: SPY sotto la SMA 20. Segnali dimezzati per cautela."
                
            return {
                "signal": multiplier,  # Notice this is a multiplier, not a direct signal!
                "confidence": 1.0,
                "reasoning": reasoning,
                "metadata": {
                    "spy_price": current_price,
                    "spy_sma20": sma_20,
                    "spy_rsi": rsi,
                    "multiplier": multiplier
                }
            }
            
        except Exception as e:
            logger.error(f"Error in MacroAgent: {e}")
            return self._default_response()
            
    def _default_response(self):
        return {
            "signal": 1.0, # Default to no penalty
            "confidence": 0.0,
            "reasoning": "Dati macro non disponibili, si assume mercato normale.",
            "metadata": {"multiplier": 1.0}
        }
