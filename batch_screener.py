import time
from loguru import logger
from data.market_data import MarketDataClient
from agents.price_agent import PriceAgent
from agents.news_agent import NewsAgent
from agents.sec_agent import SECAgent
from agents.smart_money_agent import SmartMoneyAgent
from agents.risk_agent import RiskAgent
from core.fusion_engine import SignalFusionEngine
from data.db import save_signal

# 50 Italian Stocks (FTSE MIB & Mid Cap)
ITA_STOCKS = [
    "ENEL.MI", "ISP.MI", "UCG.MI", "ENI.MI", "STLAM.MI",
    "STM.MI", "RACE.MI", "TRN.MI", "PRY.MI", "PST.MI",
    "TIT.MI", "SRG.MI", "G.MI", "SPM.MI", "HER.MI",
    "A2A.MI", "MONC.MI", "LDO.MI", "BMED.MI", "CPR.MI",
    "REC.MI", "BPE.MI", "IP.MI", "FBK.MI", "TEN.MI",
    "AMP.MI", "AZM.MI", "BAMI.MI", "DIA.MI", "ERG.MI",
    "IG.MI", "INW.MI", "NEXI.MI", "PIRC.MI", "UNI.MI",
    "BSS.MI", "MB.MI", "IVG.MI", "IREN.MI", "BPSO.MI",
    "FCT.MI", "MAI.MI", "TWS.MI", "LVEN.MI", "AR.MI",
    "SFER.MI", "MFEA.MI", "MFEB.MI", "BRE.MI", "OVS.MI"
]

# 50 US Stocks (S&P 500 / Nasdaq)
USA_STOCKS = [
    "NVDA", "AAPL", "MSFT", "GOOGL", "AMZN",
    "TSLA", "META", "NFLX", "AMD", "JPM",
    "V", "JNJ", "WMT", "PG", "MA",
    "UNH", "HD", "XOM", "BAC", "COST",
    "AVGO", "KO", "PEP", "CSCO", "ADBE",
    "CRM", "ORCL", "ABBV", "MRK", "CVX",
    "INTC", "QCOM", "TXN", "IBM", "MCD",
    "DIS", "VZ", "T", "PFE", "NKE",
    "BA", "UBER", "ABNB", "PYPL", "SQ",
    "SNOW", "PLTR", "SHOP", "SPOT", "CRWD"
]

ALL_TICKERS = ITA_STOCKS + USA_STOCKS

def run_batch():
    logger.info(f"Starting Batch Screener for {len(ALL_TICKERS)} tickers...")
    
    data_client = MarketDataClient()
    price_agent = PriceAgent()
    news_agent = NewsAgent()
    sec_agent = SECAgent()
    from agents.macro_agent import MacroAgent
    smart_money_agent = SmartMoneyAgent()
    risk_agent = RiskAgent()
    macro_agent = MacroAgent()
    fusion_engine = SignalFusionEngine()
    
    for ticker in ALL_TICKERS:
        try:
            logger.info(f"Processing {ticker}...")
            
            # Fetch data
            df = data_client.get_historical_prices(ticker, period="6mo")
            if df.empty:
                logger.warning(f"Skipping {ticker}: No data available.")
                continue
                
            company_info = data_client.get_company_info(ticker)
            data_payload = {"market_data": df, "company_info": company_info}
            
            # Run Agents
            price_res = price_agent.analyze(ticker, data_payload)
            price_res['agent_name'] = price_agent.name
            
            news_res = news_agent.analyze(ticker, data_payload)
            news_res['agent_name'] = news_agent.name
            
            sec_res = sec_agent.analyze(ticker, data_payload)
            sec_res['agent_name'] = sec_agent.name
            
            smart_money_res = smart_money_agent.analyze(ticker, data_payload)
            smart_money_res['agent_name'] = smart_money_agent.name
            
            risk_res = risk_agent.analyze(ticker, data_payload)
            risk_res['agent_name'] = risk_agent.name
            
            macro_res = macro_agent.analyze()
            macro_res['agent_name'] = macro_agent.name
            
            # Fusion
            final_result = fusion_engine.process_signals([price_res, news_res, sec_res, smart_money_res, risk_res, macro_res])
            
            # Save to Database
            save_signal(
                ticker=ticker,
                prediction=final_result['prediction'],
                final_signal=final_result['final_signal'],
                confidence=final_result['confidence'],
                risk_level=final_result['risk_level'],
                raw_data=final_result['details']
            )
            
            # Small delay to respect free API rate limits (e.g. Yahoo Finance)
            time.sleep(2)
            
        except Exception as e:
            logger.error(f"Error processing {ticker}: {e}")
            
    logger.info("Batch Screener finished successfully!")

if __name__ == "__main__":
    run_batch()
