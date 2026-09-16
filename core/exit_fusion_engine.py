from typing import List, Dict
from loguru import logger

class ExitFusionEngine:
    """
    Motore di Fusione dei Segnali di Uscita (Exit Fusion Engine).
    Aggrega i segnali dei 5 agenti AI specializzati nell'uscita per calcolare
    l'Exit Score sintetico (da 0.00 a 1.00) e la Raccomandazione Finale di Vendita.
    """
    def __init__(self):
        # Pesi base assegnati a ciascun agente di uscita
        self.weights = {
            "Exit Technical Agent": 1.5,   # ATR Trailing Stop, P&L, RSI, Medie Mobili
            "Exit Sentiment Agent": 1.0,   # Deterioramento News e Sentiment
            "Exit Fundamental Agent": 1.0, # Valutazione P/E, PEG, Contrazione Utili SEC
            "Exit Smart Money Agent": 0.75, # Vendite Insider e Deflussi Istituzionali
            "Exit Risk Agent": 0.75        # Picchi di Volatilità e Max Drawdown
        }

    def process_exit_signals(self, agent_results: List[Dict]) -> Dict:
        """
        Elabora i risultati degli agenti di uscita e restituisce:
        - exit_score: float da 0.00 a 1.00
        - recommendation: "MANTIENI", "VENDITA PARZIALE", "VENDITA TOTALE"
        - confidence: float da 0.0 a 1.0
        - reasoning: sintesi motivazionale
        - agent_breakdown: dettagli di ciascun agente
        """
        logger.info("Fusing exit signals...")
        
        if not agent_results:
            return {
                "exit_score": 0.0,
                "recommendation": "MANTIENI",
                "confidence": 0.0,
                "reasoning": "Nessun dato degli agenti di uscita disponibile.",
                "details": []
            }

        total_weighted_exit = 0.0
        total_weight = 0.0
        reasons = []

        for res in agent_results:
            name = res.get('agent_name', 'Unknown')
            signal = res.get('exit_signal', 0.0)
            conf = res.get('confidence', 0.5)
            reasoning = res.get('reasoning', '')

            base_w = self.weights.get(name, 1.0)
            weight = base_w * conf

            total_weighted_exit += signal * weight
            total_weight += weight

            if signal >= 0.35 and reasoning:
                reasons.append(f"[{name}]: {reasoning}")

        if total_weight == 0:
            exit_score = 0.0
        else:
            exit_score = total_weighted_exit / total_weight

        # Normalizza tra 0.0 e 1.0
        exit_score = float(max(0.0, min(1.0, exit_score)))

        # Determinazione della Raccomandazione Finale
        if exit_score >= 0.65:
            recommendation = "VENDITA TOTALE (100%)"
        elif exit_score >= 0.35:
            recommendation = "VENDITA PARZIALE (50%)"
        else:
            recommendation = "MANTIENI"

        # Confidenza complessiva degli agenti
        overall_conf = sum(r.get('confidence', 0.5) for r in agent_results) / len(agent_results)

        synthesis = " | ".join(reasons) if reasons else "Tutti gli indicatori concordano sul mantenimento della posizione."

        return {
            "exit_score": exit_score,
            "recommendation": recommendation,
            "confidence": float(overall_conf),
            "reasoning": synthesis,
            "details": agent_results
        }
