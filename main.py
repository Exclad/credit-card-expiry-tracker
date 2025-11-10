import streamlit as st
import pandas as pd
from datetime import datetime
import os

# --- Configuration ---
DATA_FILE = "my_cards.csv"
IMAGE_DIR = "card_images" # We will scan this folder

# --- Setup: Create data file and image directory if they don't exist ---
if not os.path.exists(DATA_FILE):
    # Create an empty CSV with the new columns
    df = pd.DataFrame(columns=[
        "Bank", "Card Name", "Annual Fee", "Expiry", "Month of Annual Fee",
        "Date Applied", "Date Approved", "Date Received Card", 
        "Date Activated Card", "First Charge", "Use Case", 
        "Image Filename" # We store the filename of the image
    ])
    df.to_csv(DATA_FILE, index=False)

if not os.path.exists(IMAGE_DIR):
    os.makedirs(IMAGE_DIR)

# --- Initialize Session State ---
# This is key for managing which "page" we are on.
if 'show_add_form' not in st.session_state:
    st.session_state.show_add_form = False

# --- Helper Functions ---
def load_data():
    """Loads the card data from the CSV file."""
    try:
        return pd.read_csv(DATA_FILE)
    except pd.errors.EmptyDataError:
        # Return an empty DataFrame if the CSV is empty
        return pd.DataFrame(columns=[
            "Bank", "Card Name", "Annual Fee", "Expiry", "Month of Annual Fee",
            "Date Applied", "Date Approved", "Date Received Card", 
            "Date Activated Card", "First Charge", "Use Case", "Image Filename"
        ])

def get_card_mapping():
    """
    Scans the IMAGE_DIR and creates a mapping.
    Returns a dictionary like:
    {
        "HSBC Revolution": "HSBC_Revolution.png",
        "DBS Altitude": "DBS_Altitude.png"
    }
    """
    card_mapping = {}
    try:
        for filename in os.listdir(IMAGE_DIR):
            if filename.endswith((".png", ".jpg", ".jpeg")):
                # Remove extension
                base_name = os.path.splitext(filename)[0]
                # Split 'Bank_CardName' into 'Bank' and 'CardName'
                parts = base_name.split("_")
                if len(parts) >= 2:
                    bank = parts[0]
                    card_name = " ".join(parts[1:]) # Re-join if card name has spaces (e.g., Absolute_Cashback)
                    display_name = f"{bank} {card_name}"
                    card_mapping[display_name] = filename
    except FileNotFoundError:
        st.error(f"Image directory '{IMAGE_DIR}' not found. Please create it.")
    return card_mapping

# =============================================================================
# 1. "Add New Card" Page (Main Area)
# =============================================================================
def show_add_card_form(card_mapping):
    """
    Displays the full-page form for adding a new card.
    """
    st.title("Add a New Card")
    st.write("Select a card from the list. This list is populated by the images in your `card_images` folder.")

    if not card_mapping:
        st.error("No card images found in the 'card_images' folder.")
        st.info("To add a card, first add an image like 'Bank_CardName.png' to the `card_images` directory in your project.")
        if st.button("Back to Dashboard"):
            st.session_state.show_add_form = False
            st.rerun()
        return # Stop execution if no cards are available

    with st.form("new_card_form"):
        # --- Card Selection (The new logic) ---
        selected_display_name = st.selectbox(
            "Choose a card*",
            options=sorted(card_mapping.keys())
        )
        
        # Show a preview of the selected card
        if selected_display_name:
            image_filename = card_mapping[selected_display_name]
            st.image(os.path.join(IMAGE_DIR, image_filename), width=200)

        st.divider()

        # --- Other Details ---
        st.subheader("Enter Your Personal Details")
        annual_fee = st.number_input("Annual Fee ($)", min_value=0.0, step=1.00, format="%.2f")
        
        month_names = ["January", "February", "March", "April", "May", "June", 
                       "July", "August", "September", "October", "November", "December"]
        fee_month = st.selectbox("Month of Annual Fee*", options=month_names)

        use_case = st.text_area("Use Case (e.g., 'Dining, Online')")
        
        st.write("---") # Visual separator
        expiry_date = st.date_input("Expiry Date")
        applied_date = st.date_input("Date Applied")
        approved_date = st.date_input("Date Approved")
        received_date = st.date_input("Date Received Card")
        activated_date = st.date_input("Date Activated Card")
        first_charge_date = st.date_input("First Charge Date")

        # Form submission buttons
        col1, col2 = st.columns([1, 1])
        with col1:
            submitted = st.form_submit_button("Add This Card", use_container_width=True, type="primary")
        with col2:
            if st.form_submit_button("Cancel", use_container_width=True):
                st.session_state.show_add_form = False
                st.rerun()

    if submitted:
        # --- Save Logic ---
        # Get the bank and card name from the selected display name
        image_filename = card_mapping[selected_display_name]
        base_name = os.path.splitext(image_filename)[0]
        parts = base_name.split("_")
        bank = parts[0]
        card_name = " ".join(parts[1:])
        
        # Create a new row as a dictionary
        new_card = {
            "Bank": bank,
            "Card Name": card_name,
            "Annual Fee": annual_fee,
            "Expiry": expiry_date,
            "Month of Annual Fee": fee_month,
            "Date Applied": applied_date,
            "Date Approved": approved_date,
            "Date Received Card": received_date,
            "Date Activated Card": activated_date,
            "First Charge": first_charge_date,
            "Use Case": use_case,
            "Image Filename": image_filename # Save the filename
        }
        
        # Append to the CSV
        df = load_data()
        new_df = pd.DataFrame([new_card])
        df = pd.concat([df, new_df], ignore_index=True)
        df.to_csv(DATA_FILE, index=False)
        
        st.success(f"Successfully added {bank} {card_name}!")
        st.session_state.show_add_form = False
        st.rerun() # Rerun to go back to the dashboard

# =============================================================================
# 2. Main Dashboard Page
# =============================================================================
def show_dashboard(all_cards_df):
    """
    Displays the main dashboard with notifications and all cards.
    """
    # --- Sidebar "Add Card" button ---
    # This button only appears on the dashboard
    if st.sidebar.button("Add New Card"):
        st.session_state.show_add_form = True
        st.rerun() # Rerun to trigger the "add form" page
    
    st.title("💳 Credit Card Dashboard")

    # --- Replicate your Apps Script Logic ---
    st.header("Annual Fee Notifications")
    
    today = datetime.today()
    current_month_index = today.month - 1 # Python's datetime month is 1-12
    next_month_index = (today.month % 12)
    month_names = ["January", "February", "March", "April", "May", "June", 
                   "July", "August", "September", "October", "November", "December"]
    current_month_name = month_names[current_month_index]
    next_month_name = month_names[next_month_index]

    cards_due_this_month = all_cards_df[all_cards_df["Month of Annual Fee"] == current_month_name]
    cards_due_next_month = all_cards_df[all_cards_df["Month of Annual Fee"] == next_month_name]

    # --- Display This Month's Notifications ---
    st.subheader(f"Due This Month ({current_month_name})")
    if cards_due_this_month.empty:
        st.write("No annual fees due this month.")
    else:
        for _, card in cards_due_this_month.iterrows():
            fee = card['Annual Fee']
            fee_text = f"The fee is **${fee:.2f}**." if fee > 0 else "This card's annual fee is $0, but please verify."
            st.warning(f"**{card['Bank']} {card['Card Name']}**: {fee_text}")

    # --- Display Next Month's Notifications ---
    st.subheader(f"Due Next Month ({next_month_name})")
    if cards_due_next_month.empty:
        st.write("No annual fees due next month.")
    else:
        for _, card in cards_due_next_month.iterrows():
            fee = card['Annual Fee']
            fee_text = f"The fee is **${fee:.2f}**." if fee > 0 else "This card's annual fee is $0, but please verify."
            st.info(f"**{card['Bank']} {card['Card Name']}**: {fee_text}")

    # --- Display All My Cards ---
    st.header("All My Cards")
    st.write("Here is a full list of all cards you are tracking.")
    
    for index, card in all_cards_df.iterrows():
        st.divider()
        col1, col2 = st.columns([1, 3])
        
        with col1:
            # Use the saved Image Filename to show the correct image
            image_path = os.path.join(IMAGE_DIR, str(card["Image Filename"]))
            if os.path.exists(image_path):
                st.image(image_path, width=150)
            else:
                st.write(f"Image not found: {card['Image Filename']}")
                st.image("", width=100) # Placeholder

        with col2:
            st.subheader(f"{card['Bank']} {card['Card Name']}")
            st.metric(label="Annual Fee", value=f"${card['Annual Fee']:.2f}", delta=f"Due in {card['Month of Annual Fee']}")
            
            with st.expander("Show All Dates and Details"):
                # We drop columns we don't need to see in the expander
                st.dataframe(card.to_frame().T.drop(columns=["Bank", "Card Name", "Annual Fee", "Month of Annual Fee", "Image Filename"]))

# =============================================================================
# MAIN APP "ROUTER"
# This logic decides which page to show
# =============================================================================
def main():
    st.set_page_config(page_title="Card Tracker", layout="wide")
    
    # Load all data and mappings
    all_cards_df = load_data()
    card_mapping = get_card_mapping()

    # --- This is the new navigation logic ---
    
    if st.session_state.show_add_form:
        # STATE 1: Show the "Add Card" form (full page)
        show_add_card_form(card_mapping)
        
    elif all_cards_df.empty:
        # STATE 2: No cards exist yet (empty state)
        st.title("Welcome to your Credit Card Tracker!")
        st.write("You don't have any cards saved yet.")
        
        # Center the button using columns
        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            if st.button("Add Your First Card", use_container_width=True, type="primary"):
                st.session_state.show_add_form = True
                st.rerun()
                
    else:
        # STATE 3: Cards exist, show the main dashboard
        show_dashboard(all_cards_df)

if __name__ == "__main__":
    main()