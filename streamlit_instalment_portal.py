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

    query = """
    INSERT INTO data (
        name, cnic, license_no,
        phone_number, gender,
        guarantors, female_guarantor, electricity_bill,
        education, occupation,
        address, city, state_province, postal_code, country,
        net_salary, emi, applicant_bank_balance, guarantor_bank_balance,
        employer_type, age, residence,
        bike_type, bike_price, decision
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """

    full_name = f"{data['first_name']} {data['last_name']}".strip()

    full_address = f"{data['street_address']}, {data['area_address']}"

    values = (
        full_name, data["cnic"], data["license_no"],
        data["phone_number"], data["gender"],
        data["guarantors"], data["female_guarantor"], data["electricity_bill"],
        data.get("education"), data.get("occupation"),
        full_address, data["city"], data["state_province"], data["postal_code"], data["country"],
        data["net_salary"], data["emi"], data["applicant_bank_balance"], data.get("guarantor_bank_balance"),
        data["employer_type"], data["age"], data["residence"],
        data["bike_type"], data["bike_price"], data["decision"]
    )

    cursor.execute(query, values)
    conn.commit()
    cursor.close()
    conn.close()

def fetch_all_applicants():
    conn = get_db_connection()
    query = """
    SELECT id, name, cnic, license_no,
           phone_number, gender,
           guarantors, female_guarantor, electricity_bill,
           education, occupation,
           address, city, state_province, postal_code, country,
           net_salary, emi, applicant_bank_balance, guarantor_bank_balance,
           employer_type, age, residence,
           bike_type, bike_price, decision
    FROM data
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

# -----------------------------
# Utility Functions (Scoring Criteria)
# -----------------------------
def validate_cnic(cnic: str) -> bool:
    return bool(re.fullmatch(r"\d{5}-\d{7}-\d", cnic))

def validate_phone(phone: str) -> bool:
    return phone.isdigit() and 11 <= len(phone) <= 12

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

def bank_balance_score(balance, emi, is_guarantor=False):
    if emi <= 0:
        return 0
    threshold = emi * (6 if is_guarantor else 3)
    score = (balance / threshold) * 100
    return min(score, 100)

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

def dti_score(outstanding, bike_price, net_salary):
    if net_salary <= 0:
        return 0, 0
    ratio = (outstanding + bike_price) / net_salary
    if ratio <= 0.5:
        return 100, ratio
    elif ratio <= 1:
        return 70, ratio
    else:
        return 40, ratio
# -----------------------------
# FINAL EXPERT-DESIGNED LANDING PAGE
# (Perfectly Centered and Styled)
# -----------------------------
def show_landing_page():
    # --- 1. Expert CSS for Professional Look and Typography ---
    st.markdown(
        """
        <style>
        /* Apply a deep, professional Indigo-Violet gradient background */
        .stApp {
            background: linear-gradient(135deg, #3f005a, #5a006c); 
            background-size: 400% 400%;
            animation: gradient-shift 15s ease infinite; 
            color: white; /* Default text color */
        }

        /* Define the gradient animation for a smooth look */
        @keyframes gradient-shift {
            0% { background-position: 0% 50%; }
            50% { background-position: 100% 50%; }
            100% { background-position: 0% 50%; }
        }
        
        /* Container for Centering (Must fill the viewport vertically) */
        .landing-page-v-center {
            /* Flex properties for perfect vertical and horizontal centering */
            display: flex;
            flex-direction: column;
            justify-content: center; /* Vertical center */
            align-items: center;    /* Horizontal center */
            text-align: center;
            height: 100vh; /* Use 100vh to ensure it covers the full screen */
            padding: 20px;
        }

        /* Title: Bold, high contrast, and perfectly wrapped */
        .landing-title-text {
            font-size: 4.5rem;
            font-weight: 800;
            margin-bottom: 5px; 
            line-height: 1.05; /* Tighten line spacing */
            text-shadow: 0px 4px 8px rgba(0,0,0,0.5); /* Strong, clean shadow */
            letter-spacing: 1px;
            color: white;
        }

        /* Subtitle: Clean and informative */
        .landing-subtitle-text {
            font-size: 1.6rem;
            font-weight: 300;
            margin-top: 15px; 
            margin-bottom: 50px; /* Space before the button */
            opacity: 0.9;
            color: #d1c4e9; /* Light purple for elegance */
        }
        
        /* Button styling: Energetic and high contrast */
        div.stButton > button {
            font-size: 1.5rem !important;
            font-weight: 700 !important;
            border-radius: 12px !important;
            padding: 15px 50px !important;
            background-color: #1affc6 !important; /* Bright Mint Green */
            color: #000000 !important; /* Black text for max contrast */
            border: none !important;
            /* Sharp, distinct box shadow */
            box-shadow: 0px 8px 20px rgba(26, 255, 198, 0.7); 
            transition: all 0.3s ease-in-out !important;
        }

        div.stButton > button:hover {
            background-color: #00e6b2 !important;
            transform: translateY(-2px); /* Slight lift on hover */
        }
        </style>
        """,
        unsafe_allow_html=True
    )

    # --- 2. Guaranteed Centering Logic ---
    # Use Streamlit containers to force content into the vertical center
    with st.container():
        # Use HTML/CSS for the content block which handles V-centering (landing-page-v-center)
        st.markdown(
            """
            <div class="landing-page-v-center">
                <div class="landing-title-text">EV Finance Portal</div>
                
                <div class="landing-subtitle-text">Next-Generation Installment Scoring.</div>
            </div>
            """,
            unsafe_allow_html=True
        )

    # --- 3. The Button (Pixel-Perfect Alignment) ---
    # We use columns to create space around the centered button, but only for horizontal padding, 
    # relying on the CSS for V-centering.
    col_l, col_c, col_r = st.columns([1, 3, 1])

    with col_c:
        # Use CSS text-align: center via markdown for the button wrapper 
        # to ensure it is centered within the middle column (col_c).
        st.markdown("<div style='text-align: center; margin-top: -300px;'>", unsafe_allow_html=True)
        
        # Crucial Fix: Use negative margin on the button container to pull it up 
        # into the correct position relative to the V-centered text block.
        if st.button("Begin Evaluation 🚀", key="perfect_start"):
            st.session_state["show_landing"] = False
            
        st.markdown("</div>", unsafe_allow_html=True)


# Landing page state control (keep this immediately after the function)
if "show_landing" not in st.session_state:
    st.session_state["show_landing"] = True

if st.session_state["show_landing"]:
    show_landing_page()
    st.stop()

# -----------------------------
# Tabs (Main App Starts Here)
# -----------------------------

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

    phone_number = st.text_input("Phone Number (11–12 digits)")
    if phone_number and not validate_phone(phone_number):
        st.error("❌ Invalid Phone Number - Please enter a valid phone number")

    gender = st.radio("Gender", ["M", "F"])

    guarantors = st.radio("Guarantors Available?", ["Yes", "No"])
    female_guarantor = None
    if guarantors == "Yes":
        female_guarantor = st.radio("At least one Female Guarantor?", ["Yes", "No"])

    electricity_bill = st.radio("Is Electricity Bill Available?", ["Yes", "No"])
    if electricity_bill == "No":
        st.error("🚫 Application Rejected: Electricity bill not available.")

    with st.expander("🎓 Qualifications (Optional)"):
        education = st.selectbox("Education", ["", "No Formal Education", "Primary", "Secondary", "Intermediate", "Bachelor's", "Master's", "PhD"])
        occupation = st.text_input("Occupation")

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

# -----------------------------
# Page 2: Evaluation
# -----------------------------
with tabs[1]:
    if not st.session_state.get("applicant_valid", False):
        st.error("🚫 Please complete Applicant Information first.")
    else:
        st.subheader("Evaluation Inputs")

        net_salary = st.number_input("Net Salary", min_value=0, step=1000, format="%i")
        emi = st.number_input("Monthly Installment (EMI)", min_value=0, step=500, format="%i")
        applicant_bank_balance = st.number_input("Applicant's Average 6M Bank Balance", min_value=0, step=1000, format="%i")
        guarantor_bank_balance = st.number_input("Guarantor's Average 6M Bank Balance (Optional)", min_value=0, step=1000, format="%i")
        salary_consistency = st.number_input("Months with Salary Credit (0–6)", min_value=0, max_value=6, step=1)
        employer_type = st.selectbox("Employer Type", ["Govt", "MNC", "SME", "Startup", "Self-employed"])
        job_years = st.number_input("Job Tenure (Years)", min_value=0, step=1, format="%i")
        age = st.number_input("Age", min_value=18, max_value=70, step=1, format="%i")
        dependents = st.number_input("Number of Dependents", min_value=0, step=1, format="%i")
        residence = st.radio("Residence", ["Owned", "Family", "Rented", "Temporary"])
        bike_type = st.selectbox("Bike Type", ["EV-1", "EV-125"])
        bike_price = st.number_input("Bike Price", min_value=0, step=1000, format="%i")
        outstanding = st.number_input("Other Loans (Outstanding)", min_value=0, step=1000, format="%i")

        st.info("➡️ Once inputs are completed, check the Results tab for scoring and decision.")

# -----------------------------
# Page 3: Results
# -----------------------------
with tabs[2]:
    if not st.session_state.get("applicant_valid", False):
        st.error("🚫 Please complete Applicant Information first.")
    else:
        st.subheader("📊 Results Summary")

        if st.session_state.get("applicant_valid") and net_salary > 0 and emi > 0:
            inc = income_score(net_salary, gender)

            if guarantor_bank_balance and guarantor_bank_balance > applicant_bank_balance:
                bal = bank_balance_score(guarantor_bank_balance, emi, is_guarantor=True)
                used_balance = guarantor_bank_balance
                bal_source = "Guarantor"
            else:
                bal = bank_balance_score(applicant_bank_balance, emi, is_guarantor=False)
                used_balance = applicant_bank_balance
                bal_source = "Applicant"

            sal = salary_consistency_score(salary_consistency)
            emp = employer_type_score(employer_type)
            job = job_tenure_score(job_years)
            ag = age_score(age)
            dep = dependents_score(dependents)
            res = residence_score(residence)
            dti, ratio = dti_score(outstanding, bike_price, net_salary)

            if ag == -1:
                st.subheader("❌ Rejected: Applicant is under 18 years old.")
            else:
                final = (
                    inc * 0.40 + bal * 0.30 + sal * 0.04 + emp * 0.04 +
                    job * 0.04 + ag * 0.04 + dep * 0.04 + res * 0.05 + dti * 0.05
                )

                if final >= 75:
                    decision = "Approved"
                    decision_display = "✅ Approve"
                elif final >= 60:
                    decision = "Review"
                    decision_display = "🟡 Review"
                else:
                    decision = "Reject"
                    decision_display = "❌ Reject"

                st.markdown("### 🔹 Detailed Scores")
                st.write(f"**Income Score (with gender adj.):** {inc:.1f}")
                st.write(f"**Bank Balance Score ({bal_source}):** {bal:.1f}")
                st.write(f"**Salary Consistency Score:** {sal:.1f}")
                st.write(f"**Employer Type Score:** {emp:.1f}")
                st.write(f"**Job Tenure Score:** {job:.1f}")
                st.write(f"**Age Score:** {ag:.1f}")
                st.write(f"**Dependents Score:** {dep:.1f}")
                st.write(f"**Residence Score:** {res:.1f}")
                st.write(f"**Debt-to-Income Ratio:** {ratio:.2f}")
                st.write(f"**Debt-to-Income Score:** {dti:.1f}")
                st.write(f"**Final Score:** {final:.1f}")
                st.subheader(f"🏆 Decision: {decision_display}")

                if decision == "Approved":
                    if st.button("💾 Save Applicant to Database"):
                        try:
                            save_to_db({
                                "first_name": first_name,
                                "last_name": last_name,
                                "cnic": cnic,
                                "license_no": license_number,
                                "guarantors": guarantors,
                                "female_guarantor": female_guarantor if female_guarantor else "No",
                                "phone_number": phone_number,
                                "street_address": street_address,
                                "area_address": area_address,
                                "city": city,
                                "state_province": state_province,
                                "postal_code": postal_code,
                                "country": country,
                                "gender": gender,
                                "electricity_bill": electricity_bill,
                                "education": education,                               
                                "occupation": occupation,
                                "net_salary": net_salary,
                                "emi": emi,
                                "applicant_bank_balance": applicant_bank_balance,
                                "guarantor_bank_balance": guarantor_bank_balance,
                                "employer_type": employer_type,
                                "age": age, 
                                "residence": residence, 
                                "bike_type": bike_type,
                                "bike_price": bike_price,
                                "decision": decision 
                            })
                            st.success("✅ Applicant information saved to database successfully!")
                        except Exception as e:
                            st.error(f"❌ Failed to save applicant: {e}")
        else:
            st.warning("⚠️ Complete Evaluation inputs first")

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
