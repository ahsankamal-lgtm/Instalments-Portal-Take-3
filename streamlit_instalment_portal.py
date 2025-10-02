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

# -----------------------------
# Save Applicant
# -----------------------------
def save_to_db(data: dict):
    conn = get_db_connection()
    cursor = conn.cursor()

    query = """
    INSERT INTO applicants (
        name, age, gender,
        guarantor_available, electricity_bill,
        post_dated_cheques, guarantor_affidavit, qualifications,
        address, net_salary, salary_consistency_months, employer_type, job_years,
        dependents, residence, outstanding_loans, bike_price,
        final_score, decision
    )
    VALUES (%s, %s, %s,
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s)
    """

    values = (
        f"{data['first_name']} {data['last_name']}",
        data["age"], data["gender"],
        data["guarantors"], data["electricity_bill"],
        data["post_dated_cheques"], data["guarantor_affidavit"], data["qualifications"],
        f"{data['street_address']}, {data['area_address']}, {data['city']}, {data['state_province']} {data['postal_code']} {data['country']}",
        data["net_salary"], data["salary_consistency"],
        data["employer_type"], data["job_years"],
        data["dependents"], data["residence"],
        data["outstanding"], data["bike_price"],
        data["final_score"], data["decision"]
    )

    cursor.execute(query, values)
    conn.commit()
    cursor.close()
    conn.close()

# -----------------------------
# Fetch Applicants
# -----------------------------
def fetch_all_applicants():
    conn = get_db_connection()
    query = """
    SELECT id, name, age, gender,
           guarantor_available, electricity_bill,
           post_dated_cheques, guarantor_affidavit, qualifications,
           address, net_salary, salary_consistency_months, employer_type, job_years,
           dependents, residence, outstanding_loans, bike_price,
           final_score, decision
    FROM applicants
    """
    df = pd.read_sql(query, conn)
    conn.close()
    return df

def resequence_ids():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SET @count = 0;")
        cursor.execute("UPDATE applicants SET id = (@count := @count + 1)")
        cursor.execute("ALTER TABLE applicants AUTO_INCREMENT = 1")
        conn.commit()
        cursor.close()
        conn.close()
        st.success("✅ IDs resequenced successfully!")
    except Exception as e:
        st.error(f"❌ Failed to resequence IDs: {e}")

# -----------------------------
# Utility Functions (Scoring)
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
# Page 1: Applicant Info
# -----------------------------
with tabs[0]:
    st.subheader("Applicant Information")

    first_name = st.text_input("First Name")
    last_name = st.text_input("Last Name")
    age = st.number_input("Age", min_value=18, max_value=70, step=1)

    gender = st.radio("Gender", ["M", "F"])

    guarantors = st.radio("Guarantors Available?", ["Yes", "No"])
    electricity_bill = st.radio("Is Electricity Bill Available?", ["Yes", "No"])

    # 🔹 New fields
    post_dated_cheques = st.radio("Is applicant willing to provide post-dated cheques?", ["Yes", "No"])
    guarantor_affidavit = st.radio("Is guarantor’s affidavit available?", ["Yes", "No"])
    qualifications = st.text_input("Applicant Qualifications")

    # Address
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
            st.components.v1.html(f'<script>window.open("{maps_url}", "_blank").focus();</script>', height=0, width=0)
        else:
            st.error("❌ Please complete address fields.")

    info_complete = all([
        first_name, last_name, age, gender,
        guarantors, electricity_bill,
        post_dated_cheques, guarantor_affidavit, qualifications,
        street_address, area_address, city, state_province, country
    ])

    st.session_state.applicant_valid = info_complete

    if info_complete:
        st.success("✅ Applicant Information completed. Proceed to Evaluation tab.")
    else:
        st.warning("⚠️ Please complete all required fields.")

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
        bank_balance = st.number_input("Average 6M Bank Balance", min_value=0, step=1000, format="%i")
        salary_consistency = st.number_input("Months with Salary Credit (0–6)", min_value=0, max_value=6, step=1)
        employer_type = st.selectbox("Employer Type", ["Govt", "MNC", "SME", "Startup", "Self-employed"])
        job_years = st.number_input("Job Tenure (Years)", min_value=0, step=1, format="%i")
        dependents = st.number_input("Number of Dependents", min_value=0, step=1, format="%i")
        residence = st.radio("Residence", ["Owned", "Family", "Rented", "Temporary"])
        bike_price = st.number_input("Bike Price", min_value=0, step=1000, format="%i")
        outstanding = st.number_input("Other Loans (Outstanding)", min_value=0, step=1000, format="%i")

# -----------------------------
# Page 3: Results
# -----------------------------
with tabs[2]:
    if not st.session_state.get("applicant_valid", False):
        st.error("🚫 Please complete Applicant Information first.")
    else:
        st.subheader("📊 Results Summary")

        if 'net_salary' in locals() and net_salary > 0 and 'emi' in locals() and emi > 0:
            inc = income_score(net_salary, gender)
            bal = bank_balance_score(bank_balance, emi)
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
                    decision = "✅ Approve"
                elif final >= 60:
                    decision = "🟡 Review"
                else:
                    decision = "❌ Reject"

                st.write(f"**Final Score:** {final:.1f}")
                st.subheader(f"🏆 Decision: {decision}")

                if decision == "✅ Approve":
                    if st.button("💾 Save Applicant to Database"):
                        try:
                            save_to_db({
                                "first_name": first_name,
                                "last_name": last_name,
                                "age": age,
                                "gender": gender,
                                "guarantors": guarantors,
                                "electricity_bill": electricity_bill,
                                "post_dated_cheques": post_dated_cheques,
                                "guarantor_affidavit": guarantor_affidavit,
                                "qualifications": qualifications,
                                "street_address": street_address,
                                "area_address": area_address,
                                "city": city,
                                "state_province": state_province,
                                "postal_code": postal_code,
                                "country": country,
                                "net_salary": net_salary,
                                "salary_consistency": salary_consistency,
                                "employer_type": employer_type,
                                "job_years": job_years,
                                "dependents": dependents,
                                "residence": residence,
                                "outstanding": outstanding,
                                "bike_price": bike_price,
                                "final_score": final,
                                "decision": decision
                            })
                            st.success("✅ Applicant information saved!")
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

    try:
        df = fetch_all_applicants()
        if not df.empty:
            st.dataframe(df, use_container_width=True)

            delete_id = st.number_input("Enter Applicant ID to Delete", min_value=1, step=1)
            if st.button("🗑️ Delete Applicant"):
                try:
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM applicants WHERE id = %s", (delete_id,))
                    conn.commit()
                    cursor.close()
                    conn.close()
                    st.success(f"✅ Applicant with ID {delete_id} deleted!")
                except Exception as e:
                    st.error(f"❌ Failed to delete applicant: {e}")

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
