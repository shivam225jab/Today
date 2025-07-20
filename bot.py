import logging
import json
import os
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ConversationHandler

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Admin ID
ADMIN_ID = 5924971946

# Conversation states
(
    USER_INPUT,
    AWAITING_REDEEM_CODE,
    AWAITING_VERIFY_CODE,
    AWAITING_LINK_TITLE,
    AWAITING_LINK_URL,
    AWAITING_VERIFY_CODE_ADD,
    AWAITING_REDEEM_CODE_ADD,
    AWAITING_REDEEM_VALUE_ADD,
    AWAITING_MIN_WITHDRAW_AMOUNT,
    AWAITING_USER_ID_FOR_BALANCE,
    AWAITING_BALANCE_ACTION,
    AWAITING_BALANCE_AMOUNT,
    AWAITING_MESSAGE_RECIPIENT,
    AWAITING_MESSAGE_CONTENT,
    AWAITING_MESSAGE_USER_ID,
    AWAITING_BAN_USER_ID,
    AWAITING_UNBAN_USER_ID,
    AWAITING_MANAGE_WITHDRAW_ID,
    AWAITING_CONTACT_INFO,
    AWAITING_TUTORIAL_INFO,
    # New states for withdraw flow
    AWAITING_WITHDRAW_AMOUNT,
    AWAITING_WITHDRAW_UPI,
    AWAITING_WITHDRAW_CONFIRMATION,
) = range(23)


# File paths for JSON storage
DATA_DIR = "data"
LINKS_FILE = os.path.join(DATA_DIR, "links.json")
VERIFIED_USERS_FILE = os.path.join(DATA_DIR, "verified_users.json")
WALLET_FILE = os.path.join(DATA_DIR, "wallet.json")
WITHDRAW_FILE = os.path.join(DATA_DIR, "withdraw.json")
CONTACT_FILE = os.path.join(DATA_DIR, "contact.json")
TUTORIAL_FILE = os.path.join(DATA_DIR, "tutorial.json")
VERIFY_CODES_FILE = os.path.join(DATA_DIR, "verify_codes.json")
REDEEM_CODES_FILE = os.path.join(DATA_DIR, "redeem_codes.json")
USERS_FILE = os.path.join(DATA_DIR, "users.json")
SETTINGS_FILE = os.path.join(DATA_DIR, "settings.json")
BANNED_FILE = os.path.join(DATA_DIR, "banned.json")
COMPLETED_FILE = os.path.join(DATA_DIR, "completed.json")

# Reusable Keyboards for Back/Cancel actions
main_panel_markup = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Panel", callback_data='main_panel')]])
admin_panel_back_button = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data='admin_panel')]])
user_panel_back_button = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data='user_panel')]])


# --- Utility Functions ---
def ensure_data_files():
    """Ensure all necessary data files and directory exist."""
    os.makedirs(DATA_DIR, exist_ok=True)
    files = {
        LINKS_FILE: [], VERIFIED_USERS_FILE: {}, WALLET_FILE: {},
        WITHDRAW_FILE: {}, CONTACT_FILE: {"info": "Contact info not set."},
        TUTORIAL_FILE: {"link": "Tutorial link not set."},
        VERIFY_CODES_FILE: [], REDEEM_CODES_FILE: {}, USERS_FILE: {},
        SETTINGS_FILE: {"min_withdraw": 100, "last_withdraw_id": 99}, 
        BANNED_FILE: [], COMPLETED_FILE: []
    }
    for file_path, default_content in files.items():
        if not os.path.exists(file_path):
            with open(file_path, 'w') as f:
                json.dump(default_content, f, indent=4)

def load_data(file_path):
    """Load data from a JSON file."""
    try:
        with open(file_path, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        default_files = {
            LINKS_FILE: [], VERIFIED_USERS_FILE: {}, WALLET_FILE: {},
            WITHDRAW_FILE: {}, CONTACT_FILE: {"info": "Contact info not set."},
            TUTORIAL_FILE: {"link": "Tutorial link not set."},
            VERIFY_CODES_FILE: [], REDEEM_CODES_FILE: {}, USERS_FILE: {},
            SETTINGS_FILE: {"min_withdraw": 100, "last_withdraw_id": 99}, 
            BANNED_FILE: [], COMPLETED_FILE: []
        }
        return default_files.get(file_path, {})


def save_data(file_path, data):
    """Save data to a JSON file."""
    with open(file_path, 'w') as f:
        json.dump(data, f, indent=4)

def get_user_wallet(user_id):
    """Get or create a user's wallet."""
    wallets = load_data(WALLET_FILE)
    user_id_str = str(user_id)
    if user_id_str not in wallets:
        wallets[user_id_str] = {"balance": 0.0, "withdrawn": 0.0, "earn_today": 0.0, "last_earn_date": ""}
        save_data(WALLET_FILE, wallets)
    return wallets[user_id_str]

def update_user_list(user):
    """Add user to the main user list if not already present."""
    users = load_data(USERS_FILE)
    user_id_str = str(user.id)
    if user_id_str not in users:
        users[user_id_str] = {
            "username": user.username or "N/A",
            "first_name": user.first_name or "N/A",
            "id": user.id,
            "hide_name": False
        }
        save_data(USERS_FILE, users)

# --- Bot Start and Main Menu ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    user = update.effective_user
    banned_users = load_data(BANNED_FILE)
    if user.id in [b.get('id') for b in banned_users]:
        await update.message.reply_text("You are banned from using this bot.")
        return

    update_user_list(user)

    if user.id == ADMIN_ID:
        await admin_panel(update, context)
    else:
        await user_panel(update, context)

async def user_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Display the main user panel."""
    user_id = update.effective_user.id
    keyboard = [
        [InlineKeyboardButton("🔗 Get Code", callback_data='get_code'), InlineKeyboardButton("✅ Verify Code", callback_data='verify_code_user')],
        [InlineKeyboardButton("🎁 Claim Reward", callback_data='claim_reward'), InlineKeyboardButton("💰 Wallet", callback_data='wallet')],
        [InlineKeyboardButton("💲 Withdraw", callback_data='withdraw'), InlineKeyboardButton("⏳ Pending Withdraw", callback_data='pending_withdraw')],
        [InlineKeyboardButton("📞 Contact", callback_data='contact'), InlineKeyboardButton("❓ How to Use Bot", callback_data='how_to_use')],
        [InlineKeyboardButton("🏆 Leaderboard", callback_data='leaderboard')]
    ]
    if user_id == ADMIN_ID:
        keyboard.append([InlineKeyboardButton("⬅️ Back to Admin Panel", callback_data='admin_panel')])

    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = "👤 Welcome to the User Panel!"
    if update.callback_query:
        await update.callback_query.edit_message_text(text=text, reply_markup=reply_markup)
    else:
        await update.message.reply_text(text=text, reply_markup=reply_markup)


async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Display the main admin panel."""
    keyboard = [
        [InlineKeyboardButton("🔗 Manage Links", callback_data='manage_links'), InlineKeyboardButton("🔐 Manage Verify Codes", callback_data='manage_verify_codes')],
        [InlineKeyboardButton("💰 Add Redeem Code", callback_data='add_redeem_code'), InlineKeyboardButton("👥 View Users", callback_data='view_users_0')],
        [InlineKeyboardButton("⚙️ Set Min Withdraw", callback_data='set_min_withdraw'), InlineKeyboardButton("✏️ Edit Balance", callback_data='edit_balance')],
        [InlineKeyboardButton("📤 Send Message", callback_data='send_message'), InlineKeyboardButton("🛠️ Manage Users", callback_data='manage_users')],
        [InlineKeyboardButton("💸 Manage Withdraw", callback_data='manage_withdraw'), InlineKeyboardButton("✅ Completed Withdraws", callback_data='completed_withdrawals')],
        [InlineKeyboardButton("📞 Add Contact Info", callback_data='add_contact_info'), InlineKeyboardButton("📹 Add Tutorial", callback_data='add_tutorial')],
        [InlineKeyboardButton("📊 Verify Code Usage", callback_data='view_verify_usage'), InlineKeyboardButton("👤 Switch to User Panel", callback_data='switch_to_user')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = "🔐 Welcome to the Admin Panel!"
    
    query = update.callback_query
    if query:
        await query.edit_message_text(text=text, reply_markup=reply_markup)
    else:
        if update.message:
            await update.message.reply_text(text=text, reply_markup=reply_markup)

# --- Button Callback Handler ---
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Parses the CallbackQuery and updates the message text."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    banned_users = load_data(BANNED_FILE)
    if user_id in [b.get('id') for b in banned_users]:
        await query.edit_message_text("You are banned from using this bot.")
        return ConversationHandler.END

    # User Panel Handlers
    if query.data == 'get_code':
        await get_code(query)
    elif query.data == 'verify_code_user':
        await query.edit_message_text("Please enter the verification code:", reply_markup=user_panel_back_button)
        return AWAITING_VERIFY_CODE
    elif query.data == 'claim_reward':
        await query.edit_message_text("Please enter your redeem code:", reply_markup=user_panel_back_button)
        return AWAITING_REDEEM_CODE
    elif query.data == 'wallet':
        await show_wallet(query)
    elif query.data == 'withdraw':
        return await start_withdraw_flow(query, context)
    elif query.data == 'confirm_withdraw':
        return await handle_withdraw_confirmation(update, context)
    elif query.data == 'cancel_withdraw_flow':
        context.user_data.clear()
        await query.edit_message_text("Withdrawal cancelled.", reply_markup=user_panel_back_button)
        return ConversationHandler.END
    elif query.data == 'pending_withdraw':
        await show_pending_withdraw(query)
    elif query.data.startswith('cancel_withdraw_'):
        withdraw_id = query.data.split('_')[2]
        await cancel_withdraw_confirm(query, withdraw_id)
    elif query.data.startswith('confirm_cancel_'):
        withdraw_id = query.data.split('_')[2]
        await cancel_withdraw(query, withdraw_id)
    elif query.data == 'contact':
        await show_contact(query)
    elif query.data == 'how_to_use':
        await show_how_to_use(query)
    elif query.data == 'leaderboard':
        await show_leaderboard(query)
    elif query.data == 'user_panel':
        await user_panel(update, context)

    # Admin Panel Handlers
    elif query.data == 'admin_panel':
        await admin_panel(update, context)
    elif query.data == 'switch_to_user':
        await user_panel(update, context)
    elif query.data == 'manage_links':
        await manage_links(query) # <<< THIS IS THE TRIGGER
    elif query.data == 'add_link_start':
        await query.edit_message_text("Enter the title for the new link:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data='manage_links')]]))
        return AWAITING_LINK_TITLE
    elif query.data.startswith('delete_link_'):
        index = int(query.data.split('_')[2])
        await handle_delete_link(query, index)
    elif query.data == 'manage_verify_codes':
        await manage_verify_codes(query)
    elif query.data == 'add_verify_code_start':
        await query.edit_message_text("Enter the new verification code:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data='manage_verify_codes')]]))
        return AWAITING_VERIFY_CODE_ADD
    elif query.data.startswith('delete_vcode_'):
        code_to_delete = query.data[len('delete_vcode_'):]
        await handle_delete_verify_code(query, code_to_delete)
    elif query.data == 'add_redeem_code':
        await query.edit_message_text("Enter the new redeem code:", reply_markup=admin_panel_back_button)
        return AWAITING_REDEEM_CODE_ADD
    elif query.data.startswith('view_users_'):
        page = int(query.data.split('_')[2])
        await view_users(query, page)
    elif query.data == 'set_min_withdraw':
        await query.edit_message_text("Enter the new minimum withdrawal amount:", reply_markup=admin_panel_back_button)
        return AWAITING_MIN_WITHDRAW_AMOUNT
    elif query.data == 'edit_balance':
        await query.edit_message_text("Enter the User ID to edit balance:", reply_markup=admin_panel_back_button)
        return AWAITING_USER_ID_FOR_BALANCE
    elif query.data.startswith('balance_action_'):
        user_id_to_edit, action = query.data.split('_')[2:]
        context.user_data['user_id_to_edit'] = user_id_to_edit
        context.user_data['balance_action'] = action
        await query.edit_message_text(f"Enter the amount to {action} for user {user_id_to_edit}:", reply_markup=admin_panel_back_button)
        return AWAITING_BALANCE_AMOUNT
    elif query.data == 'send_message':
        await send_message_menu(query)
    elif query.data == 'send_to_all':
        context.user_data['recipient'] = 'all'
        await query.edit_message_text("Enter the message to send to all users:", reply_markup=admin_panel_back_button)
        return AWAITING_MESSAGE_CONTENT
    elif query.data == 'send_to_one':
        context.user_data['recipient'] = 'one'
        await query.edit_message_text("Enter the User ID to send a message to:", reply_markup=admin_panel_back_button)
        return AWAITING_MESSAGE_USER_ID
    elif query.data == 'manage_users':
        await manage_users_menu(query)
    elif query.data == 'ban_user':
        await query.edit_message_text("Enter the User ID to ban:", reply_markup=admin_panel_back_button)
        return AWAITING_BAN_USER_ID
    elif query.data == 'unban_user':
        await query.edit_message_text("Enter the User ID to unban:", reply_markup=admin_panel_back_button)
        return AWAITING_UNBAN_USER_ID
    elif query.data == 'view_banned':
        await view_banned_users(query)
    elif query.data == 'manage_withdraw':
        await query.edit_message_text("Enter the User ID or Withdraw ID to manage:", reply_markup=admin_panel_back_button)
        return AWAITING_MANAGE_WITHDRAW_ID
    elif query.data.startswith('complete_withdraw_'):
        # Format: complete_withdraw_USERID_WITHDRAWID
        _, _, u_id, w_id = query.data.split('_', 3)
        await complete_withdraw(query, context, u_id, w_id)
    elif query.data.startswith('return_withdraw_'):
        # Format: return_withdraw_USERID_WITHDRAWID
        _, _, u_id, w_id = query.data.split('_', 3)
        await return_withdraw(query, context, u_id, w_id)
    elif query.data == 'completed_withdrawals':
        await view_completed_withdrawals(query)
    elif query.data == 'clear_completed':
        save_data(COMPLETED_FILE, [])
        await query.edit_message_text("Completed withdrawals list cleared.", reply_markup=admin_panel_back_button)
    elif query.data == 'add_contact_info':
        await query.edit_message_text("Enter the new contact information:", reply_markup=admin_panel_back_button)
        return AWAITING_CONTACT_INFO
    elif query.data == 'add_tutorial':
        await query.edit_message_text("Enter the new tutorial link:", reply_markup=admin_panel_back_button)
        return AWAITING_TUTORIAL_INFO
    elif query.data == 'view_verify_usage':
        await view_verify_code_usage(query)
        
    return ConversationHandler.END


# --- User Panel Logic ---

async def get_code(query):
    """Shows active links to the user. Skips any malformed entries in the JSON."""
    links = load_data(LINKS_FILE)

    if not isinstance(links, list) or not links:
        await query.edit_message_text("No links available.", reply_markup=user_panel_back_button)
        return

    buttons = []
    for link in links:
        if isinstance(link, dict) and 'title' in link and 'url' in link and (link['url'].startswith('http://') or link['url'].startswith('https://')):
            buttons.append([InlineKeyboardButton(link['title'], url=link['url'])])
    
    if not buttons:
        await query.edit_message_text("No links available.", reply_markup=user_panel_back_button)
        return

    buttons.append([InlineKeyboardButton("⬅️ Back", callback_data='user_panel')])
    reply_markup = InlineKeyboardMarkup(buttons)
    await query.edit_message_text("Here are the available links. Please visit them to find a verification code:", reply_markup=reply_markup)

async def handle_verify_code(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    user_id_str = str(user_id)
    code = update.message.text.strip()
    
    verified_users = load_data(VERIFIED_USERS_FILE)
    user_verifications = verified_users.get(user_id_str, {})

    if code in user_verifications:
        await update.message.reply_text("You have already used this verification code.", reply_markup=user_panel_back_button)
        return ConversationHandler.END

    valid_codes = load_data(VERIFY_CODES_FILE)
    if code in valid_codes:
        user_verifications[code] = {"verified_at": datetime.now().isoformat()}
        verified_users[user_id_str] = user_verifications
        save_data(VERIFIED_USERS_FILE, verified_users)
        await update.message.reply_text("✅ Verification successful!", reply_markup=user_panel_back_button)
    else:
        await update.message.reply_text("❌ Invalid code. Please try again.", reply_markup=user_panel_back_button)

    return ConversationHandler.END

async def handle_redeem_code(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    user_id_str = str(user.id)
    code = update.message.text.strip()

    verified_users = load_data(VERIFIED_USERS_FILE)
    if user_id_str not in verified_users or not verified_users[user_id_str]:
        await update.message.reply_text("You must verify at least one code to claim a reward.", reply_markup=user_panel_back_button)
        return ConversationHandler.END

    redeem_codes = load_data(REDEEM_CODES_FILE)
    if code in redeem_codes and redeem_codes[code]['claimed_by'] is None:
        reward = redeem_codes[code]['reward']
        redeem_codes[code]['claimed_by'] = {
            "id": user.id, 
            "first_name": user.first_name or "N/A"
        }
        save_data(REDEEM_CODES_FILE, redeem_codes)

        wallet_data = load_data(WALLET_FILE)
        user_wallet = get_user_wallet(user.id) 
        user_wallet['balance'] += reward
        wallet_data[user_id_str] = user_wallet
        save_data(WALLET_FILE, wallet_data)
        
        await update.message.reply_text(f"🎉 Congratulations! You've redeemed ₹{reward}.", reply_markup=user_panel_back_button)
    elif code in redeem_codes:
        claimer_info = redeem_codes[code]['claimed_by']
        display_name = claimer_info.get('first_name', f"ID: {claimer_info.get('id', 'a user')}")
        if display_name == "N/A":
            display_name = f"User ID: {claimer_info.get('id', 'a user')}"
        await update.message.reply_text(f"This code has already been claimed by {display_name}.", reply_markup=user_panel_back_button)
    else:
        await update.message.reply_text("Invalid or already claimed code.", reply_markup=user_panel_back_button)

    return ConversationHandler.END

async def show_wallet(query):
    user_id = query.from_user.id
    wallet = get_user_wallet(user_id)
    text = f"💰 Your Wallet:\n\nBalance: ₹{wallet.get('balance', 0):.2f}\nTotal Withdrawn: ₹{wallet.get('withdrawn', 0):.2f}"
    await query.edit_message_text(text, reply_markup=user_panel_back_button)

# --- New Step-by-Step Withdraw Flow ---
async def start_withdraw_flow(query: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the withdrawal conversation by asking for the amount."""
    settings = load_data(SETTINGS_FILE)
    min_withdraw = settings.get('min_withdraw', 100)
    wallet = get_user_wallet(query.from_user.id)
    
    text = (f"Your current balance is ₹{wallet['balance']:.2f}\n"
            f"The minimum withdrawal amount is ₹{min_withdraw}.\n\n"
            "Please enter the amount you wish to withdraw:")
    
    await query.edit_message_text(text=text, reply_markup=user_panel_back_button)
    return AWAITING_WITHDRAW_AMOUNT

async def handle_withdraw_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles the user-provided withdrawal amount."""
    try:
        amount = float(update.message.text)
    except (ValueError, TypeError):
        await update.message.reply_text("Invalid amount. Please enter a number.", reply_markup=user_panel_back_button)
        return ConversationHandler.END

    user_id = update.effective_user.id
    settings = load_data(SETTINGS_FILE)
    min_withdraw = settings.get('min_withdraw', 100)
    wallet = get_user_wallet(user_id)

    if amount < min_withdraw:
        await update.message.reply_text(f"Minimum withdrawal amount is ₹{min_withdraw}. Please try again.", reply_markup=user_panel_back_button)
        return ConversationHandler.END

    if wallet['balance'] < amount:
        await update.message.reply_text("Insufficient balance. Your balance is lower than the amount you requested.", reply_markup=user_panel_back_button)
        return ConversationHandler.END

    context.user_data['withdraw_amount'] = amount
    await update.message.reply_text("Amount received. Now, please enter your UPI ID (e.g., `example@upi`):")
    return AWAITING_WITHDRAW_UPI

async def handle_withdraw_upi(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles the user-provided UPI ID and asks for confirmation."""
    upi_id = update.message.text.strip()
    context.user_data['upi_id'] = upi_id
    amount = context.user_data['withdraw_amount']

    text = (f"Please confirm your withdrawal request:\n\n"
            f"<b>Amount:</b> ₹{amount:.2f}\n"
            f"<b>UPI ID:</b> {upi_id}\n\n"
            "Is this correct?")
            
    keyboard = [
        [InlineKeyboardButton("✅ Yes, Confirm", callback_data='confirm_withdraw')],
        [InlineKeyboardButton("❌ No, Cancel", callback_data='cancel_withdraw_flow')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='HTML')
    return AWAITING_WITHDRAW_CONFIRMATION

async def handle_withdraw_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Submits the withdrawal request after admin confirmation."""
    query = update.callback_query
    user_id = query.from_user.id
    user_id_str = str(user_id)
    amount = context.user_data.get('withdraw_amount')
    upi_id = context.user_data.get('upi_id')

    if not amount or not upi_id:
        await query.edit_message_text("An error occurred. Missing withdrawal details. Please start over.", reply_markup=user_panel_back_button)
        return ConversationHandler.END

    settings = load_data(SETTINGS_FILE)
    last_id = settings.get('last_withdraw_id', 99) 
    new_withdraw_id = last_id + 1
    settings['last_withdraw_id'] = new_withdraw_id
    save_data(SETTINGS_FILE, settings)

    all_withdraws = load_data(WITHDRAW_FILE)
    if user_id_str not in all_withdraws:
        all_withdraws[user_id_str] = []
    
    all_withdraws[user_id_str].append({
        "withdraw_id": new_withdraw_id,
        "amount": amount,
        "upi_id": upi_id,
        "status": "pending",
        "requested_at": datetime.now().isoformat()
    })
    
    wallet_data = load_data(WALLET_FILE)
    wallet_data[user_id_str]['balance'] -= amount
    save_data(WALLET_FILE, wallet_data)
    save_data(WITHDRAW_FILE, all_withdraws)

    await query.edit_message_text(f"✅ Withdrawal request of ₹{amount} submitted successfully! Your Withdraw ID is {new_withdraw_id}.", reply_markup=user_panel_back_button)
    context.user_data.clear()
    return ConversationHandler.END

# --- End of new withdraw flow ---

async def show_pending_withdraw(query):
    user_id_str = str(query.from_user.id)
    withdrawals = load_data(WITHDRAW_FILE)
    user_withdrawals = [w for w in withdrawals.get(user_id_str, []) if w.get('status') == 'pending']

    if not user_withdrawals:
        await query.edit_message_text("You have no pending withdrawals.", reply_markup=user_panel_back_button)
        return

    text = "Your pending withdrawals:\n\n"
    for req in user_withdrawals:
        text += f"ID: {req['withdraw_id']}, Amount: ₹{req['amount']:.2f}, UPI: {req['upi_id']}\n"
    
    await query.edit_message_text(text, reply_markup=user_panel_back_button)
    
async def cancel_withdraw_confirm(query, withdraw_id):
    keyboard = [
        [InlineKeyboardButton("✅ Yes, cancel it", callback_data=f"confirm_cancel_{withdraw_id}")],
        [InlineKeyboardButton("⬅️ No, go back", callback_data="pending_withdraw")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(f"Are you sure you want to cancel withdrawal request ID {withdraw_id}?", reply_markup=reply_markup)

async def cancel_withdraw(query, withdraw_id):
    user_id_str = str(query.from_user.id)
    withdrawals = load_data(WITHDRAW_FILE)
    user_requests = withdrawals.get(user_id_str, [])

    request_to_cancel = None
    for req in user_requests:
        if str(req['withdraw_id']) == withdraw_id:
            request_to_cancel = req
            break
    
    if request_to_cancel:
        wallets = load_data(WALLET_FILE)
        wallets[user_id_str]['balance'] += request_to_cancel['amount']
        save_data(WALLET_FILE, wallets)

        user_requests.remove(request_to_cancel)
        if not user_requests:
            if user_id_str in withdrawals:
                del withdrawals[user_id_str]
        else:
            withdrawals[user_id_str] = user_requests
        save_data(WITHDRAW_FILE, withdrawals)
        
        await query.edit_message_text(f"Withdrawal request {withdraw_id} has been cancelled and the amount refunded.", reply_markup=user_panel_back_button)
    else:
        await query.edit_message_text("Withdrawal request not found.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data='pending_withdraw')]]))

async def show_contact(query):
    contact = load_data(CONTACT_FILE)
    await query.edit_message_text(f"Contact Info:\n\n{contact['info']}", reply_markup=user_panel_back_button)

async def show_how_to_use(query):
    tutorial = load_data(TUTORIAL_FILE)
    await query.edit_message_text(f"How to use the bot:\n\n{tutorial['link']}", reply_markup=user_panel_back_button)

async def show_leaderboard(query):
    wallets = load_data(WALLET_FILE)
    users = load_data(USERS_FILE)
    
    sorted_users = sorted(wallets.items(), key=lambda item: item[1].get('balance', 0), reverse=True)
    
    text = "🏆 Leaderboard (Top 10 Earners):\n\n"
    if not sorted_users:
        text += "No users to display yet."

    for i, (user_id, wallet) in enumerate(sorted_users[:10], 1):
        user_info = users.get(user_id)
        if user_info:
            if user_info.get('hide_name'):
                name = "This user has hidden name"
            else:
                name = user_info.get('username') or user_info.get('first_name', 'Unknown')
            text += f"{i}. {name} - ₹{wallet['balance']:.2f}\n"
    
    await query.edit_message_text(text, reply_markup=user_panel_back_button)


# --- Admin Panel Logic ---

# ✅ FINAL FIX: This function correctly displays each link with its own "Open" and "Delete" buttons.
async def manage_links(query: Update):
    """Shows a management interface for links with Open and Delete options for each."""
    # This check is crucial for handling the callback from the ConversationHandler
    if isinstance(query, Update):
        query = query.callback_query

    links = load_data(LINKS_FILE)
    text = "🔗 **Manage Links**\n\nBelow are the current links. You can open them to check or delete them."
    buttons = []

    # Handle case where the links file is empty or corrupted.
    if not isinstance(links, list) or not links:
        text = "No links have been added yet."
    else:
        # Create a row of buttons for each valid link entry.
        for i, link in enumerate(links):
            # Defensive check: Only process valid link dictionaries to prevent crashes.
            if isinstance(link, dict) and 'title' in link and 'url' in link:
                buttons.append([
                    # Button 1: Opens the link for the admin to check.
                    InlineKeyboardButton(f"🔗 {link['title']}", url=link['url']),
                    # Button 2: Deletes this specific link using its index.
                    InlineKeyboardButton(f"❌ Delete", callback_data=f"delete_link_{i}")
                ])
    
    # Add the static control buttons at the end.
    buttons.append([InlineKeyboardButton("➕ Add New Link", callback_data="add_link_start")])
    buttons.append([InlineKeyboardButton("⬅️ Back", callback_data='admin_panel')])
    
    reply_markup = InlineKeyboardMarkup(buttons)
    # Use query.edit_message_text since this is always triggered by a button click.
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

async def handle_delete_link(query: Update, index: int):
    """Handles the deletion of a link by its index."""
    links = load_data(LINKS_FILE)
    try:
        # Remove the link at the specified index.
        links.pop(index)
        save_data(LINKS_FILE, links)
        await query.answer("Link deleted successfully.")
        # Refresh the 'Manage Links' view to show the updated list.
        await manage_links(query) 
    except IndexError:
        await query.answer("Error: Link not found. It might have been deleted already.", show_alert=True)
        await manage_links(query)


async def handle_add_link_title(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['link_title'] = update.message.text
    await update.message.reply_text("Now, send the URL for this link:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data='manage_links')]]))
    return AWAITING_LINK_URL

async def handle_add_link_url(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    title = context.user_data.pop('link_title', None)
    if not title:
        await update.message.reply_text(
            "An error occurred. Please try adding the link again from the beginning.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Manage Links", callback_data='manage_links')]]))
        return ConversationHandler.END

    url = update.message.text.strip()
    
    if not (url.startswith('http://') or url.startswith('https://')):
        await update.message.reply_text(
            "❌ Invalid URL. The URL must start with `http://` or `https://`. Please try adding the link again.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("⬅️ Back to Manage Links", callback_data='manage_links')
            ]])
        )
        return ConversationHandler.END

    links = load_data(LINKS_FILE)
    links.append({"title": title, "url": url})
    save_data(LINKS_FILE, links)
    
    await update.message.reply_text(
        "✅ Link added successfully!",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("⬅️ Back to Manage Links", callback_data='manage_links')
        ]])
    )
    return ConversationHandler.END

async def manage_verify_codes(query: Update):
    # This check is crucial for handling the callback from the ConversationHandler
    if isinstance(query, Update):
        query = query.callback_query
    codes = load_data(VERIFY_CODES_FILE)
    text = "🔐 Manage Verification Codes\n\nHere are the current codes:"
    buttons = []
    if not codes:
        text += "\n\nNo codes have been added yet."
    else:
        for code in codes:
            buttons.append([
                InlineKeyboardButton(f"`{code}`", callback_data="none"), # non-clickable
                InlineKeyboardButton(f"🗑️ Delete", callback_data=f"delete_vcode_{code}")
            ])

    buttons.append([InlineKeyboardButton("➕ Add New Code", callback_data="add_verify_code_start")])
    buttons.append([InlineKeyboardButton("⬅️ Back", callback_data='admin_panel')])
    reply_markup = InlineKeyboardMarkup(buttons)
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

async def handle_delete_verify_code(query: Update, code_to_delete: str):
    codes = load_data(VERIFY_CODES_FILE)
    if code_to_delete in codes:
        codes.remove(code_to_delete)
        save_data(VERIFY_CODES_FILE, codes)
        await query.answer("Code deleted successfully.")
        await manage_verify_codes(query) # Refresh
    else:
        await query.answer("Error: Code not found.", show_alert=True)
        await manage_verify_codes(query)

async def handle_add_verify_code(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    code = update.message.text.strip()
    codes = load_data(VERIFY_CODES_FILE)
    if code not in codes:
        codes.append(code)
        save_data(VERIFY_CODES_FILE, codes)
        await update.message.reply_text("✅ Verify code added!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Manage Codes", callback_data='manage_verify_codes')]]))
    else:
        await update.message.reply_text("This code already exists.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Manage Codes", callback_data='manage_verify_codes')]]))
    
    return ConversationHandler.END

async def handle_add_redeem_code(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['redeem_code'] = update.message.text.strip()
    await update.message.reply_text("Now, enter the reward amount (₹) for this code:", reply_markup=admin_panel_back_button)
    return AWAITING_REDEEM_VALUE_ADD

async def handle_add_redeem_value(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    code = context.user_data.pop('redeem_code')
    try:
        value = float(update.message.text)
    except ValueError:
        await update.message.reply_text("Invalid amount. Please enter a number.", reply_markup=admin_panel_back_button)
        return ConversationHandler.END
        
    codes = load_data(REDEEM_CODES_FILE)
    if code not in codes:
        codes[code] = {"reward": value, "claimed_by": None}
        save_data(REDEEM_CODES_FILE, codes)
        await update.message.reply_text(f"✅ Redeem code '{code}' for ₹{value} added!", reply_markup=admin_panel_back_button)
    else:
        await update.message.reply_text("This redeem code already exists.", reply_markup=admin_panel_back_button)

    return ConversationHandler.END

async def view_users(query, page=0):
    users = load_data(USERS_FILE)
    user_list = list(users.values())
    total_users = len(user_list)
    
    per_page = 50
    start = page * per_page
    end = start + per_page
    
    paginated_users = user_list[start:end]

    text = f"👥 Total Users: {total_users}\n\n"
    if not paginated_users:
        text += "No users to display on this page."
    else:
        for user in paginated_users:
            text += f"👤 Name: {user.get('first_name', 'N/A')} (@{user.get('username', 'N/A')})\n🆔 ID: `{user['id']}`\n\n"

    keyboard = []
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("◀️ Previous", callback_data=f"view_users_{page-1}"))
    if end < total_users:
        nav_buttons.append(InlineKeyboardButton("Next ▶️", callback_data=f"view_users_{page+1}"))
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data='admin_panel')])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    
async def handle_min_withdraw_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        amount = float(update.message.text)
        settings = load_data(SETTINGS_FILE)
        settings['min_withdraw'] = amount
        save_data(SETTINGS_FILE, settings)
        await update.message.reply_text(f"Minimum withdrawal amount set to ₹{amount}.", reply_markup=admin_panel_back_button)
    except ValueError:
        await update.message.reply_text("Invalid amount. Please enter a number.", reply_markup=admin_panel_back_button)
    
    return ConversationHandler.END

async def handle_user_id_for_balance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id_to_edit = update.message.text.strip()
    users = load_data(USERS_FILE)
    if user_id_to_edit in users:
        context.user_data['user_id_to_edit'] = user_id_to_edit
        wallet = get_user_wallet(user_id_to_edit)
        keyboard = [
            [InlineKeyboardButton("➕ Add", callback_data=f'balance_action_{user_id_to_edit}_add'),
             InlineKeyboardButton("➖ Cut", callback_data=f'balance_action_{user_id_to_edit}_cut')],
            [InlineKeyboardButton("⬅️ Back", callback_data='admin_panel')]
        ]
        await update.message.reply_text(f"Editing balance for User ID: {user_id_to_edit}\nCurrent Balance: ₹{wallet['balance']:.2f}\nChoose an action:", reply_markup=InlineKeyboardMarkup(keyboard))
        return AWAITING_BALANCE_ACTION
    else:
        await update.message.reply_text("User not found.", reply_markup=admin_panel_back_button)
        return ConversationHandler.END

async def handle_balance_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id_to_edit = context.user_data.pop('user_id_to_edit')
    action = context.user_data.pop('balance_action')
    try:
        amount = float(update.message.text)
    except ValueError:
        await update.message.reply_text("Invalid amount.", reply_markup=admin_panel_back_button)
        return ConversationHandler.END

    wallets = load_data(WALLET_FILE)
    user_wallet = get_user_wallet(user_id_to_edit)
    
    if action == 'add':
        user_wallet['balance'] += amount
    elif action == 'cut':
        user_wallet['balance'] -= amount
        
    wallets[user_id_to_edit] = user_wallet
    save_data(WALLET_FILE, wallets)

    await update.message.reply_text(f"Balance for user {user_id_to_edit} updated. New balance: ₹{user_wallet['balance']:.2f}", reply_markup=admin_panel_back_button)
    return ConversationHandler.END
    
async def send_message_menu(query):
    keyboard = [
        [InlineKeyboardButton("To All Users", callback_data='send_to_all')],
        [InlineKeyboardButton("To a Single User", callback_data='send_to_one')],
        [InlineKeyboardButton("⬅️ Back", callback_data='admin_panel')]
    ]
    await query.edit_message_text("Who should receive the message?", reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_message_content(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    message_text = update.message.text
    recipient_type = context.user_data.get('recipient')
    
    if recipient_type == 'all':
        users = load_data(USERS_FILE)
        count = 0
        for user_id in users.keys():
            try:
                await context.bot.send_message(chat_id=int(user_id), text=message_text)
                count += 1
            except Exception as e:
                logger.error(f"Failed to send message to {user_id}: {e}")
        await update.message.reply_text(f"Message sent to {count} users.", reply_markup=admin_panel_back_button)

    elif recipient_type == 'one_final':
        user_id = context.user_data.get('message_user_id')
        try:
            await context.bot.send_message(chat_id=int(user_id), text=message_text)
            await update.message.reply_text(f"Message sent to {user_id}.", reply_markup=admin_panel_back_button)
        except Exception as e:
            await update.message.reply_text(f"Failed to send message: {e}", reply_markup=admin_panel_back_button)
            
    context.user_data.clear()
    return ConversationHandler.END

async def handle_message_user_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.message.text.strip()
    users = load_data(USERS_FILE)
    if user_id in users:
        context.user_data['recipient'] = 'one_final'
        context.user_data['message_user_id'] = user_id
        await update.message.reply_text("Now enter the message content:", reply_markup=admin_panel_back_button)
        return AWAITING_MESSAGE_CONTENT
    else:
        await update.message.reply_text("User ID not found.", reply_markup=admin_panel_back_button)
        context.user_data.clear()
        return ConversationHandler.END

async def manage_users_menu(query):
    keyboard = [
        [InlineKeyboardButton("🚫 Ban a User", callback_data='ban_user'), InlineKeyboardButton("🔓 Unban a User", callback_data='unban_user')],
        [InlineKeyboardButton("📜 View Banned List", callback_data='view_banned')],
        [InlineKeyboardButton("⬅️ Back", callback_data='admin_panel')]
    ]
    await query.edit_message_text("Select a user management action:", reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id_str = update.message.text.strip()
    users = load_data(USERS_FILE)
    
    if user_id_str in users:
        user_to_ban = users[user_id_str]
        banned_users = load_data(BANNED_FILE)
        if not any(b['id'] == user_to_ban['id'] for b in banned_users):
            banned_users.append(user_to_ban)
            save_data(BANNED_FILE, banned_users)
            await update.message.reply_text(f"User {user_id_str} has been banned.", reply_markup=admin_panel_back_button)
        else:
            await update.message.reply_text("User is already banned.", reply_markup=admin_panel_back_button)
    else:
        await update.message.reply_text("User ID not found.", reply_markup=admin_panel_back_button)
    return ConversationHandler.END

async def handle_unban_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        user_id_to_unban = int(update.message.text.strip())
        banned_users = load_data(BANNED_FILE)
        user_found = False
        
        updated_banned_list = [user for user in banned_users if user['id'] != user_id_to_unban]

        if len(updated_banned_list) < len(banned_users):
             user_found = True

        if user_found:
            save_data(BANNED_FILE, updated_banned_list)
            await update.message.reply_text(f"User {user_id_to_unban} has been unbanned.", reply_markup=admin_panel_back_button)
        else:
            await update.message.reply_text("User not found in the banned list.", reply_markup=admin_panel_back_button)
    except ValueError:
        await update.message.reply_text("Invalid User ID.", reply_markup=admin_panel_back_button)
        
    return ConversationHandler.END

async def view_banned_users(query):
    banned = load_data(BANNED_FILE)
    text = "Banned Users:\n\n"
    if not banned:
        text += "The banned user list is empty."
    else:
        for user in banned:
            text += f"ID: `{user['id']}`, Username: @{user.get('username', 'N/A')}\n"
    
    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data='manage_users')]])
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

async def handle_manage_withdraw_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    search_id = update.message.text.strip()
    withdrawals = load_data(WITHDRAW_FILE)
    found_requests = []

    # Search by withdraw_id first then by user_id
    for user_id, reqs in withdrawals.items():
        for req in reqs:
            if str(req.get('withdraw_id')) == search_id and req.get('status') == 'pending':
                found_requests.append((user_id, req))
                
    if not found_requests and search_id in withdrawals:
        for req in withdrawals[search_id]:
             if req.get('status') == 'pending':
                found_requests.append((search_id, req))

    if not found_requests:
        await update.message.reply_text("No pending withdrawal found with that ID.", reply_markup=admin_panel_back_button)
        return ConversationHandler.END
        
    text = "Found Pending Requests:\n\n"
    keyboard = []
    for user_id, req in found_requests:
        text += (f"User ID: `{user_id}`\nWithdraw ID: `{req['withdraw_id']}`\n"
                 f"Amount: ₹{req['amount']}\nUPI: `{req['upi_id']}`\n\n")
        keyboard.append([
            InlineKeyboardButton(f"✅ Complete {req['withdraw_id']}", callback_data=f"complete_withdraw_{user_id}_{req['withdraw_id']}"),
            InlineKeyboardButton(f"🔁 Return {req['withdraw_id']}", callback_data=f"return_withdraw_{user_id}_{req['withdraw_id']}")
        ])
    
    keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data='admin_panel')])
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    return ConversationHandler.END

async def complete_withdraw(query, context, user_id, withdraw_id):
    withdrawals = load_data(WITHDRAW_FILE)
    user_reqs = withdrawals.get(str(user_id), [])
    req_to_process = None
    
    for req in user_reqs:
        if str(req.get('withdraw_id')) == str(withdraw_id):
            req_to_process = req
            break

    if not req_to_process:
        await query.answer("Request not found.", show_alert=True)
        await query.edit_message_text("Request not found, it might have been processed already.", reply_markup=admin_panel_back_button)
        return

    wallets = load_data(WALLET_FILE)
    if str(user_id) not in wallets:
        logger.error(f"Cannot complete withdrawal: User {user_id} has no wallet.")
        await query.edit_message_text(f"Error: User {user_id} wallet not found. Cannot process.", reply_markup=admin_panel_back_button)
        return

    wallets[str(user_id)]['withdrawn'] = wallets[str(user_id)].get('withdrawn', 0.0) + req_to_process['amount']
    save_data(WALLET_FILE, wallets)

    completed = load_data(COMPLETED_FILE)
    req_to_process['status'] = 'completed'
    completed.append(req_to_process)
    save_data(COMPLETED_FILE, completed)
    
    user_reqs.remove(req_to_process)
    if not user_reqs:
        del withdrawals[str(user_id)]
    else:
        withdrawals[str(user_id)] = user_reqs
    save_data(WITHDRAW_FILE, withdrawals)
    
    await query.edit_message_text(f"Withdrawal {withdraw_id} for user {user_id} marked as complete.", reply_markup=admin_panel_back_button)
    try:
        await context.bot.send_message(chat_id=int(user_id), text=f"✅ Your withdrawal request of ₹{req_to_process['amount']} has been completed.")
    except Exception as e:
        logger.error(f"Failed to notify user {user_id} about completion: {e}")

async def return_withdraw(query, context, user_id, withdraw_id):
    withdrawals = load_data(WITHDRAW_FILE)
    user_reqs = withdrawals.get(str(user_id), [])
    req_to_process = None

    for req in user_reqs:
        if str(req.get('withdraw_id')) == str(withdraw_id):
            req_to_process = req
            break

    if not req_to_process:
        await query.answer("Request not found.", show_alert=True)
        await query.edit_message_text("Request not found, it might have been processed already.", reply_markup=admin_panel_back_button)
        return

    wallets = load_data(WALLET_FILE)
    if str(user_id) not in wallets:
        logger.error(f"Cannot return withdrawal: User {user_id} has no wallet.")
        await query.edit_message_text(f"Error: User {user_id} wallet not found. Cannot process.", reply_markup=admin_panel_back_button)
        return

    wallets[str(user_id)]['balance'] += req_to_process['amount']
    save_data(WALLET_FILE, wallets)
    
    user_reqs.remove(req_to_process)
    if not user_reqs:
        del withdrawals[str(user_id)]
    else:
        withdrawals[str(user_id)] = user_reqs
    save_data(WITHDRAW_FILE, withdrawals)
    
    await query.edit_message_text(f"Withdrawal {withdraw_id} for user {user_id} has been returned. Balance refunded.", reply_markup=admin_panel_back_button)
    try:
        await context.bot.send_message(chat_id=int(user_id), text=f"🔁 Your withdrawal request of ₹{req_to_process['amount']} has been returned by the admin. The amount has been refunded to your wallet.")
    except Exception as e:
        logger.error(f"Failed to notify user {user_id} about return: {e}")

async def view_completed_withdrawals(query):
    completed = load_data(COMPLETED_FILE)
    text = "✅ Completed Withdrawals:\n\n"
    if not completed:
        text += "None yet."
    else:
        for req in completed:
            text += f"ID: {req['withdraw_id']}, Amount: ₹{req['amount']}, UPI: {req['upi_id']}\n"
    
    keyboard = [
        [InlineKeyboardButton("🗑️ Clear List", callback_data='clear_completed')],
        [InlineKeyboardButton("⬅️ Back", callback_data='admin_panel')]
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    
async def handle_contact_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    contact_info = update.message.text
    save_data(CONTACT_FILE, {"info": contact_info})
    await update.message.reply_text("✅ Contact info updated.", reply_markup=admin_panel_back_button)
    return ConversationHandler.END
    
async def handle_tutorial_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    tutorial_link = update.message.text
    save_data(TUTORIAL_FILE, {"link": tutorial_link})
    await update.message.reply_text("✅ Tutorial link updated.", reply_markup=admin_panel_back_button)
    return ConversationHandler.END

async def view_verify_code_usage(query):
    verified_users = load_data(VERIFIED_USERS_FILE)
    all_codes = load_data(VERIFY_CODES_FILE)
    usage_counts = {code: 0 for code in all_codes}
    
    for user_data in verified_users.values():
        for code in user_data.keys():
            if code in usage_counts:
                usage_counts[code] += 1
            
    text = "📊 Verification Code Usage:\n\n"
    if not usage_counts:
        text += "No codes have been used yet."
    else:
        for code, count in usage_counts.items():
            text += f"`{code}`: {count} times\n"
            
    await query.edit_message_text(text, reply_markup=admin_panel_back_button, parse_mode='Markdown')

# --- Conversation Fallback ---
async def return_to_main_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Ends conversation and returns user to their main panel."""
    query = update.callback_query
    await query.answer()
    context.user_data.clear()

    if query.from_user.id == ADMIN_ID:
        await admin_panel(update, context)
    else:
        await user_panel(update, context)
    
    return ConversationHandler.END

# --- Main Bot Execution ---
def main() -> None:
    """Start the bot."""
    ensure_data_files()
    
    # Use your actual bot token here
    application = Application.builder().token("7560387775:AAGkU96BfK1bH7XEmLAaiNEkRncWMtqLkXo").build()

    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(button)],
        states={
            AWAITING_REDEEM_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_redeem_code)],
            AWAITING_VERIFY_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_verify_code)],
            # Withdraw Flow
            AWAITING_WITHDRAW_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_withdraw_amount)],
            AWAITING_WITHDRAW_UPI: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_withdraw_upi)],
            AWAITING_WITHDRAW_CONFIRMATION: [CallbackQueryHandler(button)],
            # Admin Link Management
            AWAITING_LINK_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_add_link_title)],
            AWAITING_LINK_URL: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_add_link_url)],
            # Admin Verify Code Management
            AWAITING_VERIFY_CODE_ADD: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_add_verify_code)],
            # Other Admin flows
            AWAITING_REDEEM_CODE_ADD: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_add_redeem_code)],
            AWAITING_REDEEM_VALUE_ADD: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_add_redeem_value)],
            AWAITING_MIN_WITHDRAW_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_min_withdraw_amount)],
            AWAITING_USER_ID_FOR_BALANCE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_user_id_for_balance)],
            AWAITING_BALANCE_ACTION: [CallbackQueryHandler(button)],
            AWAITING_BALANCE_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_balance_amount)],
            AWAITING_MESSAGE_USER_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message_user_id)],
            AWAITING_MESSAGE_CONTENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message_content)],
            AWAITING_BAN_USER_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_ban_user)],
            AWAITING_UNBAN_USER_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_unban_user)],
            AWAITING_MANAGE_WITHDRAW_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_manage_withdraw_id)],
            AWAITING_CONTACT_INFO: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_contact_info)],
            AWAITING_TUTORIAL_INFO: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_tutorial_info)],
        },
        fallbacks=[
            CommandHandler('start', start),
            # This allows backing out of a conversation state
            CallbackQueryHandler(return_to_main_panel, pattern='^main_panel$'),
            CallbackQueryHandler(return_to_main_panel, pattern='^admin_panel$'),
            # These fallbacks allow re-entering the management menus from a conversation
            CallbackQueryHandler(manage_links, pattern='^manage_links$'),
            CallbackQueryHandler(manage_verify_codes, pattern='^manage_verify_codes$'),
        ],
        per_message=False,
        # Allow re-entry into the conversation via different buttons
        allow_reentry=True
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(conv_handler)
    # Add a fallback handler for any button clicks not caught by the conversation
    application.add_handler(CallbackQueryHandler(button))

    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()