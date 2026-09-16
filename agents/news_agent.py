import yfinance as yf
from textblob import TextBlob
from core.base_agent import BaseAgent
from loguru import logger

class NewsAgent(BaseAgent):
    """
    Agent 3: News and NLP Agent.
    Fetches latest news from Yahoo Finance for a ticker and performs basic sentiment analysis.
    """
    def __init__(self):
        super().__init__("News/NLP Agent", "Analyzes sentiment of recent news articles.")

    def analyze(self, ticker: str, data: dict = None) -> dict:
        logger.info(f"[{self.name}] Analyzing {ticker}...")
        
        try:
            stock = yf.Ticker(ticker)
            news = stock.news
            
            if not news:
                return {"signal": 0.0, "confidence": 0.0, "reasoning": "No recent news found."}

            total_sentiment = 0.0
            num_articles = len(news)
            
            articles_data = []
            for article in news:
                title = "Titolo non disponibile"
                link = "#"
                
                if isinstance(article, dict):
                    # Prova formato diretto
                    if article.get('title'):
                        title = article.get('title')
                        link = article.get('link') or article.get('url', "#")
                    # Prova formato nidificato ('content' object) - tipico delle nuove versioni yfinance
                    elif 'content' in article and isinstance(article['content'], dict):
                        content = article['content']
                        title = content.get('title', "Titolo non disponibile")
                        click_url = content.get('clickThroughUrl', {})
                        link = click_url.get('url', "#") if isinstance(click_url, dict) else "#"
                    
                    # Se il titolo è ancora mancante, stampa le chiavi per capire la struttura
                    if title == "Titolo non disponibile":
                        title = f"STRUTTURA SCONOSCIUTA: {list(article.keys())}"
                else:
                    title = f"NON E' UN DIZIONARIO: {type(article)}"

                # Basic sentiment analysis using TextBlob
                analysis = TextBlob(title)
                polarity = analysis.sentiment.polarity
                total_sentiment += polarity
                
                import datetime
                date_str = ""
                # Estrazione data
                pub_time = article.get('providerPublishTime')
                if pub_time:
                    try:
                        date_str = datetime.datetime.fromtimestamp(pub_time).strftime('%d/%m/%Y %H:%M')
                    except Exception:
                        pass
                elif article.get('pubDate'):
                    date_str = str(article.get('pubDate'))
                elif 'content' in article and isinstance(article['content'], dict):
                    pub_time = article['content'].get('pubDate')
                    if pub_time:
                        date_str = str(pub_time)[:10] # Prendi solo l'inizio se è un formato ISO

                # Aggiungiamo sempre l'articolo, anche se manca il link
                articles_data.append({"title": title, "link": link, "sentiment": polarity, "date": date_str})
            
            avg_sentiment = total_sentiment / num_articles if num_articles > 0 else 0.0
            
            # Map sentiment [-1.0, 1.0] to signal
            signal_val = max(min(avg_sentiment, 1.0), -1.0)
            
            # Confidence grows with the number of articles analyzed, capped at 0.9
            confidence = min(0.3 + (num_articles * 0.05), 0.9)
            
            reasoning = f"Analizzate {num_articles} notizie recenti. Polarità media del sentiment (NLP): {avg_sentiment:.2f}. "
            reasoning += "[La polarità va da -1.0 (molto negativo) a +1.0 (molto positivo)]. "
            if avg_sentiment > 0.2:
                reasoning += "Questo indica un sentiment generale OTTIMISTA/RIALZISTA sulle news."
            elif avg_sentiment < -0.2:
                reasoning += "Questo indica un sentiment generale PESSIMISTA/RIBASSISTA sulle news."
            else:
                reasoning += "Il sentiment generale delle news è NEUTRALE."

            return {
                "signal": float(signal_val),
                "confidence": float(confidence),
                "reasoning": reasoning,
                "metadata": {
                    "num_articles": num_articles,
                    "raw_sentiment": avg_sentiment,
                    "articles": articles_data
                }
            }
        except Exception as e:
            logger.error(f"Error in NewsAgent for {ticker}: {e}")
            return {"signal": 0.0, "confidence": 0.0, "reasoning": "Errore durante l'analisi delle news."}
