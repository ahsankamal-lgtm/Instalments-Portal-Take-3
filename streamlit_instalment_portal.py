# streamlit_instalment_portal.py
import streamlit as st
import re
import urllib.parse
import mysql.connector
import pandas as pd
from io import BytesIO

# -----------------------------
# Configuration (update if needed)
# -----------------------------
DB_HOST = "3.17.21.91"
DB_USER = "ahsan"
DB_PASS = "ahsan@321"
DB_NAME = "ev_installment_project"

# -----------------------------
# DB helpers (safe: returns None if unreachable)
# -----------------------------
def get_db_connection():
    try:
        conn = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASS,
            database=DB_NAME,
            autocommit=False
        )
        return conn
    except Exception as e:
        # Do not raise — allow app to run without DB, but show helpful message
        st.error(f"🔌 Database connection failed: {e}")
        return None

def save_to_db(data: dict) -> bool:
    """Save approved applicant to DB. Returns True on success."""
    conn = get_db_connection()
    if not conn:
        st.error("❌ Cannot save: database not available.")
        return False
    try:
        cursor = conn.cursor()
        insert_sql = """
        INSERT INTO data (
            first_name, last_name, cnic, license_no,
            guarantors, female_guarantor, street_address, area_address, city,
            state_province, postal_code, country, phone_number, gender,
            electricity_bill, net_salary, emi, bike_type, bike_price
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """
        values = (
            data.get("first_name"),
            data.get("last_name"),
            data.get("cnic"),
            data.get("license_no"),
            data.get("guarantors"),
            data.get("female_guarantor"),
            data.get("street_address"),
            data.get("area_address"),
            data.get("city"),
            data.get("state_province"),
            data.get("postal_code"),
            data.get("country"),
            data.get("phone_number"),
            data.get("gender"),
            data.get("electricity_bill"),
            int(data.get("net_salary") or 0),
            int(data.get("emi") or 0),
            data.get("bike_type"),
            int(data.get("bike_price") or 0),
        )
        cursor.execute(insert_sql, values)
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        st.error(f"❌ Failed to save applicant: {e}")
        try:
            conn.rollback()
        except Exception:
            pass
        return False

def fetch_all_applicants() -> pd.DataFrame:
    conn = get_db_connection()
    if not conn:
        return pd.DataFrame()
    try:
        df = pd.read_sql("SELECT * FROM data", conn)
        conn.close()
        return df
    except Exception as e:
        st.error(f"❌ Failed to fetch applicants: {e}")
        try:
            conn.close()
        except Exception:
            pass
        return pd.DataFrame()

def delete_applicant_by_id(applicant_id: int) -> bool:
    conn = get_db_connection()
    if not conn:
        return False
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM data WHERE id = %s", (int(applicant_id),))
        conn.commit()
        cur.close()
        conn.close()
        return True
    except Exception as e:
        st.error(f"❌ Failed to delete applicant: {e}")
        try:
            conn.rollback()
        except Exception:
            pass
        return False

# -----------------------------
# Export helpers
# -----------------------------
def df_to_excel_bytes(df: pd.DataFrame) -> bytes:
    output = BytesIO()
    # Use context manager so writer.save() is not needed
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="Applicants")
    return output.getvalue()

def df_to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")

# -----------------------------
# Validation & Scoring utilities
# -----------------------------
def validate_cnic(cnic: str) -> bool:
    return bool(re.fullmatch(r"\d{5}-\d{7}-\d", (cnic or "").strip()))

def validate_phone(phone: str) -> bool:
    s = (phone or "").strip()
    return s.isdigit() and 11 <= len(s) <= 12

# (Scoring functions left unchanged from your model — keep them if you need them later.)
# For brevity they are omitted here; the app will still work for applicant capture / DB operations.

# -----------------------------
# Streamlit UI
# -----------------------------
st.set_page_config(page_title="⚡ Electric Bike Finance Portal", layout="centered")
st.title("⚡ Electric Bike Finance Portal")

tabs = st.tabs(["📋 Applicant Information", "📊 Evaluation", "✅ Results", "📂 Applicants"])

# -----------------------------
# Page 1: Applicant Info
# -----------------------------
with tabs[0]:
    st.header("Applicant Information")

    first_name = st.text_input("First Name")
    last_name = st.text_input("Last Name")

    cnic = st.text_input("CNIC Number (Format: XXXXX-XXXXXXX-X)")
    if cnic and not validate_cnic(cnic):
        st.error("❌ Invalid CNIC format. Use XXXXX-XXXXXXX-X")

    license_suffix = st.text_input("Enter last 3 digits for License Number (#XXX)")
    # if suffix provided ensure numeric & length 3
    license_number = ""
    if validate_cnic(cnic) and license_suffix:
        if license_suffix.isdigit() and len(license_suffix) == 3:
            license_number = f"{cnic}#{license_suffix}"
        else:
            st.error("❌ License suffix must be 3 digits.")

    guarantors = st.radio("Guarantors Available?", ["Yes", "No"])
    female_guarantor = None
    if guarantors == "Yes":
        female_guarantor = st.radio("At least one Female Guarantor?", ["Yes", "No"])

    # Address fields
    street_address = st.text_input("Street Address")
    area_address = st.text_input("Area Address")
    city = st.text_input("City")
    state_province = st.text_input("State/Province")
    postal_code = st.text_input("Postal Code (optional)")
    country = st.text_input("Country")

    # View location button — opens Google Maps in a new tab
    if st.button("📍 View Location on Google Maps"):
        if street_address and area_address and city and state_province and country:
            full_address = f"{street_address}, {area_address}, {city}, {state_province}, {country}"
            if postal_code:
                full_address += f", {postal_code}"
            encoded = urllib.parse.quote_plus(full_address)
            maps_url = f"https://www.google.com/maps/search/?api=1&query={encoded}"
            # open in new tab using a tiny HTML snippet
            js = f"""<script>window.open("{maps_url}","_blank").focus();</script>"""
            st.components.v1.html(js, height=0)
        else:
            st.error("❌ Please complete Street, Area, City, State/Province and Country before viewing on Maps.")

    phone_number = st.text_input("Phone Number (11–12 digits)")
    if phone_number and not validate_phone(phone_number):
        st.error("❌ Invalid Phone Number - Please enter a valid phone number")

    gender = st.radio("Gender", ["M", "F"])
    electricity_bill = st.radio("Is electricity bill available?", ["Yes", "No"])

    # Validation rules (guarantor + electricity + required fields)
    guarantor_valid = (guarantors == "Yes")
    female_guarantor_valid = (female_guarantor == "Yes") if guarantors == "Yes" else True
    phone_valid = validate_phone(phone_number) if phone_number else False
    electricity_valid = (electricity_bill == "Yes")

    if not guarantor_valid:
        st.error("🚫 Application Rejected: No guarantor available.")
    elif guarantors == "Yes" and not female_guarantor_valid:
        st.error("🚫 Application Rejected: At least one female guarantor is required.")
    elif not electricity_valid:
        st.error("🚫 Application Rejected: Electricity bill not available.")

    info_complete = all([
        first_name, last_name, validate_cnic(cnic), license_number,
        guarantor_valid, female_guarantor_valid,
        street_address, area_address, city, state_province, country,
        phone_valid, gender, electricity_valid
    ])

    st.session_state.applicant_valid = info_complete

    if info_complete:
        st.success("✅ Applicant Information completed. Proceed to Evaluation tab.")
    else:
        st.warning("⚠️ Please complete all required fields correctly to proceed.")

# -----------------------------
# Page 2: Evaluation (placeholder — keeps flow intact)
# -----------------------------
with tabs[1]:
    if not st.session_state.get("applicant_valid", False):
        st.error("🚫 Please complete Applicant Information first.")
    else:
        st.subheader("Evaluation Inputs")
        st.info("You already have the applicant info. Add loan/product inputs on this page (EMI, bank balance, etc.).")
        # Minimal inputs (you can expand per your scoring model)
        net_salary = st.number_input("Net Salary", min_value=0, step=1000)
        emi = st.number_input("Monthly Installment (EMI)", min_value=0, step=500)
        avg_6m_balance = st.number_input("Average 6M Bank Balance", min_value=0, step=1000)
        bike_type = st.selectbox("Bike Type", ["EV-1", "EV-125"])
        bike_price = st.number_input("Bike Price", min_value=0, step=1000)
        outstanding = st.number_input("Outstanding Loan", min_value=0, step=1000)

# -----------------------------
# Page 3: Results (placeholder)
# -----------------------------
with tabs[2]:
    if not st.session_state.get("applicant_valid", False):
        st.error("🚫 Please complete Applicant Information first.")
    else:
        st.subheader("Results")
        st.info("Calculation & scoring will appear here using your scoring functions.")
        # Example display of what would be saved:
        st.write("Applicant summary (preview):")
        st.write({
            "first_name": first_name,
            "last_name": last_name,
            "cnic": cnic,
            "license_no": license_number,
            "phone": phone_number,
            "gender": gender,
            "electricity_bill": electricity_bill
        })
        # Save button — only shown if DB reachable and decision approved in your real flow
        if st.button("💾 Save to database (example)"):
            payload = {
                "first_name": first_name,
                "last_name": last_name,
                "cnic": cnic,
                "license_no": license_number,
                "guarantors": guarantors,
                "female_guarantor": female_guarantor or "No",
                "street_address": street_address,
                "area_address": area_address,
                "city": city,
                "state_province": state_province,
                "postal_code": postal_code,
                "country": country,
                "phone_number": phone_number,
                "gender": gender,
                "electricity_bill": electricity_bill,
                "net_salary": locals().get("net_salary", 0),
                "emi": locals().get("emi", 0),
                "bike_type": locals().get("bike_type", ""),
                "bike_price": locals().get("bike_price", 0),
            }
            ok = save_to_db(payload)
            if ok:
                st.success("✅ Applicant saved to database.")
                # refresh applicants tab by rerunning app
                st.experimental_rerun()

# -----------------------------
# Page 4: Applicants Database
# -----------------------------
with tabs[3]:
    st.subheader("Applicants Database")

    # Fetch applicants (graceful if DB down)
    df = fetch_all_applicants()
    if df.empty:
        st.info("No applicants found or database unavailable.")
    else:
        # Build simple dropdown of applicants for deletion (safer)
        df["label"] = df.apply(lambda r: f"{r['id']} - {r.get('first_name','')} {r.get('last_name','')}", axis=1)
        selected = st.selectbox("Select applicant to delete", options=df["label"].tolist())

        st.dataframe(df.drop(columns=["label"]), use_container_width=True)

        # Download CSV / Excel
        st.download_button("⬇️ Download CSV", data=df_to_csv_bytes(df), file_name="applicants.csv", mime="text/csv")
        st.download_button("⬇️ Download Excel", data=df_to_excel_bytes(df), file_name="applicants.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

        # Delete with confirmation
        if st.button("🗑️ Delete selected applicant"):
            confirm = st.checkbox("Please confirm deletion of the selected applicant", key="confirm_delete")
            if confirm:
                try:
                    sel_id = int(selected.split(" - ")[0])
                    ok = delete_applicant_by_id(sel_id)
                    if ok:
                        st.success(f"✅ Applicant {sel_id} deleted.")
                        st.experimental_rerun()
                    else:
                        st.error("❌ Delete failed.")
                except Exception as e:
                    st.error(f"❌ Delete error: {e}")
            else:
                st.warning("⚠️ You must check the confirmation box to delete.")
