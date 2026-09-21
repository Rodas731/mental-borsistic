import sqlite3
import json
import os
import hashlib
from datetime import datetime
from loguru import logger

DB_PATH = os.path.join(os.path.dirname(__file__), "market_data.db")

def get_connection():
    return sqlite3.connect(DB_PATH)

def init_db():
    """Initializes the SQLite database with required tables."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Table to store daily agent signals for the screener
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                date TEXT NOT NULL,
                prediction TEXT,
                final_signal REAL,
                confidence REAL,
                risk_level TEXT,
                raw_json TEXT
            )
        ''')
        
        # Tentativo di aggiungere la colonna in caso di database esistente
        try:
            cursor.execute("ALTER TABLE signals ADD COLUMN risk_level TEXT")
        except sqlite3.OperationalError:
            pass # Colonna già esistente
            
        try:
            cursor.execute("ALTER TABLE agent_portfolio ADD COLUMN buy_signal REAL")
        except sqlite3.OperationalError:
            pass
            
        try:
            cursor.execute("ALTER TABLE agent_trades ADD COLUMN signal REAL")
        except sqlite3.OperationalError:
            pass
        
        try:
            cursor.execute("ALTER TABLE portfolio ADD COLUMN buy_signal REAL")
        except sqlite3.OperationalError:
            pass
            
        try:
            cursor.execute("ALTER TABLE trades ADD COLUMN signal REAL")
        except sqlite3.OperationalError:
            pass
            
        # Table to store the current paper trading portfolio
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS portfolio (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL UNIQUE,
                shares INTEGER NOT NULL,
                avg_purchase_price REAL NOT NULL,
                buy_signal REAL
            )
        ''')
        
        # Table to store historical virtual trades
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                type TEXT NOT NULL, -- 'BUY' or 'SELL'
                date TEXT NOT NULL,
                shares INTEGER NOT NULL,
                price REAL NOT NULL,
                profit_loss REAL, -- NULL for BUY, calculated for SELL
                signal REAL
            )
        ''')
        
        # Table to store paper trading deposits & initial balance
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS paper_deposits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                amount REAL NOT NULL,
                note TEXT
            )
        ''')
        
        cursor.execute("SELECT COUNT(*) FROM paper_deposits")
        if cursor.fetchone()[0] == 0:
            cursor.execute("SELECT MIN(date) FROM trades")
            row = cursor.fetchone()
            start_date = row[0] if (row and row[0]) else datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute("INSERT INTO paper_deposits (date, amount, note) VALUES (?, ?, ?)",
                           (start_date, 100000.0, "Deposito Iniziale di Capitale"))

        # Table to store authenticated users
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        ''')
        
        # Initialize default user Rodas73 if not present or update credentials
        init_default_user(cursor)

        init_agent_db(cursor)

        # Tabella per la watchlist personalizzata dell'utente
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS watchlist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                label TEXT,
                note TEXT,
                created_at TEXT NOT NULL
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info("Database initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")

def save_signal(ticker: str, prediction_or_signal=None, final_signal: float = None, confidence: float = 0.0, risk_level: str = "SCONOSCIUTO", raw_data: dict = None, prediction: str = None):
    """Saves a new signal from the screener or live analysis."""
    try:
        if isinstance(prediction_or_signal, (int, float)):
            sig = float(prediction_or_signal)
            conf = float(final_signal) if (final_signal is not None and isinstance(final_signal, (int, float))) else 0.0
            pred = str(confidence) if isinstance(confidence, str) else (prediction or "NEUTRALE")
        else:
            pred = str(prediction_or_signal) if prediction_or_signal else (prediction or "NEUTRALE")
            sig = float(final_signal) if (final_signal is not None and isinstance(final_signal, (int, float))) else 0.0
            conf = float(confidence) if (confidence is not None and isinstance(confidence, (int, float))) else 0.0
            
        risk = str(risk_level) if risk_level else "SCONOSCIUTO"
        raw = raw_data if isinstance(raw_data, dict) else {}
        
        conn = get_connection()
        cursor = conn.cursor()
        date_str = datetime.now().strftime("%Y-%m-%d")
        
        # We keep only one record per ticker per day.
        cursor.execute("DELETE FROM signals WHERE ticker=? AND date=?", (ticker, date_str))
        
        cursor.execute('''
            INSERT INTO signals (ticker, date, prediction, final_signal, confidence, risk_level, raw_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (ticker, date_str, pred, sig, conf, risk, json.dumps(raw)))
        
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Error in save_signal for {ticker}: {e}")

def save_signals_batch(signals_list: list):
    """Saves a batch of signals in a single fast SQLite transaction."""
    if not signals_list:
        return
    try:
        conn = get_connection()
        cursor = conn.cursor()
        date_str = datetime.now().strftime("%Y-%m-%d")
        
        for s in signals_list:
            ticker = s.get('ticker')
            if not ticker:
                continue
            pred = str(s.get('prediction', 'NEUTRALE'))
            sig = float(s.get('final_signal', 0.0))
            conf = float(s.get('confidence', 0.0))
            risk = str(s.get('risk_level', 'SCONOSCIUTO'))
            raw = s.get('raw_data', {})
            
            cursor.execute("DELETE FROM signals WHERE ticker=? AND date=?", (ticker, date_str))
            cursor.execute('''
                INSERT INTO signals (ticker, date, prediction, final_signal, confidence, risk_level, raw_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (ticker, date_str, pred, sig, conf, risk, json.dumps(raw)))
            
        conn.commit()
        conn.close()
        logger.info(f"Successfully saved {len(signals_list)} signals in batch.")
    except Exception as e:
        logger.error(f"Error in save_signals_batch: {e}")


def get_latest_signals():
    """Retrieves the latest signals for the Screener UI."""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get the most recent date in the DB
    cursor.execute("SELECT MAX(date) as max_date FROM signals")
    row = cursor.fetchone()
    if not row or not row['max_date']:
        return []
        
    latest_date = row['max_date']
    
    cursor.execute("SELECT * FROM signals WHERE date = ? ORDER BY final_signal DESC", (latest_date,))
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]

def execute_trade(ticker: str, trade_type: str, shares: int, current_price: float, signal: float = None):
    """Executes a virtual trade and updates portfolio and trades history."""
    conn = get_connection()
    cursor = conn.cursor()
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    if trade_type == 'BUY':
        # Insert trade record
        cursor.execute('''
            INSERT INTO trades (ticker, type, date, shares, price, profit_loss, signal)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (ticker, 'BUY', date_str, shares, current_price, 0.0, signal))
        
        # Update Portfolio
        cursor.execute("SELECT shares, avg_purchase_price FROM portfolio WHERE ticker=?", (ticker,))
        row = cursor.fetchone()
        
        if row:
            curr_shares, avg_price = row
            new_shares = curr_shares + shares
            # Weighted average price
            new_avg_price = ((curr_shares * avg_price) + (shares * current_price)) / new_shares
            cursor.execute("UPDATE portfolio SET shares=?, avg_purchase_price=?, buy_signal=? WHERE ticker=?", 
                           (new_shares, new_avg_price, signal, ticker))
        else:
            cursor.execute("INSERT INTO portfolio (ticker, shares, avg_purchase_price, buy_signal) VALUES (?, ?, ?, ?)",
                           (ticker, shares, current_price, signal))
                           
    elif trade_type == 'SELL':
        # For sell, we must have it in portfolio
        cursor.execute("SELECT shares, avg_purchase_price FROM portfolio WHERE ticker=?", (ticker,))
        row = cursor.fetchone()
        
        if not row or row[0] < shares:
            conn.close()
            raise ValueError(f"Not enough shares to sell {ticker}")
            
        curr_shares, avg_price = row
        
        # Calculate profit
        profit = (current_price - avg_price) * shares
        
        # Record trade
        cursor.execute('''
            INSERT INTO trades (ticker, type, date, shares, price, profit_loss, signal)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (ticker, 'SELL', date_str, shares, current_price, profit, signal))
        
        # Update Portfolio
        new_shares = curr_shares - shares
        if new_shares == 0:
            cursor.execute("DELETE FROM portfolio WHERE ticker=?", (ticker,))
        else:
            cursor.execute("UPDATE portfolio SET shares=? WHERE ticker=?", (new_shares, ticker))
            
    conn.commit()
    conn.close()

def get_portfolio():
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM portfolio")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_trade_history():
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM trades ORDER BY date ASC, id ASC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_paper_deposits():
    """Retrieves all paper trading deposits."""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM paper_deposits ORDER BY date ASC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def add_paper_deposit(amount: float, note: str, date_str: str = None):
    """Adds a new deposit to the paper trading account."""
    if not date_str:
        date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO paper_deposits (date, amount, note) VALUES (?, ?, ?)",
                   (date_str, amount, note))
    conn.commit()
    conn.close()

def delete_paper_deposit(deposit_id: int):
    """Deletes a deposit from paper trading."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM paper_deposits WHERE id=?", (deposit_id,))
    conn.commit()
    conn.close()

def get_paper_account_summary(portfolio_value: float = 0.0):
    """
    Calculates summary metrics for Paper Trading account.
    """
    deposits = get_paper_deposits()
    total_deposited = sum(d['amount'] for d in deposits) if deposits else 0.0
    start_date = deposits[0]['date'] if deposits else "N/A"
    
    trades = get_trade_history()
    cash = total_deposited
    for t in trades:
        cost_or_rev = t['shares'] * t['price']
        if t['type'] == 'BUY':
            cash -= cost_or_rev
        elif t['type'] == 'SELL':
            cash += cost_or_rev
            
    total_equity = cash + portfolio_value
    total_pl = total_equity - total_deposited
    total_pl_pct = (total_pl / total_deposited) if total_deposited > 0 else 0.0
    
    return {
        "total_deposited": total_deposited,
        "start_date": start_date,
        "cash": cash,
        "total_equity": total_equity,
        "total_pl": total_pl,
        "total_pl_pct": total_pl_pct,
        "deposits": deposits
    }

# --- Autotrading Agent DB Functions ---

def init_agent_db(cursor):
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS agent_account (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            budget REAL NOT NULL,
            cash REAL NOT NULL,
            last_reset TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS agent_portfolio (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL UNIQUE,
            shares INTEGER NOT NULL,
            avg_purchase_price REAL NOT NULL,
            buy_signal REAL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS agent_trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            type TEXT NOT NULL, -- 'BUY', 'SELL', or 'RESET'
            date TEXT NOT NULL,
            shares INTEGER NOT NULL,
            price REAL NOT NULL,
            commission REAL NOT NULL,
            profit_loss REAL,
            signal REAL
        )
    ''')

def get_agent_account():
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM agent_account ORDER BY id DESC LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def set_agent_budget(budget: float):
    """Sets or resets the agent budget, clearing portfolio but keeping trades."""
    conn = get_connection()
    cursor = conn.cursor()
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Sell all current portfolio to realize P&L before reset? Or just clear?
    # User requested to clear but keep performance. Clearing portfolio means un-realized becomes 0.
    # Realized P&L is in agent_trades, which we KEEP.
    cursor.execute("DELETE FROM agent_portfolio")
    
    cursor.execute("INSERT INTO agent_account (budget, cash, last_reset) VALUES (?, ?, ?)", (budget, budget, date_str))
    
    # Record the reset in trades to know when it happened
    cursor.execute('''
        INSERT INTO agent_trades (ticker, type, date, shares, price, commission, profit_loss, signal)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', ('SYSTEM', 'RESET', date_str, 0, 0.0, 0.0, 0.0, None))
    
    conn.commit()
    conn.close()

def get_agent_portfolio():
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM agent_portfolio")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_agent_trades():
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM agent_trades ORDER BY date ASC, id ASC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def execute_agent_trade(ticker: str, trade_type: str, shares: int, current_price: float, commission: float = 5.0, signal: float = None):
    conn = get_connection()
    cursor = conn.cursor()
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Get current account
    cursor.execute("SELECT id, cash FROM agent_account ORDER BY id DESC LIMIT 1")
    acc_row = cursor.fetchone()
    if not acc_row:
        raise ValueError("Agent account not initialized.")
    acc_id, cash = acc_row
    
    cost_or_revenue = shares * current_price
    
    if trade_type == 'BUY':
        total_cost = cost_or_revenue + commission
        if cash < total_cost:
            raise ValueError(f"Not enough cash for {ticker}. Need {total_cost}, have {cash}")
            
        new_cash = cash - total_cost
        
        cursor.execute('''
            INSERT INTO agent_trades (ticker, type, date, shares, price, commission, profit_loss, signal)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (ticker, 'BUY', date_str, shares, current_price, commission, 0.0, signal))
        
        cursor.execute("SELECT shares, avg_purchase_price FROM agent_portfolio WHERE ticker=?", (ticker,))
        row = cursor.fetchone()
        if row:
            curr_shares, avg_price = row
            new_shares = curr_shares + shares
            new_avg_price = ((curr_shares * avg_price) + (shares * current_price)) / new_shares
            cursor.execute("UPDATE agent_portfolio SET shares=?, avg_purchase_price=?, buy_signal=? WHERE ticker=?", (new_shares, new_avg_price, signal, ticker))
        else:
            cursor.execute("INSERT INTO agent_portfolio (ticker, shares, avg_purchase_price, buy_signal) VALUES (?, ?, ?, ?)", (ticker, shares, current_price, signal))
            
    elif trade_type == 'SELL':
        cursor.execute("SELECT shares, avg_purchase_price FROM agent_portfolio WHERE ticker=?", (ticker,))
        row = cursor.fetchone()
        if not row or row[0] < shares:
            raise ValueError(f"Not enough shares to sell {ticker}")
            
        curr_shares, avg_price = row
        total_revenue = cost_or_revenue - commission
        new_cash = cash + total_revenue
        
        profit = (current_price - avg_price) * shares - commission
        
        cursor.execute('''
            INSERT INTO agent_trades (ticker, type, date, shares, price, commission, profit_loss, signal)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (ticker, 'SELL', date_str, shares, current_price, commission, profit, signal))
        
        new_shares = curr_shares - shares
        if new_shares == 0:
            cursor.execute("DELETE FROM agent_portfolio WHERE ticker=?", (ticker,))
        else:
            cursor.execute("UPDATE agent_portfolio SET shares=? WHERE ticker=?", (new_shares, ticker))
            
    cursor.execute("UPDATE agent_account SET cash=? WHERE id=?", (new_cash, acc_id))
    conn.commit()
    conn.close()

def hash_password(password: str) -> str:
    """Returns SHA256 hash of a password."""
    return hashlib.sha256(password.encode('utf-8')).hexdigest()

def init_default_user(cursor=None):
    """Ensures default user Rodas73 exists with the requested password."""
    default_user = "Rodas73"
    default_pass = "PxA_34@92"
    pass_hash = hash_password(default_pass)
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    close_after = False
    if cursor is None:
        conn = get_connection()
        cursor = conn.cursor()
        close_after = True
    else:
        conn = None
        
    try:
        cursor.execute("SELECT id FROM users WHERE username = ?", (default_user,))
        row = cursor.fetchone()
        if not row:
            cursor.execute(
                "INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)",
                (default_user, pass_hash, now_str)
            )
        else:
            # Update password hash to guarantee it matches the requested password
            cursor.execute(
                "UPDATE users SET password_hash = ? WHERE username = ?",
                (pass_hash, default_user)
            )
        if conn:
            conn.commit()
    finally:
        if close_after and conn:
            conn.close()

def verify_user_credentials(username: str, password: str) -> bool:
    """Verifies username and password against users table."""
    if not username or not password:
        return False
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT password_hash FROM users WHERE username = ?", (username.strip(),))
        row = cursor.fetchone()
        conn.close()
        if not row:
            return False
        stored_hash = row[0]
        return stored_hash == hash_password(password)
    except Exception as e:
        logger.error(f"Error verifying user credentials: {e}")
        return False

def update_user_password(username: str, new_password: str) -> bool:
    """Updates password for a user."""
    if not username or not new_password:
        return False
    try:
        conn = get_connection()
        cursor = conn.cursor()
        pass_hash = hash_password(new_password)
        cursor.execute("UPDATE users SET password_hash = ? WHERE username = ?", (pass_hash, username.strip()))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Error updating password: {e}")
        return False

# ---------------------------------------------------------------------------
# Watchlist personalizzata
# ---------------------------------------------------------------------------

def get_watchlist() -> list:
    """Restituisce tutti i titoli nella watchlist personalizzata."""
    try:
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM watchlist ORDER BY created_at DESC")
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return rows
    except Exception as e:
        logger.error(f"Error in get_watchlist: {e}")
        return []

def add_watchlist_item(ticker: str, label: str = "", note: str = "") -> bool:
    """Aggiunge un titolo alla watchlist."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute(
            "INSERT INTO watchlist (ticker, label, note, created_at) VALUES (?, ?, ?, ?)",
            (ticker.strip().upper(), label.strip(), note.strip(), now)
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Error in add_watchlist_item: {e}")
        return False

def update_watchlist_item(item_id: int, label: str = None, note: str = None) -> bool:
    """Aggiorna etichetta e/o nota di un elemento della watchlist."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        if label is not None and note is not None:
            cursor.execute("UPDATE watchlist SET label=?, note=? WHERE id=?", (label.strip(), note.strip(), item_id))
        elif label is not None:
            cursor.execute("UPDATE watchlist SET label=? WHERE id=?", (label.strip(), item_id))
        elif note is not None:
            cursor.execute("UPDATE watchlist SET note=? WHERE id=?", (note.strip(), item_id))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Error in update_watchlist_item: {e}")
        return False

def delete_watchlist_item(item_id: int) -> bool:
    """Rimuove un titolo dalla watchlist."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM watchlist WHERE id=?", (item_id,))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Error in delete_watchlist_item: {e}")
        return False

# Initialize on import
init_db()


