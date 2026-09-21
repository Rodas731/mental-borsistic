import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
from data.market_data import MarketDataClient, search_by_isin_or_keyword
from agents.price_agent import PriceAgent
from agents.news_agent import NewsAgent
from agents.sec_agent import SECAgent
from agents.smart_money_agent import SmartMoneyAgent
from agents.risk_agent import RiskAgent
from agents.macro_agent import MacroAgent
from core.fusion_engine import SignalFusionEngine
from data.db import (
    get_latest_signals, get_portfolio, get_trade_history, execute_trade, save_signal,
    get_agent_account, set_agent_budget, get_agent_portfolio, get_agent_trades,
    get_paper_deposits, add_paper_deposit, delete_paper_deposit, get_paper_account_summary,
    verify_user_credentials,
    get_watchlist, add_watchlist_item, update_watchlist_item, delete_watchlist_item
)
from agents.autotrading_agent import AutotradingAgent
from data.ticker_names import TICKER_NAMES

st.set_page_config(page_title="Market Intelligence Engine", layout="wide", page_icon="📈")

# Estrai la funzione per i colori così è riutilizzabile
def get_signal_color(sig):
    if sig == 0:
        return "#808080"
    elif sig > 0:
        r = int(255 * (1 - sig))
        g = int(255 - 155 * sig)
        return f"rgb({r}, {g}, 0)"
    else:
        abs_sig = abs(sig)
        r = int(255 - 116 * abs_sig)
        g = int(192 * (1 - abs_sig))
        b = int(203 * (1 - abs_sig))
        return f"rgb({r}, {g}, {b})"

def render_single_analysis(ticker):
    with st.spinner(f"Raccolta dati e analisi per {ticker}..."):
        data_client = MarketDataClient()
        df = data_client.get_historical_prices(ticker, period="6mo")
        company_info = data_client.get_company_info(ticker)
        
        if df.empty:
            st.error(f"Impossibile recuperare i dati per {ticker}. Controlla il simbolo.")
            return None
    
        name = company_info.get("longName", TICKER_NAMES.get(ticker, ticker))
        sector = company_info.get("sector", "N/A")
        st.subheader(f"{name} ({ticker}) - Settore: {sector}")
        
        # Selezione tipo di grafico
        chart_type = st.radio("Tipo di Grafico:", ["Candele", "Linea", "Area"], horizontal=True, key=f"chart_type_{ticker}")
        
        if chart_type == "Candele":
            with st.expander("💡 Come leggere le Candele Giapponesi?"):
                st.markdown("""
                Ogni candela rappresenta cosa è successo al prezzo in un singolo giorno:
                *   🟩 **Candela Verde (Prezzo salito):** La base del "corpo" è il prezzo di apertura, la cima è la chiusura.
                *   🟥 **Candela Rossa (Prezzo sceso):** La cima del "corpo" è il prezzo di apertura, la base è la chiusura.
                *   〰️ **Ombre (le lineette sopra e sotto):** Indicano il prezzo *Massimo* (in alto) e *Minimo* (in basso) toccato in quella giornata.
                """)
                
        fig = go.Figure()
        
        if chart_type == "Candele":
            fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Prezzo'))
        elif chart_type == "Linea":
            fig.add_trace(go.Scatter(x=df.index, y=df['Close'], mode='lines', name='Prezzo', line=dict(color='#1f77b4', width=2)))
        elif chart_type == "Area":
            fig.add_trace(go.Scatter(x=df.index, y=df['Close'], fill='tozeroy', mode='lines', name='Prezzo', line=dict(color='#00d2ff', width=2)))
            
        # Calcolo date per lo zoom di default (ultimi 30 giorni)
        last_date = df.index[-1]
        start_zoom_date = df.index[-30] if len(df) > 30 else df.index[0]
        
        # Calcoliamo il min e max del prezzo nell'intervallo visibile per non schiacciare l'asse Y
        df_zoom = df.loc[start_zoom_date:last_date]
        min_y = df_zoom['Low'].min() if 'Low' in df_zoom.columns else df_zoom['Close'].min()
        max_y = df_zoom['High'].max() if 'High' in df_zoom.columns else df_zoom['Close'].max()
        margin_y = (max_y - min_y) * 0.05
        
        fig.update_layout(
            height=450, 
            margin=dict(l=0, r=0, t=30, b=0),
            xaxis=dict(
                rangeselector=dict(
                    buttons=list([
                        dict(count=7, label="1 Settimana", step="day", stepmode="backward"),
                        dict(count=1, label="1 Mese", step="month", stepmode="backward"),
                        dict(count=3, label="3 Mesi", step="month", stepmode="backward"),
                        dict(step="all", label="Tutto (6 Mesi)")
                    ]),
                    font=dict(color="white"),
                    bgcolor="#1f2633",
                    activecolor="#2980b9"
                ),
                rangeslider=dict(visible=False),
                type="date",
                range=[start_zoom_date, last_date]
            ),
            yaxis=dict(
                autorange=False,
                range=[min_y - margin_y, max_y + margin_y],
                fixedrange=False,
                rangemode="normal"
            )
        )
        st.plotly_chart(fig, use_container_width=True)

        data_payload = {"market_data": df, "company_info": company_info}

        price_agent = PriceAgent()
        news_agent = NewsAgent()
        sec_agent = SECAgent()
        smart_money_agent = SmartMoneyAgent()
        risk_agent = RiskAgent()
        
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
        
        fusion_engine = SignalFusionEngine()
        final_result = fusion_engine.process_signals([price_res, news_res, sec_res, smart_money_res, risk_res])
        
        st.markdown("---")
        st.header("🔮 Verdetto Finale (Prediction Engine)")
        
        color = get_signal_color(final_result['final_signal'])
        risk_level = final_result.get('risk_level', 'SCONOSCIUTO')
        
        risk_color = "gray"
        if risk_level == "BASSO": risk_color = "green"
        elif risk_level == "MEDIO": risk_color = "orange"
        elif risk_level == "ALTO": risk_color = "orangered"
        elif risk_level == "ALTISSIMO": risk_color = "red"
        
        st.markdown(f'''
        <div style="padding: 20px; border-radius: 10px; background-color: rgba(128,128,128,0.1); text-align: center; margin-bottom: 20px;">
            <h3 style="margin-bottom: 5px;">Previsione: {final_result['prediction']}</h3>
            <h1 style="font-size: 3.5rem; margin: 0; color: {color};">Segnale: {final_result['final_signal']:.2f}</h1>
            <p style="margin-top: 5px; font-size: 1.2rem;" title="L'affidabilità globale della previsione, calcolata combinando la certezza di tutti gli agenti direzionali.">Confidenza: {final_result['confidence']:.0%} ℹ️</p>
            <hr style="margin: 10px 0; border-color: rgba(128,128,128,0.3);">
            <h3 style="margin: 0; color: {risk_color};">Livello di Rischio: {risk_level}</h3>
        </div>
        ''', unsafe_allow_html=True)
        
        with st.expander("📊 Come viene calcolato il Segnale e cosa significa?"):
            st.markdown("""
            Il **Segnale** finale è un indicatore numerico che rappresenta il consenso globale (o *Verdetto Finale*) di tutti gli agenti dell'intelligenza artificiale sul titolo analizzato.
            
            **Come si interpreta il numero?**
            *   🟢 **Da +0.20 in su (RIALZISTA):** Indica una tendenza positiva. Più il valore si avvicina a +1.00, più forte è il segnale di potenziale acquisto.
            *   🔴 **Da -0.20 in giù (RIBASSISTA):** Indica una tendenza negativa. Più il valore si avvicina a -1.00, più forte è il segnale di potenziale vendita.
            *   ⚪ **Tra -0.20 e +0.20 (NEUTRALE):** Indica che i segnali degli agenti si annullano a vicenda o che nessuno esprime una convinzione netta.

            **Come viene calcolato matematicamente?**
            Il sistema utilizza il `SignalFusionEngine` che calcola una **media ponderata** dei risultati dei 4 agenti (Analisi Tecnica, Sentiment News, Fondamentali SEC, Flussi Smart Money).
            
            Ogni agente restituisce un suo segnale (da -1 a +1) e una sua "confidenza" (livello di sicurezza dell'analisi).
            1. **Calcolo del Peso:** Ad ogni agente è assegnato un "Peso Base" (es. Analisi Tecnica ha peso maggiore) che viene poi moltiplicato per la *Confidenza* espressa dall'agente in quel momento.
            2. **Somma Ponderata:** Si moltiplica il segnale di ogni agente per il suo peso ricalcolato.
            3. **Risultato Finale:** La somma di questi valori viene divisa per la somma totale dei pesi.
            
            In questo modo, se un agente produce un segnale fortissimo ma non è per niente sicuro (confidenza bassa), il suo impatto sul Verdetto Finale sarà minimo, privilegiando le analisi più solide e con dati più chiari.
            """)

        st.markdown("---")
        st.header(f"🤖 Report degli Agenti ({ticker})")
        
        with st.expander(f"{price_agent.name} su {ticker} (Segnale: {price_res['signal']:.2f})", expanded=True):
            st.info("📉 **Come agisce:** Analizza l'azione storica del prezzo e gli indicatori matematici (es. RSI, Medie Mobili).\n🎯 **Cosa indica:** Se il titolo è in una fase di ipercomprato/ipervenduto e la forza del trend a breve termine.")
            mcol1, mcol2, mcol3 = st.columns(3)
            mcol1.metric("Segnale Tecnico", f"{price_res['signal']:.2f}")
            mcol2.metric("Valore RSI", f"{price_res.get('metadata', {}).get('rsi', 0):.2f}", help="Relative Strength Index (Indice di Forza Relativa): misura l'ipercomprato o l'ipervenduto del titolo.")
            mcol3.metric("Confidenza", f"{price_res['confidence']:.0%}", help="Livello di affidabilità tecnica: si basa sulla forza del trend, sui volumi e sulla chiarezza del grafico.")
            st.write(f"**Ragionamento:** {price_res['reasoning']}")
            
        with st.expander(f"{news_agent.name} su {ticker} (Segnale: {news_res['signal']:.2f})", expanded=True):
            st.info("📰 **Come agisce:** Legge le ultime notizie finanziarie e le interpreta usando l'Intelligenza Artificiale (NLP).\n🎯 **Cosa indica:** L'umore generale (Sentiment) e come investitori e media stanno reagendo alle novità dell'azienda.")
            mcol1, mcol2, mcol3 = st.columns(3)
            mcol1.metric("Segnale Sentiment", f"{news_res['signal']:.2f}")
            mcol2.metric("Notizie Analizzate", f"{news_res.get('metadata', {}).get('num_articles', 0)}")
            mcol3.metric("Confidenza", f"{news_res['confidence']:.0%}", help="Livello di certezza del NLP: aumenta se ci sono tante notizie coerenti tutte verso la stessa direzione (positive o negative).")
            st.write(f"**Ragionamento:** {news_res['reasoning']}")
            
            articles = news_res.get('metadata', {}).get('articles', [])
            if articles:
                with st.expander("📚 Clicca qui per vedere le notizie analizzate"):
                    for art in articles[:10]:
                        date = art.get('date', '')
                        date_str = f"🕒 <b>{date}</b> - " if date else ""
                        st.markdown(
                            f"<p style='font-size: 0.85rem; margin-bottom: 5px;'>"
                            f"{date_str}<a href='{art['link']}' target='_blank' style='text-decoration: none;'>{art['title']}</a> "
                            f"<span style='color: gray; font-size: 0.75rem;'>(Sentiment: {art['sentiment']:.2f})</span>"
                            f"</p>", 
                            unsafe_allow_html=True
                        )
            else:
                st.warning("Nessuna notizia recente trovata per questo ticker su Yahoo Finance. (Spesso accade per i titoli minori o non-USA come quelli della Borsa di Milano).")
            
        with st.expander(f"{sec_agent.name} su {ticker} (Segnale: {sec_res['signal']:.2f})", expanded=True):
            st.info("🏛️ **Come agisce:** Estrae i dati ufficiali di bilancio depositati presso gli enti regolatori (es. SEC americana).\n🎯 **Cosa indica:** La salute finanziaria e la crescita reale dell'azienda basata su metriche contabili (come l'Utile per Azione).")
            mcol1, mcol2, mcol3 = st.columns(3)
            mcol1.metric("Segnale Fondamentale", f"{sec_res['signal']:.2f}")
            eps_growth = sec_res.get('metadata', {}).get('eps_growth', 0)
            mcol2.metric("Crescita EPS", f"{eps_growth:.1%}", help="Earnings Per Share (Utile per Azione): misura la crescita della redditività dell'azienda.")
            mcol3.metric("Confidenza", f"{sec_res['confidence']:.0%}", help="Affidabilità del dato di bilancio: basata sulla quantità e sulla qualità dei dati storici estratti dalla SEC.")
            st.write(f"**Ragionamento:** {sec_res['reasoning']}")
            
        with st.expander(f"{smart_money_agent.name} su {ticker} (Segnale: {smart_money_res['signal']:.2f})", expanded=True):
            st.info("🐋 **Come agisce:** Monitora i flussi di capitale dei grandi fondi (Hedge Fund) e le compravendite dei dirigenti dell'azienda.\n🎯 **Cosa indica:** Dove i portafogli pesanti e chi ha informazioni interne stanno mettendo i propri soldi, anticipando spesso il mercato retail.")
            mcol1, mcol2, mcol3 = st.columns(3)
            mcol1.metric("Segnale Istituzionale", f"{smart_money_res['signal']:.2f}")
            mcol2.metric("Insider Flow", f"{smart_money_res.get('metadata', {}).get('net_insider_buying_score', 0):.2f}", help="Misura da -1 (Forti Vendite) a +1 (Forti Acquisti) degli Insider.")
            mcol3.metric("Confidenza", f"{smart_money_res['confidence']:.0%}", help="Solidità del segnale: indica la magnitudo dei capitali mossi e quanto chiare e inequivocabili sono le transazioni degli Insider.")
            st.write(f"**Ragionamento:**\n{smart_money_res['reasoning']}")
            
        with st.expander(f"{risk_agent.name} su {ticker} (Rischio: {risk_res.get('metadata', {}).get('risk_level', 'N/A')})", expanded=True):
            st.info("⚠️ **Come agisce:** Analizza la volatilità storica dei rendimenti e il Massimo Drawdown registrato.\n🎯 **Cosa indica:** Se il titolo è soggetto a forti oscillazioni che potrebbero causare perdite repentine, permettendoti di dosare correttamente l'investimento.")
            mcol1, mcol2, mcol3 = st.columns(3)
            mcol1.metric("Risk Score", f"{risk_res.get('metadata', {}).get('risk_score', 0):.2f}", help="Punteggio sintetico da 0 a 1: un valore vicino a 1 indica un rischio altissimo.")
            mcol2.metric("Volatilità", f"{risk_res.get('metadata', {}).get('volatility', 0):.1%}", help="Misura quanto il prezzo del titolo oscilla violentemente su base annua.")
            mcol3.metric("Max Drawdown", f"{risk_res.get('metadata', {}).get('max_drawdown', 0):.1%}", help="La percentuale di perdita massima storica che il titolo ha registrato nel periodo analizzato.")
            st.write(f"**Ragionamento:**\n{risk_res['reasoning']}")

        # -------------------------------------------------------------------------
        # AGGIUNTA ALERT USCITA IA (Valutazione determinazioni agenti dedicati alla vendita)
        # -------------------------------------------------------------------------
        try:
            auto_agent = AutotradingAgent()
            user_port = get_portfolio()
            holding = next((p for p in user_port if p['ticker'] == ticker), None) if user_port else None
            
            avg_price = holding['avg_purchase_price'] if holding else df['Close'].iloc[-1]
            shares = holding['shares'] if holding else 100
            is_in_port = bool(holding)

            exit_data_payload = {
                'market_data': df,
                'df': df,
                'news_res': news_res,
                'sec_res': sec_res,
                'smart_money_res': smart_money_res,
                'risk_res': risk_res,
                'company_info': company_info,
                'is_in_portfolio': is_in_port
            }
            exit_eval = auto_agent.run_exit_analysis(ticker, current_shares=shares, avg_price=avg_price, data_payload=exit_data_payload)
            exit_score = exit_eval.get('exit_score', 0.0)
            exit_rec = exit_eval.get('recommendation', 'MANTIENI')
            
            # Mostra l'alert visivo dedicato con cornicetta rossa e stile prioritario
            if exit_score >= 0.35:
                st.markdown("---")
                border_color = "#ff3333" if exit_score >= 0.65 else "#ff6666"
                bg_color = "rgba(255, 51, 51, 0.08)" if exit_score >= 0.65 else "rgba(255, 102, 102, 0.06)"
                badge_text = "🚨 ALLERTA VENDITA TOTALE / STOP LOSS" if exit_score >= 0.65 else "⚠️ ALLERTA VENDITA PARZIALE / TAKE PROFIT"
                
                trigger_items = ""
                for d in exit_eval.get('details', []):
                    ag_name = d.get('agent_name', 'Agente')
                    ag_sig = d.get('exit_signal', 0.0)
                    ag_reason = d.get('reasoning', '')
                    if ag_sig > 0.2:
                        trigger_items += f"<li style='margin-bottom: 6px;'><b>{ag_name}</b> (Segnale Vendita: <code>{ag_sig:.2f}</code>): {ag_reason}</li>"
                        
                alert_html = f"""
                <div style="border: 2px solid {border_color}; border-radius: 12px; background-color: {bg_color}; padding: 20px 24px; margin: 25px 0 20px 0; box-shadow: 0 4px 18px rgba(255, 51, 51, 0.18);">
                    <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid rgba(255, 51, 51, 0.3); padding-bottom: 12px; margin-bottom: 15px;">
                        <div>
                            <span style="background-color: {border_color}; color: white; padding: 4px 10px; border-radius: 6px; font-weight: bold; font-size: 0.85rem; letter-spacing: 0.5px;">{badge_text}</span>
                            <h3 style="margin: 8px 0 0 0; color: {border_color};">Radar di Uscita AI ({ticker})</h3>
                        </div>
                        <div style="text-align: right;">
                            <div style="font-size: 0.85rem; color: gray;">Exit Score:</div>
                            <div style="font-size: 1.8rem; font-weight: bold; color: {border_color};">{exit_score:.0%}</div>
                        </div>
                    </div>
                    <div style="margin-bottom: 14px; font-size: 1.05rem;">
                        <b>Raccomandazione:</b> <span style="color: {border_color}; font-weight: bold;">{exit_rec}</span> | <b>Confidenza:</b> {exit_eval.get('confidence', 0):.0%}
                    </div>
                    <div style="margin-bottom: 12px; font-size: 0.95rem; line-height: 1.4;">
                        <b>Sintesi Motivazionale:</b> {exit_eval.get('reasoning', '')}
                    </div>
                    {f"<div style='margin-top: 10px; padding-top: 10px; border-top: 1px dashed rgba(255,51,51,0.25); font-size: 0.9rem;'><b style='color: {border_color};'>Determinazioni degli Agenti di Uscita:</b><ul style='margin-top: 6px; padding-left: 20px;'>{trigger_items}</ul></div>" if trigger_items else ""}
                </div>
                """
                st.markdown(alert_html, unsafe_allow_html=True)
            else:
                with st.expander(f"🛡️ Radar di Uscita AI ({ticker}) - Stato: Posizione Regolare (Exit Score: {exit_score:.0%})", expanded=False):
                    ecol1, ecol2, ecol3 = st.columns(3)
                    ecol1.metric("Exit Score", f"{exit_score:.0%}")
                    ecol2.metric("Determinazione", exit_rec)
                    ecol3.metric("Confidenza", f"{exit_eval.get('confidence', 0):.0%}")
                    st.info(f"Nessun alert di vendita attivo. {exit_eval.get('reasoning', '')}")
        except Exception as e:
            pass
            
        return final_result

# ---------------------------------------------------------
# Autenticazione e Protezione Accesso Riservato
# ---------------------------------------------------------
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if not st.session_state["authenticated"]:
    st.markdown("""
    <style>
    .login-box {
        background-color: #1a2230;
        border: 1px solid #2d3748;
        border-radius: 14px;
        padding: 30px;
        box-shadow: 0 8px 30px rgba(0,0,0,0.4);
        margin-top: 50px;
        text-align: center;
    }
    .login-title {
        color: #ffffff;
        font-size: 1.5rem;
        font-weight: 700;
        margin-bottom: 5px;
    }
    .login-sub {
        color: #94a3b8;
        font-size: 0.9rem;
        margin-bottom: 20px;
    }
    </style>
    """, unsafe_allow_html=True)
    
    col_l1, col_l2, col_l3 = st.columns([1, 1.4, 1])
    with col_l2:
        st.markdown("""
        <div class="login-box">
            <div style="font-size: 2.8rem; margin-bottom: 8px;">🔐</div>
            <div class="login-title">Market Intelligence Engine</div>
            <div class="login-sub">Accesso Riservato ad Utente Autorizzato</div>
        </div>
        """, unsafe_allow_html=True)
        
        with st.form("login_form", clear_on_submit=False):
            username_input = st.text_input("Username", value="", placeholder="Inserisci username", autocomplete="username")
            password_input = st.text_input("Password", type="password", placeholder="Inserisci password", autocomplete="current-password")
            submit_login = st.form_submit_button("🔓 Accedi all'Applicazione", use_container_width=True, type="primary")
            
            if submit_login:
                if verify_user_credentials(username_input, password_input):
                    st.session_state["authenticated"] = True
                    st.session_state["username"] = username_input
                    st.success("Accesso autorizzato!")
                    st.rerun()
                else:
                    st.error("❌ Credenziali non valide. Accesso negato.")
        
    st.stop()

# ---------------------------------------------------------
# Navigazione Laterale (Utente Autenticato)
# ---------------------------------------------------------
user_display = st.session_state.get('username', 'Rodas73')
st.sidebar.markdown(f"""
<div style="background-color: #1a2230; padding: 10px 14px; border-radius: 10px; border: 1px solid #2d3748; margin-bottom: 12px;">
    <div style="font-size: 0.75rem; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.5px;">Sessione Attiva</div>
    <div style="font-weight: bold; color: #38bdf8; font-size: 1.05rem;">👤 {user_display}</div>
</div>
""", unsafe_allow_html=True)

if st.sidebar.button("🚪 Disconnetti", use_container_width=True):
    st.session_state["authenticated"] = False
    st.session_state.pop("username", None)
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.title("Navigazione")
page = st.sidebar.radio("Scegli la Modalità:", ["📡 Live Analysis", "🔎 Screener IA", "📋 Lista Titoli", "💼 Paper Trading", "🤖 AI Autotrading", "🌐 Guida & Trova Ticker"])

# Definizione Liste Titoli
market_lists = {
    "Milano": [
        "A2A.MI", "AMP.MI", "AZM.MI", "BPE.MI", "BMED.MI", "BAMI.MI", "BZU.MI", "CPR.MI", 
        "DIA.MI", "ENEL.MI", "ENI.MI", "ERG.MI", "FBK.MI", "RACE.MI", "G.MI", "HER.MI", 
        "INW.MI", "ISP.MI", "IG.MI", "LDO.MI", "MB.MI", "MONC.MI", "NEXI.MI", "PST.MI", 
        "PRY.MI", "REC.MI", "SRG.MI", "SPM.MI", "STLAM.MI", "STMMI.MI", "TEN.MI", "TRN.MI", 
        "TIT.MI", "UCG.MI", "UNI.MI", "IP.MI", "BRE.MI", "TGYM.MI", "FCT.MI", "OVS.MI",
        "SFER.MI", "MFEB.MI", "MFEA.MI", "ENAV.MI", "BFF.MI", "GVS.MI", "SAB.MI", "CEM.MI",
        "DAN.MI", "DIB.MI", "EUK.MI", "IGD.MI", "ITM.MI", "MTV.MI", "PRT.MI", "RCS.MI",
        "TXT.MI", "WBD.MI", "DOV.MI", "JUVE.MI", "MARR.MI", "MAIRE.MI", "SIT.MI", "SES.MI",
        "FILA.MI", "LUVE.MI", "BC.MI", "AVIO.MI", "ELN.MI", "WIIT.MI", "TIP.MI", "ARN.MI",
        "RWAY.MI", "CE.MI", "DBA.MI", "DLG.MI", "IRE.MI", "BGN.MI", "AEF.MI", "CY4.MI",
        "EQUI.MI", "GEO.MI", "IVG.MI", "REVO.MI", "SOL.MI", "ELC.MI", "IMS.MI", "MOL.MI",
        "RAT.MI", "SFL.MI", "VAL.MI"
    ],
    "New York": [
        "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "BRK-B", "UNH", "JNJ",
        "JPM", "V", "PG", "XOM", "HD", "CVX", "MA", "ABBV", "MRK", "PEP",
        "COST", "AVGO", "KO", "TMO", "CSCO", "MCD", "CRM", "ABT", "DHR", "ACN",
        "NFLX", "AMD", "INTC", "QCOM", "TXN", "SLB", "COP", "EOG", "WMT", "DIS",
        "BA", "IBM", "ORCL", "AMAT", "MU", "LRCX", "ADI", "KLAC", "NXPI", "MRVL",
        "MCHP", "SWKS", "TER", "QRVO", "WDC", "STX", "HPQ", "HPE", "DELL", "NTAP",
        "ANET", "GLW", "MSI", "ZBRA", "TRMB", "KEYS", "TDY", "IT", "CDW", "EPAM",
        "CTSH", "AKAM", "FTNT", "PANW", "CRWD", "ZS", "OKTA", "NET", "FSLY", "DDOG",
        "SNOW", "PLTR", "U", "RBLX", "PATH", "MNDY", "ASAN", "DOCN", "FIVN", "TENB",
        "VRNS", "CHKP", "NOW", "INTU", "ISRG", "BKNG", "MDLZ", "REGN", "VRTX"
    ],
    "Parigi": [
        "MC.PA", "OR.PA", "RMS.PA", "TTE.PA", "SAN.PA", "AIR.PA", "SU.PA", "AI.PA",
        "BNP.PA", "EL.PA", "CS.PA", "DG.PA", "SAF.PA", "BN.PA", "SGO.PA", "CAP.PA",
        "ACA.PA", "GLE.PA", "LR.PA", "EN.PA", "VIE.PA", "ENGI.PA", "ORA.PA", "RNO.PA",
        "ML.PA", "RI.PA", "KER.PA", "VIV.PA", "PUB.PA", "EDEN.PA", "HO.PA", "URW.PA",
        "CA.PA", "WLN.PA", "ERF.PA", "DSY.PA", "AC.PA", "ALO.PA", "SPIE.PA", "GET.PA",
        "BVI.PA", "SOI.PA", "VK.PA", "ATE.PA", "SK.PA", "DEC.PA", "GFC.PA", "ICAD.PA",
        "NEX.PA", "RCO.PA", "TE.PA", "VIRP.PA", "ELIS.PA", "BEN.PA", "COFA.PA", "DIM.PA",
        "GTT.PA", "NK.PA", "VANTI.PA", "NXI.PA", "ATO.PA", "IPN.PA", "TFI.PA", "STLAP.PA",
        "CARM.PA", "UBI.PA", "DBV.PA", "NRO.PA", "FNAC.PA", "KOF.PA", "SW.PA", "RUI.PA",
        "BIM.PA", "ALTA.PA", "BB.PA", "COV.PA", "IDIP.PA", "AMUN.PA", "OVH.PA", "BOL.PA"
    ],
    "Francoforte": [
        "SAP.DE", "SIE.DE", "ALV.DE", "DTE.DE", "VOW3.DE", "MBG.DE", "BMW.DE", "BAS.DE",
        "MUV2.DE", "IFX.DE", "BAYN.DE", "DHL.DE", "MRK.DE", "HEN3.DE", "EOAN.DE", "BEI.DE",
        "DBK.DE", "RWE.DE", "VNA.DE", "ADS.DE", "DTG.DE", "FRE.DE", "FME.DE", "HEI.DE",
        "HNR1.DE", "CON.DE", "MTX.DE", "PAH3.DE", "P911.DE", "QIA.DE", "RHM.DE", "SHL.DE",
        "SY1.DE", "ZAL.DE", "CBK.DE", "ENR.DE", "SRT3.DE", "BNR.DE", "EVK.DE", "KRN.DE",
        "LEG.DE", "G1A.DE", "FRA.DE", "HFG.DE", "PUM.DE", "LHA.DE", "TLX.DE", "AIXA.DE",
        "EVD.DE", "FPE3.DE", "GXI.DE", "NEM.DE", "TEG.DE", "WCH.DE", "BOSS.DE", "G24.DE",
        "TKA.DE", "EVT.DE", "GFT.DE", "SMHN.DE", "SDF.DE", "HLE.DE", "HAG.DE", "DEQ.DE",
        "DEZ.DE", "KBX.DE", "VOS.DE", "WAC.DE", "DUE.DE", "AMZ.DE", "SZG.DE", "HOT.DE",
        "SIX2.DE", "JEN.DE", "FNTN.DE", "BC8.DE", "DHER.DE", "NDX1.DE", "RAA.DE", "STR.DE",
        "WAF.DE", "GLJ.DE", "PFV.DE", "EKT.DE"
    ]
}

# ---------------------------------------------------------
# PAGE 1: 📡 Live Analysis
# ---------------------------------------------------------
if page == "📡 Live Analysis":
    st.title("📈 Motore di Intelligenza di Mercato (Live)")
    st.markdown("Plancia di comando: Scansione massiva opportunità, ricerca approfondita e Radar di Uscita.")

    portfolio = get_portfolio()
    portfolio_tickers = [p['ticker'] for p in portfolio] if portfolio else []

    tab_search, tab_portfolio = st.tabs([
        "🔍 Ricerca Ad-Hoc Singolo Titolo", 
        "🛡️ Radar di Uscita & Portafoglio"
    ])

    with tab_search:
        st.header("🔍 Ricerca e Analisi Singolo Titolo")
        search_mode = st.radio("Metodo di inserimento:", ["Selezione da Lista (Mercati)", "Inserimento Libero (Ticker)", "🆔 Ricerca per Codice ISIN"], horizontal=True, key="search_mode_radio")
        
        ad_hoc_ticker = ""
        if search_mode == "Selezione da Lista (Mercati)":
            col_search, col_btn, col_clear = st.columns([2, 1, 1])
            with col_search:
                col_mkt, col_tkr = st.columns(2)
                with col_mkt:
                    sel_market = st.selectbox("Seleziona Mercato:", list(market_lists.keys()), key="search_sel_market")
                with col_tkr:
                    ad_hoc_ticker = st.selectbox(
                        "Seleziona Titolo:", 
                        market_lists[sel_market],
                        format_func=lambda x: f"{x} - {TICKER_NAMES.get(x, 'Nome Sconosciuto')}",
                        key="search_sel_ticker"
                    )
            with col_btn:
                st.write("")
                st.write("")
                search_btn = st.button("Analizza Singolo Titolo", key="btn_single_search")
            with col_clear:
                st.write("")
                st.write("")
                clear_btn = st.button("Chiudi Ricerca", key="btn_single_clear")
        elif search_mode == "Inserimento Libero (Ticker)":
            col_search, col_btn, col_clear = st.columns([2, 1, 1])
            with col_search:
                ad_hoc_ticker = st.text_input("Inserisci un Ticker (es. AAPL, ENEL.MI, TSLA):", key="search_text_input").upper().strip()
            with col_btn:
                st.write("")
                st.write("")
                search_btn = st.button("Analizza Singolo Titolo", key="btn_single_search")
            with col_clear:
                st.write("")
                st.write("")
                clear_btn = st.button("Chiudi Ricerca", key="btn_single_clear")
        else: # Ricerca per Codice ISIN
            col_isin_in, col_isin_btn = st.columns([2, 1])
            with col_isin_in:
                isin_query = st.text_input("Inserisci Codice ISIN (es. IT0003128367, US0378331005, FR0000121014):", key="search_isin_input").strip().upper()
            with col_isin_btn:
                st.write("")
                st.write("")
                isin_search_btn = st.button("🔍 Trova da ISIN", key="btn_isin_lookup", type="primary")
            
            clear_btn = st.button("Chiudi Ricerca", key="btn_single_clear_isin")
            search_btn = False

            if isin_query and (isin_search_btn or st.session_state.get('last_isin_searched') == isin_query):
                st.session_state['last_isin_searched'] = isin_query
                with st.spinner(f"Ricerca del titolo per ISIN '{isin_query}'..."):
                    isin_matches = search_by_isin_or_keyword(isin_query)
                
                if isin_matches:
                    st.success(f"Trovati {len(isin_matches)} risultati compatibili per l'ISIN `{isin_query}`:")
                    match_options = [f"{m['ticker']} - {m['name']} ({m.get('exchange', 'Borsa')})" for m in isin_matches]
                    selected_match_idx = st.selectbox("Seleziona la quotazione da analizzare:", range(len(match_options)), format_func=lambda i: match_options[i], key="sel_isin_match_idx")
                    ad_hoc_ticker = isin_matches[selected_match_idx]['ticker']
                    if st.button(f"🚀 Analizza {ad_hoc_ticker}", type="primary", key="btn_run_isin_analysis"):
                        st.session_state['ad_hoc_search'] = ad_hoc_ticker
                        st.rerun()
                else:
                    st.error(f"Nessun titolo trovato su Yahoo Finance per l'ISIN `{isin_query}`. Verifica il codice o prova con il simbolo Ticker.")

        if clear_btn:
            st.session_state['ad_hoc_search'] = None
            st.rerun()

        if search_btn and ad_hoc_ticker:
            st.session_state['ad_hoc_search'] = ad_hoc_ticker

        if st.session_state.get('ad_hoc_search'):
            st.subheader(f"Risultati Ricerca: {st.session_state['ad_hoc_search']}")
            render_single_analysis(st.session_state['ad_hoc_search'])

    with tab_portfolio:
        st.header("🛡️ Radar di Uscita & Monitoraggio Portafoglio")
        st.markdown("Valutazione continua della salute dei titoli in portafoglio, determinazione alert di vendita, take profit e trailing stop.")
        
        if portfolio_tickers:
            st.info(f"💼 Titoli monitorati in portafoglio ({len(portfolio_tickers)}): {', '.join(portfolio_tickers)}")
            sel_p_ticker = st.selectbox(
                "Seleziona un titolo dal tuo portafoglio per visualizzare la scheda completa ed il Radar di Uscita:", 
                portfolio_tickers, 
                format_func=lambda x: f"{x} - {TICKER_NAMES.get(x, '')}",
                key="portfolio_tab_ticker_select"
            )
            if sel_p_ticker:
                render_single_analysis(sel_p_ticker)
        else:
            st.info("Nessun titolo attualmente in portafoglio. Acquista titoli dal simulatore Paper Trading o dall'AI Autotrading per monitorarli qui.")

# ---------------------------------------------------------
# PAGE 2: 🔎 Screener IA
# ---------------------------------------------------------
elif page == "🔎 Screener IA":
    st.title("🔎 Screener d'Investimento IA")
    st.markdown("Filtra i migliori titoli in base alle metriche combinate dei nostri agenti AI.")
    
    sel_market_scr = st.selectbox("Seleziona Mercato da Scansionare:", list(market_lists.keys()))
    min_signal = st.slider("Soglia Minima Segnale Acquisto:", -1.0, 1.0, 0.20, step=0.05)
    
    def render_screener_top_5(screener_res, market_name):
        sorted_scr = sorted(screener_res, key=lambda x: x['Segnale AI'], reverse=True)[:5]
        if not sorted_scr:
            return
        st.subheader(f"🏆 Top 5 Titoli con Score Maggiore - {market_name}")
        for i, r in enumerate(sorted_scr):
            tk = r['Ticker']
            name = r['Nome']
            sig = r['Segnale AI']
            conf = r['Confidenza']
            risk = r['Rischio']
            pred = r['Previsione']
            sig_color = "green" if sig > 0 else "red" if sig < 0 else "gray"
            
            with st.expander(f"#{i+1} {tk} ({name}) | Segnale AI: {sig:.2f} | Confidenza: {conf}", expanded=(i==0)):
                st.markdown(f"""
                <div style="display: flex; justify-content: space-around; align-items: center; padding: 12px; background-color: rgba(128,128,128,0.1); border-radius: 8px; margin-bottom: 10px;">
                    <div style="text-align: center;"><b>Previsione:</b><br>{pred}</div>
                    <div style="text-align: center;"><span style="font-size: 1.6rem; font-weight: bold; color: {sig_color};">Segnale: {sig:.2f}</span></div>
                    <div style="text-align: center;"><b>Rischio:</b><br>{risk}</div>
                </div>
                """, unsafe_allow_html=True)
                st.write(f"**Confidenza Globale dell'Analisi:** {conf}")

    if st.button("Avvia Screener IA"):
        candidates = market_lists[sel_market_scr]
        with st.spinner(f"Analisi e calcolo metriche IA per {len(candidates)} titoli su {sel_market_scr}..."):
            p_agent = PriceAgent()
            n_agent = NewsAgent()
            sec_agent = SECAgent()
            sm_agent = SmartMoneyAgent()
            r_agent = RiskAgent()
            fusion = SignalFusionEngine()
            data_client = MarketDataClient()
            
            batch_data = data_client.get_batch_historical_prices(candidates, period="3mo")
            results = []

            for ticker in candidates:
                try:
                    df = batch_data.get(ticker, pd.DataFrame())
                    if df is not None and not df.empty:
                        data_payload = {"market_data": df, "is_batch": True}
                        p_res = p_agent.analyze(ticker, data_payload)
                        p_res['agent_name'] = p_agent.name
                        n_res = n_agent.analyze(ticker, data_payload)
                        n_res['agent_name'] = n_agent.name
                        sec_res = sec_agent.analyze(ticker, data_payload)
                        sec_res['agent_name'] = sec_agent.name
                        sm_res = sm_agent.analyze(ticker, data_payload)
                        sm_res['agent_name'] = sm_agent.name
                        r_res = r_agent.analyze(ticker, data_payload)
                        r_res['agent_name'] = r_agent.name
                        
                        fusion_res = fusion.process_signals([p_res, n_res, sec_res, sm_res, r_res])
                        risk_level_str = r_res.get('metadata', {}).get('risk_level', 'MEDIO')
                        
                        # Salvataggio nel Database per AI Autotrading
                        try:
                            save_signal(
                                ticker=ticker,
                                prediction=fusion_res['prediction'],
                                final_signal=fusion_res['final_signal'],
                                confidence=fusion_res['confidence'],
                                risk_level=risk_level_str,
                                raw_data=fusion_res
                            )
                        except Exception as ex:
                            logger.error(f"Errore nel salvataggio segnale per {ticker}: {ex}")
                        
                        if fusion_res['final_signal'] >= min_signal:
                            results.append({
                                'Ticker': ticker,
                                'Nome': TICKER_NAMES.get(ticker, ticker),
                                'Segnale AI': round(fusion_res['final_signal'], 2),
                                'Previsione': fusion_res['prediction'],
                                'Confidenza': f"{fusion_res['confidence']:.0%}",
                                'Rischio': risk_level_str
                            })
                except Exception as e:
                    logger.error(f"Error in screener for {ticker}: {e}")
                
            st.session_state['screener_results'] = results
            st.session_state['screener_market'] = sel_market_scr
            st.success(f"✅ Screener completato: {len(candidates)} titoli analizzati e salvati nel database. {len(results)} titoli con segnale >= {min_signal:+.2f}!")
        
        if results:
            render_screener_top_5(results, sel_market_scr)
            st.markdown("---")
            st.subheader("📋 Tabella Completa Risultati Screener")
            df_res = pd.DataFrame(results).sort_values(by='Segnale AI', ascending=False)
            st.dataframe(df_res, width="stretch", hide_index=True)
        else:
            st.warning("Nessun titolo supera la soglia di segnale selezionata.")
    elif st.session_state.get('screener_results'):
        st.markdown("---")
        render_screener_top_5(st.session_state['screener_results'], st.session_state.get('screener_market', ''))
        st.subheader(f"📋 Ultimi Risultati Screener ({st.session_state.get('screener_market', '')})")
        df_res = pd.DataFrame(st.session_state['screener_results']).sort_values(by='Segnale AI', ascending=False)
        st.dataframe(df_res, width="stretch", hide_index=True)

# ---------------------------------------------------------
# PAGE 3: 📋 Lista Titoli
# ---------------------------------------------------------
elif page == "📋 Lista Titoli":
    st.title("📋 Lista Titoli Personale")
    st.markdown("Gestisci la tua lista personale di titoli da monitorare. Aggiungi titoli e annotazioni libere per ogni posizione.")

    watchlist = get_watchlist()

    # --- FORM AGGIUNTA NUOVO TITOLO ---
    with st.expander("➕ Aggiungi un nuovo titolo alla lista", expanded=True):
        with st.form("wl_add_form", clear_on_submit=True):
            wcol1, wcol2 = st.columns([1, 2])
            with wcol1:
                wl_ticker = st.text_input("Ticker (es. AAPL, ENEL.MI)", placeholder="AAPL").upper().strip()
                wl_label = st.text_input("Etichetta (opzionale)", placeholder="Es: Candidato acquisto")
            with wcol2:
                wl_note = st.text_area("Note iniziali", placeholder="Inserisci qui le tue osservazioni, motivazioni, livelli di prezzo di interesse...", height=100)
            if st.form_submit_button("✅ Aggiungi Titolo", type="primary", use_container_width=True):
                if wl_ticker:
                    ok = add_watchlist_item(wl_ticker, wl_label, wl_note)
                    if ok:
                        st.success(f"✅ Titolo **{wl_ticker}** aggiunto alla lista!")
                        st.rerun()
                    else:
                        st.error("Errore durante il salvataggio. Riprova.")
                else:
                    st.warning("Inserisci almeno il ticker del titolo.")

    st.markdown("---")

    # --- LISTA TITOLI SALVATI ---
    if not watchlist:
        st.info("📭 La lista è vuota. Aggiungi il primo titolo usando il pannello qui sopra.")
    else:
        st.markdown(f"**{len(watchlist)} titoli in lista:**")
        for item in watchlist:
            item_id = item['id']
            ticker = item['ticker']
            label = item.get('label') or ''
            note = item.get('note') or ''
            created = item.get('created_at', '')[:10]

            c_name = TICKER_NAMES.get(ticker, '')
            display_name = f"{ticker} — {c_name}" if c_name else ticker
            header_label = f" · *{label}*" if label else ''

            with st.expander(f"📌 {display_name}{header_label}  |  Aggiunto: {created}", expanded=False):
                edit_col, del_col = st.columns([4, 1])
                with edit_col:
                    new_label = st.text_input(
                        "Etichetta",
                        value=label,
                        key=f"wl_label_{item_id}",
                        placeholder="Es: Candidato acquisto, Osservazione..."
                    )
                    new_note = st.text_area(
                        "📝 Note",
                        value=note,
                        key=f"wl_note_{item_id}",
                        height=120,
                        placeholder="Le tue osservazioni, livelli chiave, strategie..."
                    )
                    if st.button("💾 Salva modifiche", key=f"wl_save_{item_id}"):
                        update_watchlist_item(item_id, label=new_label, note=new_note)
                        st.success("Modifiche salvate!")
                        st.rerun()
                with del_col:
                    st.write("")
                    st.write("")
                    st.write("")
                    if st.button("🗑️ Elimina", key=f"wl_del_{item_id}", type="secondary"):
                        delete_watchlist_item(item_id)
                        st.rerun()

# ---------------------------------------------------------
# PAGE 4: 💼 Paper Trading
# ---------------------------------------------------------
elif page == "💼 Paper Trading":
    st.title("💼 Simulatore di Portafoglio (Paper Trading)")
    st.markdown("Gestisci i tuoi investimenti virtuali. Usa la scheda Live o Screener per trovare opportunità, e compra qui sotto.")

    portfolio = get_portfolio()
    data_client = MarketDataClient()
    
    portfolio_val = 0.0
    total_unrealized = 0.0
    portfolio_rows = []
    
    portfolio_tickers = [item['ticker'] for item in portfolio] if portfolio else []
    batch_portfolio_dfs = data_client.get_batch_historical_prices(portfolio_tickers, period="5d") if portfolio_tickers else {}
    
    for item in portfolio:
        t = item['ticker']
        sh = item['shares']
        avg_p = item['avg_purchase_price']
        
        df_curr = batch_portfolio_dfs.get(t, pd.DataFrame())
        if df_curr.empty:
            df_curr = data_client.get_historical_prices(t, period="5d")
        curr_p = df_curr['Close'].iloc[-1] if not df_curr.empty else avg_p
        
        val = sh * curr_p
        unrealized = (curr_p - avg_p) * sh
        unrealized_pct = ((curr_p - avg_p) / avg_p) if avg_p > 0 else 0.0
        
        portfolio_val += val
        total_unrealized += unrealized
        
        c_name = TICKER_NAMES.get(t, '')
        display_ticker = f"{t} ({c_name})" if c_name else t
        
        buy_sig = item.get('buy_signal')
        sig_fmt = f"{buy_sig:.2f}" if buy_sig is not None else "N/A"
        
        portfolio_rows.append({
            'Ticker': display_ticker,
            'Azioni': sh,
            'Segnale Acquisto': sig_fmt,
            'Prezzo Carico': f"€{avg_p:.2f}",
            'Prezzo Attuale': f"€{curr_p:.2f}",
            'Controvalore': f"€{val:,.2f}",
            'P&L Non Realizzato': f"€{unrealized:,.2f} ({unrealized_pct:+.1%})"
        })

    summary = get_paper_account_summary(portfolio_value=portfolio_val)
    trades = get_trade_history()
    total_realized = sum(t['profit_loss'] for t in trades if t['profit_loss'] is not None)

    # BANNER QUADRO FINANZIARIO & CAPITALE INIZIALE
    st.markdown("### 🏦 Quadro Finanziario & Risorse Iniziali")
    overall_pl = summary['total_equity'] - summary['total_deposited']
    overall_pl_pct = (overall_pl / summary['total_deposited']) if summary['total_deposited'] > 0 else 0.0
    pl_delta_color = "normal"
    
    kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
    kpi1.metric("💰 Capitale Iniziale", f"€{summary['total_deposited']:,.2f}", help="Somma totale dei depositi e delle risorse economiche iniziali caricate sul conto.")
    kpi2.metric("📅 Data Inizio", summary['start_date'], help="Data del primo deposito o della prima transazione registrata.")
    kpi3.metric("💵 Liquidità (Cash)", f"€{summary['cash']:,.2f}", help="Capitale in euro disponibile per l'acquisto di nuovi titoli.")
    kpi4.metric("📊 Valore Totale (Equity)", f"€{summary['total_equity']:,.2f}", help="Valore complessivo del conto (Liquidità + Controvalore Titoli).")
    kpi5.metric("🎯 Guadagno/Perdita Totale", f"€{overall_pl:+,.2f}", delta=f"{overall_pl_pct:+.2%}", delta_color=pl_delta_color, help="Rendimento totale complessivo rispetto alle risorse economiche con cui hai iniziato.")

    subk1, subk2 = st.columns(2)
    subk1.metric("📈 P&L Non Realizzato Portafoglio", f"€{total_unrealized:+,.2f}")
    subk2.metric("📉 P&L Realizzato Totale Transazioni", f"€{total_realized:+,.2f}")

    with st.expander("📁 Gestione Depositi & Risorse Iniziali (Aggiungi/Rimuovi Fondi)"):
        st.markdown("Visualizza l'elenco dei depositi effettuati sul conto o inserisci nuovi versamenti di capitale.")
        dcol1, dcol2 = st.columns([2, 1])
        with dcol1:
            st.subheader("Elenco Depositi Registrati")
            deposits_list = summary['deposits']
            if deposits_list:
                df_dep = pd.DataFrame(deposits_list)
                df_dep['Importo (€)'] = df_dep['amount'].apply(lambda x: f"€{x:,.2f}")
                df_dep_disp = df_dep[['id', 'date', 'Importo (€)', 'note']]
                df_dep_disp.columns = ['ID Deposito', 'Data Inserimento', 'Importo', 'Origine / Note']
                st.dataframe(df_dep_disp, width="stretch", hide_index=True)
                st.info(f"**Somma Totale Risorse Economiche: €{summary['total_deposited']:,.2f}**")
            else:
                st.write("Nessun deposito registrato.")
        with dcol2:
            st.subheader("Registra Nuovo Deposito")
            with st.form("dep_form"):
                dep_val = st.number_input("Importo Deposito (€)", min_value=10.0, max_value=10000000.0, value=10000.0, step=1000.0)
                dep_dt = st.date_input("Data Deposito", datetime.now())
                dep_desc = st.text_input("Origine / Note", value="Versamento Capitale Iniziale")
                if st.form_submit_button("➕ Aggiungi Deposito"):
                    date_str = dep_dt.strftime("%Y-%m-%d %H:%M:%S")
                    add_paper_deposit(dep_val, dep_desc, date_str)
                    st.success("Deposito registrato con successo!")
                    st.rerun()

    st.markdown("---")

    # PORTAFOGLIO ATTIVO & NUOVA TRANSAZIONE
    col_main, col_sidebar = st.columns([2, 1])
    
    with col_main:
        st.subheader("Il Tuo Portafoglio Attivo")
        if portfolio_rows:
            df_port = pd.DataFrame(portfolio_rows)
            st.dataframe(df_port, width="stretch", hide_index=True)
            
            unrealized_color = "normal"
            st.metric(
                label="Valore Totale Portafoglio Titoli",
                value=f"€{portfolio_val:,.2f}",
                delta=f"€{total_unrealized:+,.2f} ({(total_unrealized/portfolio_val if portfolio_val > 0 else 0):+.1%})",
                delta_color=unrealized_color
            )
        else:
            st.info("Nessuna posizione aperta al momento.")

    with col_sidebar:
        st.subheader("🛒 Nuova Transazione")
        
        t_ticker = st.text_input("Ticker (es. ENEL.MI, NVDA, AAPL):", key="paper_trade_ticker").upper().strip()
        t_type = st.selectbox("Tipo Ordine:", ["BUY (Acquisto)", "SELL (Vendita)"], key="paper_trade_type")
        t_shares = st.number_input("Quantità (Azioni):", min_value=1, value=10, step=1, key="paper_trade_shares")
        
        order_action = "BUY" if "BUY" in t_type else "SELL"
        
        if t_ticker:
            try:
                with st.spinner(f"Recupero quotazione per {t_ticker}..."):
                    df_p = data_client.get_historical_prices(t_ticker, period="5d")
                    
                if df_p.empty:
                    st.error(f"❌ Quotazione non disponibile per '{t_ticker}'. Verifica il simbolo.")
                else:
                    c_price = df_p['Close'].iloc[-1]
                    op_value = c_price * t_shares
                    c_name = TICKER_NAMES.get(t_ticker, '')
                    label_ticker = f"{t_ticker} ({c_name})" if c_name else t_ticker
                    
                    # Controlli di validità
                    can_execute = True
                    held_shares = next((item['shares'] for item in portfolio if item['ticker'] == t_ticker), 0)
                    
                    if order_action == "BUY":
                        residual_cash = summary['cash'] - op_value
                        if op_value > summary['cash']:
                            can_execute = False
                            st.error(f"❌ Liquidità insufficiente! Servono €{op_value:,.2f}, ma hai solo €{summary['cash']:,.2f} disponibili.")
                        else:
                            st.info(f"""
                            **📊 Preventivo Ordine di Acquisto:**
                            * **Titolo:** {label_ticker}
                            * **Prezzo Unitario Attuale:** €{c_price:.2f}
                            * **Quantità:** {t_shares} azioni
                            * **💵 Controvalore Totale:** **€{op_value:,.2f}**
                            * **Liquidità Residua Stimata:** €{residual_cash:,.2f}
                            """)
                    else: # SELL
                        if held_shares < t_shares:
                            can_execute = False
                            st.error(f"❌ Azioni insufficienti! Possiedi {held_shares} azioni di {t_ticker}, non puoi venderne {t_shares}.")
                        else:
                            st.info(f"""
                            **📊 Preventivo Ordine di Vendita:**
                            * **Titolo:** {label_ticker}
                            * **Prezzo Unitario Attuale:** €{c_price:.2f}
                            * **Quantità da Vendere:** {t_shares} azioni (su {held_shares} possedute)
                            * **💵 Incasso Totale Stimato:** **€{op_value:,.2f}**
                            """)
                            
                    if can_execute:
                        st.markdown(f"**Vuoi procedere con l'operazione?**")
                        col_confirm, col_cancel = st.columns(2)
                        with col_confirm:
                            if st.button(f"✅ Conferma {order_action}", type="primary", key="btn_confirm_trade"):
                                execute_trade(t_ticker, order_action, t_shares, c_price)
                                st.success(f"Operazione {order_action} eseguita con successo per {t_shares} azioni di {t_ticker} a €{c_price:.2f} (Totale: €{op_value:,.2f})!")
                                st.rerun()
                        with col_cancel:
                            if st.button("❌ Annulla", key="btn_cancel_trade"):
                                st.rerun()
            except Exception as e:
                st.error(f"Errore nel calcolo del preventivo: {e}")

    st.markdown("---")
    
    # STORICO TRANSAZIONI
    st.subheader("Storico Transazioni")
    if trades:
        df_trades = pd.DataFrame(trades).sort_values(by=['id'], ascending=True)
        df_trades['controvalore_num'] = df_trades['shares'] * df_trades['price']
        df_trades['controvalore'] = df_trades['controvalore_num'].apply(lambda x: f"€{x:,.2f}")
        df_trades['price_fmt'] = df_trades['price'].apply(lambda x: f"€{x:.2f}")
        df_trades['pl_fmt'] = df_trades['profit_loss'].apply(lambda x: f"€{x:+,.2f}" if pd.notnull(x) and x != 0 else ("€0.00" if x == 0 else "-"))
        
        df_display = df_trades[['id', 'ticker', 'type', 'date', 'shares', 'price_fmt', 'controvalore', 'signal', 'pl_fmt']]
        df_display.columns = ['ID', 'Ticker', 'Tipo', 'Data', 'Azioni', 'Prezzo Unitario', 'Controvalore Totale', 'Segnale AI', 'Profitti/Perdite']
        st.dataframe(df_display, width="stretch", hide_index=True)
        
        st.metric("Profitti/Perdite Realizzati (Totale)", f"€{total_realized:+,.2f}")
    else:
        st.info("Nessuna operazione registrata.")

# ---------------------------------------------------------
# PAGE 5: 🤖 AI Autotrading
# ---------------------------------------------------------
elif page == "🤖 AI Autotrading":
    st.title("🤖 Agente Autonomo di Trading (AI Autotrading)")
    st.markdown("L'agente IA monitora autonomamente il mercato, esegue acquisti basati su segnali di consenso ed effettua uscite tramite il Radar di Uscita AI.")

    account = get_agent_account()
    agent_portfolio = get_agent_portfolio()
    agent_trades = get_agent_trades()
    data_client = MarketDataClient()

    agent_port_val = 0.0
    agent_unrealized = 0.0
    agent_portfolio_rows = []

    agent_tickers = [p['ticker'] for p in agent_portfolio] if agent_portfolio else []
    batch_agent_dfs = data_client.get_batch_historical_prices(agent_tickers, period="5d") if agent_tickers else {}

    for p in agent_portfolio:
        t = p['ticker']
        sh = p['shares']
        avg_p = p['avg_purchase_price']
        
        try:
            df_curr = batch_agent_dfs.get(t, pd.DataFrame())
            if df_curr.empty:
                df_curr = data_client.get_historical_prices(t, period="5d")
            curr_p = df_curr['Close'].iloc[-1] if not df_curr.empty else avg_p
        except Exception:
            curr_p = avg_p
            
        val = sh * curr_p
        unrealized = (curr_p - avg_p) * sh
        unrealized_pct = ((curr_p - avg_p) / avg_p) if avg_p > 0 else 0.0
        
        agent_port_val += val
        agent_unrealized += unrealized
        
        c_name = TICKER_NAMES.get(t, '')
        display_ticker = f"{t} ({c_name})" if c_name else t
        buy_sig = p.get('buy_signal')
        sig_fmt = f"{buy_sig:+.2f}" if buy_sig is not None else "-"
        
        agent_portfolio_rows.append({
            'ID': p.get('id', '-'),
            'Ticker': display_ticker,
            'Azioni': sh,
            'Prezzo di Carico': f"€{avg_p:.2f}",
            'Prezzo Attuale': f"€{curr_p:.2f}",
            'Controvalore': f"€{val:,.2f}",
            'P&L Non Realizzato': f"€{unrealized:+,.2f} ({unrealized_pct:+.1%})",
            'Segnale Acquisto AI': sig_fmt
        })

    agent_equity = account['cash'] + agent_port_val
    agent_pl = agent_equity - account['budget']
    agent_pl_pct = (agent_pl / account['budget']) if account['budget'] > 0 else 0.0
    agent_pl_color = "normal"

    bcol1, bcol2, bcol3, bcol4 = st.columns(4)
    bcol1.metric("💼 Budget Iniziale Assegnato", f"€{account['budget']:,.2f}", help="Capitale virtuale di partenza allocato all'agente autonomo.")
    bcol2.metric("💵 Liquidità (Cash)", f"€{account['cash']:,.2f}", help="Cash non investito disponibile per nuove posizioni.")
    bcol3.metric("📊 Valore Totale (Equity)", f"€{agent_equity:,.2f}", help="Patrimonio complessivo attuale (Liquidità + Controvalore Titoli).")
    bcol4.metric("🎯 Guadagno/Perdita Totale", f"€{agent_pl:+,.2f}", delta=f"{agent_pl_pct:+.2%}", delta_color=agent_pl_color, help="Rendimento complessivo realizzato e non realizzato rispetto al budget di partenza. I valori negativi appaiono in rosso, i positivi in verde.")

    with st.expander("⚙️ Configura Budget Agente"):
        with st.form("set_budget_form"):
            new_budget = st.number_input("Nuovo Budget Autotrading (€)", min_value=1000.0, max_value=1000000.0, value=account['budget'], step=5000.0)
            if st.form_submit_button("Aggiorna Budget"):
                set_agent_budget(new_budget)
                st.success("Budget aggiornato con successo!")
                st.rerun()

    # --- SORGENTE SEGNALI E AVVIO CICLO ---
    st.markdown("### 🎯 Esecuzione Ciclo di Trading IA")
    db_signals = get_latest_signals()
    
    col_mode, col_exec = st.columns([2, 1])
    with col_mode:
        trading_source = st.radio(
            "Seleziona su quali titoli operare:",
            [
                f"📥 Segnali memorizzati nel Database dallo Screener ({len(db_signals)} titoli disponibili)",
                "📋 Titoli presenti nella tua Lista Titoli (Watchlist)",
                "🇮🇹 Scansione Rapida Mercato Milano",
                "🇺🇸 Scansione Rapida Mercato New York",
                "🇫🇷 Scansione Rapida Mercato Parigi",
                "🇩🇪 Scansione Rapida Mercato Francoforte"
            ],
            key="trading_source_choice"
        )
    with col_exec:
        st.write("")
        st.write("")
        btn_start_trade = st.button("🚀 Esegui Ciclo di Trading", type="primary", use_container_width=True)

    if btn_start_trade:
        with st.spinner("L'agente IA sta elaborando i segnali, valutando il rischio e gestendo il portafoglio..."):
            import importlib
            import agents.autotrading_agent
            importlib.reload(agents.autotrading_agent)
            from agents.autotrading_agent import AutotradingAgent
            
            auto_agent = AutotradingAgent()
            
            if "Segnali memorizzati" in trading_source:
                if not db_signals:
                    st.warning("⚠️ Nessun segnale presente nel database. Vai prima su '🔎 Screener IA' ed esegui uno screening, oppure seleziona un'altra modalità qui sopra.")
                    cycle_res = None
                else:
                    cycle_res = auto_agent.run_cycle(db_signals)
            elif "Lista Titoli" in trading_source:
                wl_items = get_watchlist()
                wl_tickers = [w['ticker'] for w in wl_items]
                if not wl_tickers:
                    st.warning("⚠️ La tua Lista Titoli è vuota. Aggiungi prima dei titoli nella pagina '📋 Lista Titoli'.")
                    cycle_res = None
                else:
                    cycle_res = auto_agent.run_step(wl_tickers)
            elif "Milano" in trading_source:
                cycle_res = auto_agent.run_step(market_lists['Milano'][:15])
            elif "New York" in trading_source:
                cycle_res = auto_agent.run_step(market_lists['New York'][:15])
            elif "Parigi" in trading_source:
                cycle_res = auto_agent.run_step(market_lists['Parigi'][:15])
            else: # Francoforte
                cycle_res = auto_agent.run_step(market_lists['Francoforte'][:15])
                
            if cycle_res:
                st.session_state['last_auto_res'] = cycle_res
                st.rerun()

    if 'last_auto_res' in st.session_state and st.session_state['last_auto_res']:
        last_res = st.session_state['last_auto_res']
        acts = last_res.get('actions', [])
        d_logs = last_res.get('decision_logs', [])
        
        st.markdown("#### 📢 Esito Ultimo Ciclo Eseguito")
        if acts:
            for act in acts:
                st.success(act)
        else:
            st.info(f"ℹ️ {last_res.get('message', 'Nessun ordine inviato a mercato nel ciclo corrente.')}")
            
        if d_logs:
            with st.expander("🔍 Dettaglio Motivazioni & Log Decisionale Agente", expanded=False):
                for l in d_logs:
                    st.markdown(f"- {l}")

    col_ap, col_at = st.columns(2)
    with col_ap:
        st.subheader("💼 Portafoglio Agente IA")
        if agent_portfolio_rows:
            df_ap = pd.DataFrame(agent_portfolio_rows)
            st.dataframe(df_ap, width="stretch", hide_index=True)
        else:
            st.info("L'agente non possiede titoli al momento.")

    with col_at:
        st.subheader("📜 Storico Operazioni Agente")
        if agent_trades:
            df_at = pd.DataFrame(agent_trades).sort_values(by=['id'], ascending=True)
            df_at['Prezzo Unitario'] = df_at['price'].apply(lambda x: f"€{x:.2f}" if x > 0 else "-")
            df_at['Controvalore'] = (df_at['shares'] * df_at['price']).apply(lambda x: f"€{x:,.2f}" if x > 0 else "-")
            df_at['Commissione'] = df_at['commission'].apply(lambda x: f"€{x:.2f}")
            df_at['Profitti/Perdite'] = df_at['profit_loss'].apply(lambda x: f"€{x:+,.2f}" if pd.notnull(x) and x != 0 else ("€0.00" if x == 0 else "-"))
            df_at['Segnale AI'] = df_at['signal'].apply(lambda x: f"{x:+.2f}" if pd.notnull(x) else "-")
            
            df_at_disp = df_at[['id', 'ticker', 'type', 'date', 'shares', 'Prezzo Unitario', 'Controvalore', 'Commissione', 'Profitti/Perdite', 'Segnale AI']]
            df_at_disp.columns = ['ID', 'Ticker', 'Tipo Ordine', 'Data & Ora', 'Azioni', 'Prezzo Unitario', 'Controvalore Totale', 'Commissione', 'Profitti / Perdite', 'Segnale AI']
            st.dataframe(df_at_disp, width="stretch", hide_index=True)
        else:
            st.info("Nessuna operazione registrata dall'agente.")

# ---------------------------------------------------------
# PAGE 6: 🌐 Guida & Trova Ticker
# ---------------------------------------------------------
elif page == "🌐 Guida & Trova Ticker":
    st.title("🌐 Guida alle Borse & Ricerca Ticker")
    st.markdown("Questa sezione ti aiuta a trovare la corretta formattazione dei ticker per qualsiasi borsa mondiale e a verificare in tempo reale se un titolo è supportato dall'app.")

    tab_isin, tab_verifier, tab_guide = st.tabs(["🆔 Ricerca per Codice ISIN", "🔍 Verificatore Ticker Live", "📖 Legenda Borse & Suffissi"])

    with tab_isin:
        st.subheader("🆔 Ricerca e Conversione da Codice ISIN a Ticker")
        st.markdown("Inserisci il codice **ISIN** internazionale (12 caratteri alfanumerici) per individuare automaticamente il Ticker corrispondente su Yahoo Finance, vederne i dettagli e aggiungerlo alla tua Lista o analizzarlo.")

        is_col1, is_col2 = st.columns([2, 1])
        with is_col1:
            input_isin = st.text_input("Codice ISIN (es. IT0003128367, US0378331005, FR0000121014, NL0010273215):", key="isin_tab_input").strip().upper()
        with is_col2:
            st.write("")
            st.write("")
            btn_search_isin = st.button("🔎 Risolvi ISIN", key="btn_isin_tab_submit", type="primary")

        if input_isin and (btn_search_isin or st.session_state.get('searched_isin_tab') == input_isin):
            st.session_state['searched_isin_tab'] = input_isin
            with st.spinner(f"Interrogazione server per ISIN `{input_isin}`..."):
                found_quotes = search_by_isin_or_keyword(input_isin)

            if found_quotes:
                st.success(f"✅ Trovata/e **{len(found_quotes)}** quotazione/i per l'ISIN `{input_isin}`:")
                for q in found_quotes:
                    tkr = q['ticker']
                    q_name = q.get('name', tkr)
                    q_exch = q.get('exchange', 'Borsa')
                    q_type = q.get('quoteType', 'Azione')

                    with st.expander(f"📍 **{tkr}** — {q_name} (Borsa: {q_exch} | {q_type})", expanded=True):
                        # Recupero info live veloci
                        try:
                            import yfinance as yf
                            stk = yf.Ticker(tkr)
                            stk_inf = stk.info or {}
                            stk_hist = stk.history(period="5d")
                            price_val = stk_hist['Close'].iloc[-1] if not stk_hist.empty else stk_inf.get('regularMarketPrice', 0.0)
                            curr_val = stk_inf.get('currency', 'EUR/USD')
                            sect_val = stk_inf.get('sector', 'N/D')
                            
                            st.markdown(f"""
                            * **Nome Ufficiale:** {q_name}
                            * **Ticker Yahoo Finance:** `{tkr}`
                            * **Borsa di Negoziazione:** {q_exch}
                            * **Settore:** {sect_val}
                            * **Ultimo Prezzo:** **{curr_val} {price_val:.2f}**
                            """)
                        except Exception:
                            st.markdown(f"* **Ticker:** `{tkr}` | **Borsa:** {q_exch}")

                        act_col1, act_col2 = st.columns(2)
                        with act_col1:
                            # Form salvataggio in Lista Titoli
                            with st.form(f"isin_save_form_{tkr}"):
                                lbl_in = st.text_input("Etichetta:", value=f"ISIN: {input_isin}", key=f"lbl_isin_{tkr}")
                                not_in = st.text_area("Note:", value=f"Aggiunto tramite ricerca ISIN {input_isin}", key=f"not_isin_{tkr}", height=80)
                                if st.form_submit_button("💾 Salva nella Lista Titoli", type="primary"):
                                    add_watchlist_item(tkr, lbl_in, not_in)
                                    st.success(f"✅ `{tkr}` aggiunto alla tua Lista Titoli!")
                        with act_col2:
                            st.info("Vuoi analizzare questo titolo con l'Intelligenza Artificiale?")
                            if st.button(f"🚀 Avvia Analisi Live per {tkr}", key=f"btn_isin_go_live_{tkr}"):
                                st.session_state['ad_hoc_search'] = tkr
                                st.info(f"Vai alla scheda **📡 Live Analysis** per visualizzare i grafici e il report IA di {tkr}!")
            else:
                st.error(f"❌ Nessun titolo trovato per l'ISIN `{input_isin}` su Yahoo Finance.")
                st.markdown("""
                **Suggerimenti:**
                * Verifica che il codice ISIN sia corretto e composto da 12 caratteri (es. `IT0003128367`).
                * Alcune emissioni illiquide o mercati minori non sono indicizzati per ISIN su Yahoo Finance: in tal caso, cerca direttamente per nome o ticker nella scheda *Verificatore Ticker Live*.
                """)

    with tab_verifier:
        st.subheader("🔍 Verifica Compatibilità Ticker in Tempo Reale")
        st.markdown("Inserisci il ticker (o componilo scegliendo il mercato) per controllare se Yahoo Finance fornisce i dati e visualizzare subito le informazioni chiave dell'azienda.")

        vcol1, vcol2 = st.columns([2, 1])
        with vcol1:
            raw_input = st.text_input("Inserisci il simbolo del titolo (es. AAPL, ENEL, MC, SAP, ASML, SHEL):", key="val_ticker_input").upper().strip()
        with vcol2:
            suffix_choice = st.selectbox("Seleziona Mercato / Suffisso:", [
                "Nessuno (USA - NYSE/NASDAQ)",
                ".MI (Italia - Milano)",
                ".DE (Germania - Francoforte / XETRA)",
                ".PA (Francia - Parigi)",
                ".AS (Paesi Bassi - Amsterdam)",
                ".MC (Spagna - Madrid)",
                ".L (Regno Unito - Londra)",
                ".SW (Svizzera - Zurigo)",
                ".ST (Svezia - Stoccolma)",
                ".BR (Belgio - Bruxelles)",
                ".LS (Portogallo - Lisbona)",
                ".VI (Austria - Vienna)",
                ".TO (Canada - Toronto)",
                ".AX (Australia - Sydney)",
                ".HK (Hong Kong)"
            ], key="val_suffix_choice")

        # Costruzione ticker completo
        suffix_code = ""
        if "(" in suffix_choice and not suffix_choice.startswith("Nessuno"):
            suffix_code = suffix_choice.split()[0].strip()

        # Se l'utente ha già messo il suffisso manualmente, non duplicarlo
        if raw_input:
            if "." in raw_input:
                final_test_ticker = raw_input
            else:
                final_test_ticker = raw_input + suffix_code
        else:
            final_test_ticker = ""

        if final_test_ticker:
            st.info(f"Ticker da verificare: **`{final_test_ticker}`**")

        if st.button("🚀 Verifica Ticker su Yahoo Finance", key="btn_run_val", type="primary"):
            if not final_test_ticker:
                st.warning("Inserisci prima un simbolo da verificare.")
            else:
                with st.spinner(f"Interrogazione server Yahoo Finance per `{final_test_ticker}`..."):
                    import yfinance as yf
                    try:
                        stock_obj = yf.Ticker(final_test_ticker)
                        info_dict = stock_obj.info or {}
                        hist_check = stock_obj.history(period="5d")
                        
                        has_data = not hist_check.empty and len(hist_check) > 0
                        short_name = info_dict.get("shortName") or info_dict.get("longName") or TICKER_NAMES.get(final_test_ticker, "")
                        
                        if has_data or short_name:
                            curr_p = hist_check['Close'].iloc[-1] if not hist_check.empty else info_dict.get('regularMarketPrice', 0.0)
                            curr_currency = info_dict.get('currency', 'EUR/USD')
                            sector_val = info_dict.get('sector', 'N/D')
                            industry_val = info_dict.get('industry', 'N/D')
                            exchange_val = info_dict.get('exchange', 'N/D')
                            mkt_cap = info_dict.get('marketCap')
                            mkt_cap_str = f"€{mkt_cap:,.0f}" if mkt_cap else "N/D"

                            st.success(f"✅ **Titolo Trovato e Pienamente Compatibile!**")
                            
                            st.markdown(f"""
                            <div style="background-color: #1a2230; padding: 20px; border-radius: 12px; border: 1px solid #2d3748; margin-bottom: 15px;">
                                <h2 style="margin:0; color:#38bdf8;">{short_name} ({final_test_ticker})</h2>
                                <p style="color:gray; margin-top:4px;">Borsa: <b>{exchange_val}</b> | Valuta: <b>{curr_currency}</b></p>
                                <hr style="border-color: rgba(255,255,255,0.1); margin: 10px 0;">
                                <div style="display:flex; justify-content:space-between; flex-wrap:wrap; gap:10px;">
                                    <div><b>Ultimo Prezzo:</b> <span style="font-size:1.3rem; font-weight:bold; color:#4ade80;">{curr_currency} {curr_p:.2f}</span></div>
                                    <div><b>Settore:</b> {sector_val}</div>
                                    <div><b>Industria:</b> {industry_val}</div>
                                </div>
                            </div>
                            """, unsafe_allow_html=True)

                            # Salvataggio veloce in Watchlist
                            st.markdown("#### ➕ Aggiungi direttamente alla tua Lista Titoli")
                            with st.form("quick_add_wl_form"):
                                q_label = st.text_input("Etichetta (opzionale):", value=f"{sector_val}", key="quick_add_label")
                                q_note = st.text_area("Note iniziali:", value=f"Aggiunto dalla guida. Prezzo rif: {curr_p:.2f} {curr_currency}", key="quick_add_note")
                                if st.form_submit_button("💾 Salva nella Lista Titoli", type="primary"):
                                    add_watchlist_item(final_test_ticker, q_label, q_note)
                                    st.success(f"✅ `{final_test_ticker}` inserito con successo nella tua Lista Titoli!")
                        else:
                            st.error(f"❌ **Titolo `{final_test_ticker}` non trovato su Yahoo Finance.**")
                            st.markdown("""
                            **Possibili cause:**
                            1. **Suffisso mancante o errato:** Ad esempio, i titoli italiani necessitano di `.MI` (es. `ENEL.MI`), quelli francesi di `.PA` (es. `MC.PA`).
                            2. **Mercato non coperto:** Alcuni mercati minori (come il *Nasdaq First North Baltic* di Tallinn/Riga/Vilnius) o mercati OTC non quotati non sono inclusi nel feed gratuito di Yahoo Finance.
                            3. **Verifica su Yahoo:** Cerca l'azienda direttamente su [finance.yahoo.com](https://finance.yahoo.com) per scoprire il codice esatto.
                            """)
                    except Exception as err:
                        st.error(f"Errore durante la verifica: {err}")

    with tab_guide:
        st.subheader("📖 Legenda Completa delle Borse Mondiali & Suffissi")
        st.markdown("""
        L'applicazione si collega all'infrastruttura di **Yahoo Finance**, il principale provider mondiale di dati finanziari.
        Per i titoli **non quotati a Wall Street**, è necessario specificare il suffisso del rispettivo mercato.
        """)

        guide_data = [
            {"Bandiera": "🇺🇸", "Paese / Mercato": "Stati Uniti (NYSE, NASDAQ, AMEX)", "Suffisso": "*Nessuno*", "Esempi Pratici": "AAPL, MSFT, NVDA, TSLA, AMZN, GOOGL"},
            {"Bandiera": "🇮🇹", "Paese / Mercato": "Italia (Borsa Italiana / Piazza Affari)", "Suffisso": "`.MI`", "Esempi Pratici": "ENEL.MI, ISP.MI, RACE.MI, LDO.MI, UCG.MI, ENI.MI"},
            {"Bandiera": "🇩🇪", "Paese / Mercato": "Germania (XETRA / Francoforte)", "Suffisso": "`.DE`", "Esempi Pratici": "SAP.DE, BMW.DE, MBG.DE, SIE.DE, ALV.DE, AIR.DE"},
            {"Bandiera": "🇫🇷", "Paese / Mercato": "Francia (Euronext Paris)", "Suffisso": "`.PA`", "Esempi Pratici": "MC.PA (LVMH), OR.PA (L'Oréal), TTE.PA (Total), SAN.PA"},
            {"Bandiera": "🇳🇱", "Paese / Mercato": "Paesi Bassi (Euronext Amsterdam)", "Suffisso": "`.AS`", "Esempi Pratici": "ASML.AS, INGA.AS, PRX.AS, AD.AS, HEIA.AS"},
            {"Bandiera": "🇪🇸", "Paese / Mercato": "Spagna (Bolsa de Madrid)", "Suffisso": "`.MC`", "Esempi Pratici": "SAN.MC (Santander), ITX.MC (Inditex), BBVA.MC, IBE.MC"},
            {"Bandiera": "🇬🇧", "Paese / Mercato": "Regno Unito (London Stock Exchange)", "Suffisso": "`.L`", "Esempi Pratici": "SHEL.L (Shell), AZN.L (AstraZeneca), BP.L, HSBA.L"},
            {"Bandiera": "🇨🇭", "Paese / Mercato": "Svizzera (SIX Swiss Exchange)", "Suffisso": "`.SW`", "Esempi Pratici": "NESN.SW (Nestlé), NOVN.SW (Novartis), ROG.SW (Roche)"},
            {"Bandiera": "🇸🇪", "Paese / Mercato": "Svezia (Nasdaq Stockholm)", "Suffisso": "`.ST`", "Esempi Pratici": "VOLV-B.ST (Volvo), ERIC-B.ST (Ericsson), SPOT"},
            {"Bandiera": "🇧🇪", "Paese / Mercato": "Belgio (Euronext Brussels)", "Suffisso": "`.BR`", "Esempi Pratici": "ABI.BR (Anheuser-Busch InBev), KBC.BR, UCB.BR"},
            {"Bandiera": "🇵🇹", "Paese / Mercato": "Portogallo (Euronext Lisbon)", "Suffisso": "`.LS`", "Esempi Pratici": "EDP.LS, GALP.LS, JMT.LS"},
            {"Bandiera": "🇦🇹", "Paese / Mercato": "Austria (Wiener Börse)", "Suffisso": "`.VI`", "Esempi Pratici": "EBS.VI (Erste Group), OMV.VI, VOE.VI"},
            {"Bandiera": "🇨🇦", "Paese / Mercato": "Canada (Toronto Stock Exchange)", "Suffisso": "`.TO`", "Esempi Pratici": "SHOP.TO (Shopify), RY.TO, TD.TO, CNR.TO"},
            {"Bandiera": "🇦🇺", "Paese / Mercato": "Australia (ASX Sydney)", "Suffisso": "`.AX`", "Esempi Pratici": "BHP.AX, CBA.AX, CSL.AX, NAB.AX"},
            {"Bandiera": "🇭🇰", "Paese / Mercato": "Hong Kong (HKEX)", "Suffisso": "`.HK`", "Esempi Pratici": "0700.HK (Tencent), 9988.HK (Alibaba HK), 0941.HK"}
        ]

        df_guide = pd.DataFrame(guide_data)
        st.dataframe(df_guide, width="stretch", hide_index=True)

        st.markdown("---")
        st.markdown("### ❓ Domande Frequenti sui Titoli")
        with st.expander("📌 Perché aziende come Saunum Group (SAUNA) o altre micro-cap non funzionano?"):
            st.markdown("""
            Aziende come **Saunum Group AS** sono quotate su listini multilaterali regionali (nel caso specifico il **Nasdaq First North Baltic** di Tallinn, Estonia).
            Yahoo Finance copre quasi tutte le borse regolamentate europee e globali (Milano, Parigi, Francoforte, Londra, Madrid, Amsterdam, Zurigo, Stoccolma, ecc.), ma **non indicizza i mercati minori baltici (Tallinn, Riga, Vilnius)**.
            Se un titolo non è presente su Yahoo Finance, l'app non può estrarne lo storico dei prezzi o i bilanci per gli agenti.
            """)

        with st.expander("📌 Come faccio a trovare il ticker esatto di un'azienda sconosciuta?"):
            st.markdown("""
            1. Vai su **[finance.yahoo.com](https://finance.yahoo.com)**.
            2. Digita il nome dell'azienda nella barra di ricerca in alto (es. *Ferrari*, *L'Oreal*, *LVMH*, *ASML*).
            3. Nel menu a tendina vedrai il codice con il suffisso (es. `RACE.MI`, `OR.PA`, `MC.PA`).
            4. Copia quel codice e usalo nella tua app per l'analisi!
            """)

