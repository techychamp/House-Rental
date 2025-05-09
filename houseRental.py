import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from datetime import datetime
from io import BytesIO
import hashlib

# === Utility Functions ===
def hash_string(s):
    return hashlib.sha256(s.encode()).hexdigest()

def check_hash(input_text, stored_hash):
    return hash_string(input_text.strip().lower()) == stored_hash

# === Session Initialization ===
if "users" not in st.session_state:
    st.session_state.users = {
        "admin@broker.com": {
            "name": "Admin",
            "password": hash_string("admin123"),
            "role": "Admin",
            "security": {
                "food": hash_string("none"),
                "pet": hash_string("none")
            }
        },
        "agent@broker.com": {
            "name": "Agent",
            "password": hash_string("password"),
            "role": "Agent",
            "security": {
                "food": hash_string("none"),
                "pet": hash_string("none")
            }
        }
    }

if "user" not in st.session_state:
    st.session_state.user = None

if "auth_mode" not in st.session_state:
    st.session_state.auth_mode = 0

if "listings" not in st.session_state:
    st.session_state.listings = []

if "favorites" not in st.session_state:
    st.session_state.favorites = []

if "active_tab" not in st.session_state:
    st.session_state.active_tab = "🏡 Listings"

if "selected_property" not in st.session_state:
    st.session_state.selected_property = 0

# === Auth UI ===
st.set_page_config(page_title="House Brokerage App", layout="wide")

if st.session_state.user == None:
    st.sidebar.title("User Access")

    auth_mode = st.sidebar.radio("Auth Mode", ["Login", "Register", "Reset Password"],index = st.session_state.auth_mode)
    with st.sidebar.form("auth_form") as auth_data:
        if auth_mode == "Register":
            st.session_state.auth_mode = 1
            st.sidebar.subheader("🔐 Register")
            new_name = st.sidebar.text_input("Full Name")
            new_email = st.sidebar.text_input("Email")
            new_pass = st.sidebar.text_input("Password", type="password")
            confirm_pass = st.sidebar.text_input("Confirm Password", type="password")
            dob = st.sidebar.date_input("Date of Birth")
            new_role = st.sidebar.selectbox("Role", ["Buyer", "Agent"])
            fav_food = st.sidebar.text_input("Favorite Food?")
            pet_name = st.sidebar.text_input("Pet's Name?")
            if st.sidebar.button("Register"):
                if new_email in st.session_state.users:
                    st.sidebar.error("Email already registered.")
                elif not all([new_email, new_pass, confirm_pass, fav_food, pet_name]):
                    st.sidebar.warning("All fields are required.")
                elif new_pass != confirm_pass:
                    st.sidebar.error("Passwords do not match.")
                else:
                    st.session_state.users[new_email] = {
                        "name": new_name,
                        "dob": str(dob),
                        "password": hash_string(new_pass),
                        "role": new_role,
                        "security": {
                            "food": hash_string(fav_food),
                            "pet": hash_string(pet_name)
                        }
                    }
                    st.sidebar.success("Registered! You can now log in.")
                    st.rerun()

        elif auth_mode == "Login":
            st.session_state.auth_mode = 0
            st.sidebar.subheader("🔓 Login")
            email = st.sidebar.text_input("Email")
            password = st.sidebar.text_input("Password", type="password")
            if st.sidebar.button("Login"):
                user_data = st.session_state.users.get(email)
                if user_data and check_hash(password, user_data["password"]):
                    st.session_state.user = {
                        "email": email,
                        "name": user_data["name"],
                        "role": user_data["role"]
                    }
                    st.sidebar.success(f"Welcome {user_data['name']} ({user_data['role']})")
                else:
                    st.sidebar.error("Invalid credentials")

        elif auth_mode == "Reset Password":
            st.session_state.auth_mode = 2
            st.sidebar.subheader("🔁 Reset Password")
            email = st.sidebar.text_input("Registered Email")
            food_ans = st.sidebar.text_input("What is your favorite food?")
            pet_ans = st.sidebar.text_input("What is your pet's name?")
            new_pass = st.sidebar.text_input("New Password", type="password")
            if st.sidebar.button("Reset Password"):
                user = st.session_state.users.get(email)
                if not user:
                    st.sidebar.error("Email not found.")
                elif (check_hash(food_ans, user["security"]["food"]) and
                      check_hash(pet_ans, user["security"]["pet"])):
                    user["password"] = hash_string(new_pass)
                    st.sidebar.success("Password reset successful!")
                    st.rerun()
                else:
                    st.sidebar.error("Security answers do not match.")
else:
    st.sidebar.success(f"Welcome {st.session_state.user['name']} ({st.session_state.user['role']})")
    if st.sidebar.button("Logout"):
        st.session_state.user = None
        st.rerun()

# === Access Protection ===
if not st.session_state.user:
    st.warning("Please log in or register to use the app.")
    st.stop()

user = st.session_state.user

# === Tabs ===

def filter_tabs(allowed, tabs):
    return [t for i, t in enumerate(tabs) if allowed[i]]

base_tabs = ["🏡 Listings", "➕ Add Property", "📍 Map", "💾 Favorites",
             "📞 Contact", "💰 Mortgage", "📊 Dashboard"]

permitted_tabs = [True for _ in base_tabs]

if user["role"] == "Buyer":
    permitted_tabs[1] = False
    permitted_tabs[-1] = False
if user["role"] == "Agent":
    permitted_tabs[-1] = False

filtered_tabs = filter_tabs(permitted_tabs, base_tabs)

# Sort tabs to put active_tab first to force focus
if st.session_state.active_tab in filtered_tabs:
    filtered_tabs.remove(st.session_state.active_tab)
    filtered_tabs.insert(0, st.session_state.active_tab)

tabs = st.tabs(filtered_tabs)

LISTING_LIMIT = 50

def contact_seller(id):
    st.session_state.selected_property = id
    st.session_state.active_tab = "📞 Contact"
    st.rerun()

# === Listings Tab ===
with tabs[filtered_tabs.index("🏡 Listings")]:
    st.subheader("Available Listings")

    with st.expander("🔍 Filters"):
        type_filter = st.selectbox("Type", ["All", "Sale", "Rent"])
        price_max = st.slider("Max Price", 500, 1000000, 300000)
        keyword = st.text_input("Keyword Search")

    df = pd.DataFrame(st.session_state.listings)
    if not df.empty:
        if type_filter != "All":
            df = df[df["Type"] == type_filter]
        df = df[df["Price"] <= price_max]
        if keyword:
            df = df[df["Title"].str.contains(keyword, case=False)]

        for i, row in df.iterrows():
            with st.container():
                cols = st.columns([1, 3])
                with cols[0]:
                    if row["Image"]:
                        st.image(BytesIO(row["Image"]), width=150)
                with cols[1]:
                    st.markdown(f"**{row['Title']}**")
                    st.markdown(f"{row['Location']} • {row['Type']} • ${row['Price']}")
                    st.markdown(f"{row['Bedrooms']} Beds • {row['Bathrooms']} Baths • {row['Size']} sqft")
                    #contact button
                    st.button("📞 Contact Seller", key=i,on_click=contact_seller,args=(i,))
                    if user["role"] != "Admin":
                        if st.button("💾 Save to Favorites", key=f"fav_{i}"):
                            st.session_state.favorites.append(row["Title"])
    else:
        st.info("No listings available.")

# === Add Property Tab ===
if user["role"] in ["Agent", "Admin"]:
    with tabs[filtered_tabs.index("➕ Add Property")]:
        st.subheader("Add New Property")
        if len(st.session_state.listings) >= LISTING_LIMIT:
            st.warning("Listing limit reached. Delete old entries to add more.")
        else:
            with st.form("add_listing",clear_on_submit=True):
                title = st.text_input("Title")
                location = st.text_input("Location")
                price = st.number_input("Price", min_value=0)
                ptype = st.selectbox("Type", ["Sale", "Rent"])
                beds = st.slider("Bedrooms", 1, 10, 2)
                baths = st.slider("Bathrooms", 1, 10, 1)
                area = st.number_input("Size (sqft)", min_value=100)
                lat = st.number_input("Latitude", format="%.6f")
                lon = st.number_input("Longitude", format="%.6f")
                image = st.file_uploader("Upload Image", type=["png", "jpg", "jpeg"])
                submit = st.form_submit_button("Add Listing")

                if submit and title and location:
                    image_bytes = image.read() if image else None
                    st.session_state.listings.append({
                        "Title": title,
                        "Location": location,
                        "Price": price,
                        "Type": ptype,
                        "Bedrooms": beds,
                        "Bathrooms": baths,
                        "Size": area,
                        "Latitude": lat,
                        "Longitude": lon,
                        "Image": image_bytes,
                        "Date": datetime.now().strftime("%Y-%m-%d")
                    })
                    st.success("Property added successfully!")

# === Map Tab ===
with tabs[filtered_tabs.index("📍 Map")]:
    st.subheader("Map View")
    m = folium.Map(location=[20, 77], zoom_start=4)
    for row in st.session_state.listings:
        folium.Marker([row["Latitude"], row["Longitude"]],
                      popup=f"{row['Title']} (${row['Price']})").add_to(m)
    st_folium(m, width=700)

# === Favorites Tab ===
with tabs[filtered_tabs.index("💾 Favorites")]:
    st.subheader("Saved Favorites")
    favs = st.session_state.favorites
    if favs:
        st.write(pd.Series(favs).value_counts())
    else:
        st.info("No favorites saved.")

# === Contact Tab ===
with tabs[filtered_tabs.index("📞 Contact")]:
    st.subheader("Contact Seller / Broker")
    with st.form("contact_form"):
        name = st.text_input("Your Name", value=user["name"], disabled=True)
        email = st.text_input("Email", value=user["email"], disabled=True)
        property_title = st.selectbox("Select Listing", [p["Title"] for p in st.session_state.listings],index=st.session_state.selected_property)
        message = st.text_area("Message")
        send = st.form_submit_button("Send Inquiry")
        if send:
            st.success(f"Inquiry sent regarding '{property_title}' (simulated).")

# === Mortgage Calculator ===
with tabs[filtered_tabs.index("💰 Mortgage")]:
    st.subheader("Mortgage Calculator")
    amount = st.number_input("Property Price", value=100000)
    rate = st.number_input("Interest Rate (%)", value=7.0)
    years = st.number_input("Loan Term (Years)", value=20)
    if st.button("Calculate"):
        r = rate / 12 / 100
        n = years * 12
        if r > 0:
            emi = (amount * r * (1 + r)**n) / ((1 + r)**n - 1)
            st.success(f"Monthly EMI: ${emi:.2f}")
        else:
            st.warning("Enter a valid interest rate.")

# === Admin Dashboard ===
if user["role"] == "Admin":
    with tabs[filtered_tabs.index("📊 Dashboard")]:
        st.subheader("Admin Dashboard")
        st.write("Total Listings:", len(st.session_state.listings))

        if st.session_state.favorites:
            most_fav = pd.Series(st.session_state.favorites).value_counts().idxmax()
            st.write("Most Saved Property:", most_fav)

        if(len(st.session_state.listings)>0):
          df_export = pd.DataFrame(st.session_state.listings).drop(columns=["Image"])
          csv = df_export.to_csv(index=False).encode("utf-8")
          st.download_button("📤 Export Listings as CSV", csv, "listings.csv", "text/csv")
          st.markdown("### 🗑️ Delete a Listing")
          titles = [p["Title"] for p in st.session_state.listings]
          if titles:
              to_delete = st.selectbox("Select listing to delete", titles)
              if st.button("Delete Listing"):
                  st.session_state.listings = [l for l in st.session_state.listings if l["Title"] != to_delete]
                  st.success(f"'{to_delete}' has been deleted.")
                  st.rerun()

        else:
          st.info("No listings to display.")

