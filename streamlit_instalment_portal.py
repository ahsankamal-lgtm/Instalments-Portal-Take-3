import streamlit as st
import re
import urllib.parse
import mysql.connector
import pandas as pd
import io

# Database connection function
def create_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="applicants_db"
    )

# ------------------ Scoring Functions ------------------ #
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

# ------------------ Database Functions ------------------ #
def fetch_all_applicants():
    conn = create_connection()
    query = """
        SELECT id, first_name, last_name, cnic, license_no, guarantors, female_guarantor,
               phone_number, street_address, area_address, city, state_province, postal_code,
               country, gender, electricity_bill, net_salary, emi, bike_type, bike_price
        FROM data
    """
    df = pd.read_sql(query, conn)
    conn.close()
    return df

# ------------------ Streamlit App ------------------ #
st.set_page_config(page_title="Bike Finance Portal", layout="wide")

menu = ["New Application", "Applicant Database"]
choice = st.sidebar.selectbox("Menu", menu)

if choice == "New Application":
    st.header("📋 New Application Form")
    
    with st.form("app_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            first_name = st.text_input("First Name")
            last_name = st.text_input("Last Name")
            cnic = st.text_input("CNIC")
            license_no = st.text_input("License No")
            gender = st.selectbox("Gender", ["M", "F"])
            age = st.number_input("Age", min_value=0, max_value=100, step=1)
            dependents = st.number_input("Dependents", min_value=0, step=1)
            residence = st.selectbox("Residence Type", ["Owned", "Family", "Rented", "Temporary"])
        
        with col2:
            phone_number = st.text_input("Phone Number")
            street_address = st.text_input("Street Address")
            area_address = st.text_input("Area Address")
            city = st.text_input("City")
            state_province = st.text_input("State/Province")
            postal_code = st.text_input("Postal Code")
            country = st.text_input("Country")
            net_salary = st.number_input("Net Salary", min_value=0, step=1000)
            employer_type = st.selectbox("Employer Type", ["Govt", "MNC", "SME", "Startup", "Self-employed"])
            job_tenure = st.number_input("Job Tenure (years)", min_value=0, step=1)
            consistency_months = st.number_input("Salary Consistency (months)", min_value=0, max_value=6, step=1)
            bike_price = st.number_input("Bike Price", min_value=0, step=1000)
            outstanding = st.number_input("Outstanding Loans", min_value=0, step=1000)
            emi = st.number_input("EMI", min_value=0, step=500)
            bike_type = st.text_input("Bike Type")

        submitted = st.form_submit_button("Submit Application")

        if submitted:
            income = income_score(net_salary, gender)
            salary_consistency = salary_consistency_score(consistency_months)
            employer = employer_type_score(employer_type)
            tenure = job_tenure_score(job_tenure)
            age_sc = age_score(age)
            dependents_sc = dependents_score(dependents)
            residence_sc = residence_score(residence)
            dti_sc, dti_ratio = dti_score(outstanding, bike_price, net_salary)

            if age_sc == -1:
                st.error("Application Rejected: Applicant under 18.")
            else:
                total_score = (income + salary_consistency + employer + tenure + age_sc + dependents_sc + residence_sc + dti_sc) / 8
                st.success(f"Application Submitted! Credit Score: {total_score:.2f}")

elif choice == "Applicant Database":
    st.header("📂 Applicant Database")
    df = fetch_all_applicants()
    st.dataframe(df, use_container_width=True)

    # Export to Excel (without is_deleted & created_at)
    towrite = io.BytesIO()
    df.to_excel(towrite, index=False, engine='xlsxwriter')
    towrite.seek(0)
    st.download_button(
        label="📥 Download Excel",
        data=towrite,
        file_name="applicants.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

