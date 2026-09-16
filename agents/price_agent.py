import pandas as pd
import numpy as np
from core.base_agent import BaseAgent
from loguru import logger

class PriceAgent(BaseAgent):
    """
    Agent 1: Price and Momentum Agent.
    Analyzes technical indicators like SMA, EMA, and RSI to determine momentum.
    """
    def __init__(self):
        super().__init__("Price/Momentum Agent", "Analyzes technical indicators from historical price data.")

    def _calculate_rsi(self, data: pd.Series, window: int = 14) -> pd.Series:
        delta = data.diff()
        gain = (delta.where(delta > 0, 0)).fillna(0)
        loss = (-delta.where(delta < 0, 0)).fillna(0)
        
        avg_gain = gain.rolling(window=window, min_periods=1).mean()
        avg_loss = loss.rolling(window=window, min_periods=1).mean()
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def analyze(self, ticker: str, data = None) -> dict:
        """
        Accepts either a DataFrame or a dict containing 'market_data' or 'df'.
        """
        logger.info(f"[{self.name}] Analyzing {ticker}...")
        
        if data is None:
            logger.error("No market data provided.")
            return {"signal": 0.0, "confidence": 0.0, "reasoning": "Missing market data"}
            
        if isinstance(data, pd.DataFrame):
            df = data
        elif isinstance(data, dict):
            df = data.get('market_data', data.get('df'))
        else:
            df = None

        if df is None or df.empty or len(df) < 20:
            return {"signal": 0.0, "confidence": 0.0, "reasoning": "Insufficient data"}

        # Calculate indicators
        close_prices = df['Close']
        sma_20 = close_prices.rolling(window=20).mean().iloc[-1]
        sma_50 = close_prices.rolling(window=50).mean().iloc[-1] if len(df) >= 50 else sma_20
        rsi_14 = self._calculate_rsi(close_prices).iloc[-1]
        current_price = close_prices.iloc[-1]

        # Logica di base:
        # Rialzista se Prezzo > SMA20 > SMA50 e RSI è tra 40 e 70 (non in ipercomprato ma in trend)
        # Ribassista se Prezzo < SMA20 < SMA50 o RSI > 70
        
        signal_val = 0.0
        reasoning_parts = []
        confidence = 0.5

        if current_price > sma_20 > sma_50:
            signal_val += 0.5
            reasoning_parts.append(f"Prezzo ({current_price:.2f}$) > SMA 20gg ({sma_20:.2f}$) > SMA 50gg ({sma_50:.2f}$) [Questo indica un trend RIALZISTA di breve/medio termine]")
            confidence += 0.2
        elif current_price < sma_20 < sma_50:
            signal_val -= 0.5
            reasoning_parts.append(f"Prezzo ({current_price:.2f}$) < SMA 20gg ({sma_20:.2f}$) < SMA 50gg ({sma_50:.2f}$) [Questo indica un trend RIBASSISTA di breve/medio termine]")
            confidence += 0.2
        else:
            reasoning_parts.append(f"Prezzo ({current_price:.2f}$) in fase laterale o senza trend definito rispetto alle medie mobili (SMA).")

        if rsi_14 > 70:
            signal_val -= 0.3
            reasoning_parts.append(f"RSI in Ipercomprato ({rsi_14:.2f}) [L'Indice di Forza Relativa sopra 70 indica che il titolo è salito troppo velocemente e potrebbe subire una correzione al ribasso]")
        elif rsi_14 < 30:
            signal_val += 0.3
            reasoning_parts.append(f"RSI in Ipervenduto ({rsi_14:.2f}) [L'Indice di Forza Relativa sotto 30 indica che il titolo è sceso troppo velocemente e potrebbe rimbalzare]")
            confidence += 0.1
        else:
            reasoning_parts.append(f"RSI Neutrale ({rsi_14:.2f}) [Indica che la forza del trend è equilibrata, non ci sono eccessi di acquisto o vendita]")

        # Normalizza segnale a [-1.0, 1.0]
        signal_val = max(min(signal_val, 1.0), -1.0)
        confidence = min(confidence, 1.0)

        return {
            "signal": float(signal_val),
            "confidence": float(confidence),
            "reasoning": " | ".join(reasoning_parts),
            "metadata": {
                "current_price": current_price,
                "sma20": sma_20,
                "sma50": sma_50,
                "rsi": rsi_14
            }
        }
