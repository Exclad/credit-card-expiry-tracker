import streamlit as st
import pandas as pd
from datetime import datetime
import os
import re
import json  # Used for reading/writing the tags.json file
from collections import Counter  # Used for finding duplicates in the sort list
from pandas.tseries.offsets import DateOffset  # Used to add 13 months for re-apply date

# --- Configuration ---
# These are global constants that define file paths
DATA_FILE = "my_cards.csv"  # Main database for all card info
TAGS_FILE = "my_tags.json"  # Stores the user-created master list of tags
IMAGE_DIR = "card_images"  # Folder to store card images
DEFAULT_IMAGE = "default.png"  # Fallback image if a card's image is not found

# --- App Constants ---
# Defines the date formats the user can choose from in the sidebar
DATE_FORMATS = ["DD/MM/YYYY", "MM/DD/YYYY", "YYYY-MM-DD"]
# Maps the user-friendly format to the Python `strftime` code
STRFTIME_MAP = {
    "DD/MM/YYYY": "%d/%m/%Y",
    "MM/DD/YYYY": "%m/%d/%Y",
    "YYYY-MM-DD": "%Y-%m-%d"
}

# A list of all columns that should be treated as dates
DATE_COLUMNS = [
    "Date Applied", "Date Approved", "Date Received Card",
    "Date Activated Card", "First Charge Date",
    "Cancellation Date", "Re-apply Date", "Min Spend Deadline"
]

# Used to map the expiry month (e.g., "05") to the month name ("May")
MONTH_NAMES = ["January", "February", "March", "April", "May", "June",
               "July", "August", "September", "October", "November", "December"]
MONTH_MAP = {f"{i+1:02d}": name for i, name in enumerate(MONTH_NAMES)}

# Defines the master schema for the my_cards.csv file.
# This ensures all columns are created and loaded correctly.
ALL_COLUMNS = [
    "Bank", "Card Name", "Annual Fee", "Card Expiry (MM/YY)", "Month of Annual Fee",
    "Date Applied", "Date Approved", "Date Received Card",
    "Date Activated Card", "First Charge Date", "Image Filename", "Sort Order",
    "Notes", "Cancellation Date", "Re-apply Date", "Tags",
    "Bonus Offer", "Min Spend", "Min Spend Deadline", "Bonus Status"
]
# Defines the specific data type for each column for robust loading with Pandas.
COLUMN_DTYPES = {
    "Bank": "object", "Card Name": "object", "Annual Fee": "float",
    "Card Expiry (MM/YY)": "object", "Month of Annual Fee": "object",
    "Date Applied": "datetime64[ns]", "Date Approved": "datetime64[ns]",
    "Date Received Card": "datetime64[ns]", "Date Activated Card": "datetime64[ns]",
    "First Charge Date": "datetime64[ns]", "Image Filename": "object",
    "Sort Order": "int",
    "Notes": "object", "Cancellation Date": "datetime64[ns]", "Re-apply Date": "datetime64[ns]",
    "Tags": "object",
    "Bonus Offer": "object",
    "Min Spend": "float",
    "Min Spend Deadline": "datetime64[ns]",
    "Bonus Status": "object"
}

# --- Setup: Create data file/directory if it doesn't exist ---
# This runs once when the app starts.
if not os.path.exists(DATA_FILE):
    # If the CSV doesn't exist, create an empty one with the correct columns
    df = pd.DataFrame(columns=ALL_COLUMNS)
    df.to_csv(DATA_FILE, index=False)

if not os.path.exists(IMAGE_DIR):
    # If the image directory doesn't exist, create it
    os.makedirs(IMAGE_DIR)

# --- Initialize Session State ---
# `st.session_state` is Streamlit's way of "remembering" variables between reruns.
# We use it to control which "page" is shown and to store temporary data.
if 'show_add_form' not in st.session_state:
    st.session_state.show_add_form = False  # Controls the "Add New Card" page
if 'date_format' not in st.session_state:
    st.session_state.date_format = "DD/MM/YYYY"  # Stores user's date format choice
if 'show_edit_form' not in st.session_state:
    st.session_state.show_edit_form = False  # Controls the "Edit Card" page
if 'card_to_edit' not in st.session_state:
    st.session_state.card_to_edit = None  # Stores the index of the card being edited
if 'add_method' not in st.session_state:
    st.session_state.add_method = "Choose from list"  # Remembers the radio button on Add page
if 'card_to_add_selection' not in st.session_state:
    st.session_state.card_to_add_selection = None  # Remembers dropdown choice on Add page
if 'card_to_delete' not in st.session_state:
    st.session_state.card_to_delete = None  # Stores card index for cancel confirmation
if 'show_sort_form' not in st.session_state:
    st.session_state.show_sort_form = False  # Controls the "Edit Sort Order" page
if 'duplicate_sort_numbers' not in st.session_state:
    st.session_state.duplicate_sort_numbers = []  # Stores list of duplicates for sort page
if 'show_details_page' not in st.session_state:
    st.session_state.show_details_page = False  # Controls the "Card Details" page
if 'card_to_view' not in st.session_state:
    st.session_state.card_to_view = None  # Stores the index of the card being viewed
if 'show_tag_manager' not in st.session_state:
    st.session_state.show_tag_manager = False  # Controls the "Manage Tags" page


# =============================================================================
#  Helper Functions
# =============================================================================

def load_data():
    """
    Loads the card data from the CSV file.
    This function also handles "migrations" by adding any missing columns
    to an existing CSV, ensuring the app doesn't crash on new features.
    """
    try:
        # Try to read the main CSV file
        df = pd.read_csv(DATA_FILE)
    except pd.errors.EmptyDataError:
        # If the file is completely empty, create a new DataFrame in memory
        df = pd.DataFrame(columns=ALL_COLUMNS)
        df = df.astype(COLUMN_DTYPES)
        return df

    # --- Data Migration Block ---
    # Check if each column exists. If not, add it with a default value.
    if "Sort Order" not in df.columns:
        df["Sort Order"] = range(1, len(df) + 1)
    if "Notes" not in df.columns:
        df["Notes"] = ""
    if "Cancellation Date" not in df.columns:
        df["Cancellation Date"] = pd.NaT  # "Not a Time" (Pandas' version of null for dates)
    if "Re-apply Date" not in df.columns:
        df["Re-apply Date"] = pd.NaT
    if "Tags" not in df.columns:
        df["Tags"] = ""
    if "Bonus Offer" not in df.columns:
        df["Bonus Offer"] = ""
    if "Min Spend" not in df.columns:
        df["Min Spend"] = 0.0
    if "Min Spend Deadline" not in df.columns:
        df["Min Spend Deadline"] = pd.NaT
    if "Bonus Status" not in df.columns:
        df["Bonus Status"] = ""
    
    # --- Type Coercion Block ---
    # Ensure all date columns are properly converted to datetime objects
    for col in DATE_COLUMNS:
        df[col] = pd.to_datetime(df[col], errors='coerce')

    # Ensure other specific columns have the correct type and defaults
    df["Sort Order"] = pd.to_numeric(df["Sort Order"], errors='coerce').fillna(99).astype(int)
    df["Sort Order"] = df["Sort Order"].apply(lambda x: 99 if x < 1 else x)
    
    # Fill any null values with an empty string *before* converting to string
    # This prevents 'nan' from showing up in text fields.
    df["Notes"] = df["Notes"].fillna("").astype(str)
    df["Tags"] = df["Tags"].fillna("").astype(str)
    df["Bonus Offer"] = df["Bonus Offer"].fillna("").astype(str)
    df["Min Spend"] = pd.to_numeric(df["Min Spend"], errors='coerce').fillna(0.0).astype(float)
    df["Bonus Status"] = df["Bonus Status"].fillna("").astype(str)

    return df


def prettify_bank_name(bank_name):
    """Converts file-safe bank names (e.g., 'AmericanExpress') to display-friendly names."""
    if bank_name == "StandardChartered":
        return "Standard Chartered"
    if bank_name == "AmericanExpress":
        return "American Express"
    return bank_name


def get_card_mapping():
    """
    Scans the IMAGE_DIR and creates a mapping.
    It reads filenames like 'AmericanExpress_Platinum.png' and turns them into
    a dictionary: {'American Express Platinum': 'AmericanExpress_Platinum.png'}
    This mapping is used to populate the "Choose from list" dropdown.
    """
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


def load_tags():
    """Loads the master list of tags from tags.json."""
    if not os.path.exists(TAGS_FILE):
        return []  # Return empty list if file doesn't exist
    try:
        with open(TAGS_FILE, 'r') as f:
            tags = json.load(f)
            return sorted(list(set(tags)))  # Ensure list is sorted and unique
    except (json.JSONDecodeError, FileNotFoundError):
        return []  # Return empty list on error


def save_tags(tags_list):
    """Saves the master list of tags to tags.json."""
    # Clean the list: remove whitespace, ensure uniqueness, and sort
    unique_sorted_tags = sorted(list(set(t.strip() for t in tags_list if t.strip())))
    try:
        with open(TAGS_FILE, 'w') as f:
            json.dump(unique_sorted_tags, f, indent=4)
        return True
    except Exception as e:
        st.error(f"Failed to save tags: {e}")
        return False


# =============================================================================
# 1. "Add New Card" Page (Main Area)
# =============================================================================
def show_add_card_form(card_mapping):
    """Displays the form for adding a new card."""
    st.title("Add a New Card", anchor=False)

    # Radio button to switch between pre-filled and custom card
    st.radio(
        "How would you like to add a card?",
        ("Choose from list", "Add a custom card"),
        horizontal=True,
        key="add_method"  # Stored in session state
    )

    bank, card_name, image_filename = None, None, None

    # --- Logic for "Choose from list" ---
    if st.session_state.add_method == "Choose from list":
        if not card_mapping:
            st.error("No pre-listed card images found in 'card_images' folder.")
            st.session_state.card_to_add_selection = None
        else:
            # Set a default selection if one isn't already set
            if st.session_state.card_to_add_selection is None and card_mapping:
                st.session_state.card_to_add_selection = sorted(card_mapping.keys())[0]
            # The dropdown box
            st.selectbox(
                "Choose a card*",
                options=sorted(card_mapping.keys()),
                key="card_to_add_selection"
            )
            # Show the image of the selected card
            if st.session_state.card_to_add_selection:
                image_filename = card_mapping[st.session_state.card_to_add_selection]
                st.image(os.path.join(IMAGE_DIR, image_filename))
    
    # --- Logic for "Add a custom card" ---
    else:
        st.info(f"Your card will be saved with the default image ({DEFAULT_IMAGE}).")
        default_image_path = os.path.join(IMAGE_DIR, DEFAULT_IMAGE)
        if os.path.exists(default_image_path):
            st.image(default_image_path)
        image_filename = DEFAULT_IMAGE  # Set image to default

    # --- The Main Form ---
    with st.form("new_card_form"):
        # Only show these fields if user is adding a custom card
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

        # Load master tag list and display as a multiselect box
        all_tags = load_tags()
        selected_tags = st.multiselect("Tags", options=all_tags)

        st.subheader("Notes", anchor=False)
        notes = st.text_area("Add any notes for this card (e.g., waiver info, benefits).")

        # --- Welcome Offer Tracking Section ---
        st.divider()
        st.subheader("Welcome Offer Tracking (Optional)", anchor=False)
        bonus_offer = st.text_input("Bonus Offer", placeholder="e.g., 50,000 miles or $200 cashback")
        min_spend = st.number_input("Min Spend Required ($)", min_value=0.0, step=100.0, format="%.2f")
        min_spend_deadline = st.date_input("Min Spend Deadline", value=None, format=st.session_state.date_format)
        bonus_status = st.selectbox(
            "Bonus Status",
            ("Not Started", "In Progress", "Met", "Received"),
            index=0,  # Defaults to "Not Started"
            help="Set this to 'Met' or 'Received' when you're done!"
        )

        # --- Optional Dates Section ---
        st.write("---")
        st.subheader("Optional Dates", anchor=False)
        st.caption("You can leave these blank. To clear a set date, click the 'x' in the date widget.")
        applied_date = st.date_input("Date Applied", value=None, format=st.session_state.date_format)
        approved_date = st.date_input("Date Approved", value=None, format=st.session_state.date_format)
        received_date = st.date_input("Date Received Card", value=None, format=st.session_state.date_format)
        activated_date = st.date_input("Date Activated Card", value=None, format=st.session_state.date_format)
        first_charge_date = st.date_input("First Charge Date", value=None, format=st.session_state.date_format)

        # --- Form Buttons ---
        col1, col2 = st.columns([1, 1])
        with col1:
            submitted = st.form_submit_button("Add This Card", use_container_width=True, type="primary")
        with col2:
            if st.form_submit_button("Cancel", use_container_width=True):
                st.session_state.show_add_form = False  # Set state to go back to dashboard
                st.rerun()

    # --- Form Submission Logic ---
    if submitted:
        df = load_data()  # Load current data
        
        # If user chose from the list, parse the Bank/Card Name from the selection
        if st.session_state.add_method == "Choose from list":
            if not st.session_state.card_to_add_selection:
                st.error("Please select a card from the list."); return
            image_filename = card_mapping[st.session_state.card_to_add_selection]
            base_name = os.path.splitext(image_filename)[0]
            parts = base_name.split("_")
            bank_raw = parts[0]
            bank = prettify_bank_name(bank_raw)
            card_name = " ".join(parts[1:])
        # If user added a custom card, validate the required fields
        else:
            if not bank or not card_name:
                st.error("Bank Name and Card Name are required for custom cards."); return
            image_filename = DEFAULT_IMAGE  # Already set, but good to be explicit

        # --- Validation ---
        month_match = re.match(r"^(0[1-9]|1[0-2])$", expiry_mm)
        if not month_match: st.error("Expiry MM must be a valid month (e.g., 01, 05, 12)."); return
        year_match = re.match(r"^\d{2}$", expiry_yy)
        if not year_match: st.error("Expiry YY must be two digits (e.g., 25, 27)."); return
        
        card_expiry_mm_yy = f"{expiry_mm}/{expiry_yy}"
        fee_month = MONTH_MAP.get(expiry_mm)  # Get month name (e.g., "May")

        # Find the highest "Sort Order" and add 1
        max_sort = df['Sort Order'].max()
        if pd.isna(max_sort) or max_sort < 1:
            new_sort_order = 1
        else:
            new_sort_order = int(max_sort + 1)

        # --- Create New Card Record ---
        # Build a dictionary for the new card
        new_card = {
            "Bank": bank, "Card Name": card_name, "Annual Fee": annual_fee,
            "Card Expiry (MM/YY)": card_expiry_mm_yy, "Month of Annual Fee": fee_month,
            "Image Filename": image_filename,
            "Date Applied": pd.to_datetime(applied_date),
            "Date Approved": pd.to_datetime(approved_date),
            "Date Received Card": pd.to_datetime(received_date),
            "Date Activated Card": pd.to_datetime(activated_date),
            "First Charge Date": pd.to_datetime(first_charge_date),
            "Sort Order": new_sort_order,
            "Notes": notes,
            "Cancellation Date": pd.NaT,
            "Re-apply Date": pd.NaT,
            "Tags": ",".join(selected_tags),  # Save list of tags as a single string
            "Bonus Offer": bonus_offer,
            "Min Spend": min_spend,
            "Min Spend Deadline": pd.to_datetime(min_spend_deadline),
            "Bonus Status": bonus_status
        }

        # --- Save to CSV ---
        new_df = pd.DataFrame([new_card])  # Convert dict to a single-row DataFrame
        df = pd.concat([df, new_df], ignore_index=True)  # Append to the main DataFrame
        df.to_csv(DATA_FILE, index=False)  # Save back to CSV

        st.success(f"Successfully added {bank} {card_name}!")
        st.session_state.show_add_form = False  # Go back to dashboard
        st.rerun()


# =============================================================================
# 2. "Edit Card" Page
# =============================================================================
def show_edit_form():
    """Displays the form for editing an existing card."""
    st.title("Edit Card Details", anchor=False)
    all_cards_df = load_data()
    
    # Get the index of the card to edit from session state
    card_index = st.session_state.card_to_edit
    if card_index is None or card_index not in all_cards_df.index:
        st.error("Could not find card to edit. Returning to dashboard.")
        st.session_state.show_edit_form = False; st.rerun(); return
    
    # Get the specific card's data using its index
    card_data = all_cards_df.iloc[card_index]

    # Pre-process expiry date for the form
    try:
        default_mm, default_yy = card_data["Card Expiry (MM/YY)"].split('/')
    except (ValueError, AttributeError):
        default_mm, default_yy = "", ""

    # --- The Edit Form ---
    # All fields are pre-filled with existing data using the `value=` or `default=` argument
    with st.form("edit_card_form"):
        st.subheader(f"Editing: {card_data['Bank']} {card_data['Card Name']}", anchor=False)
        st.caption("Note: You cannot change the card image here. To change the manual sort order, use the 'Edit Manual Order' button on the dashboard.")
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

        annual_fee = st.number_input("Annual Fee ($)", min_value=0.0, step=1.00, format="%.2f", value=card_data["Annual Fee"])
        
        # Pre-load existing tags
        all_tags = load_tags()
        default_tags_str = card_data.get("Tags", "")
        default_tags = [t for t in default_tags_str.split(',') if t]  # Convert string to list
        selected_tags = st.multiselect("Tags", options=all_tags, default=default_tags)

        st.subheader("Notes", anchor=False)
        notes = st.text_area("Card notes", value=card_data.get("Notes", ""))
        
        # --- Welcome Offer Tracking Section ---
        st.divider()
        st.subheader("Welcome Offer Tracking", anchor=False)
        bonus_offer = st.text_input("Bonus Offer", value=card_data.get("Bonus Offer", ""))
        min_spend = st.number_input("Min Spend Required ($)", min_value=0.0, step=100.0, format="%.2f", value=card_data.get("Min Spend", 0.0))
        
        # Helper function to safely convert date values for the widget
        def get_date(date_val):
            return pd.to_datetime(date_val) if pd.notna(date_val) else None
        
        min_spend_deadline = st.date_input("Min Spend Deadline", value=get_date(card_data.get("Min Spend Deadline")), format=st.session_state.date_format)
        
        # Find the index of the saved status to set the default on the selectbox
        status_options = ["Not Started", "In Progress", "Met", "Received"]
        default_status = card_data.get("Bonus Status", "Not Started")
        status_index = status_options.index(default_status) if default_status in status_options else 0
        bonus_status = st.selectbox("Bonus Status", status_options, index=status_index)
        
        # --- Edit Optional Dates Section ---
        st.write("---")
        st.subheader("Edit Optional Dates", anchor=False)
        applied_date = st.date_input("Date Applied", value=get_date(card_data["Date Applied"]), format=st.session_state.date_format)
        approved_date = st.date_input("Date Approved", value=get_date(card_data["Date Approved"]), format=st.session_state.date_format)
        received_date = st.date_input("Date Received Card", value=get_date(card_data["Date Received Card"]), format=st.session_state.date_format)
        activated_date = st.date_input("Date Activated Card", value=get_date(card_data["Date Activated Card"]), format=st.session_state.date_format)
        first_charge_date = st.date_input("First Charge Date", value=get_date(card_data["First Charge Date"]), format=st.session_state.date_format)
        
        st.caption("Cancellation and Re-apply dates are handled via the 'Cancel Card' button on the dashboard.")

        # --- Form Buttons ---
        col1, col2 = st.columns([1, 1])
        with col1:
            submitted = st.form_submit_button("Save Changes", use_container_width=True, type="primary")
        with col2:
            if st.form_submit_button("Cancel", use_container_width=True):
                st.session_state.show_edit_form = False; st.session_state.card_to_edit = None; st.rerun()

    # --- Form Submission Logic ---
    if submitted:
        # Validation
        if not bank or not card_name: st.error("Bank Name and Card Name are required."); return
        month_match = re.match(r"^(0[1-9]|1[0-2])$", expiry_mm); 
        if not month_match: st.error("Expiry MM must be a valid month (e.g., 01, 05, 12)."); return
        year_match = re.match(r"^\d{2}$", expiry_yy); 
        if not year_match: st.error("Expiry YY must be two digits (e.g., 25, 27)."); return
        
        card_expiry_mm_yy = f"{expiry_mm}/{expiry_yy}"
        fee_month = MONTH_MAP.get(expiry_mm)

        # --- Update Record in DataFrame ---
        # Use .loc to find the specific row (by index) and update its columns
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
        all_cards_df.loc[card_index, "Notes"] = notes
        all_cards_df.loc[card_index, "Tags"] = ",".join(selected_tags)
        all_cards_df.loc[card_index, "Bonus Offer"] = bonus_offer
        all_cards_df.loc[card_index, "Min Spend"] = min_spend
        all_cards_df.loc[card_index, "Min Spend Deadline"] = pd.to_datetime(min_spend_deadline)
        all_cards_df.loc[card_index, "Bonus Status"] = bonus_status
        
        # --- Save to CSV ---
        all_cards_df.to_csv(DATA_FILE, index=False)
        st.success(f"Successfully updated {bank} {card_name}!"); 
        st.session_state.show_edit_form = False; st.session_state.card_to_edit = None; st.rerun()

# =============================================================================
# 3. Main Dashboard Page
# =============================================================================
def show_dashboard(all_cards_df):
    """Displays the main dashboard, including sidebar, summaries, and card list."""
    
    # --- Sidebar Setup ---
    st.sidebar.selectbox("Select Date Display Format", options=DATE_FORMATS, key="date_format")
    if st.sidebar.button("Add New Card"):
        st.session_state.show_add_form = True; st.rerun()
    
    if st.sidebar.button("Manage Tags"):
        st.session_state.show_tag_manager = True
        st.rerun()

    st.sidebar.divider()
    
    show_cancelled = st.sidebar.checkbox("Show Cancelled Cards", value=True)
    
    # --- Export Data Button ---
    try:
        csv_data = all_cards_df.to_csv(index=False).encode('utf-8')
        st.sidebar.download_button(
            label="Export Card Data (CSV)",
            data=csv_data,
            file_name="my_cards_backup.csv",
            mime="text/csv",
            use_container_width=True
        )
    except Exception as e:
        st.sidebar.error(f"Error exporting data: {e}")

    # --- Main Page Title ---
    st.title("💳 Credit Card Dashboard", anchor=False)

    # --- Date & Month Calculations ---
    today_dt = pd.to_datetime(datetime.today())
    current_month_index = today_dt.month - 1
    next_month_index = (current_month_index + 1) % 12
    current_month_name = MONTH_NAMES[current_month_index]
    next_month_name = MONTH_NAMES[next_month_index]

    # --- Filter Data Based on Checkbox ---
    if show_cancelled:
        cards_to_display_df = all_cards_df.copy()
        st.info("Showing all cards, including cancelled.")
    else:
        # Filter out any card that has a "Cancellation Date"
        cards_to_display_df = all_cards_df[pd.isna(all_cards_df['Cancellation Date'])].copy()

    # --- Summary Metrics Section ---
    st.header("Summary", anchor=False)
    
    # Helper to convert month name back to an index (0-11) for sorting
    def get_month_index(month_name):
        try: return MONTH_NAMES.index(month_name)
        except (ValueError, TypeError): return -1
            
    cards_to_display_df['due_month_index'] = cards_to_display_df['Month of Annual Fee'].apply(get_month_index)
    # Find cards due from this month onward
    cards_due_this_year_df = cards_to_display_df[cards_to_display_df['due_month_index'] >= current_month_index]
    count_due_this_year = len(cards_due_this_year_df)
    amount_due_this_year = cards_due_this_year_df['Annual Fee'].sum()

    # Display metrics in 4 columns
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Cards (Active)" if not show_cancelled else "Total Cards (All)", len(cards_to_display_df))
    col2.metric("Total Annual Fees", f"${cards_to_display_df['Annual Fee'].sum():,.2f}")
    col3.metric("Fees Due This Year (#)", count_due_this_year)
    col4.metric("Fees Due This Year ($)", f"${amount_due_this_year:,.2f}")
    
    st.divider()

    # --- Welcome Bonus Tracker Section ---
    st.header("Welcome Bonus Tracker", anchor=False)
    st.caption("Shows active bonuses with a status of 'Not Started' or 'In Progress'.")

    # Filter for cards that have a deadline AND are in progress
    active_bonuses_df = cards_to_display_df[
        (pd.notna(cards_to_display_df['Min Spend Deadline'])) &
        (cards_to_display_df['Bonus Status'].isin(['Not Started', 'In Progress']))
    ].copy()

    if active_bonuses_df.empty:
        st.write("No active minimum spend deadlines to track.")
    else:
        # Calculate days left and sort by soonest deadline
        active_bonuses_df['Days Left'] = (active_bonuses_df['Min Spend Deadline'] - today_dt).dt.days
        active_bonuses_df = active_bonuses_df.sort_values(by='Days Left')
        
        # Loop and show a status alert for each
        for _, card in active_bonuses_df.iterrows():
            days_left = card['Days Left']
            card_name = f"**{card['Bank']} {card['Card Name']}**"
            deadline_str = card['Min Spend Deadline'].strftime('%d %b %Y')
            spend_str = f"**${card['Min Spend']:.0f}**"
            
            if days_left < 0:
                st.error(f"{card_name}: Deadline **EXPIRED** on {deadline_str}. (Required: {spend_str})")
            elif days_left <= 30:
                st.warning(f"{card_name}: **{days_left} days left** to meet {spend_str} spend! (Deadline: {deadline_str})")
            else:
                st.info(f"{card_name}: {days_left} days left to meet {spend_str} spend. (Deadline: {deadline_str})")
    st.divider()

    # --- Annual Fee Notifications Section ---
    st.header("Annual Fee Notifications", anchor=False)
    # Filter for cards due this month
    cards_due_this_month = cards_to_display_df[cards_to_display_df["Month of Annual Fee"] == current_month_name]
    # Filter for cards due next month
    cards_due_next_month = cards_to_display_df[cards_to_display_df["Month of Annual Fee"] == next_month_name]
    
    st.subheader(f"Due This Month ({current_month_name})", anchor=False)
    if cards_due_this_month.empty: st.write("No annual fees due this month.")
    else:
        for _, card_data in cards_due_this_month.iterrows():
            fee = card_data['Annual Fee']; fee_text = f"The fee is **${fee:.2f}**." if fee > 0 else "Fee is $0, but please verify."
            st.error(f"**{card_data['Bank']} {card_data['Card Name']}**: {fee_text}")
            
    st.subheader(f"Due Next Month ({next_month_name})", anchor=False)
    if cards_due_next_month.empty: st.write("No annual fees due next month.")
    else:
        for _, card_data in cards_due_next_month.iterrows():
            fee = card_data['Annual Fee']; fee_text = f"The fee is **${fee:.2f}**." if fee > 0 else "Fee is $0, but please verify."
            st.warning(f"**{card_data['Bank']} {card_data['Card Name']}**: {fee_text}")
    
    st.divider()

    # --- Re-application Notifications Section ---
    st.header("Re-application Notifications", anchor=False)
    st.caption("Shows cards that were cancelled and are now (or soon) eligible to re-apply for a new bonus.")
    
    # Must use `all_cards_df` here since we are only looking for *cancelled* cards
    reapply_df = all_cards_df[pd.notna(all_cards_df['Re-apply Date'])].copy()
    # Find cards eligible to re-apply now or in the next 60 days
    eligible_cards = reapply_df[
        (reapply_df['Re-apply Date'] <= today_dt + pd.DateOffset(days=60))
    ].sort_values(by='Re-apply Date')

    if eligible_cards.empty:
        st.write("No cards are eligible for re-application soon.")
    else:
        for _, card in eligible_cards.iterrows():
            card_name = f"{card['Bank']} {card['Card Name']}"
            reapply_date_str = card['Re-apply Date'].strftime('%d %b %Y')
            
            if card['Re-apply Date'] <= today_dt:
                st.success(f"**{card_name}**: You are **now eligible** to re-apply! (Eligible since {reapply_date_str})")
            else:
                days_until = (card['Re-apply Date'] - today_dt).days
                st.info(f"**{card_name}**: Eligible to re-apply in **{days_until} days**. (On {reapply_date_str})")
    
    st.divider()

    # --- "All My Cards" List Section ---
    st.header("All My Cards", anchor=False)
    
    # Create a sort key for "Due Date". This magic formula (modulo 12)
    # wraps the year, so if it's Nov (10), Dec (11) is next, then Jan (0).
    cards_to_display_df['due_sort_key'] = (cards_to_display_df['due_month_index'] - current_month_index + 12) % 12

    # --- Filters and Sort ---
    f_col1, f_col2, f_col3 = st.columns(3)
    with f_col1:
        bank_options = sorted(cards_to_display_df['Bank'].unique())
        selected_banks = st.multiselect("Filter by Bank", options=bank_options)
    with f_col2:
        tag_options = load_tags()
        selected_tags = st.multiselect("Filter by Tag", options=tag_options)
    with f_col3:
        sort_options = {
            "Manual (Custom Order)": "Sort Order",
            "Due Date (Soonest First)": "due_sort_key",
            "Annual Fee (High to Low)": "Annual Fee_desc",
            "Annual Fee (Low to High)": "Annual Fee_asc",
        }
        selected_sort_key = st.selectbox("Sort by", options=sort_options.keys())
    
        # Show "Edit Manual Order" button only if that sort is selected
        if sort_options[selected_sort_key] == "Sort Order":
            if st.button("Edit Manual Order", use_container_width=True):
                st.session_state.show_sort_form = True
                st.session_state.duplicate_sort_numbers = [] 
                st.rerun()
    
    # --- Apply Filters ---
    cards_to_show_df_sorted = cards_to_display_df.copy()
    if selected_banks:
        cards_to_show_df_sorted = cards_to_show_df_sorted[cards_to_show_df_sorted['Bank'].isin(selected_banks)]
    if selected_tags:
        # Custom function to check if a card's tags (string) contains all selected tags (list)
        def check_tags(card_tags_str):
            card_tags = set(t.strip() for t in card_tags_str.split(','))
            return all(tag in card_tags for tag in selected_tags)
        
        cards_to_show_df_sorted = cards_to_show_df_sorted[
            cards_to_show_df_sorted['Tags'].apply(check_tags)
        ]

    # --- Apply Sort ---
    sort_logic = sort_options[selected_sort_key]
    if sort_logic == "Annual Fee_desc":
        cards_to_show_df_sorted = cards_to_show_df_sorted.sort_values(by="Annual Fee", ascending=False)
    elif sort_logic == "Annual Fee_asc":
        cards_to_show_df_sorted = cards_to_show_df_sorted.sort_values(by="Annual Fee", ascending=True)
    elif sort_logic == "due_sort_key":
        cards_to_show_df_sorted = cards_to_show_df_sorted.sort_values(by="due_sort_key", ascending=True)
    else:  # Default to "Sort Order"
        cards_to_show_df_sorted = cards_to_show_df_sorted.sort_values(by="Sort Order", ascending=True)

    # Get the chosen date format string
    strftime_code = STRFTIME_MAP[st.session_state.date_format]
    if cards_to_show_df_sorted.empty:
        st.info("No cards match your current filters.")

    # --- Main Card Loop ---
    # Helper function to format dates, defined here to use `strftime_code`
    def format_date_display(date_val):
        if pd.isna(date_val):
            return "N/A"
        return pd.to_datetime(date_val).strftime(strftime_code)

    # Loop through every card in the filtered/sorted DataFrame
    for index, card_row in cards_to_show_df_sorted.iterrows():
        st.divider()
        col1, col2 = st.columns([1, 3])  # Image column, Info column

        # --- Left Column (Image) ---
        with col1:
            image_path = os.path.join(IMAGE_DIR, str(card_row["Image Filename"]))
            if not os.path.exists(image_path): 
                image_path = os.path.join(IMAGE_DIR, DEFAULT_IMAGE)  # Fallback
            if os.path.exists(image_path): 
                st.image(image_path)
            else: 
                st.caption("No Image")

        # --- Right Column (Info) ---
        with col2:
            st.subheader(f"{card_row['Bank']} {card_row['Card Name']}", anchor=False)
            
            is_cancelled = pd.notna(card_row["Cancellation Date"])
            
            # Show EITHER annual fee OR cancellation/re-apply dates
            if is_cancelled:
                st.error("Status: Cancelled")
                c_col1, c_col2 = st.columns(2)
                with c_col1:
                    st.metric("Cancelled On", pd.to_datetime(card_row["Cancellation Date"]).strftime("%d %b %Y"))
                with c_col2:
                    st.metric("Re-apply After", pd.to_datetime(card_row["Re-apply Date"]).strftime("%d %b %Y"))
            else:
                st.metric(label="Annual Fee", value=f"${card_row['Annual Fee']:.2f}")

            # Show due date status (only if not cancelled)
            due_month_name = card_row['Month of Annual Fee']
            due_month_index = card_row['due_month_index'] 
            if not is_cancelled:
                if due_month_index == current_month_index:
                    st.error(f"❗ **Due this month** ({due_month_name})")
                elif due_month_index == next_month_index:
                    st.warning(f"⚠️ **Due next month** ({due_month_name})")
                elif due_month_index != -1:
                    st.info(f"✅ Due in {due_month_name}")
                else:
                    st.info(f"Due in {due_month_name}")
            
            # Show tags if they exist
            tags_str = card_row.get("Tags", "")
            if tags_str:
                st.markdown(f"**Tags:** `{tags_str.replace(',', ', ')}`")

            # Show notes if they exist
            notes = card_row.get("Notes", "")
            if notes and pd.notna(notes):
                st.markdown("**Notes:**")
                st.markdown(notes)

            st.write("")  # Spacer
            
            # --- Button Grid ---
            b_col1, b_col2, b_col3, b_col4 = st.columns([1, 1, 1, 1])
            
            with b_col1:
                # "Details" button
                if st.button("Details", key=f"details_{index}", use_container_width=True):
                    st.session_state.card_to_view = index; st.session_state.show_details_page = True; st.session_state.card_to_edit = None; st.session_state.card_to_delete = None; st.rerun()

            with b_col2:
                # "Edit" button
                if st.button("Edit", key=f"edit_{index}", use_container_width=True):
                    st.session_state.card_to_edit = index; st.session_state.show_edit_form = True; st.session_state.card_to_delete = None; st.rerun()
            
            with b_col3:
                # "Re-activate" OR "Cancel Card" button
                if is_cancelled:
                    if st.button("Re-activate", key=f"reactivate_{index}", use_container_width=True):
                        df = load_data()
                        df.loc[index, "Cancellation Date"] = pd.NaT  # Set date to null
                        df.loc[index, "Re-apply Date"] = pd.NaT
                        df.to_csv(DATA_FILE, index=False)
                        st.success(f"Re-activated {card_row['Bank']} {card_row['Card Name']}.")
                        st.rerun()
                else:
                    # This is a 2-step confirmation
                    if st.session_state.card_to_delete == index:
                        if st.button("Confirm Cancel", key=f"confirm_cancel_{index}", type="primary", use_container_width=True):
                            df = load_data()
                            cancel_date = pd.to_datetime('today')
                            reapply_date = cancel_date + DateOffset(months=13)  # Set re-apply 13 months out
                            df.loc[index, "Cancellation Date"] = cancel_date
                            df.loc[index, "Re-apply Date"] = reapply_date
                            df.to_csv(DATA_FILE, index=False)
                            st.session_state.card_to_delete = None
                            st.success(f"Cancelled {card_row['Bank']} {card_row['Card Name']}.")
                            st.rerun()
                        if st.button("Cancel Action", key=f"cancel_cancel_{index}", use_container_width=True):
                            st.session_state.card_to_delete = None; st.rerun()
                    else:
                        if st.button("Cancel Card", key=f"cancel_{index}", use_container_width=True):
                            st.session_state.card_to_delete = index; st.session_state.card_to_edit = None; st.rerun()
            
            with b_col4:
                # "Delete Permanently" button (also 2-step)
                if st.session_state.get(f"confirm_permanent_delete_{index}", False):
                    if st.button("CONFIRM DELETE", key=f"confirm_delete_permanent_{index}", type="primary", use_container_width=True):
                        df = load_data()
                        df = df.drop(index).reset_index(drop=True)  # Drop the row
                        df.to_csv(DATA_FILE, index=False)
                        st.session_state[f"confirm_permanent_delete_{index}"] = False 
                        st.success(f"Permanently deleted {card_row['Bank']} {card_row['Card Name']}.")
                        st.rerun()
                    if st.button("No, Keep Card", key=f"cancel_delete_permanent_{index}", use_container_width=True):
                        st.session_state[f"confirm_permanent_delete_{index}"] = False 
                        st.rerun()
                else:
                    if st.button("Delete Permanently", key=f"delete_permanent_{index}", use_container_width=True):
                        st.session_state[f"confirm_permanent_delete_{index}"] = True 
                        st.session_state.card_to_edit = None
                        st.session_state.card_to_delete = None 
                        st.rerun()

            # --- Expander for Other Dates ---
            with st.expander("Show All Dates and Details"):
                st.markdown(f"**Card Expiry:** {card_row['Card Expiry (MM/YY)']}")
                
                # Use columns and metrics for a clean date layout
                d_col1, d_col2, d_col3 = st.columns(3)
                with d_col1:
                    st.metric("Date Applied", format_date_display(card_row["Date Applied"]))
                    st.metric("Date Approved", format_date_display(card_row["Date Approved"]))
                with d_col2:
                    st.metric("Date Received", format_date_display(card_row["Date Received Card"]))
                    st.metric("Date Activated", format_date_display(card_row["Date Activated Card"]))
                with d_col3:
                    st.metric("First Charge Date", format_date_display(card_row["First Charge Date"]))

# =============================================================================
# 4. "Edit Sort Order" Page
# =============================================================================
def show_sort_order_form():
    """Displays a page to let the user manually re-order active cards."""
    st.title("Edit Manual Card Order", anchor=False)
    st.write("Change the numbers to reorder your cards. Lower numbers appear first. Click 'Save Order' when done.")
    
    all_cards_df = load_data()
    # Only allow sorting of active cards
    active_cards_df = all_cards_df[pd.isna(all_cards_df['Cancellation Date'])].sort_values(by="Sort Order")
    st.info("Only active cards are shown. Cancelled cards cannot be re-ordered.")
    
    with st.form("sort_order_form"):
        # Show an error if duplicates were found on the last save attempt
        if st.session_state.duplicate_sort_numbers:
                st.error(f"Found duplicate numbers: {', '.join(map(str, st.session_state.duplicate_sort_numbers))}. Please fix and save again.")
        
        # Loop through active cards and create a number input for each
        for index, card in active_cards_df.iterrows():
            col1, col2 = st.columns([1, 3])
            # Get the value from session state if it exists (for sticky form)
            default_val = st.session_state.get(f"sort_{index}", int(card["Sort Order"]))
            
            with col1:
                st.number_input(
                    "Order", 
                    value=default_val, 
                    key=f"sort_{index}",  # Unique key for each input
                    step=1,
                    min_value=1
                )
            with col2:
                st.subheader(f"{card['Bank']} {card['Card Name']}", anchor=False)
                # Show error on the specific row with a duplicate
                if default_val in st.session_state.duplicate_sort_numbers:
                    st.error("This number is a duplicate.")
            st.divider()

        # --- Form Buttons ---
        col1, col2 = st.columns([1, 1])
        with col1:
            submitted = st.form_submit_button("Save Order", use_container_width=True, type="primary")
        with col2:
            if st.form_submit_button("Cancel", use_container_width=True):
                st.session_state.duplicate_sort_numbers = []
                st.session_state.show_sort_form = False
                st.rerun()

    # --- Form Submission Logic ---
    if submitted:
        # Check for duplicates
        all_new_orders = []
        for index in active_cards_df.index:
            all_new_orders.append(st.session_state[f"sort_{index}"])
        
        # Use Counter to find items with a count > 1
        duplicates = [item for item, count in Counter(all_new_orders).items() if count > 1]
        
        if duplicates:
            # If duplicates found, save them to state and rerun to show errors
            st.session_state.duplicate_sort_numbers = duplicates
            st.rerun()
        else:
            # No duplicates, proceed with saving
            st.session_state.duplicate_sort_numbers = [] 
            df_to_save = load_data()
            for index in active_cards_df.index:
                new_order = st.session_state[f"sort_{index}"]
                df_to_save.loc[index, "Sort Order"] = new_order
            
            df_to_save.to_csv(DATA_FILE, index=False)
            st.success("Card order saved!")
            st.session_state.show_sort_form = False
            st.rerun()

# =============================================================================
# 5. "Card Details" Page
# =============================================================================
def show_details_page():
    """Displays a full, clean page with all details for a single card."""
    st.title("Card Details", anchor=False)
    
    all_cards_df = load_data()
    card_index = st.session_state.card_to_view  # Get index from state
    
    if card_index is None or card_index not in all_cards_df.index:
        st.error("Could not find card to view. Returning to dashboard."); 
        st.session_state.show_details_page = False; 
        st.rerun(); 
        return
        
    card = all_cards_df.iloc[card_index]  # Get the card data
    
    if st.button("← Back to Dashboard"):
        st.session_state.show_details_page = False
        st.session_state.card_to_view = None
        st.rerun()
    
    st.divider()
    
    # Helper for formatting dates
    strftime_code = STRFTIME_MAP[st.session_state.date_format]
    def format_date_display(date_val):
        if pd.isna(date_val):
            return "N/A"
        return pd.to_datetime(date_val).strftime(strftime_code)

    # --- Main Details ---
    col1, col2 = st.columns([1, 2])
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
        st.markdown(f"**Annual Fee:** ${card['Annual Fee']:.2f}")
        st.markdown(f"**Fee Month:** {card['Month of Annual Fee']}")
        st.markdown(f"**Card Expiry:** {card['Card Expiry (MM/YY)']}")
        tags_str = card.get("Tags", "")
        if tags_str:
            st.markdown(f"**Tags:** `{tags_str.replace(',', ', ')}`")

    # --- Notes ---
    notes = card.get("Notes", "")
    if notes and pd.notna(notes):
        st.divider()
        st.subheader("Notes", anchor=False)
        st.markdown(notes)

    # --- Welcome Offer ---
    st.divider()
    st.subheader("Welcome Offer", anchor=False)
    bonus_offer = card.get("Bonus Offer", "")
    min_spend = card.get("Min Spend", 0.0)
    
    if not bonus_offer and min_spend == 0.0:
        st.write("No welcome offer details logged for this card.")
    else:
        b_col1, b_col2, b_col3 = st.columns(3)
        b_col1.metric("Bonus Offer", bonus_offer if bonus_offer else "N/A")
        b_col2.metric("Min Spend", f"${min_spend:,.2f}")
        b_col3.metric("Bonus Status", card.get("Bonus Status", "N/A"))
        st.metric("Min Spend Deadline", format_date_display(card["Min Spend Deadline"]))

    # --- Card Dates ---
    st.divider()
    st.subheader("Card Dates", anchor=False)
    d_col1, d_col2, d_col3 = st.columns(3)
    with d_col1:
        st.metric("Date Applied", format_date_display(card["Date Applied"]))
        st.metric("Date Approved", format_date_display(card["Date Approved"]))
    with d_col2:
        st.metric("Date Received", format_date_display(card["Date Received Card"]))
        st.metric("Date Activated", format_date_display(card["Date Activated Card"]))
    with d_col3:
        st.metric("First Charge Date", format_date_display(card["First Charge Date"]))

    # --- Cancellation Info (if it exists) ---
    if pd.notna(card["Cancellation Date"]):
        st.divider()
        st.subheader("Cancellation Info", anchor=False)
        c_col1, c_col2 = st.columns(2)
        c_col1.metric("Cancelled On", format_date_display(card["Cancellation Date"]))
        c_col2.metric("Re-apply After", format_date_display(card["Re-apply Date"]))


# =============================================================================
# 6. "Manage Tags" Page
# =============================================================================
def show_tag_manager_page():
    """Displays a page to add/delete tags from the master tag list."""
    st.title("🏷️ Manage Tags", anchor=False)
    if st.button("← Back to Dashboard"):
        st.session_state.show_tag_manager = False
        st.rerun()
    
    st.write("Here you can add or remove tags from the master list. This list will appear as options when you add or edit a card.")
    
    all_tags = load_tags()
    
    # --- "Add New Tag" Form ---
    st.divider()
    st.subheader("Add a New Tag", anchor=False)
    with st.form("add_tag_form", clear_on_submit=True):
        new_tag = st.text_input("New Tag Name")
        submitted = st.form_submit_button("Add Tag")
        
        if submitted and new_tag:
            if new_tag in all_tags:
                st.warning(f"Tag '{new_tag}' already exists.")
            else:
                all_tags.append(new_tag)
                if save_tags(all_tags):  # Save the updated list
                    st.success(f"Added tag '{new_tag}'.")
                    st.rerun()  # Rerun to show the new tag in the list below
                
    st.divider()
    st.subheader("Existing Tags", anchor=False)
    
    if not all_tags:
        st.info("No tags added yet.")
        return  # Don't show the delete form if there are no tags

    # --- "Delete Tags" Form ---
    # This UI is cleaner than individual delete buttons
    with st.form("delete_tags_form"):
        tags_to_delete = st.multiselect(
            "Select tags to delete",
            options=all_tags
        )
        
        submitted_delete = st.form_submit_button("Delete Selected Tags", type="primary")
        
        if submitted_delete and tags_to_delete:
            # Create a new list containing only the tags to keep
            tags_to_keep = [tag for tag in all_tags if tag not in tags_to_delete]
            
            if save_tags(tags_to_keep):  # Save the filtered list
                st.success(f"Deleted tags: {', '.join(tags_to_delete)}")
                
                # --- Critical Step: Remove deleted tags from all cards ---
                df = load_data()
                def remove_deleted_tags(tags_str):
                    tags_list = [t.strip() for t in tags_str.split(',') if t.strip()]
                    # Re-build the list, only keeping non-deleted tags
                    cleaned_list = [t for t in tags_list if t not in tags_to_delete]
                    return ",".join(cleaned_list)
                
                df["Tags"] = df["Tags"].apply(remove_deleted_tags)
                df.to_csv(DATA_FILE, index=False)  # Save the main CSV
                st.rerun()
        elif submitted_delete:
            st.warning("Please select at least one tag to delete.")


# =============================================================================
# MAIN APP "ROUTER"
# =============================================================================
def main():
    """
    This is the main function that runs the app.
    It controls the "routing" logic to show the correct page.
    """
    
    # --- Page Configuration (must be the first st command) ---
    st.set_page_config(
        page_title="Card Tracker",
        layout="wide",
        initial_sidebar_state="expanded",
        menu_items={
            'About': "Credit Card Tracker App"
        }
    )

    # --- Custom CSS Injection ---
    # This block injects custom CSS to style the app.
    st.markdown("""
    <style>
    /* Style for all card images */
    .stImage img {
        width: 158px;
        height: 100px;
        object-fit: contain;
    }
    
    /* A small margin fix for containers */
    [data-testid="stVerticalBlock"] > [data-testid="stHorizontalBlock"] > [data-testid="stContainer"] {
        margin-top: 10px;
    }

    /* --- CSS FOR TAG BUTTONS (on Manage Tags page) --- */
    /* Targets only buttons with this specific tooltip */
    button[title^="Click to delete tag:"] {
        background-color: #31333F;
        color: #FAFAFA;
        border: 1px solid #555555;
        border-radius: 20px; /* Makes it a "pill" */
        padding: 4px 12px;
        margin: 0;
        transition: background-color 0.2s ease, border-color 0.2s ease;
    }
    button[title^="Click to delete tag:"]:hover {
        background-color: #44444A;
        border-color: #777777;
    }
    button[title^="Click to delete tag:"]:active {
        background-color: #2A2B32;
        border-color: #555555;
    }
    </style>
    """, unsafe_allow_html=True)

    # --- Load Data ---
    all_cards_df = load_data()
    card_mapping = get_card_mapping()

    # --- Page Routing Logic ---
    # This `if/elif` block checks the session state to decide which page-function to run.
    # This is how Streamlit can simulate a multi-page app.
    if st.session_state.show_add_form:
        show_add_card_form(card_mapping)
    elif st.session_state.show_edit_form:
        show_edit_form()
    elif st.session_state.show_sort_form:
        show_sort_order_form()
    elif st.session_state.show_details_page:
        show_details_page()
    elif st.session_state.show_tag_manager:
        show_tag_manager_page()
    elif all_cards_df.empty:
        # --- "Empty State" Page ---
        # Show this only if the CSV is empty
        st.title("Welcome to your Credit Card Tracker!", anchor=False)
        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            if st.button("Add Your First Card", use_container_width=True, type="primary"):
                st.session_state.show_add_form = True
                st.rerun()
    else:
        # --- Default Page ---
        # If no other state is active, show the main dashboard
        show_dashboard(all_cards_df)

# --- Standard Python Entry Point ---
if __name__ == "__main__":
    main()