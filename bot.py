import logging
import pandas as pd
import os
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
# MessageHandler and filters to catch text inputs
from telegram.ext import (ApplicationBuilder, ContextTypes, CommandHandler, 
                          CallbackQueryHandler, MessageHandler, filters)

# Load environment variables
load_dotenv()

# --- Configuration ---
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
YOUR_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
DATA_FILE = os.getenv("DATA_FILE", "my_cards.csv")

if not TOKEN or not YOUR_CHAT_ID:
    raise ValueError("Error: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not found in .env file.")

MONTH_NAMES = ["January", "February", "March", "April", "May", "June",
               "July", "August", "September", "October", "November", "December"]

COLUMN_DTYPES = {
    "Bank": "object", "Card Name": "object", "Annual Fee": "float",
    "Card Expiry (MM/YY)": "object", "Month of Annual Fee": "object",
    "Date Applied": "datetime64[ns]", "Date Approved": "datetime64[ns]",
    "Date Received Card": "datetime64[ns]", "Date Activated Card": "datetime64[ns]",
    "First Charge Date": "datetime64[ns]", "Image Filename": "object",
    "Sort Order": "int",
    "Notes": "object", "Cancellation Date": "datetime64[ns]", "Re-apply Date": "datetime64[ns]",
    "Tags": "object",
    "Bonus Offer": "object", "Min Spend": "float", 
    "Min Spend Deadline": "datetime64[ns]", "Bonus Status": "object",
    "Last 4 Digits": "object", "Current Spend": "float",
    "FeeWaivedCount": "int", "FeePaidCount": "int",
    "LastFeeActionYear": "int", "LastFeeAction": "object"
}

# --- Helper Functions ---

def load_data():
    """Reads the CSV file."""
    if not os.path.exists(DATA_FILE):
        return pd.DataFrame() 
    df = pd.read_csv(DATA_FILE)
    df = df.astype(COLUMN_DTYPES)
    return df

def save_data(df):
    """Saves the dataframe."""
    df.to_csv(DATA_FILE, index=False)

def get_card_list_message(df, mode="text", width=32):
    """Generates the string for the card list based on the selected mode."""
    active_cards = df[pd.isna(df['Cancellation Date'])].sort_values(by="Sort Order")
    
    if active_cards.empty:
        return "No active cards found."

    if mode == "text":
        # --- Clean Text View ---
        message = "📂 *Your Active Cards*\n\n"
        for idx, row in active_cards.iterrows():
            fee = f"${row['Annual Fee']:.2f}"
            if row['Annual Fee'] == 0:
                fee = "Free"
            
            message += f"💳 *{row['Bank']} {row['Card Name']}*\n"
            message += f"   💰 {fee}   🗓️ {row['Month of Annual Fee']}\n\n"
        return message

    else:
        # --- Dynamic Table View ---
        fee_col_w = 9 
        due_col_w = 3
        name_col_w = max(10, width - fee_col_w - due_col_w - 1) 
        
        message = "📂 *Your Active Cards*\n```\n"
        
        # Header
        header = f"{'Card':<{name_col_w}} {'Fee':>{fee_col_w}} {'Due':>{due_col_w}}"
        message += header + "\n"
        message += "-" * width + "\n"

        for idx, row in active_cards.iterrows():
            full_name = f"{row['Bank']} {row['Card Name']}"
            if len(full_name) > name_col_w:
                display_name = full_name[:name_col_w-1] + "…"
            else:
                display_name = full_name

            fee = f"{row['Annual Fee']:.2f}" 
            month = row['Month of Annual Fee'][:3] 

            # Add dots to lead the eye
            row_str = f"{display_name:.<{name_col_w}} {fee:>{fee_col_w}} {month:>{due_col_w}}"
            message += row_str + "\n"

        message += "```"
        return message

# --- Bot Command Functions ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends the main menu."""
    msg = (
        "💳 *Card Bot Ready!*\n\n"
        "/cards - List all cards\n"
        "/info - Deep card details\n"
        "/fees - Check upcoming fees\n"
        "/bonus - Check bonus status\n"
        "/track - Add spend to bonus\n"
        "/stats - Portfolio analysis"
    )
    await context.bot.send_message(chat_id=update.effective_chat.id, text=msg, parse_mode='Markdown')

async def list_cards(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Command: /cards - Shows cards with view options."""
    df = load_data()
    current_mode = context.user_data.get('view_mode', 'text')
    current_width = context.user_data.get('table_width', 32)
    
    message_text = get_card_list_message(df, mode=current_mode, width=current_width)
    
    keyboard = []
    if current_mode == 'text':
        keyboard.append([InlineKeyboardButton("📊 Switch to Table View", callback_data="set_view_table")])
    else:
        keyboard.append([InlineKeyboardButton("📝 Switch to Text View", callback_data="set_view_text")])
        keyboard.append([InlineKeyboardButton("⚙️ Adjust Width", callback_data="width_menu")])

    keyboard.append([InlineKeyboardButton("🏠 Home", callback_data="home")])

    await context.bot.send_message(
        chat_id=update.effective_chat.id, 
        text=message_text, 
        reply_markup=InlineKeyboardMarkup(keyboard), 
        parse_mode='Markdown'
    )

async def check_fees(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Checks for annual fees due."""
    df = load_data()
    df = df[pd.isna(df['Cancellation Date'])]
    
    today = datetime.now()
    current_month_idx = today.month - 1
    next_month_idx = (current_month_idx + 1) % 12
    current_year = today.year
    
    current_month_name = MONTH_NAMES[current_month_idx]
    next_month_name = MONTH_NAMES[next_month_idx]
    
    message = f"📅 *Fee Status Report*\n\n"
    
    this_month_cards = df[df["Month of Annual Fee"] == current_month_name]
    message += f"*Due This Month ({current_month_name}):*\n"
    if this_month_cards.empty:
        message += "No fees due.\n"
    else:
        for idx, row in this_month_cards.iterrows():
            status = "🔴 (Action Needed)"
            if row['LastFeeActionYear'] == current_year:
                status = f"({row['LastFeeAction']}) ✅"
            message += f"- {row['Bank']} {row['Card Name']}: ${row['Annual Fee']:.2f} {status}\n"

    next_month_cards = df[df["Month of Annual Fee"] == next_month_name]
    message += f"\n*Due Next Month ({next_month_name}):*\n"
    if next_month_cards.empty:
        message += "No fees due.\n"
    else:
        for idx, row in next_month_cards.iterrows():
            message += f"- {row['Bank']} {row['Card Name']}: ${row['Annual Fee']:.2f}\n"
            
    keyboard = [[InlineKeyboardButton("🏠 Home", callback_data="home")]]
    await context.bot.send_message(chat_id=update.effective_chat.id, text=message, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

async def check_bonuses(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lists active bonuses."""
    df = load_data()
    bonus_cards = df[
        (pd.isna(df['Cancellation Date'])) & 
        (df['Bonus Status'].isin(['In Progress', 'Not Started'])) &
        (pd.notna(df['Min Spend Deadline']))
    ]

    keyboard = [[InlineKeyboardButton("🏠 Home", callback_data="home")]]

    if bonus_cards.empty:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="🎉 No active bonuses!", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    message = "🎯 *Active Bonus Tracker*\n\n"
    for idx, row in bonus_cards.iterrows():
        min_spend = row['Min Spend']
        current = row['Current Spend']
        remaining = max(0, min_spend - current)
        deadline = row['Min Spend Deadline'].strftime('%d %b %Y')
        
        message += f"🏆 *{row['Bank']} {row['Card Name']}*\n"
        message += f"   Left: ${remaining:,.2f} (of ${min_spend:,.2f})\n"
        message += f"   Deadline: {deadline}\n\n"

    await context.bot.send_message(chat_id=update.effective_chat.id, text=message, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

async def portfolio_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Command: /stats - Calculates summary statistics."""
    df = load_data()
    active_cards = df[pd.isna(df['Cancellation Date'])]
    
    total_cards = len(active_cards)
    total_fees = active_cards['Annual Fee'].sum()
    total_waived = df['FeeWaivedCount'].sum() # Includes cancelled history
    total_paid = df['FeePaidCount'].sum()
    
    message = "📊 *Portfolio Stats*\n\n"
    message += f"💳 *Total Active Cards:* {total_cards}\n"
    message += f"💰 *Total Annual Liability:* ${total_fees:,.2f}\n\n"
    
    message += "🏆 *Fee History (Lifetime)*\n"
    message += f"✅ Waived: {total_waived} times\n"
    message += f"💸 Paid: {total_paid} times\n"

    keyboard = [[InlineKeyboardButton("🏠 Home", callback_data="home")]]
    await context.bot.send_message(chat_id=update.effective_chat.id, text=message, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

async def track_spend_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Command: /track - Shows buttons for cards with active bonuses."""
    df = load_data()
    # Filter for active bonuses
    bonus_cards = df[
        (pd.isna(df['Cancellation Date'])) & 
        (df['Bonus Status'].isin(['In Progress', 'Not Started'])) &
        (pd.notna(df['Min Spend Deadline']))
    ]

    if bonus_cards.empty:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="🎉 No active bonuses to track!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Home", callback_data="home")]]))
        return

    keyboard = []
    # Create a button for each card
    for idx, row in bonus_cards.iterrows():
        button_text = f"{row['Bank']} {row['Card Name']}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"track_select_{idx}")])
    
    keyboard.append([InlineKeyboardButton("🏠 Home", callback_data="home")])

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="🛍️ *Select a card to add spend:*",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def card_info_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Command: /info - Shows buttons for all active cards to view details."""
    df = load_data()
    active_cards = df[pd.isna(df['Cancellation Date'])].sort_values(by="Sort Order")

    if active_cards.empty:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="No cards found.")
        return

    keyboard = []
    # Create buttons, 2 per row for compactness
    row_buttons = []
    for idx, row in active_cards.iterrows():
        button_text = f"{row['Bank']} {row['Card Name']}"
        # If name is very long, truncate for button
        if len(button_text) > 20: 
            button_text = button_text[:18] + ".."
            
        row_buttons.append(InlineKeyboardButton(button_text, callback_data=f"info_select_{idx}"))
        
        if len(row_buttons) == 2:
            keyboard.append(row_buttons)
            row_buttons = []
    
    # Add remaining button if odd number
    if row_buttons:
        keyboard.append(row_buttons)

    keyboard.append([InlineKeyboardButton("🏠 Home", callback_data="home")])

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="ℹ️ *Select a card for details:*",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def send_weekly_notifications(context: ContextTypes.DEFAULT_TYPE):
    """Scheduled job for fee reminders."""
    df = load_data()
    df = df[pd.isna(df['Cancellation Date'])]
    
    today = datetime.now()
    current_month_name = MONTH_NAMES[today.month - 1]
    current_year = today.year
    
    due_cards = df[
        (df["Month of Annual Fee"] == current_month_name) & 
        (df["LastFeeActionYear"] != current_year)
    ]
    
    if due_cards.empty:
        return

    await context.bot.send_message(chat_id=YOUR_CHAT_ID, text=f"🔔 *Weekly Fee Reminder ({current_month_name})*", parse_mode='Markdown')
    
    for idx, row in due_cards.iterrows():
        card_name = f"{row['Bank']} {row['Card Name']}"
        fee = row['Annual Fee']
        keyboard = [
            [InlineKeyboardButton("✅ Waived", callback_data=f"waived_{idx}"),
             InlineKeyboardButton("💰 Paid", callback_data=f"paid_{idx}")],
            [InlineKeyboardButton("❌ Ignore", callback_data=f"ignore_{idx}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(chat_id=YOUR_CHAT_ID, text=f"*{card_name}*\nFee: ${fee:.2f}", reply_markup=reply_markup, parse_mode='Markdown')

# --- BUTTON HANDLER ---
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles all button interactions."""
    query = update.callback_query
    await query.answer() 
    
    data = query.data

    # --- HOME NAVIGATION ---
    if data == "home":
        msg = (
            "💳 *Card Bot Ready!*\n\n"
            "/cards - List all cards\n"
            "/info - Deep card details\n"
            "/fees - Check upcoming fees\n"
            "/bonus - Check bonus status\n"
            "/track - Add spend to bonus\n"
            "/stats - Portfolio analysis"
        )
        try:
            await query.edit_message_text(text=msg, parse_mode='Markdown')
        except:
            await context.bot.send_message(chat_id=update.effective_chat.id, text=msg, parse_mode='Markdown')
        return

    # --- TRACK SPEND LOGIC ---
    if data.startswith("track_select_"):
        card_index = int(data.split("_")[2])
        # Save which card we are tracking to session memory
        context.user_data['tracking_card_index'] = card_index
        context.user_data['awaiting_spend_input'] = True
        
        await query.edit_message_text(text="💵 How much did you spend? (Type a number, e.g., 50.50)")
        return

    # --- INFO DISPLAY LOGIC ---
    if data.startswith("info_select_"):
        card_index = int(data.split("_")[2])
        df = load_data()
        card = df.loc[card_index]
        
        # Build Detail String
        info_msg = f"💳 *{card['Bank']} {card['Card Name']}*\n"
        if card['Last 4 Digits']:
            info_msg += f"Ends in: `{card['Last 4 Digits']}`\n"
        info_msg += "\n"
        
        info_msg += f"📅 *Applied:* {pd.to_datetime(card['Date Applied']).strftime('%d %b %Y') if pd.notna(card['Date Applied']) else 'N/A'}\n"
        info_msg += f"📅 *Expiry:* {card['Card Expiry (MM/YY)']}\n"
        info_msg += f"💰 *Annual Fee:* ${card['Annual Fee']:.2f} ({card['Month of Annual Fee']})\n\n"
        
        if card['Notes']:
            info_msg += f"📝 *Notes:*\n_{card['Notes']}_\n\n"
            
        if card['Tags']:
            info_msg += f"🏷️ *Tags:* {card['Tags']}"

        keyboard = [
            [InlineKeyboardButton("🔙 Back to List", callback_data="info_menu")],
            [InlineKeyboardButton("🏠 Home", callback_data="home")]
        ]
        await query.edit_message_text(text=info_msg, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data == "info_menu":
        # Call the menu function again
        await card_info_menu(update, context)
        return

    # --- VIEW MODES ---
    if data == "set_view_table":
        context.user_data['view_mode'] = 'table'
        await refresh_cards_message(query, context)
        return
    elif data == "set_view_text":
        context.user_data['view_mode'] = 'text'
        context.user_data['awaiting_custom_width'] = False 
        await refresh_cards_message(query, context)
        return

    # --- WIDTH MENU ---
    elif data == "width_menu":
        keyboard = [
            [InlineKeyboardButton("Narrow (28)", callback_data="set_width_28"),
             InlineKeyboardButton("Normal (33)", callback_data="set_width_33"),
             InlineKeyboardButton("Wide (38)", callback_data="set_width_38")],
            [InlineKeyboardButton("✏️ Custom", callback_data="set_width_custom")],
            [InlineKeyboardButton("🔙 Back", callback_data="set_view_table")]
        ]
        await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(keyboard))
        return
    elif data == "set_width_custom":
        context.user_data['awaiting_custom_width'] = True
        await query.edit_message_text("📏 Please type a number for the table width (e.g. 45):")
        return
    elif data.startswith("set_width_"):
        new_width = int(data.split("_")[2])
        context.user_data['table_width'] = new_width
        await refresh_cards_message(query, context)
        return

    # --- FEE ACTIONS ---
    elif "_" in data:
        # Expected format: action_index (e.g. waived_5)
        parts = data.split("_")
        # Safety check to ensure we don't crash on other button types
        if len(parts) == 2 and parts[0] in ["waived", "paid", "ignore"]:
            action, card_index = parts
            card_index = int(card_index)
            
            if action == "ignore":
                await query.edit_message_text(text=f"Skipped notification for this card.")
                return

            df = load_data()
            current_year = datetime.now().year
            card_name = f"{df.loc[card_index, 'Bank']} {df.loc[card_index, 'Card Name']}"
            
            if action == "waived":
                df.loc[card_index, "FeeWaivedCount"] += 1
                df.loc[card_index, "LastFeeAction"] = "Waived"
                new_text = f"✅ Marked *{card_name}* as *Waived*!"
            elif action == "paid":
                df.loc[card_index, "FeePaidCount"] += 1
                df.loc[card_index, "LastFeeAction"] = "Paid"
                new_text = f"💰 Marked *{card_name}* as *Paid*!"
                
            df.loc[card_index, "LastFeeActionYear"] = current_year
            save_data(df)
            
            keyboard = [[InlineKeyboardButton("🏠 Home", callback_data="home")]]
            await query.edit_message_text(text=new_text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

# --- TEXT MESSAGE HANDLER ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Catches text messages. Used for custom width input AND spend tracking."""
    text = update.message.text.strip()

    # 1. Handle Custom Table Width
    if context.user_data.get('awaiting_custom_width'):
        if text.isdigit():
            width = int(text)
            if 20 <= width <= 100:
                context.user_data['table_width'] = width
                context.user_data['awaiting_custom_width'] = False 
                await update.message.reply_text(f"✅ Width set to {width}.")
                await list_cards(update, context)
            else:
                await update.message.reply_text("⚠️ Enter number between 20-100.")
        else:
            await update.message.reply_text("⚠️ Please enter a number.")
        return

    # 2. Handle Spend Tracking Input
    if context.user_data.get('awaiting_spend_input'):
        # Clean input (remove $ or ,)
        clean_text = text.replace('$', '').replace(',', '')
        try:
            amount_added = float(clean_text)
            card_index = context.user_data.get('tracking_card_index')
            
            # Load, Update, Save
            df = load_data()
            current_spend = df.loc[card_index, "Current Spend"]
            new_spend = current_spend + amount_added
            df.loc[card_index, "Current Spend"] = new_spend
            
            # Check if Bonus is met
            min_spend = df.loc[card_index, "Min Spend"]
            bonus_status = df.loc[card_index, "Bonus Status"]
            
            msg = f"✅ Added ${amount_added:,.2f}. Total: ${new_spend:,.2f}"
            
            # Auto-update status if met
            if new_spend >= min_spend and min_spend > 0 and bonus_status != "Met":
                df.loc[card_index, "Bonus Status"] = "Met"
                msg += "\n🎉 **Congratulations! Minimum spend met!**"
            elif min_spend > 0:
                remaining = min_spend - new_spend
                msg += f"\n📉 ${remaining:,.2f} left to go."

            save_data(df)
            
            # Reset state
            context.user_data['awaiting_spend_input'] = False
            context.user_data['tracking_card_index'] = None
            
            keyboard = [[InlineKeyboardButton("🏠 Home", callback_data="home")]]
            await update.message.reply_text(msg, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
            
        except ValueError:
            await update.message.reply_text("⚠️ Invalid number. Please try again (e.g. 50.50).")
        return

async def refresh_cards_message(query, context):
    """Helper to re-render the card list."""
    df = load_data()
    mode = context.user_data.get('view_mode', 'text')
    width = context.user_data.get('table_width', 32)
    
    new_text = get_card_list_message(df, mode=mode, width=width)
    
    keyboard = []
    if mode == 'text':
        keyboard.append([InlineKeyboardButton("📊 Switch to Table View", callback_data="set_view_table")])
    else:
        keyboard.append([InlineKeyboardButton("📝 Switch to Text View", callback_data="set_view_text")])
        keyboard.append([InlineKeyboardButton("⚙️ Adjust Width", callback_data="width_menu")])

    keyboard.append([InlineKeyboardButton("🏠 Home", callback_data="home")])

    await query.edit_message_text(
        text=new_text, 
        reply_markup=InlineKeyboardMarkup(keyboard), 
        parse_mode='Markdown'
    )

if __name__ == '__main__':
    logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
    
    application = ApplicationBuilder().token(TOKEN).build()
    
    # Commands
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('fees', check_fees))
    application.add_handler(CommandHandler('cards', list_cards))
    application.add_handler(CommandHandler('bonus', check_bonuses))
    application.add_handler(CommandHandler('stats', portfolio_stats)) # New
    application.add_handler(CommandHandler('track', track_spend_menu)) # New
    application.add_handler(CommandHandler('info', card_info_menu))   # New
    
    # Handlers
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    # Scheduler
    job_queue = application.job_queue
    job_queue.run_repeating(send_weekly_notifications, interval=604800, first=10, chat_id=YOUR_CHAT_ID)
    
    print("Bot is running...")
    application.run_polling()
