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

    query = """
    INSERT INTO data (
        name, cnic, license_no, phone_number, gender,
        guarantors, female_guarantor, electricity_bill,
        education, occupation,
        address, city, state_province, postal_code, country,
        net_salary, emi, applicant_bank_balance, guarantor_bank_balance,
        employer_type, age, residence,
        bike_type, bike_price, decision
    )
    VALUES (%s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s,
            %s, %s, %s)
    """

    # 👇 Concatenate name + address
    full_name = f"{data['first_name']} {data['last_name']}"
    full_address = f"{data['street_address']}, {data['area_address']}"

    values = (
        full_name,
        data["cnic"],
        data["license_no"],
        data["phone_number"],
        data["gender"],
        data["guarantors"],
        data["female_guarantor"],
        data["electricity_bill"],
        data.get("education"),   # optional
        data.get("occupation"),  # optional
        full_address,
        data["city"],
        data["state_province"],
        data["postal_code"],
        data["country"],
        data["net_salary"],
        data["emi"],
        data["bank_balance"],
        data.get("guarantor_bank_balance"),  # optional
        data["employer_type"],
        data["age"],
        data["residence"],
        data["bike_type"],
        data["bike_price"],
        data["decision"]
    )

    cursor.execute(query, values)
    conn.commit()
    cursor.close()
    conn.close()

def fetch_all_applicants():
    conn = get_db_connection()
    query = "SELECT * FROM data"
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

def bank_balance_score(balance, emi):
    if emi <= 0:
        return 0
    threshold = emi * 3
    score = (balance / threshold) * 100
    return min(score, 100)

def guarantor_balance_score(balance, emi):
    if emi <= 0:
        return 0
    threshold = emi * 6
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
        return -1
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
# Streamlit App
# -----------------------------
st.set_page_config(page_title="⚡ Electric Bike Finance Portal", layout="centered")
st.title("⚡ Electric Bike Finance Portal")

tabs = st.tabs(["📋 Applicant Information", "📊 Evaluation", "✅ Results", "📂 Applicants"])

# -----------------------------
# Applicant Info Tab
# -----------------------------
with tabs[0]:
    st.subheader("Applicant Information")

    first_name = st.text_input("First Name")
    last_name = st.text_input("Last Name")

    cnic = st.text_input("CNIC Number (Format: XXXXX-XXXXXXX-X)")
    if cnic and not validate_cnic(cnic):
        st.error("❌ Invalid CNIC format. Use XXXXX-XXXXXXX-X")

    license_suffix = st.number_input("Enter last 3 digits for License Number", min_value=0, max_value=999, step=1, format="%03d")
    license_number = f"{cnic}#{license_suffix}" if validate_cnic(cnic) else ""

    phone_number = st.text_input("Phone Number (11–12 digits)")
    if phone_number and not validate_phone(phone_number):
        st.error("❌ Invalid Phone Number")

    gender = st.radio("Gender", ["M", "F"])
    guarantors = st.radio("Guarantors Available?", ["Yes", "No"])
    female_guarantor = None
    if guarantors == "Yes":
        female_guarantor = st.radio("At least one Female Guarantor?", ["Yes", "No"])

    electricity_bill = st.radio("Is Electricity Bill Available?", ["Yes", "No"])
    education = st.text_input("Education (Optional)")
    occupation = st.text_input("Occupation (Optional)")

    street_address = st.text_input("Street Address")
    area_address = st.text_input("Area Address")
    city = st.text_input("City")
    state_province = st.text_input("State/Province")
    postal_code = st.text_input("Postal Code (Optional)")
    country = st.text_input("Country")

    guarantor_valid = (guarantors == "Yes")
    female_guarantor_valid = (female_guarantor == "Yes") if guarantors == "Yes" else True

    info_complete = all([
        first_name, last_name, validate_cnic(cnic), license_suffix,
        guarantor_valid, female_guarantor_valid,
        phone_number and validate_phone(phone_number),
        street_address, area_address, city, state_province, country,
        gender, electricity_bill == "Yes"
    ])

    st.session_state.applicant_valid = info_complete

    if info_complete:
        st.success("✅ Applicant Information completed. Proceed to Evaluation tab.")

# -----------------------------
# Evaluation Tab
# -----------------------------
with tabs[1]:
    if not st.session_state.get("applicant_valid", False):
        st.error("🚫 Complete Applicant Information first.")
    else:
        st.subheader("Evaluation Inputs")

        net_salary = st.number_input("Net Salary", min_value=0, step=1000, format="%i")
        emi = st.number_input("Monthly Installment (EMI)", min_value=0, step=500, format="%i")
        bank_balance = st.number_input("Applicant's Average 6M Bank Balance", min_value=0, step=1000, format="%i")
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

# -----------------------------
# Results Tab
# -----------------------------
with tabs[2]:
    if not st.session_state.get("applicant_valid", False):
        st.error("🚫 Complete Applicant Information first.")
    else:
        st.subheader("📊 Results Summary")

        if net_salary > 0 and emi > 0:
            inc = income_score(net_salary, gender)

            # ✅ Use applicant or guarantor balance
            if guarantor_bank_balance > bank_balance:
                bal = guarantor_balance_score(guarantor_bank_balance, emi)
            else:
                bal = bank_balance_score(bank_balance, emi)

            sal = salary_consistency_score(salary_consistency)
            emp = employer_type_score(employer_type)
            job = job_tenure_score(job_years)
            ag = age_score(age)
            dep = dependents_score(dependents)
            res = residence_score(residence)
            dti, ratio = dti_score(outstanding, bike_price, net_salary)

            if ag == -1:
                st.subheader("❌ Rejected: Applicant under 18.")
            else:
                final = (
                    inc * 0.40 + bal * 0.30 + sal * 0.04 + emp * 0.04 +
                    job * 0.04 + ag * 0.04 + dep * 0.04 + res * 0.05 + dti * 0.05
                )

                if final >= 75:
                    decision = "Approved"
                elif final >= 60:
                    decision = "Review"
                else:
                    decision = "Reject"

                st.write(f"**Final Score:** {final:.1f}")
                st.subheader(f"🏆 Decision: {decision}")

                if st.button("💾 Save Applicant to Database"):
                    try:
                        save_to_db({
                            "first_name": first_name,
                            "last_name": last_name,
                            "cnic": cnic,
                            "license_no": license_number,
                            "phone_number": phone_number,
                            "gender": gender,
                            "guarantors": guarantors,
                            "female_guarantor": female_guarantor if female_guarantor else "No",
                            "electricity_bill": electricity_bill,
                            "education": education,
                            "occupation": occupation,
                            "street_address": street_address,
                            "area_address": area_address,
                            "city": city,
                            "state_province": state_province,
                            "postal_code": postal_code,
                            "country": country,
                            "net_salary": net_salary,
                            "emi": emi,
                            "bank_balance": bank_balance,
                            "guarantor_bank_balance": guarantor_bank_balance,
                            "employer_type": employer_type,
                            "age": age,
                            "residence": residence,
                            "bike_type": bike_type,
                            "bike_price": bike_price,
                            "decision": decision
                        })
                        st.success("✅ Applicant saved to database!")
                    except Exception as e:
                        st.error(f"❌ Failed to save applicant: {e}")

# -----------------------------
# Applicants Tab
# -----------------------------
with tabs[3]:
    st.subheader("📂 Applicants Database")

    if st.button("🔄 Refresh Data"):
        resequence_ids()
        st.session_state.refresh = True

    try:
        df = fetch_all_applicants()
        if not df.empty:
            st.dataframe(df, use_container_width=True)

            delete_id = st.number_input("Enter Applicant ID to Delete", min_value=1, step=1)
            if st.button("🗑️ Delete Applicant"):
                try:
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM data WHERE id = %s", (delete_id,))
                    conn.commit()
                    cursor.close()
                    conn.close()
                    st.success(f"✅ Applicant ID {delete_id} deleted!")
                except Exception as e:
                    st.error(f"❌ Delete failed: {e}")

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
            st.info("ℹ️ No applicants found yet.")
    except Exception as e:
        st.error(f"❌ Failed to load applicants: {e}")
