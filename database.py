import sqlite3
from datetime import datetime

DATABASE_FILE = "bot_data.db"

def get_db_connection():
    """Establishes a connection to the database."""
    conn = sqlite3.connect(DATABASE_FILE)
    conn.row_factory = sqlite3.Row  # This allows accessing columns by name
    return conn

def init_db():
    """Initializes the database and creates tables if they don't exist."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # --- User and Wallet Management ---
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        balance REAL DEFAULT 0,
        withdrawn REAL DEFAULT 0,
        joined_at TEXT NOT NULL
    )''')

    # --- Redeem Codes ---
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS redeem_codes (
        code TEXT PRIMARY KEY,
        reward REAL NOT NULL,
        is_used INTEGER DEFAULT 0,
        used_by INTEGER,
        used_at TEXT,
        FOREIGN KEY (used_by) REFERENCES users(id)
    )''')
    
    # --- Verification Codes & Usage Tracking ---
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS verification_codes (
        code TEXT PRIMARY KEY
    )''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS user_verifications (
        user_id INTEGER NOT NULL,
        code TEXT NOT NULL,
        verified_at TEXT NOT NULL,
        PRIMARY KEY (user_id, code),
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (code) REFERENCES verification_codes(code)
    )''')

    # --- Withdraw Requests ---
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS withdraw_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        amount REAL NOT NULL,
        upi_id TEXT NOT NULL,
        status TEXT DEFAULT 'pending',
        requested_at TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )''')

    # --- Link Management ---
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS links (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        url TEXT NOT NULL UNIQUE
    )''')
    
    # --- Banned Users ---
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS banned_users (
        user_id INTEGER PRIMARY KEY,
        banned_at TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )''')

    # --- Admin Settings ---
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS admin_settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )''')
    
    # --- Default Settings ---
    cursor.execute("INSERT OR IGNORE INTO admin_settings (key, value) VALUES (?, ?)", ('min_withdraw', '100'))
    cursor.execute("INSERT OR IGNORE INTO admin_settings (key, value) VALUES (?, ?)", ('contact_info', 'Contact info not set.'))
    cursor.execute("INSERT OR IGNORE INTO admin_settings (key, value) VALUES (?, ?)", ('tutorial_link', 'Tutorial link not set.'))

    conn.commit()
    conn.close()

# --- User Functions ---

def add_or_update_user(user_id, username, first_name):
    """Adds a new user or updates their name if they already exist."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR IGNORE INTO users (id, username, first_name, joined_at) VALUES (?, ?, ?, ?)",
        (user_id, username, first_name, datetime.now().isoformat())
    )
    # Update names in case they change
    cursor.execute(
        "UPDATE users SET username = ?, first_name = ? WHERE id = ?",
        (username, first_name, user_id)
    )
    conn.commit()
    conn.close()

def get_user_wallet(user_id):
    """Retrieves a user's wallet details."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT balance, withdrawn FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()
    conn.close()
    if user:
        return {'balance': user['balance'], 'withdrawn': user['withdrawn']}
    return {'balance': 0, 'withdrawn': 0}

def update_user_balance(user_id, amount, is_withdrawal=False):
    """Adds or subtracts from a user's balance."""
    conn = get_db_connection()
    cursor = conn.cursor()
    if is_withdrawal:
        cursor.execute("UPDATE users SET balance = balance - ?, withdrawn = withdrawn + ? WHERE id = ?", (amount, amount, user_id))
    else:
        cursor.execute("UPDATE users SET balance = balance + ? WHERE id = ?", (amount, user_id))
    conn.commit()
    conn.close()

def get_leaderboard(limit=10):
    """Gets the top users by balance."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT first_name, username, balance FROM users ORDER BY balance DESC LIMIT ?", (limit,))
    leaderboard = cursor.fetchall()
    conn.close()
    return leaderboard
    
def get_all_users(page=0, per_page=50):
    """Retrieves all users with pagination."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(id) FROM users")
    total_users = cursor.fetchone()[0]
    
    offset = page * per_page
    cursor.execute("SELECT id, first_name, username FROM users LIMIT ? OFFSET ?", (per_page, offset))
    users = cursor.fetchall()
    conn.close()
    return users, total_users

# --- Redeem Code Functions ---

def add_redeem_code(code, reward):
    """Adds a new redeem code to the database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO redeem_codes (code, reward) VALUES (?, ?)", (code, reward))
        conn.commit()
        return True
    except sqlite3.IntegrityError: # Code already exists
        return False
    finally:
        conn.close()

def redeem_code(user_id, code):
    """Allows a user to redeem a code. Returns status and message."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT reward, is_used, used_by FROM redeem_codes WHERE code = ?", (code,))
    redeem = cursor.fetchone()

    if not redeem:
        conn.close()
        return "invalid", "Invalid or already claimed code."

    if redeem['is_used']:
        cursor.execute("SELECT first_name FROM users WHERE id = ?", (redeem['used_by'],))
        claimer = cursor.fetchone()
        claimer_name = f"User ID {redeem['used_by']}" if not claimer else claimer['first_name']
        conn.close()
        return "claimed", f"This code has already been claimed by {claimer_name}."

    # Mark as used and update user balance
    cursor.execute(
        "UPDATE redeem_codes SET is_used = 1, used_by = ?, used_at = ? WHERE code = ?",
        (user_id, datetime.now().isoformat(), code)
    )
    cursor.execute("UPDATE users SET balance = balance + ? WHERE id = ?", (redeem['reward'], user_id))
    conn.commit()
    conn.close()
    return "success", f"🎉 Congratulations! You've redeemed ₹{redeem['reward']}."

# --- Withdraw Functions ---

def submit_withdraw_request(user_id, amount, upi_id):
    """Submits a new withdrawal request."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Decrement balance immediately upon request
    cursor.execute("UPDATE users SET balance = balance - ? WHERE id = ?", (amount, user_id))
    
    cursor.execute(
        "INSERT INTO withdraw_requests (user_id, amount, upi_id, requested_at) VALUES (?, ?, ?, ?)",
        (user_id, amount, upi_id, datetime.now().isoformat())
    )
    request_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return request_id

def get_pending_withdrawals(user_id=None):
    """Gets all pending withdrawals, optionally for a specific user."""
    conn = get_db_connection()
    cursor = conn.cursor()
    if user_id:
        cursor.execute("SELECT id, amount, upi_id FROM withdraw_requests WHERE user_id = ? AND status = 'pending'", (user_id,))
    else:
        cursor.execute("SELECT id, user_id, amount, upi_id FROM withdraw_requests WHERE status = 'pending'")
    requests = cursor.fetchall()
    conn.close()
    return requests

def get_withdrawal_by_id(withdraw_id):
    """Finds a single withdrawal request by its ID."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM withdraw_requests WHERE id = ? AND status = 'pending'", (withdraw_id,))
    request = cursor.fetchone()
    conn.close()
    return request

def update_withdrawal_status(withdraw_id, new_status, amount=0, user_id=0):
    """Updates a withdrawal's status to 'completed' or 'returned'."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if new_status == 'completed':
        # On completion, update the user's total withdrawn amount
        cursor.execute("UPDATE users SET withdrawn = withdrawn + ? WHERE id = ?", (amount, user_id))
    elif new_status == 'returned':
        # If returned, refund the balance to the user
        cursor.execute("UPDATE users SET balance = balance + ? WHERE id = ?", (amount, user_id))

    cursor.execute("UPDATE withdraw_requests SET status = ? WHERE id = ?", (new_status, withdraw_id))
    conn.commit()
    conn.close()

# --- Admin & Settings Functions ---

def get_setting(key):
    """Retrieves a setting value."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM admin_settings WHERE key = ?", (key,))
    result = cursor.fetchone()
    conn.close()
    return result['value'] if result else None

def set_setting(key, value):
    """Sets a setting value."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE admin_settings SET value = ? WHERE key = ?", (value, key))
    conn.commit()
    conn.close()

# --- Link Management Functions ---
def add_link(title, url):
    """Adds a new link."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO links (title, url) VALUES (?, ?)", (title, url))
        conn.commit()
    except sqlite3.IntegrityError:
        # Handle case where URL is not unique
        pass
    finally:
        conn.close()

def get_links():
    """Retrieves all links."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, url FROM links")
    links = cursor.fetchall()
    conn.close()
    return links
    
def delete_link(link_id):
    """Deletes a link by its ID."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM links WHERE id = ?", (link_id,))
    conn.commit()
    conn.close()

# --- Verification Code Functions ---

def add_verification_code(code):
    """Adds a new verification code."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO verification_codes (code) VALUES (?)", (code,))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False # Already exists
    finally:
        conn.close()
        
def get_verification_codes():
    """Retrieves all verification codes."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT code FROM verification_codes")
    codes = [row['code'] for row in cursor.fetchall()]
    conn.close()
    return codes
    
def delete_verification_code(code):
    """Deletes a verification code."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM verification_codes WHERE code = ?", (code,))
    conn.commit()
    conn.close()

def verify_user_code(user_id, code):
    """Marks a code as used by a user."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO user_verifications (user_id, code, verified_at) VALUES (?, ?, ?)",
            (user_id, code, datetime.now().isoformat())
        )
        conn.commit()
        return "success"
    except sqlite3.IntegrityError:
        return "already_used"
    finally:
        conn.close()
        
def has_user_verified_code(user_id, code):
    """Checks if a user has already used a specific verification code."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM user_verifications WHERE user_id = ? AND code = ?", (user_id, code))
    exists = cursor.fetchone()
    conn.close()
    return exists is not None

def has_user_verified_any_code(user_id):
    """Checks if a user has verified at least one code."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM user_verifications WHERE user_id = ?", (user_id,))
    exists = cursor.fetchone()
    conn.close()
    return exists is not None

# --- Banned User Functions ---
def ban_user(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO banned_users (user_id, banned_at) VALUES (?, ?)", (user_id, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def unban_user(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM banned_users WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()
    
def is_user_banned(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM banned_users WHERE user_id = ?", (user_id,))
    is_banned = cursor.fetchone()
    conn.close()
    return is_banned is not None

def get_banned_users():
    conn = get_db_connection()
    cursor = conn.cursor()
    # Join with users table to get their names
    cursor.execute("""
        SELECT u.id, u.username, u.first_name 
        FROM banned_users b
        JOIN users u ON b.user_id = u.id
    """)
    banned = cursor.fetchall()
    conn.close()
    return banned