import streamlit as st
import pandas as pd
from datetime import datetime
import os
import re

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
    "Date Activated Card", "First Charge Date"
]
MONTH_NAMES = ["January", "February", "March", "April", "May", "June",
               "July", "August", "September", "October", "November", "December"]
MONTH_MAP = {f"{i+1:02d}": name for i, name in enumerate(MONTH_NAMES)}

ALL_COLUMNS = [
    "Bank", "Card Name", "Annual Fee", "Card Expiry (MM/YY)", "Month of Annual Fee",
    "Date Applied", "Date Approved", "Date Received Card",
    "Date Activated Card", "First Charge Date", "Image Filename"
]
COLUMN_DTYPES = {
    "Bank": "object", "Card Name": "object", "Annual Fee": "float",
    "Card Expiry (MM/YY)": "object", "Month of Annual Fee": "object",
    "Date Applied": "datetime64[ns]", "Date Approved": "datetime64[ns]",
    "Date Received Card": "datetime64[ns]", "Date Activated Card": "datetime64[ns]",
    "First Charge Date": "datetime64[ns]", "Image Filename": "object"
}

# --- Setup: Create data file if it doesn't exist ---
if not os.path.exists(DATA_FILE):
    df = pd.DataFrame(columns=ALL_COLUMNS)
    df.to_csv(DATA_FILE, index=False)

if not os.path.exists(IMAGE_DIR):
    os.makedirs(IMAGE_DIR)

# --- Initialize Session State ---
if 'show_add_form' not in st.session_state:
    st.session_state.show_add_form = False
if 'date_format' not in st.session_state:
    st.session_state.date_format = "DD/MM/YYYY"
if 'show_edit_form' not in st.session_state:
    st.session_state.show_edit_form = False
if 'card_to_edit' not in st.session_state:
    st.session_state.card_to_edit = None
if 'add_method' not in st.session_state:
    st.session_state.add_method = "Choose from list"
if 'card_to_add_selection' not in st.session_state:
    st.session_state.card_to_add_selection = None


# --- Helper Functions ---
def load_data():
    """Loads the card data from the CSV file."""
    try:
        return pd.read_csv(DATA_FILE, parse_dates=DATE_COLUMNS)
    except pd.errors.EmptyDataError:
        df = pd.DataFrame(columns=ALL_COLUMNS)
        df = df.astype(COLUMN_DTYPES)
        return df

def prettify_bank_name(bank_name):
    """Converts file-safe bank names to display-friendly names."""
    if bank_name == "StandardChartered":
        return "Standard Chartered"
    if bank_name == "AmericanExpress":
        return "American Express"
    return bank_name

def get_card_mapping():
    """Scans the IMAGE_DIR and creates a mapping."""
    card_mapping = {}
    try:
        for filename in os.listdir(IMAGE_DIR):
            if filename.endswith((".png", ".jpg", ".jpeg")) and filename != DEFAULT_IMAGE:
                base_name = os.path.splitext(filename)[0]
                parts = base_name.split("_")
                if len(parts) >= 2:
                    bank_raw = parts[0]
                    bank = prettify_bank_name(bank_raw)
                    card_name = " ".join(parts[1:])
                    display_name = f"{bank} {card_name}"
                    card_mapping[display_name] = filename
    except FileNotFoundError:
        st.error(f"Image directory '{IMAGE_DIR}' not found. Please create it.")
    return card_mapping

# =============================================================================
# 1. "Add New Card" Page (Main Area)
# =============================================================================
def show_add_card_form(card_mapping):
    st.title("Add a New Card", anchor=False)

    st.radio(
        "How would you like to add a card?",
        ("Choose from list", "Add a custom card"),
        horizontal=True,
        key="add_method"
    )

    bank, card_name, image_filename = None, None, None

    if st.session_state.add_method == "Choose from list":
        if not card_mapping:
            st.error("No pre-listed card images found in 'card_images' folder.")
            st.session_state.card_to_add_selection = None
        else:
            # Set default if state is empty and mapping is available
            if st.session_state.card_to_add_selection is None and card_mapping:
                st.session_state.card_to_add_selection = sorted(card_mapping.keys())[0]

            st.selectbox(
                "Choose a card*",
                options=sorted(card_mapping.keys()),
                key="card_to_add_selection"
            )

            if st.session_state.card_to_add_selection:
                image_filename = card_mapping[st.session_state.card_to_add_selection]
                st.image(os.path.join(IMAGE_DIR, image_filename))

    else:
        # --- MODIFIED: Added st.image() to show the default image ---
        st.info(f"Your card will be saved with the default image ({DEFAULT_IMAGE}).")
        default_image_path = os.path.join(IMAGE_DIR, DEFAULT_IMAGE)
        if os.path.exists(default_image_path):
            st.image(default_image_path)
        image_filename = DEFAULT_IMAGE
        # --- End of modification ---

    with st.form("new_card_form"):

        if st.session_state.add_method == "Add a custom card":
            st.subheader("Card Details", anchor=False)
            bank = st.text_input("Bank Name*")
            card_name = st.text_input("Card Name*")

        st.divider()
        st.subheader("Enter Your Personal Details", anchor=False)
        st.write("Card Expiry*")
        col1, col2 = st.columns(2)
        with col1:
            expiry_mm = st.text_input("MM*", placeholder="05", max_chars=2, help="e.g., 05 for May")
        with col2:
            expiry_yy = st.text_input("YY*", placeholder="27", max_chars=2, help="e.g., 27 for 2027")

        annual_fee = st.number_input("Annual Fee ($)", min_value=0.0, step=1.00, format="%.2f")

        st.write("---")
        st.subheader("Optional Dates", anchor=False)
        st.caption("You can leave these blank. To clear a set date, click the 'x' in the date widget.")
        applied_date = st.date_input("Date Applied", value=None, format=st.session_state.date_format)
        approved_date = st.date_input("Date Approved", value=None, format=st.session_state.date_format)
        received_date = st.date_input("Date Received Card", value=None, format=st.session_state.date_format)
        activated_date = st.date_input("Date Activated Card", value=None, format=st.session_state.date_format)
        first_charge_date = st.date_input("First Charge Date", value=None, format=st.session_state.date_format)

        col1, col2 = st.columns([1, 1])
        with col1:
            submitted = st.form_submit_button("Add This Card", use_container_width=True, type="primary")
        with col2:
            if st.form_submit_button("Cancel", use_container_width=True):
                st.session_state.show_add_form = False
                st.rerun()

    if submitted:

        if st.session_state.add_method == "Choose from list":
            if not st.session_state.card_to_add_selection:
                st.error("Please select a card from the list.")
                return

            image_filename = card_mapping[st.session_state.card_to_add_selection]
            base_name = os.path.splitext(image_filename)[0]
            parts = base_name.split("_")

            bank_raw = parts[0]
            bank = prettify_bank_name(bank_raw)
            card_name = " ".join(parts[1:])

        else:
            if not bank or not card_name:
                st.error("Bank Name and Card Name are required for custom cards.")
                return
            image_filename = DEFAULT_IMAGE

        month_match = re.match(r"^(0[1-9]|1[0-2])$", expiry_mm)
        if not month_match:
            st.error("Expiry MM must be a valid month (e.g., 01, 05, 12).")
            return
        year_match = re.match(r"^\d{2}$", expiry_yy)
        if not year_match:
            st.error("Expiry YY must be two digits (e.g., 25, 27).")
            return

        card_expiry_mm_yy = f"{expiry_mm}/{expiry_yy}"
        fee_month = MONTH_MAP.get(expiry_mm)

        new_card = {
            "Bank": bank, "Card Name": card_name, "Annual Fee": annual_fee,
            "Card Expiry (MM/YY)": card_expiry_mm_yy, "Month of Annual Fee": fee_month,
            "Image Filename": image_filename,
            "Date Applied": pd.to_datetime(applied_date),
            "Date Approved": pd.to_datetime(approved_date),
            "Date Received Card": pd.to_datetime(received_date),
            "Date Activated Card": pd.to_datetime(activated_date),
            "First Charge Date": pd.to_datetime(first_charge_date)
        }

        df = load_data()
        new_df = pd.DataFrame([new_card])
        df = pd.concat([df, new_df], ignore_index=True)
        df.to_csv(DATA_FILE, index=False)

        st.success(f"Successfully added {bank} {card_name}!")
        st.session_state.show_add_form = False
        st.rerun()

# =============================================================================
# 2. "Edit Card" Page
# =============================================================================
def show_edit_form():
    st.title("Edit Card Details", anchor=False)

    all_cards_df = load_data()
    card_index = st.session_state.card_to_edit

    if card_index is None or card_index not in all_cards_df.index:
        st.error("Could not find card to edit. Returning to dashboard.")
        st.session_state.show_edit_form = False
        st.rerun()
        return

    card_data = all_cards_df.iloc[card_index]

    try:
        default_mm, default_yy = card_data["Card Expiry (MM/YY)"].split('/')
    except (ValueError, AttributeError):
        default_mm, default_yy = "", ""

    with st.form("edit_card_form"):
        st.subheader(f"Editing: {card_data['Bank']} {card_data['Card Name']}", anchor=False)
        st.caption("Note: You cannot change the card image here. To change an image, please add the card again.")

        bank = st.text_input("Bank Name*", value=card_data["Bank"])
        card_name = st.text_input("Card Name*", value=card_data["Card Name"])

        st.divider()
        st.subheader("Edit Personal Details", anchor=False)

        st.write("Card Expiry*")
        col1, col2 = st.columns(2)
        with col1:
            expiry_mm = st.text_input("MM*", value=default_mm, max_chars=2, help="e.g., 05 for May")
        with col2:
            expiry_yy = st.text_input("YY*", value=default_yy, max_chars=2, help="e.g., 27 for 2027")

        annual_fee = st.number_input(
            "Annual Fee ($)",
            min_value=0.0,
            step=1.00,
            format="%.2f",
            value=card_data["Annual Fee"]
        )

        st.write("---")
        st.subheader("Edit Optional Dates", anchor=False)

        def get_date(date_val):
            return pd.to_datetime(date_val) if pd.notna(date_val) else None

        applied_date = st.date_input("Date Applied", value=get_date(card_data["Date Applied"]), format=st.session_state.date_format)
        approved_date = st.date_input("Date Approved", value=get_date(card_data["Date Approved"]), format=st.session_state.date_format)
        received_date = st.date_input("Date Received Card", value=get_date(card_data["Date Received Card"]), format=st.session_state.date_format)
        activated_date = st.date_input("Date Activated Card", value=get_date(card_data["Date Activated Card"]), format=st.session_state.date_format)
        first_charge_date = st.date_input("First Charge Date", value=get_date(card_data["First Charge Date"]), format=st.session_state.date_format)


        col1, col2 = st.columns([1, 1])
        with col1:
            submitted = st.form_submit_button("Save Changes", use_container_width=True, type="primary")
        with col2:
            if st.form_submit_button("Cancel", use_container_width=True):
                st.session_state.show_edit_form = False
                st.session_state.card_to_edit = None
                st.rerun()

    if submitted:
        if not bank or not card_name:
            st.error("Bank Name and Card Name are required.")
            return

        month_match = re.match(r"^(0[1-9]|1[0-2])$", expiry_mm)
        if not month_match:
            st.error("Expiry MM must be a valid month (e.g., 01, 05, 12).")
            return

        year_match = re.match(r"^\d{2}$", expiry_yy)
        if not year_match:
            st.error("Expiry YY must be two digits (e.g., 25, 27).")
            return

        card_expiry_mm_yy = f"{expiry_mm}/{expiry_yy}"
        fee_month = MONTH_MAP.get(expiry_mm)

        all_cards_df.loc[card_index, "Bank"] = bank
        all_cards_df.loc[card_index, "Card Name"] = card_name
        all_cards_df.loc[card_index, "Annual Fee"] = annual_fee
        all_cards_df.loc[card_index, "Card Expiry (MM/YY)"] = card_expiry_mm_yy
        all_cards_df.loc[card_index, "Month of Annual Fee"] = fee_month
        all_cards_df.loc[card_index, "Date Applied"] = pd.to_datetime(applied_date)
        all_cards_df.loc[card_index, "Date Approved"] = pd.to_datetime(approved_date)
        all_cards_df.loc[card_index, "Date Received Card"] = pd.to_datetime(received_date)
        all_cards_df.loc[card_index, "Date Activated Card"] = pd.to_datetime(activated_date)
        all_cards_df.loc[card_index, "First Charge Date"] = pd.to_datetime(first_charge_date)

        all_cards_df.to_csv(DATA_FILE, index=False)

        st.success(f"Successfully updated {bank} {card_name}!")
        st.session_state.show_edit_form = False
        st.session_state.card_to_edit = None
        st.rerun()

# =============================================================================
# 3. Main Dashboard Page
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

    st.title("💳 Credit Card Dashboard", anchor=False)

    today = datetime.today()
    current_month_index = today.month - 1
    next_month_index = (current_month_index + 1) % 12
    current_month_name = MONTH_NAMES[current_month_index]
    next_month_name = MONTH_NAMES[next_month_index]

    st.header("Annual Fee Notifications", anchor=False)
    cards_due_this_month = all_cards_df[all_cards_df["Month of Annual Fee"] == current_month_name]
    cards_due_next_month = all_cards_df[all_cards_df["Month of Annual Fee"] == next_month_name]

    st.subheader(f"Due This Month ({current_month_name})", anchor=False)
    if cards_due_this_month.empty: st.write("No annual fees due this month.")
    else:
        for _, card in cards_due_this_month.iterrows():
            fee = card['Annual Fee']; fee_text = f"The fee is **${fee:.2f}**." if fee > 0 else "Fee is $0, but please verify."
            st.warning(f"**{card['Bank']} {card['Card Name']}**: {fee_text}")

    st.subheader(f"Due Next Month ({next_month_name})", anchor=False)
    if cards_due_next_month.empty: st.write("No annual fees due next month.")
    else:
        for _, card in cards_due_next_month.iterrows():
            fee = card['Annual Fee']; fee_text = f"The fee is **${fee:.2f}**." if fee > 0 else "Fee is $0, but please verify."
            st.info(f"**{card['Bank']} {card['Card Name']}**: {fee_text}")

    st.header("All My Cards", anchor=False)
    strftime_code = STRFTIME_MAP[st.session_state.date_format]

    for index, card in all_cards_df.iterrows():
        st.divider()
        col1, col2 = st.columns([1, 3])

        with col1:
            image_path = os.path.join(IMAGE_DIR, str(card["Image Filename"]))
            if not os.path.exists(image_path):
                image_path = os.path.join(IMAGE_DIR, DEFAULT_IMAGE)
            if os.path.exists(image_path):
                st.image(image_path)
            else:
                st.caption("No Image")

        with col2:
            st.subheader(f"{card['Bank']} {card['Card Name']}", anchor=False)

            st.metric(label="Annual Fee", value=f"${card['Annual Fee']:.2f}")

            due_month_name = card['Month of Annual Fee']
            try:
                due_month_index = MONTH_NAMES.index(due_month_name)
            except (ValueError, TypeError):
                due_month_index = -1

            if due_month_index == current_month_index:
                st.error(f"❗ **Due this month** ({due_month_name})")
            elif due_month_index == next_month_index:
                st.warning(f"⚠️ **Due next month** ({due_month_name})")
            elif due_month_index != -1:
                st.success(f"✅ Due in {due_month_name}")
            else:
                st.info(f"Due in {due_month_name}")

            if st.button("Edit Card", key=f"edit_{index}"):
                st.session_state.card_to_edit = index
                st.session_state.show_edit_form = True
                st.rerun()

            with st.expander("Show All Dates and Details"):
                details_df = card.to_frame().T.drop(columns=[
                    "Bank", "Card Name", "Annual Fee",
                    "Month of Annual Fee", "Image Filename"
                ])
                for col in DATE_COLUMNS:
                    if col in details_df.columns:
                        details_df[col] = pd.to_datetime(details_df[col]).dt.strftime(strftime_code).replace('NaT', 'N/A')

                st.dataframe(details_df, hide_index=True)

# =================================_===========================================
# MAIN APP "ROUTER"
# =============================================================================
def main():
    st.set_page_config(
        page_title="Card Tracker",
        layout="wide",
        initial_sidebar_state="expanded",
        menu_items={
            'About': "Credit Card Tracker App"
        }
    )

    st.markdown("""
    <style>
    /* Target all image elements within Streamlit */
    .stImage img {
        /* Set a fixed box size */
        width: 158px;
        height: 100px;
        /* Fit the image within the box, padding as needed */
        object-fit: contain;
    }
    </style>
    """, unsafe_allow_html=True)

    all_cards_df = load_data()
    card_mapping = get_card_mapping()

    if st.session_state.show_add_form:
        show_add_card_form(card_mapping)

    elif st.session_state.show_edit_form:
        show_edit_form()

    elif all_cards_df.empty:
        st.title("Welcome to your Credit Card Tracker!", anchor=False)
        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            if st.button("Add Your First Card", use_container_width=True, type="primary"):
                st.session_state.show_add_form = True
                st.rerun()

    else:
        show_dashboard(all_cards_df)

if __name__ == "__main__":
    main()
