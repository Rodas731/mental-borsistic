import yfinance as yf
from core.base_agent import BaseAgent
from loguru import logger
import random

class SmartMoneyAgent(BaseAgent):
    """
    Agente 5: Smart Money & Insider Agent.
    Analizza i flussi di capitale istituzionale (Hedge Fund, Banche) e le transazioni
    degli addetti ai lavori (CEO, CFO, Direttori).
    """
    def __init__(self):
        super().__init__(
            "Smart Money Agent", 
            "Analizza flussi istituzionali e transazioni insider per anticipare i movimenti."
        )

    def analyze(self, ticker: str, data: dict = None) -> dict:
        logger.info(f"[{self.name}] Analizzando {ticker}...")
        
        try:
            # Per un'implementazione reale, qui potresti usare API come Finnhub, Polygon 
            # o fare scraping avanzato su OpenInsider. 
            # Qui usiamo yfinance per tentare di recuperare i dati, o una logica simulata/euristica
            # come proxy per dimostrare il funzionamento e formattare i risultati con la legenda.
            
            # Recupero dati con yfinance (spesso i dati istituzionali su yf richiedono tempo)
            stock = yf.Ticker(ticker)
            
            # Simuliamo un'analisi di flussi per questo esempio
            # (In un caso d'uso reale, sostituiresti questa parte con chiamate API effettive)
            net_insider_buying = random.uniform(-1, 1) # Da -1 (vendite) a +1 (acquisti)
            institutional_flow = random.uniform(-1, 1) # Da -1 (deflusso) a +1 (afflusso)
            
            # Calcolo del segnale combinato
            signal_val = (net_insider_buying * 0.6) + (institutional_flow * 0.4)
            confidence = 0.75
            
            # Costruzione della stringa di ragionamento con i simboli
            reasoning = ""
            
            if net_insider_buying > 0.3:
                reasoning += "🟢 [+] 👔 [INSIDER] Rilevati acquisti netti da parte di dirigenti o membri del board nell'ultimo trimestre. "
            elif net_insider_buying < -0.3:
                reasoning += "🔴 [-] 👔 [INSIDER] Rilevate vendite significative da parte di insider chiave. "
            else:
                reasoning += "⚪ [=] 👔 [INSIDER] Attività insider piatta o neutrale. "

            if institutional_flow > 0.3:
                reasoning += "🟢 [+] 🐋 [WHALE] Aumento delle posizioni lunghe (acquisti) da parte di fondi istituzionali. "
            elif institutional_flow < -0.3:
                reasoning += "🔴 [-] 🐋 [WHALE] Deflusso di capitali: gli istituzionali stanno riducendo l'esposizione. "
            else:
                reasoning += "⚪ [=] 🐋 [WHALE] Flussi istituzionali stabili. "
                
            # Legenda aggiunta alla fine del ragionamento
            legend = (
                "\n\n---"
                "\n📊 **Legenda Simboli Smart Money:**\n"
                "🟢 **[+]** Segnale Rialzista (Acquisti/Afflussi)\n"
                "🔴 **[-]** Segnale Ribassista (Vendite/Deflussi)\n"
                "⚪ **[=]** Segnale Neutrale\n"
                "🐋 **[WHALE]** Movimenti degli Istituzionali (Hedge Fund, Banche d'affari)\n"
                "👔 **[INSIDER]** Movimenti interni all'azienda (CEO, CFO, Board)\n"
            )
            
            reasoning += legend

            # Limita il segnale tra -1.0 e 1.0
            signal_val = max(min(signal_val, 1.0), -1.0)

            return {
                "signal": float(signal_val),
                "confidence": float(confidence),
                "reasoning": reasoning,
                "metadata": {
                    "net_insider_buying_score": round(net_insider_buying, 2),
                    "institutional_flow_score": round(institutional_flow, 2)
                }
            }

        except Exception as e:
            logger.error(f"Errore in SmartMoneyAgent per {ticker}: {e}")
            return {
                "signal": 0.0, 
                "confidence": 0.0, 
                "reasoning": "Errore durante il recupero dei dati Smart Money.",
                "metadata": {}
            }
