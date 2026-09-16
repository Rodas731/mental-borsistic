import sys

file_path = 'c:/Users/rgd73/OneDrive/Documenti/mental borsistic/app.py'

with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# keep up to line 640
lines = lines[:640]

tail = """                unrealized_pl = current_val - invested
                pl_pct = unrealized_pl / invested if invested > 0 else 0
                
                total_portfolio_value += current_val
                
                portfolio_data.append({
                    "Ticker": ticker,
                    "Azioni": shares,
                    "Segnale Acquisto": f"{p.get('buy_signal', 0.0):.2f}" if p.get('buy_signal') is not None else "N/A",
                    "Prezzo Carico": f"€{avg_price:.2f}",
                    "Prezzo Attuale": f"€{current_price:.2f}",
                    "Controvalore": f"€{current_val:.2f}",
                    "P&L Non Realizzato": f"€{unrealized_pl:.2f} ({pl_pct:.1%})"
                })
            
            st.dataframe(pd.DataFrame(portfolio_data), use_container_width=True)
            
        if account:
            total_equity = account['cash'] + total_portfolio_value
            st.metric("Valore Totale (Equity)", f"€{total_equity:.2f}", f"Rispetto al budget: €{total_equity - account['budget']:.2f}", delta_color="normal")
            
    st.markdown("---")
    st.subheader("📜 Storico e Performance (Commissioni 5€/Eseguito)")
    
    trades = get_agent_trades()
    if trades:
        df_trades = pd.DataFrame(trades)
        
        # Performance Mensile
        st.write("### 📅 Performance Realizzata Mensile")
        df_trades['Data_Ora'] = pd.to_datetime(df_trades['date'])
        df_trades['Mese'] = df_trades['Data_Ora'].dt.to_period('M')
        
        # Filtriamo solo le chiusure (SELL) per il calcolo del P&L realizzato, e i RESET li escludiamo
        sells = df_trades[df_trades['type'] == 'SELL']
        if not sells.empty:
            monthly_pl = sells.groupby('Mese')['profit_loss'].sum().reset_index()
            monthly_pl['Mese'] = monthly_pl['Mese'].astype(str)
            
            fig = go.Figure(data=[
                go.Bar(x=monthly_pl['Mese'], y=monthly_pl['profit_loss'], 
                       marker_color=['green' if val > 0 else 'red' for val in monthly_pl['profit_loss']])
            ])
            fig.update_layout(title="Profitti/Perdite per Mese", height=300, margin=dict(l=0, r=0, t=30, b=0))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Nessuna operazione chiusa per calcolare le performance.")
            
        st.write("### 🗂️ Lista Completa Transazioni")
        if 'signal' not in df_trades.columns:
            df_trades['signal'] = None
        df_display = df_trades[['id', 'ticker', 'type', 'date', 'shares', 'price', 'commission', 'signal', 'profit_loss']]
        df_display.columns = ['ID', 'Ticker', 'Tipo', 'Data', 'Azioni', 'Prezzo', 'Commissione', 'Segnale AI', 'P&L Realizzato']
        st.dataframe(df_display, use_container_width=True)
"""

lines.append(tail)

with open(file_path, 'w', encoding='utf-8') as f:
    f.writelines(lines)

print('app.py fixed!')
