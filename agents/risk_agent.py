import pandas as pd
import numpy as np
from core.base_agent import BaseAgent
from typing import Dict, Any

class RiskAgent(BaseAgent):
    def __init__(self):
        super().__init__("Risk Analyst Agent", "Valuta il livello di rischio e la volatilità del titolo.")

    def analyze(self, ticker: str, data: Any = None) -> Dict[str, Any]:
        if data is None:
            return {
                "agent_name": self.name,
                "signal": 0.0,
                "confidence": 0.0,
                "reasoning": "Dati di mercato non disponibili per calcolare il rischio.",
                "metadata": {"risk_score": 0.5, "risk_level": "MEDIO"}
            }

        if isinstance(data, pd.DataFrame):
            df = data
        elif isinstance(data, dict):
            df = data.get('market_data', data.get('df'))
        else:
            df = None

        if df is None or df.empty:
            return {
                "agent_name": self.name,
                "signal": 0.0,
                "confidence": 0.0,
                "reasoning": "Dati di mercato vuoti.",
                "metadata": {"risk_score": 0.5, "risk_level": "MEDIO"}
            }
        
        # Calculate daily returns
        if 'Close' not in df.columns:
            return {
                "agent_name": self.name,
                "signal": 0.0,
                "confidence": 0.0,
                "reasoning": "Colonna 'Close' non trovata.",
                "metadata": {"risk_score": 0.5, "risk_level": "MEDIO"}
            }
            
        returns = df['Close'].pct_change().dropna()
        
        if returns.empty:
            return {
                "agent_name": self.name,
                "signal": 0.0,
                "confidence": 0.0,
                "reasoning": "Dati insufficienti per i rendimenti.",
                "metadata": {"risk_score": 0.5, "risk_level": "MEDIO"}
            }

        # 1. Annualized Volatility (assuming ~252 trading days)
        # We cap it around 1.0 (100% volatility) for scoring purposes
        volatility = returns.std() * np.sqrt(252)
        vol_score = min(volatility / 0.80, 1.0) # 80% vol is considered max risk (1.0)

        # 2. Max Drawdown (over the given period, e.g. 6mo)
        cumulative_returns = (1 + returns).cumprod()
        peak = cumulative_returns.cummax()
        drawdown = (cumulative_returns - peak) / peak
        max_drawdown = abs(drawdown.min())
        md_score = min(max_drawdown / 0.50, 1.0) # 50% drawdown is max risk (1.0)

        # Combine into a single risk score [0.0 to 1.0]
        # Let's weight volatility 60% and max drawdown 40%
        risk_score = (vol_score * 0.6) + (md_score * 0.4)
        
        # Determine Text Level
        if risk_score < 0.25:
            risk_level = "BASSO"
            color = "🟢"
        elif risk_score < 0.50:
            risk_level = "MEDIO"
            color = "🟡"
        elif risk_score < 0.75:
            risk_level = "ALTO"
            color = "🟠"
        else:
            risk_level = "ALTISSIMO"
            color = "🔴"

        reasoning = (
            f"Il titolo presenta una volatilità annualizzata stimata del {volatility:.1%} "
            f"e un Max Drawdown nel periodo del {max_drawdown:.1%}. "
            f"Il livello di rischio calcolato è {risk_level} ({color})."
        )

        return {
            "agent_name": self.name,
            "signal": 0.0, # Signal 0.0 so it doesn't skew the directional prediction
            "confidence": 1.0, # Math is exact based on data
            "reasoning": reasoning,
            "metadata": {
                "risk_score": float(risk_score),
                "risk_level": risk_level,
                "volatility": float(volatility),
                "max_drawdown": float(max_drawdown)
            }
        }
