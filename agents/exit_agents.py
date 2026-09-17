import pandas as pd
import numpy as np
from core.base_agent import BaseAgent
from loguru import logger

class ExitTechnicalAgent(BaseAgent):
    """
    Agente 1 di Uscita: Analisi Tecnica, ATR Trailing Stop e Momentum.
    Valuta P&L accumulato, ATR Trailing Stop, RSI in Ipercomprato/Divergenza e medie mobili.
    """
    def __init__(self):
        super().__init__("Exit Technical Agent", "Analizza ATR Trailing Stop, RSI, medie mobili e P&L accumulato per la vendita.")

    def _calculate_atr(self, df: pd.DataFrame, period: int = 14) -> float:
        if len(df) < period + 1:
            return 0.0
        high = df['High']
        low = df['Low']
        close = df['Close'].shift(1)
        
        tr1 = high - low
        tr2 = (high - close).abs()
        tr3 = (low - close).abs()
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean().iloc[-1]
        return float(atr) if pd.notnull(atr) else 0.0

    def analyze(self, ticker: str, data: dict = None) -> dict:
        logger.info(f"[{self.name}] Analisi di uscita per {ticker}...")
        if data is None:
            return {"exit_signal": 0.0, "confidence": 0.0, "reasoning": "Dati di mercato mancanti."}
            
        if isinstance(data, pd.DataFrame):
            df = data
        elif isinstance(data, dict):
            df = data.get('market_data', data.get('df'))
        else:
            df = None

        if df is None or df.empty or len(df) < 15:
            return {"exit_signal": 0.0, "confidence": 0.0, "reasoning": "Dati storici insufficienti per l'uscita."}

        avg_price = data.get('avg_purchase_price', df['Close'].iloc[-1])
        current_price = df['Close'].iloc[-1]
        
        # P&L accumulato
        pl_pct = (current_price - avg_price) / avg_price if avg_price > 0 else 0.0
        
        # Massimo prezzo registrato dall'ingresso (o dal dataset)
        highest_price = data.get('highest_price_since_entry', df['High'].max())
        highest_price = max(highest_price, current_price)
        
        # Calcolo ATR
        atr = self._calculate_atr(df)
        trailing_stop_level = highest_price - (2.5 * atr) if atr > 0 else highest_price * 0.92

        # Indicatori Tecnici
        close_prices = df['Close']
        sma_20 = close_prices.rolling(window=20).mean().iloc[-1] if len(df) >= 20 else current_price
        sma_50 = close_prices.rolling(window=50).mean().iloc[-1] if len(df) >= 50 else sma_20
        
        # RSI
        delta = close_prices.diff()
        gain = (delta.where(delta > 0, 0)).fillna(0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).fillna(0).rolling(14).mean()
        rs = gain / loss.replace(0, 1e-6)
        rsi = (100 - (100 / (1 + rs))).iloc[-1]

        exit_val = 0.0
        reasons = []
        confidence = 0.7

        # 1. Trailing Stop ATR / Drawdown dal massimo
        drawdown_from_high = (current_price - highest_price) / highest_price if highest_price > 0 else 0.0
        if current_price < trailing_stop_level:
            exit_val += 0.8
            reasons.append(f"Prezzo sotto il Trailing Stop ATR (€{trailing_stop_level:.2f}) [Perdita del {abs(drawdown_from_high):.1%} dal massimo di €{highest_price:.2f}]")
            confidence += 0.2
        elif drawdown_from_high <= -0.07:
            exit_val += 0.4
            reasons.append(f"Flessione del {abs(drawdown_from_high):.1%} dal picco massimo di €{highest_price:.2f}.")

        # 2. Stop Loss & Take Profit predefiniti (applicati solo a posizioni aperte in portafoglio)
        is_in_portfolio = data.get('is_in_portfolio', True)
        if is_in_portfolio and pl_pct <= -0.08:
            exit_val += 0.9
            reasons.append(f"STOP LOSS di sicurezza attivato (P&L: {pl_pct:.1%}).")
            confidence = 0.95
        elif is_in_portfolio and pl_pct >= 0.20:
            exit_val += 0.6
            reasons.append(f"TAKE PROFIT raggiunto per forte guadagno accumulato (P&L: +{pl_pct:.1%}). Consigliato incasso parziale o totale.")

        # 3. RSI & Medie Mobili
        if rsi >= 75:
            exit_val += 0.4
            reasons.append(f"RSI in ipercomprato estremo ({rsi:.1f}): rischio correzione o inversione del trend.")
        if current_price < sma_20 < sma_50:
            exit_val += 0.4
            reasons.append(f"Trend tecnico invertito: Prezzo (€{current_price:.2f}) sotto SMA 20 (€{sma_20:.2f}) e SMA 50 (€{sma_50:.2f}).")

        exit_val = max(0.0, min(1.0, exit_val))
        confidence = min(1.0, confidence)
        
        if not reasons:
            reasons.append(f"Trend tecnico favorevole. P&L attuale: {pl_pct:+.1%}, RSI: {rsi:.1f}.")

        return {
            "exit_signal": float(exit_val),
            "confidence": float(confidence),
            "reasoning": " | ".join(reasons),
            "metadata": {
                "pl_pct": pl_pct,
                "rsi": rsi,
                "atr": atr,
                "trailing_stop": trailing_stop_level,
                "highest_price": highest_price
            }
        }


class ExitSentimentAgent(BaseAgent):
    """
    Agente 2 di Uscita: News & Sentiment Decay.
    Rileva il deterioramento delle notizie, sentiment negativo ed eventuali rassegne di notizie critiche.
    """
    def __init__(self):
        super().__init__("Exit Sentiment Agent", "Analizza il deterioramento del sentiment e le notizie negative recenti.")

    def analyze(self, ticker: str, data: dict = None) -> dict:
        logger.info(f"[{self.name}] Analisi sentiment di uscita per {ticker}...")
        
        news_res = data.get('news_res', {}) if data else {}
        news_signal = news_res.get('signal', 0.0)
        articles = news_res.get('metadata', {}).get('articles', [])
        
        exit_val = 0.0
        reasons = []
        confidence = news_res.get('confidence', 0.5)

        if news_signal <= -0.40:
            exit_val += 0.85
            reasons.append(f"Forte sentiment negativo delle notizie (Segnale News: {news_signal:.2f}). Uscita preventiva consigliata.")
        elif news_signal < 0.0:
            exit_val += 0.45
            reasons.append(f"Sentiment delle notizie in deterioramento (Segnale News: {news_signal:.2f}).")
        else:
            reasons.append(f"Sentiment delle notizie stabile/positivo (Segnale News: {news_signal:.2f}).")

        # Conteggio articoli fortemente negativi
        neg_count = sum(1 for a in articles if a.get('sentiment', 0) < -0.3)
        if neg_count >= 3:
            exit_val += 0.3
            reasons.append(f"Rilevati {neg_count} articoli di stampa fortemente negativi di recente.")

        exit_val = max(0.0, min(1.0, exit_val))
        return {
            "exit_signal": float(exit_val),
            "confidence": float(confidence),
            "reasoning": " | ".join(reasons),
            "metadata": {"news_signal": news_signal, "negative_articles": neg_count}
        }


class ExitFundamentalAgent(BaseAgent):
    """
    Agente 3 di Uscita: Scienze Finanziarie & Valutazione Fondamentale.
    Valuta sopravvalutazione di mercato, rallentamento dei dati di bilancio (EPS) e salute finanziaria.
    """
    def __init__(self):
        super().__init__("Exit Fundamental Agent", "Analizza sopravvalutazione fondamentale e deterioramento delle metriche di bilancio.")

    def analyze(self, ticker: str, data: dict = None) -> dict:
        logger.info(f"[{self.name}] Analisi fondamentale di uscita per {ticker}...")
        
        sec_res = data.get('sec_res', {}) if data else {}
        company_info = data.get('company_info', {}) if data else {}
        
        exit_val = 0.0
        reasons = []
        confidence = 0.6

        # Check Forward P/E or Trailing P/E
        pe_ratio = company_info.get('trailingPE') or company_info.get('forwardPE')
        peg_ratio = company_info.get('pegRatio')

        if pe_ratio and pe_ratio > 45:
            exit_val += 0.4
            reasons.append(f"Multiplo P/E elevato ({pe_ratio:.1f}x): il titolo si trova in zona di sopravvalutazione o rischio multipli.")
        
        if peg_ratio and peg_ratio > 2.5:
            exit_val += 0.3
            reasons.append(f"Rapporto PEG alto ({peg_ratio:.2f}): il prezzo supera nettamente le prospettive di crescita stimata.")

        # SEC signal check
        sec_signal = sec_res.get('signal', 0.0)
        eps_growth = sec_res.get('metadata', {}).get('eps_growth', 0.0)
        
        if sec_signal < 0.0:
            exit_val += 0.4
            reasons.append(f"Segnale fondamentale negativo ({sec_signal:.2f}) da bilancio SEC.")
        if eps_growth < 0:
            exit_val += 0.3
            reasons.append(f"Crescita EPS negativa ({eps_growth:.1%}): contrazione degli utili aziendali.")

        exit_val = max(0.0, min(1.0, exit_val))
        if not reasons:
            reasons.append("Fondamentali e stime di bilancio stabili.")

        return {
            "exit_signal": float(exit_val),
            "confidence": float(confidence),
            "reasoning": " | ".join(reasons),
            "metadata": {"pe_ratio": pe_ratio, "peg_ratio": peg_ratio, "eps_growth": eps_growth}
        }


class ExitSmartMoneyAgent(BaseAgent):
    """
    Agente 4 di Uscita: Flussi Istituzionali & Insider Selling.
    Monitora se i grandi fondi o i dirigenti d'azienda stanno scaricando le posizioni.
    """
    def __init__(self):
        super().__init__("Exit Smart Money Agent", "Valuta vendite di insider e deflussi di capitale istituzionale.")

    def analyze(self, ticker: str, data: dict = None) -> dict:
        logger.info(f"[{self.name}] Analisi flussi istituzionali di uscita per {ticker}...")
        
        smart_res = data.get('smart_money_res', {}) if data else {}
        smart_signal = smart_res.get('signal', 0.0)
        insider_score = smart_res.get('metadata', {}).get('net_insider_buying_score', 0.0)

        exit_val = 0.0
        reasons = []
        confidence = smart_res.get('confidence', 0.5)

        if insider_score < -0.3:
            exit_val += 0.7
            reasons.append(f"Forti vendite da parte dei dirigenti/insider (Insider Score: {insider_score:.2f}).")
            confidence += 0.2
        elif insider_score < 0:
            exit_val += 0.3
            reasons.append(f"Prevalenza di vendite insider rispetto agli acquisti.")

        if smart_signal < -0.2:
            exit_val += 0.4
            reasons.append(f"Deflusso di capitale istituzionale (Segnale Smart Money: {smart_signal:.2f}).")

        exit_val = max(0.0, min(1.0, exit_val))
        if not reasons:
            reasons.append(f"Flussi istituzionali neutri o in accumulo (Segnale Smart Money: {smart_signal:.2f}).")

        return {
            "exit_signal": float(exit_val),
            "confidence": float(confidence),
            "reasoning": " | ".join(reasons),
            "metadata": {"smart_signal": smart_signal, "insider_score": insider_score}
        }


class ExitRiskAgent(BaseAgent):
    """
    Agente 5 di Uscita: Protezione dal Rischio & Volatilità.
    Spara alert di uscita se la volatilità o il Max Drawdown aumentano bruscamente.
    """
    def __init__(self):
        super().__init__("Exit Risk Agent", "Supervisiona l'aumento di volatilità e il Max Drawdown del titolo in portafoglio.")

    def analyze(self, ticker: str, data: dict = None) -> dict:
        logger.info(f"[{self.name}] Analisi rischio di uscita per {ticker}...")
        
        risk_res = data.get('risk_res', {}) if data else {}
        risk_score = risk_res.get('metadata', {}).get('risk_score', 0.0)
        risk_level = risk_res.get('metadata', {}).get('risk_level', 'MEDIO')
        max_dd = risk_res.get('metadata', {}).get('max_drawdown', 0.0)
        volatility = risk_res.get('metadata', {}).get('volatility', 0.0)

        exit_val = 0.0
        reasons = []
        confidence = 0.8

        if risk_level == "ALTISSIMO":
            exit_val += 0.85
            reasons.append(f"Livello di Rischio ALTISSIMO (Risk Score: {risk_score:.2f}). Uscita preventiva per de-risking.")
        elif risk_level == "ALTO":
            exit_val += 0.5
            reasons.append(f"Rischio elevato individuato (Risk Score: {risk_score:.2f}). Consigliata riduzione dell'esposizione.")

        if abs(max_dd) > 0.25:
            exit_val += 0.3
            reasons.append(f"Max Drawdown storico significativo ({max_dd:.1%}).")
        if volatility > 0.40:
            exit_val += 0.3
            reasons.append(f"Volatilità annua elevata ({volatility:.1%}).")

        exit_val = max(0.0, min(1.0, exit_val))
        if not reasons:
            reasons.append(f"Profilo di rischio controllato ({risk_level}, Volatilità: {volatility:.1%}).")

        return {
            "exit_signal": float(exit_val),
            "confidence": float(confidence),
            "reasoning": " | ".join(reasons),
            "metadata": {"risk_score": risk_score, "risk_level": risk_level, "volatility": volatility}
        }
