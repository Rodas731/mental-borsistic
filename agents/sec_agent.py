import requests
import pandas as pd
from core.base_agent import BaseAgent
from loguru import logger

class SECAgent(BaseAgent):
    """
    Agent 4: SEC Fundamentals Agent.
    Fetches basic financial metrics (e.g., EPS, Net Income) from the SEC EDGAR API.
    """
    def __init__(self):
        super().__init__("SEC Fundamentals Agent", "Analyzes fundamental data from SEC XBRL filings.")
        # SEC requires a descriptive user agent
        self.headers = {'User-Agent': 'MarketIntelligenceEngine contact@example.com'}

    def _get_cik(self, ticker: str) -> str:
        try:
            # Get the CIK mappings
            url = "https://www.sec.gov/files/company_tickers.json"
            response = requests.get(url, headers=self.headers)
            if response.status_code == 200:
                data = response.json()
                for key, val in data.items():
                    if val['ticker'].upper() == ticker.upper():
                        return str(val['cik_str']).zfill(10)
            return ""
        except Exception as e:
            logger.error(f"Error fetching CIK for {ticker}: {e}")
            return ""

    def analyze(self, ticker: str, data: dict = None) -> dict:
        logger.info(f"[{self.name}] Analyzing {ticker}...")
        
        # Le aziende europee (.MI, .PA, .DE, .AS, ecc.) o non americane non sono depositate presso la SEC USA
        if '.' in ticker:
            suffix = ticker.split('.')[-1]
            return {
                "signal": 0.0, 
                "confidence": 0.0, 
                "reasoning": f"L'azienda è quotata su un mercato europeo (.{suffix}). I dati fondamentali SEC (EDGAR USA) non sono applicabili.",
                "metadata": {}
            }
        
        cik = self._get_cik(ticker)
        if not cik:
            return {"signal": 0.0, "confidence": 0.0, "reasoning": "Non è stato possibile trovare il codice CIK per la SEC. (Probabilmente non è un'azienda USA)."}

        try:
            # Fetch company facts (XBRL data)
            url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
            response = requests.get(url, headers=self.headers)
            
            if response.status_code != 200:
                return {"signal": 0.0, "confidence": 0.0, "reasoning": "Failed to retrieve SEC facts."}
                
            facts = response.json().get("facts", {})
            us_gaap = facts.get("us-gaap", {})
            
            # Simple fundamental analysis based on Earnings Per Share (EPS) trend
            eps_data = us_gaap.get("EarningsPerShareBasic", {}).get("units", {}).get("USD/shares", [])
            
            if not eps_data:
                return {"signal": 0.0, "confidence": 0.0, "reasoning": "No EPS data found in recent filings."}

            # Filter for annual (10-K) data where form is 10-K
            annual_eps = [item for item in eps_data if item.get('form') == '10-K']
            
            if len(annual_eps) < 2:
                return {"signal": 0.0, "confidence": 0.0, "reasoning": "Not enough historical EPS data."}
                
            # Sort by date
            annual_eps.sort(key=lambda x: x['end'])
            
            latest_eps = annual_eps[-1]['val']
            previous_eps = annual_eps[-2]['val']
            
            # Calculate growth
            if previous_eps != 0:
                growth = (latest_eps - previous_eps) / abs(previous_eps)
            else:
                growth = 0.0
                
            signal_val = max(min(growth, 1.0), -1.0)
            
            reasoning = f"Utile Per Azione (EPS) dell'ultimo anno: {latest_eps:.2f}$, Anno Precedente: {previous_eps:.2f}$. "
            reasoning += f"Crescita su base annua: {growth:.1%}. "
            reasoning += "[L'EPS è un indicatore fondamentale della redditività di un'azienda]."
            
            if growth > 0.1:
                reasoning += " Una crescita > 10% indica fondamentali aziendali molto forti (Positivo)."
                signal_val = min(signal_val + 0.2, 1.0)
            elif growth < 0:
                reasoning += " Una crescita negativa indica deterioramento dei fondamentali aziendali (Negativo)."
            else:
                reasoning += " Crescita piatta o debole, fondamentali stabili."
                
            return {
                "signal": float(signal_val),
                "confidence": 0.8,
                "reasoning": reasoning,
                "metadata": {
                    "latest_eps": latest_eps,
                    "previous_eps": previous_eps,
                    "eps_growth": growth
                }
            }

        except Exception as e:
            logger.error(f"Error in SECAgent for {ticker}: {e}")
            return {"signal": 0.0, "confidence": 0.0, "reasoning": "Errore durante il parsing dei dati SEC."}
