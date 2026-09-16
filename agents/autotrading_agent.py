from loguru import logger
import math
from data.db import (
    get_agent_account, 
    get_agent_portfolio, 
    execute_agent_trade, 
    get_latest_signals
)
from data.market_data import MarketDataClient

from agents.exit_agents import (
    ExitTechnicalAgent, ExitSentimentAgent, ExitFundamentalAgent,
    ExitSmartMoneyAgent, ExitRiskAgent
)
from core.exit_fusion_engine import ExitFusionEngine

class AutotradingAgent:
    """
    Autonomous agent that manages a virtual budget and trades based on the SignalFusionEngine's signals.
    """
    def __init__(self):
        self.market_client = MarketDataClient()
        self.commission = 5.0 # Fixed commission of 5 EUR/USD per executed trade
        self.min_trade_amount = 2000.0 # Minimo importo operazione: 2000 € (per ammortizzare commissioni e costi)
        
        # Agenti AI di Uscita e Motore di Fusione di Vendita
        self.exit_tech = ExitTechnicalAgent()
        self.exit_sent = ExitSentimentAgent()
        self.exit_fund = ExitFundamentalAgent()
        self.exit_smart = ExitSmartMoneyAgent()
        self.exit_risk = ExitRiskAgent()
        self.exit_fusion_engine = ExitFusionEngine()

    def _calculate_position_size(self, signal: float, cash: float, risk_level: str = "SCONOSCIUTO") -> float:
        """
        Calculates how much cash to invest based on the signal strength.
        Diversifies between 10% and 30% of the available budget.
        Adjusts sizing based on the Risk Level.
        Ensures position size meets the minimum 2000 EUR threshold if cash allows.
        """
        if signal < 0.34:
            return 0.0
            
        if risk_level == "ALTISSIMO":
            logger.info("Skipping investment due to ALTISSIMO risk.")
            return 0.0
            
        if cash < (self.min_trade_amount + self.commission):
            logger.info(f"Cash insufficient for minimum trade of {self.min_trade_amount} EUR (Cash: {cash:.2f})")
            return 0.0
            
        # Map signal [0.34, 1.00] to percentage [0.10, 0.30]
        # Formula: 0.10 + (signal - 0.34) / (0.66) * 0.20
        percentage = 0.10 + ((signal - 0.34) / 0.66) * 0.20
        
        # Ensure it stays within bounds
        percentage = max(0.10, min(0.30, percentage))
        
        # Reduce exposure if risk is HIGH
        if risk_level == "ALTO":
            percentage *= 0.5
            
        amount = cash * percentage
        # Se l'importo calcolato è inferiore alla soglia minima di 2000€ ma c'è abbastanza cassa,
        # impostiamo l'importo almeno alla soglia minima (2000€ + commissione)
        if amount < (self.min_trade_amount + self.commission):
            amount = self.min_trade_amount + self.commission

        return min(amount, cash)

    def run_exit_analysis(self, ticker: str, current_shares: int, avg_price: float, data_payload: dict = None) -> dict:
        """
        Esegue l'analisi completa di uscita tramite i 5 agenti AI dedicati e calcola l'Exit Score pesato.
        """
        if data_payload is None:
            data_payload = {}
            
        if 'market_data' not in data_payload:
            data_payload['market_data'] = self.market_client.get_historical_prices(ticker, period="6mo")
        if 'company_info' not in data_payload:
            data_payload['company_info'] = self.market_client.get_company_info(ticker)
            
        data_payload['avg_purchase_price'] = avg_price
        data_payload['shares'] = current_shares

        # Analisi preliminare degli agenti di base se mancanti
        if 'news_res' not in data_payload:
            from agents.news_agent import NewsAgent
            news_agent = NewsAgent()
            data_payload['news_res'] = news_agent.analyze(ticker, data_payload)
            data_payload['news_res']['agent_name'] = news_agent.name

        if 'sec_res' not in data_payload:
            from agents.sec_agent import SECAgent
            sec_agent = SECAgent()
            data_payload['sec_res'] = sec_agent.analyze(ticker, data_payload)
            data_payload['sec_res']['agent_name'] = sec_agent.name

        if 'smart_money_res' not in data_payload:
            from agents.smart_money_agent import SmartMoneyAgent
            smart_money_agent = SmartMoneyAgent()
            data_payload['smart_money_res'] = smart_money_agent.analyze(ticker, data_payload)
            data_payload['smart_money_res']['agent_name'] = smart_money_agent.name

        if 'risk_res' not in data_payload:
            from agents.risk_agent import RiskAgent
            risk_agent = RiskAgent()
            data_payload['risk_res'] = risk_agent.analyze(ticker, data_payload)
            data_payload['risk_res']['agent_name'] = risk_agent.name

        # Esecuzione dei 5 Agenti AI di Uscita
        res_tech = self.exit_tech.analyze(ticker, data_payload)
        res_tech['agent_name'] = self.exit_tech.name

        res_sent = self.exit_sent.analyze(ticker, data_payload)
        res_sent['agent_name'] = self.exit_sent.name

        res_fund = self.exit_fund.analyze(ticker, data_payload)
        res_fund['agent_name'] = self.exit_fund.name

        res_smart = self.exit_smart.analyze(ticker, data_payload)
        res_smart['agent_name'] = self.exit_smart.name

        res_risk = self.exit_risk.analyze(ticker, data_payload)
        res_risk['agent_name'] = self.exit_risk.name

        # Fusione dei segnali tramite ExitFusionEngine
        return self.exit_fusion_engine.process_exit_signals([res_tech, res_sent, res_fund, res_smart, res_risk])

    def _evaluate_exit(self, ticker: str, signal: float, current_shares: int, avg_price: float, current_price: float) -> int:
        """
        Autonomously decides how many shares to sell using the Exit Intelligence Engine.
        Returns the number of shares to sell.
        Avoids fractional micro-tranches to prevent wasting commissions.
        """
        exit_res = self.run_exit_analysis(ticker, current_shares, avg_price)
        exit_score = exit_res['exit_score']
        pos_value = current_shares * current_price
        
        if exit_score >= 0.60:
            logger.info(f"FULL EXIT (100%) triggered for {ticker} with Exit Score: {exit_score:.2f}")
            return current_shares
        elif exit_score >= 0.40:
            # Se la posizione è grande (> 4.000€), possiamo vendere il 50% solo se la tranche è >= 2.000€
            half_shares = current_shares // 2
            if pos_value > 4000.0 and (half_shares * current_price) >= self.min_trade_amount:
                logger.info(f"PARTIAL EXIT (50%) triggered for {ticker} with Exit Score: {exit_score:.2f}")
                return half_shares
            else:
                # Per posizioni normali o piccole, eseguiamo un'uscita completa al 100% in una sola operazione per non pagare commissioni multiple
                logger.info(f"FULL EXIT (100%) triggered for {ticker} with Exit Score: {exit_score:.2f} (Valore posizione: €{pos_value:,.2f})")
                return current_shares
            
        return 0

    def run_step(self, tickers: list = None) -> list:
        """
        Runs one step of the autotrading agent.
        If tickers are provided, analyzes them and saves signals to DB, then executes the cycle.
        Returns list of action strings.
        """
        if tickers:
            from agents.price_agent import PriceAgent
            from agents.news_agent import NewsAgent
            from agents.sec_agent import SECAgent
            from agents.smart_money_agent import SmartMoneyAgent
            from agents.risk_agent import RiskAgent
            from agents.macro_agent import MacroAgent
            from core.fusion_engine import SignalFusionEngine
            from data.db import save_signal
            
            p_agent = PriceAgent()
            n_agent = NewsAgent()
            sec_agent = SECAgent()
            sm_agent = SmartMoneyAgent()
            r_agent = RiskAgent()
            macro_agent = MacroAgent()
            fusion = SignalFusionEngine()
            
            for t in tickers:
                try:
                    df = self.market_client.get_historical_prices(t, period="3mo")
                    if not df.empty:
                        data_p = {"market_data": df}
                        pr = p_agent.analyze(t, data_p)
                        nr = n_agent.analyze(t, data_p)
                        sr = sec_agent.analyze(t, data_p)
                        smr = sm_agent.analyze(t, data_p)
                        rr = r_agent.analyze(t, data_p)
                        mr = macro_agent.analyze(t, data_p)
                        
                        f_res = fusion.process_signals([pr, nr, sr, smr, rr, mr])
                        save_signal(
                            ticker=t, 
                            prediction=f_res['prediction'], 
                            final_signal=f_res['final_signal'], 
                            confidence=f_res['confidence'], 
                            risk_level=f_res.get('risk_level', 'SCONOSCIUTO'), 
                            raw_data=f_res
                        )
                except Exception as e:
                    logger.error(f"Error scanning {t} in autotrading step: {e}")
                    
        result = self.run_cycle()
        return result.get('actions', [])

    def run_cycle(self) -> dict:
        """
        Runs one cycle of the autotrading engine.
        Evaluates current signals and executes trades if necessary.
        Returns a summary of actions taken.
        """
        account = get_agent_account()
        if not account:
            logger.warning("Agent account not initialized. Run initialization first.")
            return {"status": "error", "message": "Account non inizializzato."}
            
        cash = account['cash']
        portfolio = {p['ticker']: p for p in get_agent_portfolio()}
        signals = get_latest_signals()
        agent_trades = get_agent_trades()
        
        # Identifica titoli venduti recentemente per evitare riacquisti a raffica (anti-churning / cooldown)
        recent_sells = set(t['ticker'] for t in agent_trades[-8:] if t.get('type') == 'SELL')
        sold_in_this_cycle = set()
        
        if not signals:
            return {"status": "info", "message": "Nessun segnale recente trovato nel DB."}
            
        actions_taken = []
        
        logger.info(f"Autotrading Cycle Start - Cash: {cash:.2f}")
        
        total_equity = cash
        for p in portfolio.values():
            try:
                df_curr = self.market_client.get_historical_prices(p['ticker'], period="1d")
                if not df_curr.empty:
                    total_equity += p['shares'] * df_curr['Close'].iloc[-1]
                else:
                    total_equity += p['shares'] * p['avg_purchase_price']
            except:
                total_equity += p['shares'] * p['avg_purchase_price']
                
        MAX_POSITIONS = 8
        MIN_CASH_PCT = 0.15
        
        # 1. Process sells first to free up cash
        for sig_data in signals:
            ticker = sig_data['ticker']
            final_signal = sig_data['final_signal']
            
            if ticker in portfolio:
                pos = portfolio[ticker]
                try:
                    df = self.market_client.get_historical_prices(ticker, period="5d")
                    if df.empty:
                        continue
                    current_price = df['Close'].iloc[-1]
                    
                    shares_to_sell = self._evaluate_exit(ticker, final_signal, pos['shares'], pos['avg_purchase_price'], current_price)
                    
                    if shares_to_sell > 0:
                        total_pos_value = pos['shares'] * current_price
                        sell_value = shares_to_sell * current_price
                        
                        # Se la vendita parziale ha un controvalore inferiore a 2000€ ma la posizione totale vale >= 2000€:
                        if sell_value < self.min_trade_amount and total_pos_value >= self.min_trade_amount:
                            needed_shares = math.ceil(self.min_trade_amount / current_price)
                            shares_to_sell = min(pos['shares'], needed_shares)
                            sell_value = shares_to_sell * current_price
                            
                        # Se è un'uscita parziale inferiore a 2000€, non eseguiamo micro-vendite
                        if sell_value < self.min_trade_amount and shares_to_sell < pos['shares']:
                            logger.info(f"Skipping partial sell for {ticker}: value {sell_value:.2f} < {self.min_trade_amount} EUR")
                            continue
                            
                        if shares_to_sell > 0:
                            execute_agent_trade(ticker, 'SELL', shares_to_sell, current_price, self.commission, final_signal)
                            cash += (shares_to_sell * current_price) - self.commission
                            sold_in_this_cycle.add(ticker)
                            del portfolio[ticker] # Rimosso dal portafoglio attivo per questo ciclo
                            actions_taken.append(f"VENDITA: {shares_to_sell} {ticker} a €{current_price:.2f} (Totale: €{shares_to_sell * current_price:,.2f}, Segnale: {final_signal:.2f})")
                            logger.info(f"Agent SOLD {shares_to_sell} {ticker} at {current_price} (Total: {shares_to_sell * current_price:.2f} EUR)")
                        
                except Exception as e:
                    logger.error(f"Error evaluating SELL for {ticker}: {e}")

        # 2. Process buys
        for sig_data in signals:
            ticker = sig_data['ticker']
            final_signal = sig_data['final_signal']
            risk_level = sig_data.get('risk_level', 'SCONOSCIUTO')
            
            # Anti-churning: NON riacquistare titoli venduti in questo ciclo o nelle ultime operazioni
            if ticker in sold_in_this_cycle or ticker in recent_sells:
                logger.info(f"Skipping BUY for {ticker}: titolo in periodo di cooldown dopo recente vendita.")
                continue
            
            # Limit max positions
            if len(portfolio) >= MAX_POSITIONS and ticker not in portfolio:
                continue
                
            # Reserve minimum cash
            if cash < (total_equity * MIN_CASH_PCT):
                continue
                
            # Check DCA condition or fresh buy
            is_dca = False
            if ticker in portfolio:
                pos = portfolio[ticker]
                try:
                    df = self.market_client.get_historical_prices(ticker, period="1d")
                    if df.empty:
                        continue
                    current_price = df['Close'].iloc[-1]
                    pl_pct = (current_price - pos['avg_purchase_price']) / pos['avg_purchase_price']
                    
                    # Se in perdita tra -5% e -8% e il segnale è molto forte, mediamo
                    if pl_pct <= -0.05 and pl_pct > -0.08 and final_signal >= 0.50:
                        is_dca = True
                    else:
                        continue # No DCA
                except:
                    continue
            
            # Buy if we don't hold it, or if it's a DCA opportunity
            if (ticker not in portfolio and final_signal >= 0.35) or is_dca:
                try:
                    df = self.market_client.get_historical_prices(ticker, period="5d")
                    if df.empty:
                        continue
                    current_price = df['Close'].iloc[-1]
                    
                    # Verifica preventiva: se l'analisi di uscita su questo titolo rileva già un exit_score elevato, non compriamo
                    exit_chk = self.run_exit_analysis(ticker, 10, current_price)
                    if exit_chk.get('exit_score', 0.0) >= 0.35:
                        logger.info(f"Skipping BUY for {ticker}: segnali di uscita/ipercomprato preventivi attivi (Exit Score: {exit_chk.get('exit_score'):.2f})")
                        continue
                    
                    investment_amount = self._calculate_position_size(final_signal, cash, risk_level)
                    if is_dca:
                        investment_amount = max(self.min_trade_amount + self.commission, investment_amount * 0.5)
                        
                    # Deduct commission from investment amount
                    actual_investment = investment_amount - self.commission
                    if actual_investment < self.min_trade_amount:
                        continue
                        
                    shares_to_buy = math.floor(actual_investment / current_price)
                    
                    # Se per arrotondamento scende sotto 2000€, verifichiamo se possiamo comprare 1 quota in più entro la cassa disponibile
                    if (shares_to_buy * current_price) < self.min_trade_amount:
                        if ((shares_to_buy + 1) * current_price + self.commission) <= cash:
                            shares_to_buy += 1
                            
                    trade_value = shares_to_buy * current_price
                    if trade_value < self.min_trade_amount:
                        logger.info(f"Skipping buy for {ticker}: trade value {trade_value:.2f} < {self.min_trade_amount} EUR")
                        continue
                        
                    if shares_to_buy > 0 and (trade_value + self.commission) <= cash:
                        execute_agent_trade(ticker, 'BUY', shares_to_buy, current_price, self.commission, final_signal)
                        cash -= (trade_value + self.commission) # Optimistic update
                        
                        action_type = "DCA ACQUISTO" if is_dca else "ACQUISTO"
                        if ticker not in portfolio:
                            portfolio[ticker] = {'shares': shares_to_buy, 'avg_purchase_price': current_price}
                        else:
                            # Update avg price
                            portfolio[ticker]['shares'] += shares_to_buy
                            
                        actions_taken.append(f"{action_type}: {shares_to_buy} {ticker} a €{current_price:.2f} (Totale: €{trade_value:,.2f}, Segnale: {final_signal:.2f})")
                        logger.info(f"Agent {action_type} {shares_to_buy} {ticker} at {current_price} (Total: {trade_value:.2f} EUR)")
                        
                except Exception as e:
                    logger.error(f"Error evaluating BUY for {ticker}: {e}")
                    
        if len(actions_taken) == 0 and signals:
            best_sig = max(signals, key=lambda x: x.get('final_signal', 0.0))
            best_ticker = best_sig.get('ticker', 'N/A')
            best_val = best_sig.get('final_signal', 0.0)
            best_risk = best_sig.get('risk_level', 'SCONOSCIUTO')
            
            if best_val < 0.34:
                reason = "Sotto la soglia minima di acquisto (0.34)"
            elif best_ticker in portfolio:
                reason = "Titolo già presente in portafoglio (Nessun riacquisto)"
            elif best_risk == "ALTISSIMO":
                reason = "Rischio ALTISSIMO bloccante"
            else:
                reason = "Liquidità insufficiente o errore di mercato"
                
            msg = f"Ciclo completato. 0 operazioni eseguite. (Miglior segnale: {best_val:.2f} per {best_ticker} -> Ignorato: {reason})"
        else:
            msg = f"Ciclo completato. {len(actions_taken)} operazioni eseguite."
            
        return {
            "status": "success", 
            "message": msg,
            "actions": actions_taken
        }
