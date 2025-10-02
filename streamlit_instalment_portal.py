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
        host="localhost",
        user="root",
        password="",
        database="scoring_db"
    )

# -----------------------------
# Scoring Functions
# -----------------------------

def income_score(net_salary: float, gender: str) -> int:
    if net_salary < 50000:
        score = 0
    elif net_salary < 70000:
        score = 20
    elif net_salary < 90000:
        score = 35
    elif net_salary < 100000:
        score = 50
    elif net_salary < 120000:
        score = 60
    elif net_salary < 150000:
        score = 80
    else:
        score = 100

    if gender == "F":
        score = min(int(score * 1.1), 100)
    return score

def salary_consistency_score(months: int) -> int:
    score = (months / 6) * 100
    return min(int(score), 100)

def employment_type_score(employment_type: str) -> int:
    mapping = {
        "Govt": 100,
        "MNC": 80,
        "SME": 60,
        "Startup": 40,
        "Self-employed": 20
    }
    return mapping.get(employment_type, 0)

def job_tenure_score(years: float) -> int:
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

def age_score(age: int) -> int:
    if age < 18:
        return -1  # Reject
    elif age < 25:
        return 80
    elif age < 30:
        return 100
    elif age < 40:
        return 60
    else:
        return 30

def dependents_score(dependents: int) -> int:
    if dependents == 0:
        return 100
    elif dependents <= 2:
        return 80
    elif dependents <= 4:
        return 60
    else:
        return 40

def residence_score(residence_type: str) -> int:
    mapping = {
        "Owned": 100,
        "Family": 80,
        "Rented": 60,
        "Temporary": 40
    }
    return mapping.get(residence_type, 0)

def dti_score(dti: float) -> int:
    if dti <= 0.5:
        return 100
    elif dti <= 1:
        return 70
    else:
        return 40

# -----------------------------
# Helper: Save Applicant
# -----------------------------
def save_applicant(data):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO data 
        (name, gender, age, salary, months_salary, employment_type, job_years, dependents, residence, dti, score)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """, (
        data["name"], data["gender"], data["age"], data["salary"], data["months_salary"],
        data["employment_type"], data["job_years"], data["dependents"], data["residence"],
        data["dti"], data["score"]
    ))
    conn.commit()
    cursor.close()
    conn.close()

def fetch_all_applicants():
    conn = get_db_connection()
    df = pd.read_sql("SELECT * FROM data", conn)
    conn.close()
    return df

# -----------------------------
# Streamlit App
# -----------------------------
st.set_page_config(page_title="Credit Scoring Model", layout="wide")

st.title("📊 Credit Scoring Application")

tabs = st.tabs(["🏠 Home", "📝 Apply", "📈 Score Result", "📂 Applicants Database"])

# -----------------------------
# Home Page
# -----------------------------
with tabs[0]:
    st.markdown("### Welcome to the Credit Scoring Application")
    st.write("Use this tool to evaluate applicants based on custom scoring criteria.")

# -----------------------------
# Apply Page
# -----------------------------
with tabs[1]:
    st.subheader("📝 Enter Applicant Details")

    with st.form("application_form"):
        name = st.text_input("Full Name")
        gender = st.selectbox("Gender", ["M", "F"])
        age = st.number_input("Age", min_value=0, max_value=100, step=1)
        salary = st.number_input("Net Monthly Salary (PKR)", min_value=0, step=1000)
        months_salary = st.number_input("Salary Consistency (Months)", min_value=0, max_value=6, step=1)
        employment_type = st.selectbox("Employment Type", ["Govt", "MNC", "SME", "Startup", "Self-employed"])
        job_years = st.number_input("Job Tenure (Years)", min_value=0.0, step=0.5)
        dependents = st.number_input("Number of Dependents", min_value=0, step=1)
        residence = st.selectbox("Residence Type", ["Owned", "Family", "Rented", "Temporary"])
        dti = st.number_input("Debt-to-Income Ratio", min_value=0.0, step=0.01)

        submitted = st.form_submit_button("Calculate Score")

    if submitted:
        scores = {
            "Income": income_score(salary, gender),
            "Salary Consistency": salary_consistency_score(months_salary),
            "Employment Type": employment_type_score(employment_type),
            "Job Tenure": job_tenure_score(job_years),
            "Age": age_score(age),
            "Dependents": dependents_score(dependents),
            "Residence": residence_score(residence),
            "DTI": dti_score(dti)
        }

        if scores["Age"] == -1:
            total_score = 0
            st.error("❌ Applicant rejected due to age < 18.")
        else:
            total_score = int(sum(scores.values()) / len(scores))

        st.session_state["latest_score"] = total_score

        # Save to DB
        save_applicant({
            "name": name, "gender": gender, "age": age, "salary": salary,
            "months_salary": months_salary, "employment_type": employment_type,
            "job_years": job_years, "dependents": dependents, "residence": residence,
            "dti": dti, "score": total_score
        })

        st.success(f"✅ Applicant Scored: {total_score}")

# -----------------------------
# Score Result Page
# -----------------------------
with tabs[2]:
    st.subheader("📈 Latest Score Result")
    if "latest_score" in st.session_state:
        st.metric("Applicant Score", st.session_state["latest_score"])
    else:
        st.info("No score calculated yet.")

# -----------------------------
# Applicants Database Page
# -----------------------------
with tabs[3]:
    st.subheader("📂 Applicants Database")

    if st.button("🔄 Refresh Data"):
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
            if st.button("🗑️ Delete Applicant"):
                if delete_id in df["id"].values:
                    delete_applicant(delete_id)
                else:
                    st.error("❌ Invalid ID. Please enter a valid Applicant ID from the table.")

            # Download Excel
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
