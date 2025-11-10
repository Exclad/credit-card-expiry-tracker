import streamlit as st
import pandas as pd
from datetime import datetime
import os
import re # Import regular expressions for validation

# --- Configuration ---
DATA_FILE = "my_cards.csv"
IMAGE_DIR = "card_images"
DEFAULT_IMAGE = "default.png"

# --- App Constants ---
DATE_FORMATS = ["DD/MM/YYYY", "MM/DD/YYYY", "YYYY-MM-DD"]
STRFTIME_MAP = {
    "DD/MM/YYYY": "%d/%m/%Y",
    "MM/DD/YYYY": "%m/%d/%Y",
    "YYYY-MM-DD": "%Y-%m-%d"
}
DATE_COLUMNS = [
    "Date Applied", "Date Approved", "Date Received Card", 
    "Date Activated Card", "First Charge"
]
MONTH_NAMES = ["January", "February", "March", "April", "May", "June", 
               "July", "August", "September", "October", "November", "December"]
MONTH_MAP = {f"{i+1:02d}": name for i, name in enumerate(MONTH_NAMES)}

# --- Setup: Create data file if it doesn't exist ---
if not os.path.exists(DATA_FILE):
    df = pd.DataFrame(columns=[
        "Bank", "Card Name", "Annual Fee", "Card Expiry (MM/YY)", "Month of Annual Fee",
        "Date Applied", "Date Approved", "Date Received Card", 
        "Date Activated Card", "First Charge", "Image Filename"
    ])
    df.to_csv(DATA_FILE, index=False)

if not os.path.exists(IMAGE_DIR):
    os.makedirs(IMAGE_DIR)

# --- Initialize Session State ---
if 'show_add_form' not in st.session_state:
    st.session_state.show_add_form = False
if 'date_format' not in st.session_state:
    st.session_state.date_format = "DD/MM/YYYY"
# REMOVED: 'fee_month_display' session state is no longer needed

# --- Helper Functions ---
def load_data():
    """Loads the card data from the CSV file."""
    try:
        return pd.read_csv(DATA_FILE, parse_dates=DATE_COLUMNS)
    except pd.errors.EmptyDataError:
        return pd.DataFrame(columns=[
            "Bank", "Card Name", "Annual Fee", "Card Expiry (MM/YY)", 
            "Month of Annual Fee", "Image Filename"
        ] + DATE_COLUMNS)

def get_card_mapping():
    """Scans the IMAGE_DIR and creates a mapping."""
    card_mapping = {}
    try:
        for filename in os.listdir(IMAGE_DIR):
            if filename.endswith((".png", ".jpg", ".jpeg")) and filename != DEFAULT_IMAGE:
                base_name = os.path.splitext(filename)[0]
                parts = base_name.split("_")
                if len(parts) >= 2:
                    bank = parts[0]
                    card_name = " ".join(parts[1:])
                    display_name = f"{bank} {card_name}"
                    card_mapping[display_name] = filename
    except FileNotFoundError:
        st.error(f"Image directory '{IMAGE_DIR}' not found. Please create it.")
    return card_mapping

# REMOVED: The 'update_fee_month' callback function is no longer needed

# =============================================================================
# 1. "Add New Card" Page (Main Area)
# =============================================================================
# =============================================================================
# 1. "Add New Card" Page (Main Area)
# =============================================================================
def show_add_card_form(card_mapping):
    st.title("Add a New Card")
    add_method = st.radio(
        "How would you like to add a card?",
        ("Choose from list", "Add a custom card"),
        horizontal=True
    )

    with st.form("new_card_form"):
        bank, card_name, image_filename = None, None, None
        
        if add_method == "Choose from list":
            # ... (logic for choosing from list is unchanged) ...
            if not card_mapping:
                st.error("No pre-listed card images found in 'card_images' folder.")
            else:
                selected_display_name = st.selectbox(
                    "Choose a card*",
                    options=sorted(card_mapping.keys())
                )
                if selected_display_name:
                    image_filename = card_mapping[selected_display_name]
                    st.image(os.path.join(IMAGE_DIR, image_filename), width=200)
                    base_name = os.path.splitext(image_filename)[0]
                    parts = base_name.split("_")
                    bank = parts[0]
                    card_name = " ".join(parts[1:])
        else:
            st.info(f"Your card will be saved with the default image ({DEFAULT_IMAGE}).")
            bank = st.text_input("Bank Name*")
            card_name = st.text_input("Card Name*")
            image_filename = DEFAULT_IMAGE

        st.divider()

        # --- UPDATED: Personal Details Section ---
        st.subheader("Enter Your Personal Details")

        # UPDATED: 'on_change' and 'key' are removed from this widget
        card_expiry_mm_yy = st.text_input(
            "Card Expiry (MM/YY)*",
            placeholder="e.g., 05/27"
        )
        # REMOVED: The st.text() for live feedback is gone
        
        annual_fee = st.number_input("Annual Fee ($)", min_value=0.0, step=1.00, format="%.2f")
        
        st.write("---")
        st.subheader("Optional Dates")
        st.caption("You can leave these blank. To clear a set date, click the 'x' in the date widget.")
        
        applied_date = st.date_input("Date Applied", value=None, format=st.session_state.date_format)
        approved_date = st.date_input("Date Approved", value=None, format=st.session_state.date_format)
        received_date = st.date_input("Date Received Card", value=None, format=st.session_state.date_format)
        activated_date = st.date_input("Date Activated Card", value=None, format=st.session_state.date_format)
        first_charge_date = st.date_input("First Charge Date", value=None, format=st.session_state.date_format)

        # Form submission buttons
        col1, col2 = st.columns([1, 1])
        with col1:
            submitted = st.form_submit_button("Add This Card", use_container_width=True, type="primary")
        with col2:
            if st.form_submit_button("Cancel", use_container_width=True):
                st.session_state.show_add_form = False
                # REMOVED: No session state to reset
                st.rerun()

    if submitted:
        # --- UPDATED: Save Logic ---
        if not bank or not card_name:
            st.error("Bank Name and Card Name are required. Please check your inputs.")
            return # Use 'return' to stop execution inside a function

        # NEW: Validation is now done *after* submission
        # 'card_expiry_mm_yy' is the variable from the st.text_input above
        match = re.match(r"^(0[1-9]|1[0-2])\/\d{2}$", card_expiry_mm_yy)
        
        if not match:
            st.error("Card Expiry (MM/YY) is required and must be in MM/YY format.")
            return # Stop submission
        
        # Get the derived month name
        month_str = match.group(1)
        fee_month = MONTH_MAP.get(month_str)

        new_card = {
            "Bank": bank,
            "Card Name": card_name,
            "Annual Fee": annual_fee,
            "Card Expiry (MM/YY)": card_expiry_mm_yy, # Save the MM/YY string
            "Month of Annual Fee": fee_month,   # Save the derived month name
            "Image Filename": image_filename,
            "Date Applied": applied_date,
            "Date Approved": approved_date,
            "Date Received Card": received_date,
            "Date Activated Card": activated_date,
            "First Charge": first_charge_date
        }
        
        df = load_data()
        new_df = pd.DataFrame([new_card])
        df = pd.concat([df, new_df], ignore_index=True)
        df.to_csv(DATA_FILE, index=False)
        
        st.success(f"Successfully added {bank} {card_name}!")
        st.session_state.show_add_form = False
        st.rerun()
# =============================================================================
# 2. Main Dashboard Page (Unchanged)
# =============================================================================
def show_dashboard(all_cards_df):
    st.sidebar.selectbox(
        "Select Date Display Format",
        options=DATE_FORMATS,
        key="date_format"
    )
    if st.sidebar.button("Add New Card"):
        st.session_state.show_add_form = True
        st.rerun()
    
    st.title("💳 Credit Card Dashboard")

    st.header("Annual Fee Notifications")
    today = datetime.today()
    current_month_index = today.month - 1
    next_month_index = (today.month % 12)
    current_month_name = MONTH_NAMES[current_month_index]
    next_month_name = MONTH_NAMES[next_month_index]

    cards_due_this_month = all_cards_df[all_cards_df["Month of Annual Fee"] == current_month_name]
    cards_due_next_month = all_cards_df[all_cards_df["Month of Annual Fee"] == next_month_name]
    
    st.subheader(f"Due This Month ({current_month_name})")
    if cards_due_this_month.empty:
        st.write("No annual fees due this month.")
    else:
        for _, card in cards_due_this_month.iterrows():
            fee = card['Annual Fee']
            fee_text = f"The fee is **${fee:.2f}**." if fee > 0 else "This card's annual fee is $0, but please verify."
            st.warning(f"**{card['Bank']} {card['Card Name']}**: {fee_text}")

    st.subheader(f"Due Next Month ({next_month_name})")
    if cards_due_next_month.empty:
        st.write("No annual fees due next month.")
    else:
        for _, card in cards_due_next_month.iterrows():
            fee = card['Annual Fee']
            fee_text = f"The fee is **${fee:.2f}**." if fee > 0 else "This card's annual fee is $0, but please verify."
            st.info(f"**{card['Bank']} {card['Card Name']}**: {fee_text}")

    st.header("All My Cards")
    strftime_code = STRFTIME_MAP[st.session_state.date_format]

    for index, card in all_cards_df.iterrows():
        st.divider()
        col1, col2 = st.columns([1, 3])
        
        with col1:
            image_path = os.path.join(IMAGE_DIR, str(card["Image Filename"]))
            if not os.path.exists(image_path):
                image_path = os.path.join(IMAGE_DIR, DEFAULT_IMAGE)
            if os.path.exists(image_path):
                st.image(image_path, width=150)
            else:
                st.caption("No Image")

        with col2:
            st.subheader(f"{card['Bank']} {card['Card Name']}")
            st.metric(label="Annual Fee", value=f"${card['Annual Fee']:.2f}", delta=f"Due in {card['Month of Annual Fee']}")
            
            with st.expander("Show All Dates and Details"):
                details_df = card.to_frame().T.drop(columns=[
                    "Bank", "Card Name", "Annual Fee", 
                    "Month of Annual Fee", "Image Filename"
                ])
                
                for col in DATE_COLUMNS:
                    if col in details_df.columns:
                        details_df[col] = pd.to_datetime(details_df[col]).dt.strftime(strftime_code).replace('NaT', 'N/A')
                        
                st.dataframe(details_df)

# =============================================================================
# MAIN APP "ROUTER" (Unchanged)
# =============================================================================
def main():
    st.set_page_config(page_title="Card Tracker", layout="wide")
    
    all_cards_df = load_data()
    card_mapping = get_card_mapping()

    if st.session_state.show_add_form:
        show_add_card_form(card_mapping)
        
    elif all_cards_df.empty:
        st.title("Welcome to your Credit Card Tracker!")
        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            if st.button("Add Your First Card", use_container_width=True, type="primary"):
                st.session_state.show_add_form = True
                st.rerun()
                
    else:
        show_dashboard(all_cards_df)

if __name__ == "__main__":
    main()