import streamlit as st
import re
import urllib.parse
import mysql.connector
import pandas as pd
from io import BytesIO

# -----------------------------
# Database Connection
# -----------------------------
def get_db_connection():
    return mysql.connector.connect(
        host="3.17.21.91",
        user="ahsan",
        password="ahsan@321",
        database="ev_installment_project"
    )
def save_to_db(data: dict):
    conn = get_db_connection()
    cursor = conn.cursor()

    # --- Check if CNIC already exists ---
    cursor.execute("SELECT COUNT(*) FROM data WHERE cnic = %s", (data["cnic"],))
    (exists,) = cursor.fetchone()
    if exists > 0:
        cursor.close()
        conn.close()
        raise ValueError("❌ CNIC already exists in the database. Please enter a unique CNIC.")

    # Columns in the exact order we will pass values
    columns = [
        "name", "cnic", "license_no",
        "phone_number", "gender",
        "guarantors", "female_guarantor", "electricity_bill", "pdc_option",  
        "education", "occupation", "designation",
        "employer_name", "employer_contact",
        "address", "city", "state_province", "postal_code", "country",
        "net_salary", "applicant_bank_balance", "guarantor_bank_balance",
        "employer_type", "age", "residence",
        "bike_type", "bike_price", "down_payment", "tenure", "emi",
        "outstanding",
        "decision"
    ]

    full_name = f"{data['first_name']} {data['last_name']}".strip()
    full_address = f"{data['street_address']}, {data['area_address']}"

    # Values in the same order as `columns`
    values = (
        full_name, data["cnic"], data["license_no"],
        data["phone_number"], data["gender"],
        data["guarantors"], data["female_guarantor"], data["electricity_bill"], data["pdc_option"],
        data.get("education"), data.get("occupation"), data.get("designation"),
        data.get("employer_name"), data.get("employer_contact"),
        full_address, data["city"], data["state_province"], data["postal_code"], data["country"],
        data["net_salary"], data["applicant_bank_balance"], data.get("guarantor_bank_balance"),
        data["employer_type"], data["age"], data["residence"],
        data["bike_type"], data["bike_price"], data["down_payment"], data["tenure"], data["emi"],data["outstanding"],
        data["decision"]
    )


    # Build placeholders dynamically so counts always match
    placeholders = ", ".join(["%s"] * len(values))
    cols_sql = ", ".join(columns)
    query = f"INSERT INTO data ({cols_sql}) VALUES ({placeholders})"

    cursor.execute(query, values)
    conn.commit()
    cursor.close()
    conn.close()


def fetch_all_applicants():
    conn = get_db_connection()
    query = """
    SELECT 
        id, 
        name, 
        cnic, 
        license_no,
        phone_number, 
        gender,
        guarantors, 
        female_guarantor, 
        electricity_bill,
        pdc_option,
        education, 
        occupation, 
        designation,
        employer_name,
        employer_contact,
        address, 
        city, 
        state_province, 
        postal_code, 
        country,
        net_salary, 
        applicant_bank_balance, 
        guarantor_bank_balance,
        employer_type, 
        age, 
        residence,
        bike_type, 
        bike_price, 
        down_payment,
        tenure,
        emi, 
        outstanding,
        decision
    FROM data
    ORDER BY id ASC;
    """
    df = pd.read_sql(query, conn)
    conn.close()
    return df


def resequence_ids():
    """ Re-sequence IDs after deletion and reset AUTO_INCREMENT """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SET @count = 0;")
        cursor.execute("UPDATE data SET id = (@count := @count + 1)")
        cursor.execute("ALTER TABLE data AUTO_INCREMENT = 1")
        conn.commit()
        cursor.close()
        conn.close()
        st.success("✅ IDs resequenced successfully!")
    except Exception as e:
        st.error(f"❌ Failed to resequence IDs: {e}")

import math
import re

# -----------------------------
# Validation Functions
# -----------------------------
def validate_cnic(cnic: str) -> bool:
    return bool(re.fullmatch(r"\d{5}-\d{7}-\d", cnic))

def validate_phone(phone: str) -> bool:
    return phone.isdigit() and len(phone) == 11

# -----------------------------
# Scoring Functions
# -----------------------------
def income_score(net_salary, gender):
    if net_salary < 50000:
        base = 0
    elif net_salary < 70000:
        base = 20
    elif net_salary < 90000:
        base = 35
    elif net_salary < 100000:
        base = 50
    elif net_salary < 120000:
        base = 60
    elif net_salary < 150000:
        base = 80
    else:
        base = 100
    if gender == "F":
        base *= 1.1
    return min(base, 100)

def bank_balance_score_custom(applicant_balance, guarantor_balance, emi):
    """
    Bank Balance Scoring Logic:
    1. If applicant_balance >= 3×EMI → score = 100
    2. Else:
       a. If guarantor_balance is not provided → score proportional to applicant_balance
       b. If guarantor_balance is provided and >= 6×EMI → score = 100
       c. Else → score proportional to guarantor_balance
    Returns:
        score (0-100), source_used (str)
    """
    if emi <= 0:
        return 0, None

    # Case 1: Applicant meets threshold
    if applicant_balance >= 3 * emi:
        return 100, "Applicant"

    # Applicant does not meet threshold
    if not guarantor_balance:
        # No guarantor provided → score based on applicant
        score = min((applicant_balance / (3 * emi)) * 100, 100)
        return score, "Applicant (Below Threshold, No Guarantor)"

    # Guarantor provided
    if guarantor_balance >= 6 * emi:
        return 100, "Guarantor"

    # Guarantor does not meet full threshold → scale proportionally
    score = min((guarantor_balance / (6 * emi)) * 100, 100)
    return score, "Guarantor (Below Threshold)"

def salary_consistency_score(months):
    return min((months / 6) * 100, 100)

def employer_type_score(emp_type):
    mapping = {"Govt": 100, "MNC": 80, "SME": 60, "Startup": 40, "Self-employed": 20}
    return mapping.get(emp_type, 0)

def job_tenure_score(years):
    if years >= 10:
        return 100
    elif years >= 5:
        return 70
    elif years >= 3:
        return 50
    elif years >= 1:
        return 20
    else:
        return 0

def age_score(age):
    if age < 18:
        return -1  # reject
    elif age <= 25:
        return 80
    elif age <= 30:
        return 100
    elif age <= 40:
        return 60
    else:
        return 30

def dependents_score(dep):
    if dep == 0:
        return 100
    elif dep <= 2:
        return 80
    elif dep <= 4:
        return 60
    else:
        return 40

def residence_score(res):
    mapping = {"Owned": 100, "Family": 80, "Rented": 60, "Temporary": 40}
    return mapping.get(res, 0)

def dti_score(outstanding, emi, net_salary, tenure):
    """
    Debt-to-Income (DTI) Score:
    ratio = (Outstanding / tenure + EMI) / Net Salary
    """
    if net_salary <= 0 or tenure <= 0:
        return 0, 0

    monthly_obligation = (outstanding / tenure) + emi
    ratio = monthly_obligation / net_salary

    if ratio <= 0.4:
        score = 100
    elif ratio <= 0.6:
        score = 80
    elif ratio <= 0.8:
        score = 60
    elif ratio <= 1.0:
        score = 40
    else:
        score = 20

    return score, ratio

def financial_feasibility_score(bike_price, down_payment, emi, tenure):
    """Score based on EMI × Tenure + Down Payment covering bike price"""
    if tenure <= 0 or bike_price <= 0:
        return 0
    total_covered = emi * tenure + down_payment
    return min(total_covered / bike_price, 1) * 100

def calculate_min_emi(bike_price, down_payment, tenure):
    """Minimum EMI needed to cover bike price"""
    if tenure <= 0:
        return 0
    return math.ceil((bike_price - down_payment) / tenure)



import streamlit as st

# --- PAGE CONFIG ---
st.set_page_config(page_title="EV Bike Finance Portal", layout="centered")

# --- SESSION STATE INIT ---
if 'app_started' not in st.session_state:
    st.session_state['app_started'] = False

# --- LANDING PAGE ---
if not st.session_state['app_started']:
    # Custom styling (gradient background + blue button)
    page_bg = """
    <style>
    [data-testid="stAppViewContainer"] {
        background: linear-gradient(135deg, #001F3F 0%, #0074D9 50%, #7FDBFF 100%);
        color: white;
        padding-top: 6rem;
    }
    [data-testid="stHeader"] {background: rgba(0,0,0,0);}
    .title {
        font-size: 2.8rem;
        font-weight: 800;
        margin-bottom: 1rem;
        text-align: center;
        background: linear-gradient(to right, #7FDBFF, #39CCCC, #01FF70);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .subtitle {
        font-size: 1.1rem;
        color: #E0E0E0;
        text-align: center;
        margin-bottom: 2.5rem;
    }
    .divider {
        border: none;
        height: 1px;
        background-color: rgba(255, 255, 255, 0.3);
        margin: 2rem 0;
    }
    /* --- Custom blue button --- */
    div.stButton > button:first-child {
        background-color: #0074D9;
        color: white;
        border: none;
        padding: 0.75rem 1.5rem;
        border-radius: 10px;
        font-size: 1.1rem;
        font-weight: 600;
        transition: 0.3s ease-in-out;
    }
    div.stButton > button:first-child:hover {
        background-color: #005fa3;
        transform: translateY(-2px);
        box-shadow: 0 4px 10px rgba(0,0,0,0.3);
    }
    </style>
    """
    st.markdown(page_bg, unsafe_allow_html=True)

    # Main content block
    st.markdown('<h1 class="title">⚡ EV Bike Finance Portal</h1>', unsafe_allow_html=True)
    st.markdown(
        '<p class="subtitle">A unified digital platform to evaluate, approve, and manage electric bike financing — faster, smarter, and sustainable.</p>',
        unsafe_allow_html=True
    )

    st.markdown('<hr class="divider">', unsafe_allow_html=True)

    # CTA button (blue now!)
    if st.button("🚀 Launch App Now", use_container_width=True):
        st.session_state['app_started'] = True
        st.rerun()

    st.stop()


# -----------------------------
# Streamlit App
# -----------------------------
st.set_page_config(page_title="⚡ Electric Bike Finance Portal", layout="centered")
st.title("⚡ Electric Bike Finance Portal")

tabs = st.tabs(["📋 Applicant Information", "📊 Evaluation", "✅ Results", "📂 Applicants"])

# -----------------------------
# Page 1: Applicant Info
# -----------------------------
with tabs[0]:
    st.subheader("Applicant Information")

    first_name = st.text_input("First Name")
    last_name = st.text_input("Last Name")

    cnic = st.text_input("CNIC Number (Format: XXXXX-XXXXXXX-X)")
    if cnic and not validate_cnic(cnic):
        st.error("❌ Invalid CNIC format. Use XXXXX-XXXXXXX-X")

    license_suffix = st.number_input(
        "Enter last 3 digits for License Number (#XXX)",
        min_value=0, max_value=999, step=1, format="%03d"
    )
    license_number = f"{cnic}#{license_suffix}" if validate_cnic(cnic) else ""

    phone_number = st.text_input("Phone Number (11 digits only)")
    if phone_number and not validate_phone(phone_number):
        st.error("❌ Invalid Phone Number - Please enter exactly 11 digits")

    gender = st.radio("Gender", ["M", "F"])

    guarantors = st.radio("Guarantors Available?", ["Yes", "No"])
    female_guarantor = None
    if guarantors == "Yes":
        female_guarantor = st.radio("At least one Female Guarantor?", ["Yes", "No"])

    electricity_bill = st.radio("Is Electricity Bill Available?", ["Yes", "No"])
    if electricity_bill == "No":
        st.error("🚫 Application Rejected: Electricity bill not available.")

    pdc_option = st.radio("Is the candidate willing to provide post-dated cheques (PDCs)?", ["Yes", "No"])
    if pdc_option == "No":
        st.error("🚫 Application Rejected: PDCs not available")

    with st.expander("🎓 Qualifications (Optional)"):
        education = st.selectbox(
            "Education",
            ["", "No Formal Education", "Primary", "Secondary", "Intermediate", "Bachelor's", "Master's", "PhD"]
        )
        occupation = st.text_input("Occupation")
        designation = st.text_input("Designation")
        employer_name = st.text_input("Employer Name")
        employer_contact = st.text_input("Employer Contact (11 digits)")

        # Validate employer contact only if entered
        if employer_contact and not validate_phone(employer_contact):
            st.error("❌ Invalid Employer Contact - Please enter exactly 11 digits")


    street_address = st.text_input("Street Address")
    area_address = st.text_input("Area Address")
    city = st.text_input("City")
    state_province = st.text_input("State/Province")
    postal_code = st.text_input("Postal Code (Optional)")
    country = st.text_input("Country")

    if st.button("📍 View Location"):
        if street_address and area_address and city and state_province and country:
            full_address = f"{street_address}, {area_address}, {city}, {state_province}, {country} {postal_code or ''}"
            encoded = urllib.parse.quote_plus(full_address)
            maps_url = f"https://www.google.com/maps/search/?api=1&query={encoded}"

            js = f"""
            <script>
            window.open("{maps_url}", "_blank").focus();
            </script>
            """
            st.components.v1.html(js, height=0, width=0)
        else:
            st.error("❌ Please complete all mandatory address fields before viewing on Maps.")

    guarantor_valid = (guarantors == "Yes")
    female_guarantor_valid = (female_guarantor == "Yes") if guarantors == "Yes" else True

    if not guarantor_valid:
        st.error("🚫 Application Rejected: No guarantor available.")
    elif guarantors == "Yes" and not female_guarantor_valid:
        st.error("🚫 Application Rejected: At least one female guarantor is required.")

    info_complete = all([
        first_name, last_name, validate_cnic(cnic),
        guarantor_valid, female_guarantor_valid,
        phone_number and validate_phone(phone_number),
        street_address, area_address, city, state_province, country,
        gender, electricity_bill == "Yes"
    ])

    st.session_state.applicant_valid = info_complete

    if info_complete:
        st.success("✅ Applicant Information completed. Proceed to Evaluation tab.")
    else:
        st.warning("⚠️ Please complete all required fields before proceeding.")

#-------------------
# EVALUATION 
#-------------------

with tabs[1]:
    if not st.session_state.get("applicant_valid", False):
        st.error("🚫 Please complete Applicant Information first.")
    else:
        st.subheader("Evaluation Inputs")

        net_salary = st.number_input("Net Salary", min_value=0, step=1000, format="%i")
        applicant_bank_balance = st.number_input("Applicant's Average 6M Bank Balance", min_value=0, step=1000, format="%i")
        guarantor_bank_balance = st.number_input("Guarantor's Average 6M Bank Balance (Optional)", min_value=0, step=1000, format="%i")
        salary_consistency = st.number_input("Months with Salary Credit (0–6)", min_value=0, max_value=6, step=1)
        employer_type = st.selectbox("Employer Type", ["Govt", "MNC", "SME", "Startup", "Self-employed"])
        job_years = st.number_input("Job Tenure (Years)", min_value=0, step=1)
        age = st.number_input("Age", min_value=18, max_value=70, step=1)
        dependents = st.number_input("Number of Dependents", min_value=0, step=1)
        residence = st.radio("Residence", ["Owned", "Family", "Rented", "Temporary"])
        bike_type = st.selectbox("Bike Type", ["EV-1", "EV-125"])
        bike_price = st.number_input("Bike Price", min_value=0, step=1000)
        down_payment = st.number_input("Down Payment", min_value=0, step=1000)
        tenure = st.selectbox("Installment Tenure (Months)", [6, 12, 18, 24, 30, 36])
        outstanding = st.number_input("Outstanding Obligation", min_value=0, step=1000)

        # Minimum EMI Suggestion
        min_emi = calculate_min_emi(bike_price, down_payment, tenure)
        st.info(f"💡 Suggested minimum EMI to cover bike: {min_emi}")

        emi = st.number_input(
            "Monthly Installment (EMI)", 
            min_value=min_emi,
            step=500,
            value=min_emi
        )

        if emi < min_emi:
            st.warning(f"⚠️ Entered EMI ({emi}) is less than minimum required ({min_emi}) to cover the bike.")



# -----------------------------
# Page 3: Results
# -----------------------------
with tabs[2]:
    if not st.session_state.get("applicant_valid", False):
        st.error("🚫 Please complete Applicant Information first.")
    else:
        st.subheader("📊 Results Summary")

        if net_salary > 0 and tenure > 0:
            # --- Calculate Scores ---
            inc = income_score(net_salary, gender)
            min_emi = calculate_min_emi(bike_price, down_payment, tenure)
            adjusted_emi = max(emi, min_emi)

            bal, bal_source = bank_balance_score_custom(applicant_bank_balance, guarantor_bank_balance, adjusted_emi)
            sal = salary_consistency_score(salary_consistency)
            emp = employer_type_score(employer_type)
            job = job_tenure_score(job_years)
            ag = age_score(age)
            dep = dependents_score(dependents)
            res = residence_score(residence)
            dti, ratio = dti_score(outstanding, adjusted_emi, net_salary, tenure)
            feasibility = financial_feasibility_score(bike_price, down_payment, adjusted_emi, tenure)

            # --- Final Decision ---
            if ag == -1:
                decision = "Reject"
                decision_display = "❌ Reject (Underage)"
            else:
                # --- Adjusted weights ---
                final_score = (
                    inc * 0.40 +          # Income
                    bal * 0.30 +          # Bank Balance
                    sal * 0.0343 +        # Salary Consistency
                    emp * 0.0343 +        # Employer Type
                    job * 0.0343 +        # Job Tenure
                    ag * 0.0343 +         # Age
                    dep * 0.0343 +        # Dependents
                    res * 0.0429 +        # Residence
                    dti * 0.0429 +        # Debt-to-Income
                    feasibility * 0.0429  # Financial Feasibility
                )

                # --- Decision thresholds ---
                if final_score >= 75:
                    decision = "Approved"
                    decision_display = "✅ Approve"
                elif final_score >= 60:
                    decision = "Review"
                    decision_display = "🟡 Review"
                else:
                    decision = "Reject"
                    decision_display = "❌ Reject"

            # --- Display Detailed Scores ---
            st.markdown("### 🔹 Detailed Scores")
            st.write(f"Income Score: {inc:.1f}")
            st.write(f"Bank Balance Score ({bal_source}): {bal:.1f}")
            st.write(f"Salary Consistency: {sal:.1f}")
            st.write(f"Employer Type Score: {emp:.1f}")
            st.write(f"Job Tenure Score: {job:.1f}")
            st.write(f"Age Score: {ag:.1f}")
            st.write(f"Dependents Score: {dep:.1f}")
            st.write(f"Residence Score: {res:.1f}")
            st.write(f"Debt-to-Income Ratio: {ratio:.2f}")
            st.write(f"Debt-to-Income Score: {dti:.1f}")
            st.write(f"Financial Feasibility Score: {feasibility:.1f}")
            st.write(f"EMI used for scoring: {adjusted_emi}")
            st.write(f"Final Score: {final_score:.1f}")
            st.subheader(f"🏆 Decision: {decision_display}")

            # --- Financial Plan for Approved Applicant ---
            if decision == "Approved":
                st.markdown("### 💰 Applicant Financial Plan")
                
                remaining_price = bike_price - down_payment
                total_payment = adjusted_emi * tenure
                break_even = down_payment + total_payment

                st.write(f"**Down Payment:** {down_payment:,.0f}")
                st.write(f"**Bike Price:** {bike_price:,.0f}")
                st.write(f"**Remaining Bike Price after Down Payment:** {remaining_price:,.0f}")
                st.write(f"**Installment Tenure (Months):** {tenure}")
                st.write(f"**Monthly EMI:** {adjusted_emi:,.0f}")
                st.write(f"**Total EMI over Tenure:** {total_payment:,.0f}")
                st.write(f"**Break-even Point Reached (Down Payment + EMIs):** {break_even:,.0f}")

# -----------------------------
# Save Applicant Button
# -----------------------------
if st.button("💾 Save Applicant to Database"):
    try:
        # Build a dictionary with all required fields
        applicant_data = {
            "first_name": first_name,
            "last_name": last_name,
            "cnic": cnic,
            "license_no": license_number,
            "phone_number": phone_number,
            "gender": gender,
            "guarantors": guarantors,
            "female_guarantor": female_guarantor,
            "electricity_bill": electricity_bill,
            "pdc_option": pdc_option,
            "education": education,
            "occupation": occupation,
            "designation": designation,
            "employer_name": employer_name,
            "employer_contact": employer_contact,
            "street_address": street_address,
            "area_address": area_address,
            "city": city,
            "state_province": state_province,
            "postal_code": postal_code,
            "country": country,
            "net_salary": net_salary,
            "applicant_bank_balance": applicant_bank_balance,
            "guarantor_bank_balance": guarantor_bank_balance,
            "employer_type": employer_type,
            "age": age,
            "residence": residence,
            "bike_type": bike_type,
            "bike_price": bike_price,
            "down_payment": down_payment,
            "tenure": tenure,
            "emi": adjusted_emi,
            "outstanding": outstanding,
            "decision": decision
        }

        save_to_db(applicant_data)
        st.success("✅ Applicant saved successfully!")
    except Exception as e:
        st.error(f"❌ Failed to save applicant: {e}")




# -----------------------------
# Page 4: Applicants
# -----------------------------
with tabs[3]:
    st.subheader("📂 Applicants Database")

    if st.button("🔄 Refresh Data"):
        resequence_ids()
        st.session_state.refresh = True

    def delete_applicant(applicant_id: int):
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM data WHERE id = %s", (applicant_id,))
            conn.commit()
            cursor.close()
            conn.close()
            st.success(f"✅ Applicant with ID {applicant_id} deleted successfully!")
        except Exception as e:
            st.error(f"❌ Failed to delete applicant: {e}")

    try:
        df = fetch_all_applicants()
        if not df.empty:
            st.dataframe(df, use_container_width=True)

            delete_id = st.number_input("Enter Applicant ID to Delete", min_value=1, step=1)

            # 🔹 NEW: Two-step confirmation logic
            if "confirm_delete" not in st.session_state:
                st.session_state.confirm_delete = None

            if st.button("🗑️ Delete Applicant"):
                if delete_id in df["id"].values:
                    # Store selected ID + Name for confirmation
                    applicant_name = df.loc[df["id"] == delete_id, "name"].values[0]
                    st.session_state.confirm_delete = {"id": delete_id, "name": applicant_name}
                else:
                    st.error("❌ Invalid ID. Please enter a valid Applicant ID from the table.")

            # Show confirmation prompt if a delete is triggered
            if st.session_state.confirm_delete:
                c_id = st.session_state.confirm_delete["id"]
                c_name = st.session_state.confirm_delete["name"]
                st.warning(f"⚠️ Are you sure you want to delete the data for ID: {c_id} and Name: {c_name}?")

                col1, col2 = st.columns(2)
                with col1:
                    if st.button("✅ Yes, Delete"):
                        delete_applicant(c_id)
                        st.session_state.confirm_delete = None  # reset confirmation
                with col2:
                    if st.button("❌ No, Cancel"):
                        st.info("Deletion cancelled.")
                        st.session_state.confirm_delete = None  # reset confirmation

            # Excel download remains the same
            df = df.sort_values(by="id", ascending=True)
            output = BytesIO()
            with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
                df.to_excel(writer, index=False, sheet_name="Applicants")
            excel_data = output.getvalue()

            st.download_button(
                label="📥 Download Excel",
                data=excel_data,
                file_name="applicants.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.info("ℹ️ No applicants found in the database yet.")
    except Exception as e:
        st.error(f"❌ Failed to load applicants: {e}")
