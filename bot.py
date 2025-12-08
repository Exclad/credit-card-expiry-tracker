import logging
import pandas as pd
import os
import shutil 
from datetime import datetime, time
from functools import wraps # <--- For the Security Decorator
from dotenv import load_dotenv
from filelock import FileLock 
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (ApplicationBuilder, ContextTypes, CommandHandler, 
                          CallbackQueryHandler, MessageHandler, filters)

# --- Configuration & Setup ---
load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
YOUR_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
DATA_FILE = os.getenv("DATA_FILE", "my_cards.csv")
LOCK_FILE = f"{DATA_FILE}.lock" 
IMAGE_DIR = "card_images"
BACKUP_DIR = "backups"

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

# --- Security Decorator (The Bouncer) ---
def restricted(func):
    """Restricts access to your specific user ID only."""
    @wraps(func)
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        # Convert both to strings to ensure safe comparison
        if str(user_id) != str(YOUR_CHAT_ID):
            print(f"⛔ Unauthorized access attempt from User ID: {user_id}")
            return # Ignore them completely
        return await func(update, context, *args, **kwargs)
    return wrapped

# --- Helper Functions ---

def load_data():
    """Reads the CSV file with thread safety (FileLock)."""
    if not os.path.exists(DATA_FILE):
        return pd.DataFrame() 
    
    with FileLock(LOCK_FILE):
        df = pd.read_csv(DATA_FILE)
        df = df.astype(COLUMN_DTYPES)
    return df

def save_data(df):
    """Saves the dataframe with thread safety (FileLock)."""
    with FileLock(LOCK_FILE):
        df.to_csv(DATA_FILE, index=False)

def get_card_list_message(df, mode="text", width=32):
    """Generates the string for the card list based on the selected mode."""
    active_cards = df[pd.isna(df['Cancellation Date'])].sort_values(by="Sort Order")
    
    if active_cards.empty:
        return "No active cards found."

    if mode == "text":
        message = "📂 *Your Active Cards*\n\n"
        for idx, row in active_cards.iterrows():
            fee = f"${row['Annual Fee']:.2f}"
            if row['Annual Fee'] == 0:
                fee = "Free"
            
            message += f"💳 *{row['Bank']} {row['Card Name']}*\n"
            message += f"   💰 {fee}   🗓️ {row['Month of Annual Fee']}\n\n"
        return message

    else:
        # Table Logic
        fee_col_w = 9 
        due_col_w = 3
        name_col_w = max(10, width - fee_col_w - due_col_w - 1) 
        
        message = "📂 *Your Active Cards*\n```\n"
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

# --- Backup Logic ---

def create_backup_file():
    """Performs the actual copy operation with rotation."""
    if not os.path.exists(DATA_FILE): return None
    if not os.path.exists(BACKUP_DIR): os.makedirs(BACKUP_DIR)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"cards_backup_{timestamp}.csv"
    backup_path = os.path.join(BACKUP_DIR, filename)

    try:
        with FileLock(LOCK_FILE):
            shutil.copy(DATA_FILE, backup_path)
        
        # Cleanup old backups (Keep 5 newest)
        files = [os.path.join(BACKUP_DIR, f) for f in os.listdir(BACKUP_DIR) if f.startswith("cards_backup_") and f.endswith(".csv")]
        files.sort(key=os.path.getmtime)
        while len(files) > 5:
            os.remove(files.pop(0))
            
        return filename
    except Exception as e:
        print(f"Backup Error: {e}")
        return None

async def automated_backup(context: ContextTypes.DEFAULT_TYPE):
    """Scheduled job for 4 AM."""
    name = create_backup_file()
    if name:
        print(f"✅ Automated Backup Created: {name}")

@restricted
async def backup_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Command: /backup - Lists backups and allows manual creation."""
    if not os.path.exists(BACKUP_DIR):
        message = "No backups found yet."
    else:
        files = [f for f in os.listdir(BACKUP_DIR) if f.startswith("cards_backup_") and f.endswith(".csv")]
        files.sort(reverse=True) # Newest first
        
        if not files:
            message = "No backups found yet."
        else:
            message = "📂 **Available Backups:**\n"
            for i, f in enumerate(files[:5]):
                message += f"{i+1}. `{f}`\n"

    keyboard = [
        [InlineKeyboardButton("💾 Create Backup Now", callback_data="create_backup")],
        [InlineKeyboardButton("🏠 Home", callback_data="home")]
    ]
    await context.bot.send_message(chat_id=update.effective_chat.id, text=message, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

@restricted
async def export_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Command: /export - Sends the .csv file."""
    if not os.path.exists(DATA_FILE):
        await context.bot.send_message(chat_id=update.effective_chat.id, text="❌ No data file found.")
        return

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="upload_document")
    
    try:
        with FileLock(LOCK_FILE):
            await context.bot.send_document(
                chat_id=update.effective_chat.id,
                document=open(DATA_FILE, 'rb'),
                filename="my_cards_export.csv",
                caption=f"📅 Exported on {datetime.now().strftime('%d %b %Y')}"
            )
    except Exception as e:
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"❌ Error exporting: {e}")

# --- Bot Command Functions ---

@restricted
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends the main menu."""
    msg = (
        "💳 *Card Bot Ready!*\n\n"
        "/cards - List all cards\n"
        "/info - Deep card details\n"
        "/fees - Check upcoming fees\n"
        "/bonus - Check bonus status\n"
        "/track - Add spend to bonus\n"
        "/stats - Portfolio analysis\n"
        "/backup - Manage backups\n"
        "/export - Download CSV file"
    )
    await context.bot.send_message(chat_id=update.effective_chat.id, text=msg, parse_mode='Markdown')

@restricted
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

@restricted
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

@restricted
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

@restricted
async def portfolio_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Command: /stats - Calculates summary statistics."""
    df = load_data()
    active_cards = df[pd.isna(df['Cancellation Date'])]
    
    total_cards = len(active_cards)
    total_fees = active_cards['Annual Fee'].sum()
    total_waived = df['FeeWaivedCount'].sum()
    total_paid = df['FeePaidCount'].sum()
    
    message = "📊 *Portfolio Stats*\n\n"
    message += f"💳 *Total Active Cards:* {total_cards}\n"
    message += f"💰 *Total Annual Liability:* ${total_fees:,.2f}\n\n"
    message += "🏆 *Fee History (Lifetime)*\n"
    message += f"✅ Waived: {total_waived} times\n"
    message += f"💸 Paid: {total_paid} times\n"

    keyboard = [[InlineKeyboardButton("🏠 Home", callback_data="home")]]
    await context.bot.send_message(chat_id=update.effective_chat.id, text=message, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

@restricted
async def track_spend_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Command: /track - Shows buttons for cards with active bonuses."""
    df = load_data()
    bonus_cards = df[
        (pd.isna(df['Cancellation Date'])) & 
        (df['Bonus Status'].isin(['In Progress', 'Not Started'])) &
        (pd.notna(df['Min Spend Deadline']))
    ]

    if bonus_cards.empty:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="🎉 No active bonuses to track!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Home", callback_data="home")]]))
        return

    keyboard = []
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

@restricted
async def card_info_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Command: /info - Shows buttons for all active cards."""
    df = load_data()
    active_cards = df[pd.isna(df['Cancellation Date'])].sort_values(by="Sort Order")

    if active_cards.empty:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="No cards found.")
        return

    keyboard = []
    row_buttons = []
    for idx, row in active_cards.iterrows():
        button_text = f"{row['Bank']} {row['Card Name']}"
        if len(button_text) > 20: 
            button_text = button_text[:18] + ".."
            
        row_buttons.append(InlineKeyboardButton(button_text, callback_data=f"info_select_{idx}"))
        
        if len(row_buttons) == 2:
            keyboard.append(row_buttons)
            row_buttons = []
    
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
    """Scheduled job: Checks for Unpaid Fees AND Expiring Bonuses."""
    df = load_data()
    active_cards = df[pd.isna(df['Cancellation Date'])]
    
    today = datetime.now()
    current_month_name = MONTH_NAMES[today.month - 1]
    current_year = today.year
    
    # 1. FEE CHECKS
    due_cards = active_cards[
        (active_cards["Month of Annual Fee"] == current_month_name) & 
        (active_cards["LastFeeActionYear"] != current_year)
    ]
    
    if not due_cards.empty:
        await context.bot.send_message(chat_id=YOUR_CHAT_ID, text=f"🔔 *Weekly Fee Reminder ({current_month_name})*", parse_mode='Markdown')
        for idx, row in due_cards.iterrows():
            card_name = f"{row['Bank']} {row['Card Name']}"
            fee = row['Annual Fee']
            keyboard = [
                [InlineKeyboardButton("✅ Waived", callback_data=f"waived_{idx}"),
                 InlineKeyboardButton("💰 Paid", callback_data=f"paid_{idx}")],
                [InlineKeyboardButton("❌ Ignore", callback_data=f"ignore_{idx}")]
            ]
            await context.bot.send_message(chat_id=YOUR_CHAT_ID, text=f"*{card_name}*\nFee: ${fee:.2f}", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    # 2. BONUS DEADLINE CHECKS
    bonus_cards = active_cards[
        (active_cards['Bonus Status'].isin(['In Progress', 'Not Started'])) &
        (pd.notna(active_cards['Min Spend Deadline']))
    ].copy()
    
    if not bonus_cards.empty:
        for idx, row in bonus_cards.iterrows():
            deadline = pd.to_datetime(row['Min Spend Deadline'])
            days_left = (deadline - today).days
            
            # Warn if deadline is within 30 days
            if 0 <= days_left <= 30:
                card_name = f"{row['Bank']} {row['Card Name']}"
                min_spend = row['Min Spend']
                current = row['Current Spend']
                remaining = max(0, min_spend - current)
                
                urgency = "⚠️" if days_left > 7 else "🚨🚨 URGENT:"
                msg = (
                    f"{urgency} *Bonus Deadline Approaching!*\n"
                    f"💳 *{card_name}*\n"
                    f"⏳ {days_left} days left (Deadline: {deadline.strftime('%d %b')})\n"
                    f"📉 You need to spend *${remaining:,.2f}* more!"
                )
                keyboard = [[InlineKeyboardButton("💵 Add Spend", callback_data=f"track_select_{idx}")]]
                await context.bot.send_message(chat_id=YOUR_CHAT_ID, text=msg, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

# --- BUTTON HANDLER ---
@restricted
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles all button interactions."""
    query = update.callback_query
    await query.answer() 
    data = query.data

    # --- HOME ---
    if data == "home":
        msg = (
            "💳 *Card Bot Ready!*\n\n"
            "/cards - List all cards\n"
            "/info - Deep card details\n"
            "/fees - Check upcoming fees\n"
            "/bonus - Check bonus status\n"
            "/track - Add spend to bonus\n"
            "/stats - Portfolio analysis\n"
            "/backup - Manage backups\n"
            "/export - Download CSV file"
        )
        try:
            await query.edit_message_text(text=msg, parse_mode='Markdown')
        except:
            await query.delete_message()
            await context.bot.send_message(chat_id=update.effective_chat.id, text=msg, parse_mode='Markdown')
        return

    # --- BACKUP ---
    if data == "create_backup":
        filename = create_backup_file()
        text = f"✅ Success! Created `{filename}`" if filename else "❌ Failed to create backup."
        await query.delete_message()
        await context.bot.send_message(chat_id=update.effective_chat.id, text=text, parse_mode='Markdown')
        await backup_menu(update, context)
        return

    # --- TRACK SPEND ---
    if data.startswith("track_select_"):
        card_index = int(data.split("_")[2])
        context.user_data['tracking_card_index'] = card_index
        context.user_data['awaiting_spend_input'] = True
        await query.edit_message_text(text="💵 How much did you spend? (Type a number, e.g., 50.50)")
        return

    # --- INFO DISPLAY ---
    if data.startswith("info_select_"):
        card_index = int(data.split("_")[2])
        df = load_data()
        card = df.loc[card_index]
        
        image_filename = card.get("Image Filename", "default.png")
        image_path = os.path.join(IMAGE_DIR, str(image_filename))
        if not os.path.exists(image_path): image_path = os.path.join(IMAGE_DIR, "default.png")

        info_msg = f"💳 *{card['Bank']} {card['Card Name']}*\n"
        if card['Last 4 Digits']: info_msg += f"Ends in: `{card['Last 4 Digits']}`\n"
        info_msg += "\n"
        info_msg += f"📅 *Applied:* {pd.to_datetime(card['Date Applied']).strftime('%d %b %Y') if pd.notna(card['Date Applied']) else 'N/A'}\n"
        info_msg += f"📅 *Expiry:* {card['Card Expiry (MM/YY)']}\n"
        info_msg += f"💰 *Annual Fee:* ${card['Annual Fee']:.2f} ({card['Month of Annual Fee']})\n\n"
        
        if card['Notes']: info_msg += f"📝 *Notes:*\n_{card['Notes']}_\n\n"
        if card['Tags']: info_msg += f"🏷️ *Tags:* {card['Tags']}"

        keyboard = [
            [InlineKeyboardButton("🔙 Back to List", callback_data="info_menu")],
            [InlineKeyboardButton("🏠 Home", callback_data="home")]
        ]
        
        await query.delete_message()
        if os.path.exists(image_path):
            try:
                await context.bot.send_photo(chat_id=update.effective_chat.id, photo=open(image_path, 'rb'), caption=info_msg, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
            except:
                await context.bot.send_message(chat_id=update.effective_chat.id, text=f"{info_msg}\n_(Image failed)_", parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await context.bot.send_message(chat_id=update.effective_chat.id, text=info_msg, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data == "info_menu":
        await query.delete_message()
        await card_info_menu(update, context)
        return

    # --- VIEW MODES ---
    if data == "set_view_table":
        context.user_data['view_mode'] = 'table'; await refresh_cards_message(query, context); return
    elif data == "set_view_text":
        context.user_data['view_mode'] = 'text'; context.user_data['awaiting_custom_width'] = False; await refresh_cards_message(query, context); return

    # --- WIDTH MENU ---
    elif data == "width_menu":
        keyboard = [
            [InlineKeyboardButton("Narrow (28)", callback_data="set_width_28"), InlineKeyboardButton("Normal (33)", callback_data="set_width_33"), InlineKeyboardButton("Wide (38)", callback_data="set_width_38")],
            [InlineKeyboardButton("✏️ Custom", callback_data="set_width_custom")], [InlineKeyboardButton("🔙 Back", callback_data="set_view_table")]
        ]
        await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(keyboard)); return
    elif data == "set_width_custom":
        context.user_data['awaiting_custom_width'] = True; await query.edit_message_text("📏 Please type a number for the table width (e.g. 45):"); return
    elif data.startswith("set_width_"):
        new_width = int(data.split("_")[2]); context.user_data['table_width'] = new_width; await refresh_cards_message(query, context); return

    # --- FEE ACTIONS ---
    elif "_" in data:
        parts = data.split("_")
        if len(parts) == 2 and parts[0] in ["waived", "paid", "ignore"]:
            action, card_index = parts; card_index = int(card_index)
            if action == "ignore": await query.edit_message_text(text=f"Skipped notification."); return

            df = load_data(); current_year = datetime.now().year
            card_name = f"{df.loc[card_index, 'Bank']} {df.loc[card_index, 'Card Name']}"
            
            if action == "waived":
                df.loc[card_index, "FeeWaivedCount"] += 1; df.loc[card_index, "LastFeeAction"] = "Waived"; new_text = f"✅ Marked *{card_name}* as *Waived*!"
            elif action == "paid":
                df.loc[card_index, "FeePaidCount"] += 1; df.loc[card_index, "LastFeeAction"] = "Paid"; new_text = f"💰 Marked *{card_name}* as *Paid*!"
                
            df.loc[card_index, "LastFeeActionYear"] = current_year; save_data(df)
            keyboard = [[InlineKeyboardButton("🏠 Home", callback_data="home")]]
            await query.edit_message_text(text=new_text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

# --- TEXT MESSAGE HANDLER ---
@restricted
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Catches text messages."""
    text = update.message.text.strip()

    if context.user_data.get('awaiting_custom_width'):
        if text.isdigit():
            width = int(text)
            if 20 <= width <= 100:
                context.user_data['table_width'] = width; context.user_data['awaiting_custom_width'] = False
                await update.message.reply_text(f"✅ Width set to {width}."); await list_cards(update, context)
            else: await update.message.reply_text("⚠️ Enter number between 20-100.")
        else: await update.message.reply_text("⚠️ Please enter a number.")
        return

    if context.user_data.get('awaiting_spend_input'):
        clean_text = text.replace('$', '').replace(',', '')
        try:
            amount_added = float(clean_text)
            card_index = context.user_data.get('tracking_card_index')
            df = load_data()
            current_spend = df.loc[card_index, "Current Spend"]
            new_spend = current_spend + amount_added
            df.loc[card_index, "Current Spend"] = new_spend
            
            min_spend = df.loc[card_index, "Min Spend"]; bonus_status = df.loc[card_index, "Bonus Status"]
            msg = f"✅ Added ${amount_added:,.2f}. Total: ${new_spend:,.2f}"
            
            if new_spend >= min_spend and min_spend > 0 and bonus_status != "Met":
                df.loc[card_index, "Bonus Status"] = "Met"; msg += "\n🎉 **Congratulations! Minimum spend met!**"
            elif min_spend > 0:
                remaining = min_spend - new_spend; msg += f"\n📉 ${remaining:,.2f} left to go."

            save_data(df)
            context.user_data['awaiting_spend_input'] = False; context.user_data['tracking_card_index'] = None
            keyboard = [[InlineKeyboardButton("🏠 Home", callback_data="home")]]
            await update.message.reply_text(msg, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
        except ValueError: await update.message.reply_text("⚠️ Invalid number.")
        return

async def refresh_cards_message(query, context):
    df = load_data()
    mode = context.user_data.get('view_mode', 'text'); width = context.user_data.get('table_width', 32)
    new_text = get_card_list_message(df, mode=mode, width=width)
    keyboard = []
    if mode == 'text': keyboard.append([InlineKeyboardButton("📊 Switch to Table View", callback_data="set_view_table")])
    else: keyboard.append([InlineKeyboardButton("📝 Switch to Text View", callback_data="set_view_text")]); keyboard.append([InlineKeyboardButton("⚙️ Adjust Width", callback_data="width_menu")])
    keyboard.append([InlineKeyboardButton("🏠 Home", callback_data="home")])
    await query.edit_message_text(text=new_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

if __name__ == '__main__':
    logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
    application = ApplicationBuilder().token(TOKEN).build()
    
    # Register Commands with @restricted automatically applied via decorator
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('fees', check_fees))
    application.add_handler(CommandHandler('cards', list_cards))
    application.add_handler(CommandHandler('bonus', check_bonuses))
    application.add_handler(CommandHandler('stats', portfolio_stats))
    application.add_handler(CommandHandler('track', track_spend_menu))
    application.add_handler(CommandHandler('info', card_info_menu))
    application.add_handler(CommandHandler('backup', backup_menu))
    application.add_handler(CommandHandler('export', export_data))
    
    # Handlers
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    # Jobs
    job_queue = application.job_queue
    job_queue.run_repeating(send_weekly_notifications, interval=604800, first=10, chat_id=YOUR_CHAT_ID)
    job_queue.run_daily(automated_backup, time=time(hour=4, minute=0, second=0))
    
    print("Bot is running...")
    application.run_polling()
    