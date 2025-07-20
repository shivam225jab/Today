import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ConversationHandler

# Import the new database module
import database as db

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Admin ID
ADMIN_ID = 5924971946 # Replace with your Admin ID

# Conversation states remain the same
(
    USER_INPUT, AWAITING_REDEEM_CODE, AWAITING_VERIFY_CODE, AWAITING_LINK_TITLE,
    AWAITING_LINK_URL, AWAITING_VERIFY_CODE_ADD, AWAITING_REDEEM_CODE_ADD,
    AWAITING_REDEEM_VALUE_ADD, AWAITING_MIN_WITHDRAW_AMOUNT, AWAITING_USER_ID_FOR_BALANCE,
    AWAITING_BALANCE_ACTION, AWAITING_BALANCE_AMOUNT, AWAITING_MESSAGE_RECIPIENT,
    AWAITING_MESSAGE_CONTENT, AWAITING_MESSAGE_USER_ID, AWAITING_BAN_USER_ID,
    AWAITING_UNBAN_USER_ID, AWAITING_MANAGE_WITHDRAW_ID, AWAITING_CONTACT_INFO,
    AWAITING_TUTORIAL_INFO, AWAITING_WITHDRAW_AMOUNT, AWAITING_WITHDRAW_UPI,
    AWAITING_WITHDRAW_CONFIRMATION,
) = range(23)

# Reusable Keyboards
main_panel_markup = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Panel", callback_data='main_panel')]])
admin_panel_back_button = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data='admin_panel')]])
user_panel_back_button = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data='user_panel')]])


# --- Bot Start and Main Menu ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    user = update.effective_user
    
    if db.is_user_banned(user.id):
        await update.message.reply_text("You are banned from using this bot.")
        return

    # Add or update user in the database
    db.add_or_update_user(user.id, user.username, user.first_name)

    if user.id == ADMIN_ID:
        await admin_panel(update, context)
    else:
        await user_panel(update, context)

# --- USER-FACING FUNCTIONS (Refactored) ---

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

async def get_code(query: Update):
    """Shows active links to the user from the database."""
    links = db.get_links()

    if not links:
        await query.edit_message_text("No links available.", reply_markup=user_panel_back_button)
        return

    buttons = [[InlineKeyboardButton(link['title'], url=link['url'])] for link in links]
    buttons.append([InlineKeyboardButton("⬅️ Back", callback_data='user_panel')])
    
    reply_markup = InlineKeyboardMarkup(buttons)
    await query.edit_message_text("Here are the available links. Please visit them to find a verification code:", reply_markup=reply_markup)

async def handle_verify_code(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    code = update.message.text.strip()
    
    if db.has_user_verified_code(user_id, code):
        await update.message.reply_text("You have already used this verification code.", reply_markup=user_panel_back_button)
        return ConversationHandler.END

    valid_codes = db.get_verification_codes()
    if code in valid_codes:
        db.verify_user_code(user_id, code)
        await update.message.reply_text("✅ Verification successful!", reply_markup=user_panel_back_button)
    else:
        await update.message.reply_text("❌ Invalid code. Please try again.", reply_markup=user_panel_back_button)
    return ConversationHandler.END

async def handle_redeem_code(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user

    if not db.has_user_verified_any_code(user.id):
        await update.message.reply_text("You must verify at least one code to claim a reward.", reply_markup=user_panel_back_button)
        return ConversationHandler.END

    code = update.message.text.strip()
    status, message = db.redeem_code(user.id, code)

    await update.message.reply_text(message, reply_markup=user_panel_back_button)
    return ConversationHandler.END

async def show_wallet(query: Update):
    user_id = query.from_user.id
    wallet = db.get_user_wallet(user_id)
    text = f"💰 Your Wallet:\n\nBalance: ₹{wallet['balance']:.2f}\nTotal Withdrawn: ₹{wallet['withdrawn']:.2f}"
    await query.edit_message_text(text, reply_markup=user_panel_back_button)

async def start_withdraw_flow(query: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the withdrawal conversation."""
    min_withdraw = float(db.get_setting('min_withdraw'))
    wallet = db.get_user_wallet(query.from_user.id)
    
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
    min_withdraw = float(db.get_setting('min_withdraw'))
    wallet = db.get_user_wallet(user_id)

    if amount < min_withdraw:
        await update.message.reply_text(f"Minimum withdrawal amount is ₹{min_withdraw}. Please try again.", reply_markup=user_panel_back_button)
        return ConversationHandler.END

    if wallet['balance'] < amount:
        await update.message.reply_text("Insufficient balance.", reply_markup=user_panel_back_button)
        return ConversationHandler.END

    context.user_data['withdraw_amount'] = amount
    await update.message.reply_text("Amount received. Now, please enter your UPI ID:")
    return AWAITING_WITHDRAW_UPI

async def handle_withdraw_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Submits the withdrawal request after user confirmation."""
    query = update.callback_query
    user_id = query.from_user.id
    amount = context.user_data.get('withdraw_amount')
    upi_id = context.user_data.get('upi_id')

    if not amount or not upi_id:
        await query.edit_message_text("An error occurred. Missing withdrawal details.", reply_markup=user_panel_back_button)
        return ConversationHandler.END
    
    # The function now returns the new request ID
    withdraw_id = db.submit_withdraw_request(user_id, amount, upi_id)

    await query.edit_message_text(f"✅ Withdrawal request of ₹{amount} submitted successfully! Your Withdraw ID is {withdraw_id}.", reply_markup=user_panel_back_button)
    context.user_data.clear()
    return ConversationHandler.END

async def show_pending_withdraw(query: Update):
    user_id = query.from_user.id
    user_withdrawals = db.get_pending_withdrawals(user_id)

    if not user_withdrawals:
        await query.edit_message_text("You have no pending withdrawals.", reply_markup=user_panel_back_button)
        return

    text = "Your pending withdrawals:\n\n"
    for req in user_withdrawals:
        text += f"ID: {req['id']}, Amount: ₹{req['amount']:.2f}, UPI: {req['upi_id']}\n"
    
    await query.edit_message_text(text, reply_markup=user_panel_back_button)

async def show_leaderboard(query):
    """Displays the top 10 users by balance from the database."""
    leaderboard = db.get_leaderboard(10)
    
    text = "🏆 Leaderboard (Top 10 Earners):\n\n"
    if not leaderboard:
        text += "No users to display yet."
    else:
        for i, user in enumerate(leaderboard, 1):
            name = user['username'] or user['first_name'] or 'Unknown'
            text += f"{i}. {name} - ₹{user['balance']:.2f}\n"
    
    await query.edit_message_text(text, reply_markup=user_panel_back_button)


# --- ADMIN-FACING FUNCTIONS (Refactored) ---

async def manage_links(query: Update):
    """Shows a management interface for links with Open and Delete options."""
    if isinstance(query, Update):
        query = query.callback_query

    links = db.get_links()
    text = "🔗 **Manage Links**\n\nBelow are the current links."
    buttons = []

    if not links:
        text = "No links have been added yet."
    else:
        for link in links:
            buttons.append([
                InlineKeyboardButton(f"🔗 {link['title']}", url=link['url']),
                InlineKeyboardButton(f"❌ Delete", callback_data=f"delete_link_{link['id']}")
            ])
    
    buttons.append([InlineKeyboardButton("➕ Add New Link", callback_data="add_link_start")])
    buttons.append([InlineKeyboardButton("⬅️ Back", callback_data='admin_panel')])
    
    reply_markup = InlineKeyboardMarkup(buttons)
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

async def handle_delete_link(query: Update, link_id: int):
    """Handles the deletion of a link by its ID."""
    db.delete_link(link_id)
    await query.answer("Link deleted successfully.")
    await manage_links(query) # Refresh the view

async def handle_add_link_url(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Adds a new link to the database."""
    title = context.user_data.pop('link_title')
    url = update.message.text.strip()
    
    if not (url.startswith('http://') or url.startswith('https://')):
        await update.message.reply_text("❌ Invalid URL. Must start with `http://` or `https://`.")
        return ConversationHandler.END

    db.add_link(title, url)
    await update.message.reply_text("✅ Link added successfully!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data='manage_links')]]))
    return ConversationHandler.END

async def handle_min_withdraw_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Sets the minimum withdrawal amount in the database."""
    try:
        amount = float(update.message.text)
        db.set_setting('min_withdraw', str(amount))
        await update.message.reply_text(f"Minimum withdrawal amount set to ₹{amount}.", reply_markup=admin_panel_back_button)
    except ValueError:
        await update.message.reply_text("Invalid amount.", reply_markup=admin_panel_back_button)
    return ConversationHandler.END

async def handle_ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        user_id_to_ban = int(update.message.text.strip())
        db.ban_user(user_id_to_ban)
        await update.message.reply_text(f"User {user_id_to_ban} has been banned.", reply_markup=admin_panel_back_button)
    except ValueError:
        await update.message.reply_text("Invalid User ID.", reply_markup=admin_panel_back_button)
    return ConversationHandler.END

async def handle_unban_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        user_id_to_unban = int(update.message.text.strip())
        db.unban_user(user_id_to_unban)
        await update.message.reply_text(f"User {user_id_to_unban} has been unbanned.", reply_markup=admin_panel_back_button)
    except ValueError:
        await update.message.reply_text("Invalid User ID.", reply_markup=admin_panel_back_button)
    return ConversationHandler.END

async def view_banned_users(query: Update):
    banned_users = db.get_banned_users()
    text = "Banned Users:\n\n"
    if not banned_users:
        text += "The banned user list is empty."
    else:
        for user in banned_users:
            text += f"ID: `{user['id']}`, Username: @{user.get('username', 'N/A')}\n"
    
    reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data='manage_users')]])
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

async def complete_withdraw(query: Update, context: ContextTypes.DEFAULT_TYPE, user_id: str, withdraw_id: str):
    """Marks a withdrawal as complete."""
    request = db.get_withdrawal_by_id(int(withdraw_id))
    if not request:
        await query.answer("Request not found.", show_alert=True)
        return

    db.update_withdrawal_status(int(withdraw_id), 'completed', request['amount'], request['user_id'])
    
    await query.edit_message_text(f"Withdrawal {withdraw_id} for user {user_id} marked as complete.", reply_markup=admin_panel_back_button)
    try:
        await context.bot.send_message(chat_id=int(user_id), text=f"✅ Your withdrawal request of ₹{request['amount']} has been completed.")
    except Exception as e:
        logger.error(f"Failed to notify user {user_id} about completion: {e}")

async def return_withdraw(query: Update, context: ContextTypes.DEFAULT_TYPE, user_id: str, withdraw_id: str):
    """Returns a withdrawal amount to the user's balance."""
    request = db.get_withdrawal_by_id(int(withdraw_id))
    if not request:
        await query.answer("Request not found.", show_alert=True)
        return

    db.update_withdrawal_status(int(withdraw_id), 'returned', request['amount'], request['user_id'])

    await query.edit_message_text(f"Withdrawal {withdraw_id} for user {user_id} has been returned. Balance refunded.", reply_markup=admin_panel_back_button)
    try:
        await context.bot.send_message(chat_id=int(user_id), text=f"🔁 Your withdrawal request of ₹{request['amount']} has been returned. The amount has been refunded.")
    except Exception as e:
        logger.error(f"Failed to notify user {user_id} about return: {e}")


# --- Main Bot Execution ---
def main() -> None:
    """Start the bot."""
    # Initialize the database on first run
    db.init_db()
    
    # Use your actual bot token here from environment variables for security
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "7560387775:AAGkU96BfK1bH7XEmLAaiNEkRncWMtqLkXo")
    if not bot_token:
        logger.error("FATAL: TELEGRAM_BOT_TOKEN is not set.")
        return

    application = Application.builder().token(bot_token).build()

    # The ConversationHandler logic remains largely the same, as it deals with flow control.
    # The actual data operations within the handlers have been updated.
    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(button)],
        states={
            AWAITING_REDEEM_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_redeem_code)],
            AWAITING_VERIFY_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_verify_code)],
            AWAITING_WITHDRAW_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_withdraw_amount)],
            AWAITING_WITHDRAW_UPI: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_withdraw_upi)],
            AWAITING_WITHDRAW_CONFIRMATION: [CallbackQueryHandler(button)],
            AWAITING_LINK_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_add_link_title)],
            AWAITING_LINK_URL: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_add_link_url)],
            AWAITING_BAN_USER_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_ban_user)],
            AWAITING_UNBAN_USER_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_unban_user)],
            AWAITING_MIN_WITHDRAW_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_min_withdraw_amount)],
            # ... include other states from your original bot as needed
        },
        fallbacks=[
            CommandHandler('start', start),
            CallbackQueryHandler(admin_panel, pattern='^admin_panel$'),
            CallbackQueryHandler(user_panel, pattern='^user_panel$'),
        ],
        per_message=False,
        allow_reentry=True
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(conv_handler)
    application.add_handler(CallbackQueryHandler(button)) # Fallback for non-conversation buttons

    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()