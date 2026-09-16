# Manuale d'Uso: Motore di Intelligenza di Mercato

Benvenuto nella guida completa all'utilizzo del tuo **Motore di Intelligenza di Mercato (Market Intelligence Engine)**. Questo documento spiega il funzionamento delle singole Intelligenze Artificiali (Agenti di Ingresso e di Uscita), come collaborano per fornirti previsioni affidabili e decisioni ottimali di vendita, e come sfruttare al meglio tutte le funzionalità dell'applicazione.

---

## 1. Architettura del Sistema Multi-Agente

L'applicazione è basata su una solida architettura **Multi-Agente**. Invece di affidare l'analisi a un singolo algoritmo generalista, il sistema divide il lavoro tra esperti virtuali dedicati alla **Fase di Ingresso (Cosa e quando comprare)** e alla **Fase di Uscita (Quando vendere e proteggere il capitale)** per la gestione attiva e ponderata dei titoli in portafoglio.

```mermaid
graph TD
    subgraph Fase di Ingresso - Acquisto
        Data[(Dati Mercato & Bilanci)] --> A1[Price/Momentum Agent]
        Data --> A2[News Sentiment Agent]
        Data --> A3[SEC Fundamentals Agent]
        Data --> A4[Smart Money Agent]
        Data --> A5[Risk Analyst Agent]
        Data --> A6[Macro Analyst Agent]
        
        A1 & A2 & A3 & A4 --> FE{Signal Fusion Engine}
        A5 --> R[Livello di Rischio]
        A6 --> M[Moltiplicatore Macro S&P500]
        M --> FE
        FE --> VF[Verdetto Ingresso: Rialzista/Ribassista]
    end

    subgraph Fase di Uscita - Vendita (Portafoglio Attivo)
        Port[(Titoli in Portafoglio)] --> E1[Exit Technical Agent - ATR Trailing]
        Port --> E2[Exit Sentiment Agent - Decay Notizie]
        Port --> E3[Exit Fundamental Agent - Sopravvalutazione]
        Port --> E4[Exit Smart Money Agent - Insider Selling]
        Port --> E5[Exit Risk Agent - Spike Volatilità]
        
        E1 & E2 & E3 & E4 & E5 --> EFE{Exit Fusion Engine}
        EFE --> ES[Exit Score: 0.00 - 1.00]
        ES --> EA[Verdetto Uscita: Mantenere / Vendita 50% / Vendita 100%]
    end

    VF --> UI((Dashboard App))
    EA --> UI
```

---

## 2. Come Lavorano gli Agenti AI

### A. Squadra Agenti di Ingresso (Acquisto)

Ogni agente di ingresso analizza i dati da una specifica prospettiva e restituisce due valori fondamentali:
1. **Segnale:** Da `-1.0` (Forte Ribasso) a `+1.0` (Forte Rialzo).
2. **Confidenza:** Da `0%` a `100%`, indica il grado di certezza statistica dell'analisi.

* 📉 **Price/Momentum Agent (Analisi Tecnica):** Studia l'azione storica del prezzo, le medie mobili (SMA 20 e SMA 50) e l'indice RSI (Relative Strength Index) per rilevare fasi di ipercomprato o ipervenduto.
* 📰 **News Sentiment Agent (Analisi del Testo & NLP):** Elabora le notizie finanziarie recenti tramite Natural Language Processing, analizzando l'umore generale dei media e l'impatto sul titolo. Include il link diretto alle notizie analizzate.
* 🏛️ **SEC Fundamentals Agent (Salute Aziendale & Bilanci):** Esamina i dati ufficiali di bilancio (crescita utili EPS, ricavi, indebitamento, metriche contabili).
* 🐋 **Smart Money Agent (Flussi Istituzionali):** Monitora le compravendite eseguite dai dirigenti aziendali (*Insider Trading*) e i flussi di capitale dei grandi fondi d'investimento.
* ⚠️ **Risk Analyst Agent (Gestione del Rischio):** Calcola la volatilità annualizzata e il Massimo Drawdown storico, assegnando un livello di rischio (`BASSO`, `MEDIO`, `ALTO`, `ALTISSIMO`).
* 🌐 **Macro Analyst Agent (Sentinella di Mercato):** Monitora il trend dell'indice S&P 500 per applicare un moltiplicatore protettivo del capitale in contesti macroeconomici avversi.

---

### B. Squadra Agenti di Uscita (Vendita - Exit Intelligence)

Per i titoli monitorati e presenti in portafoglio (solitamente tra 10 e 20 posizioni), una squadra di 5 Agenti AI specializzati presidia costantemente i rischi per individuare il momento ottimale di monetizzazione o de-risking:

1. 🛡️ **Exit Technical Agent (ATR Trailing Stop & P&L):**
   * Calcola un **Trailing Stop ATR dinamico** ($2.5 \times \text{ATR}$ dal picco massimo toccato dall'ingresso).
   * Monitora l'ipercomprato estremo sull'RSI ($\ge 75$), l'inversione sotto le medie mobili e gli obiettivi di Stop Loss o Take Profit.
2. 📰 **Exit Sentiment Agent (Sentiment Decay):**
   * Rileva il deterioramento delle notizie e picchi di rassegna stampa negativa.
   * Suggerisce una vendita preventiva prima che il pessimismo si rifletta sui prezzi.
3. 📊 **Exit Fundamental Agent (Sopravvalutazione & Bilancio):**
   * Monitora multipli di borsa eccessivi (P/E $> 45$, PEG $> 2.5$) e contrazioni della crescita degli utili per azione (EPS negativo).
4. 🐋 **Exit Smart Money Agent (Insider Selling):**
   * Rileva quando i manager interni iniziano a vendere massicciamente le proprie azioni o quando i grandi fondi riducono l'esposizione.
5. ⚠️ **Exit Risk Agent (Spike di Volatilità & Drawdown):**
   * Segnala aumenti improvvisi di volatilità ($>40\%$) o avvicinamento ai limiti di perdita tollerabili.

---

## 3. Motori di Fusione: `SignalFusionEngine` ed `ExitFusionEngine`

### A. Signal Fusion Engine (Verdetto Acquisto)
Calcola una **media ponderata basata sulla confidenza** dei segnali degli agenti di acquisto:
* 🟢 **Segnale $\ge +0.20$ (`RIALZISTA`):** Consenso positivo; potenziale opportunità di acquisto.
* ⚪ **Segnale tra $-0.20$ e $+0.20$ (`NEUTRALE`):** Segnali contrastanti o assenza di direzione netta.
* 🔴 **Segnale $\le -0.20$ (`RIBASSISTA`):** Consenso negativo; acquisto sconsigliato.

### B. Exit Fusion Engine (Exit Score di Vendita)
Sintetizza i segnali dei 5 agenti di uscita generando un **Exit Score da 0.00 a 1.00 (0% - 100%)**:
* 🟢 **Exit Score < 35% (`MANTIENI`):** La posizione è sana e in trend; non viene segnalata alcuna allerta.
* 🟡 **Exit Score 35% - 65% (`VENDITA PARZIALE 50%`):** Allerta di alleggerimento/take profit per incassare guadagni o ridurre l'esposizione al rischio.
* 🔴 **Exit Score $\ge$ 65% (`VENDITA TOTALE 100%`):** Allerta critica di chiusura totale per Stop Loss, rottura del Trailing Stop o forti vendite istituzionali.

---

## 4. Guida alle Sezioni dell'Applicazione

### 📡 1. Live Analysis
* **Ricerca Ad-Hoc & Liste Complete:** Selezione dei titoli tramite ricerca libera o menu a tendina divisi per mercato:
  * 🇮🇹 **Milano:** Oltre 40 titoli del FTSE MIB e Mid Cap.
  * 🇺🇸 **New York:** Oltre 80 titoli dell'S&P 500 e Nasdaq.
  * 🇫🇷 **Parigi:** Oltre 70 titoli del CAC 40 e SBF 120.
  * 🇩🇪 **Francoforte:** Oltre 70 titoli del DAX 40 e MDAX.
* **Grafico Interattivo:** Candele Giapponesi, Linea e Area con pulsanti di zoom a 1 Settimana, 1 Mese, 3 Mesi e Tutto (6 Mesi).
* **🔮 Verdetto Finale:** Visualizzazione del Segnale Numerico colorato, Previsione qualitativa, Confidenza ed expander esplicativo.
* **🤖 Report dei 5 Agenti:** Schede espandibili con metriche tecniche, RSI, sentiment NLP, bilanci SEC, insider flow e risk score.
* **🚨 Alert di Uscita AI (Cornice Rossa):** Riquadro prioritario bordato di rosso che si attiva se le IA di vendita determinano un `Exit Score ≥ 35%`, evidenziando la raccomandazione e gli agenti specifici che hanno sollevato l'allerta.
* **🚀 Scansione Opportunità Massiva:** Analisi in tempo reale della piazza selezionata con la sezione **🏆 Top 5 Titoli con Score Maggiore** sempre in evidenza.

---

### 🔎 2. Screener IA
* **Filtro Multi-Mercato:** Imposta una soglia minima di segnale AI (es. $+0.20$) per trovare automaticamente le migliori opportunità.
* **🏆 Top 5 in Evidenza:** Presentazione dei primi 5 titoli con il punteggio più alto in schede ad alta leggibilità.
* **📋 Tabella Completa:** Elenco tabellare di tutti i titoli che superano i criteri impostati, ordinati per punteggio decrescente.

---

### 💼 3. Paper Trading (Simulatore di Portafoglio)
* **🏦 Quadro Finanziario & Risorse Iniziali:** Banner sintetico con 5 metriche essenziali:
  1. 💰 **Capitale Iniziale:** Somma totale dei depositi e delle risorse economiche caricate sul conto (es. €100,000.00).
  2. 📅 **Data Inizio:** Data del primo versamento o transazione registrata.
  3. 💵 **Liquidità (Cash):** Capitale in contanti non investito utilizzabile per nuovi acquisti.
  4. 📊 **Valore Totale (Equity):** Valore complessivo attuale del conto (Liquidità + Controvalore Titoli).
  5. 🎯 **Guadagno/Perdita Totale (vs Inizio):** Rendimento complessivo netto rispetto alla condizione di partenza (in Euro e in percentuale con indicatore cromatico di performance).
* **📁 Gestione Depositi:** Tabella con la cronologia di tutti i versamenti (ID, Data, Importo, Origine) e modulo per registrare ulteriori versamenti di capitale.
* **📊 Portafoglio Attivo:** Visualizzazione delle posizioni aperte, prezzo medio di carico, quotazione attuale, **Controvalore Totale (€)** e P&L non realizzato.
* **➕ Nuova Transazione Virtuale:** Inserimento ordini `BUY` o `SELL` con **controllo preventivo del cash disponibile** (impedisce acquisti superiori alla liquidità disponibile).
* **📜 Storico Transazioni:** Tabella dettagliata in italiano con Prezzo Unitario, Controvalore Totale, Segnale AI e Profitti/Perdite realizzati.

---

### 🤖 4. AI Autotrading (Trading Autonomo)
* **Metriche di Monitoraggio Continuo:**
  1. 💼 **Budget Iniziale Assegnato:** Il capitale virtuale di partenza allocato all'agente.
  2. 💵 **Liquidità (Cash):** Liquidità libera a disposizione.
  3. 📊 **Valore Totale (Equity):** Patrimonio complessivo dell'agente (Liquidità + Controvalore titoli posseduti).
  4. 🎯 **Guadagno/Perdita Totale (vs Inizio):** Rendimento complessivo netto in Euro e in percentuale rispetto al budget di partenza.
* **Gestione Budget Agente:** Possibilità di aggiornare in qualunque momento il budget allocato.
* **Ciclo Autonomo con 1-Click:** Premendo *"🚀 Avvia Ciclo Autonomo di Trading"* l'agente esegue la scansione, aggiorna i segnali ed effettua compravendite nel rispetto delle regole di money management (max 8 posizioni, riserva di liquidità al 15%, acquisti proporzionali al segnale, Dollar Cost Averaging).
* **Esecuzione Uscite Intelligenti:** L'agente autonomo applica l'**Exit Intelligence Engine**: se un titolo in portafoglio raggiunge un Exit Score critico (come nel caso di forti vendite insider o aumento di volatilità), l'agente esegue in automatico la vendita parziale (50%) o totale (100%).
* **Tabelle in Italiano:** Portafoglio e Storico Operazioni completamente formattati in Euro con dettagli su commissioni, prezzi e profitti.

---

## 5. Buone Pratiche Operative

1. **Usa la Scansione Live o lo Screener** per identificare i titoli con segnale $\ge +0.35$ e confidenza elevata.
2. **Verifica il Profilo di Rischio:** Preferisci titoli con profilo `BASSO` o `MEDIO`; riduci l'esposizione sui titoli ad `ALTO` rischio ed evita titoli con rischio `ALTISSIMO`.
3. **Consulta il Radar di Uscita AI:** Per i titoli in portafoglio, verifica regolarmente la presenza di alert di uscita per monetizzare i guadagni ed evitare inversioni di trend improvvise.
4. **Monitora il Quadro Finanziario:** Tieni traccia dell'Equity complessiva e mantieni sempre un cuscinetto di liquidità disponibile per sfruttare nuove opportunità di mercato.
