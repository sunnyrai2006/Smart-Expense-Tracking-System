import streamlit as st
import requests
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime,date

BACKEND = "http://127.0.0.1:5000"

st.set_page_config(page_title="Smart Expense Tracker",
                   page_icon="fevicon.png",
                   layout="wide")

# ---------- SESSION ----------
if "login" not in st.session_state:
    st.session_state.login = False
if "email" not in st.session_state:
    st.session_state.email = ""

# ---------- LOGIN ----------
def login():
    st.title("🔐 Login")
    email = st.text_input("Email", key="login_email")
    password = st.text_input("Password", type="password", key="login_pass")
    if st.button("Login"):
        r = requests.post(f"{BACKEND}/login", json={"email": email, "password": password}).json()
        if "error" in r:
            st.error(r["error"])
        else:
            st.session_state.login = True
            st.session_state.email = email
            st.rerun()

# ---------- SIGNUP ----------
def signup():
    st.title("📝 Signup")
    email = st.text_input("Email", key="signup_email")
    password = st.text_input("Password", type="password", key="signup_pass")
    dob = st.date_input("Date of Birth", min_value=date(1900, 1, 1), max_value=date.today() ,key="signup_dob")
    gender = st.selectbox("Gender", ["Male", "Female", "Other"], key="signup_gender")
    salary_day = st.number_input("Salary Day", 1, 28, key="signup_salary_day")
    if st.button("Signup"):
        r = requests.post(f"{BACKEND}/signup", json={
            "email": email,
            "password": password,
            "dob": str(dob),
            "gender": gender,
            "salary_day": salary_day
        }).json()
        if "error" in r:
            st.error(r["error"])
        else:
            st.success("Signup success 🎉")
            st.balloons()

# ---------- SALARY POPUP ----------
def salary_popup():
    prof = requests.get(f"{BACKEND}/profile/{st.session_state.email}").json()
    salary_day = int(prof.get("salary_day", 1))
    today = datetime.now()
    month = today.strftime("%b")
    year = today.year

    # Only show popup on salary day
    if today.day != salary_day:
        return

    # Check if salary is already saved
    key = f"{st.session_state.email}_{month}_{year}"
    chk = requests.get(f"{BACKEND}/salary_check/{key}").json()
    if chk.get("exists", False):
        return

    st.warning("💰 It's Salary Day! Enter Salary & Savings")
    salary_input = st.number_input("Salary", min_value=0, key=f"salary_input_{month}_{year}")
    savings_input = st.number_input("Savings", min_value=0, key=f"savings_input_{month}_{year}")
    if st.button("Save Salary"):
        requests.post(f"{BACKEND}/salary_update", json={
            "email": st.session_state.email,
            "month": month,
            "year": year,
            "salary": salary_input,
            "savings": savings_input
        })
        st.success("✅ Salary & Savings saved for this month")
        st.rerun()

# ---------- DASHBOARD ----------
def dashboard():
    st.title("📊 Dashboard")
    prof = requests.get(f"{BACKEND}/profile/{st.session_state.email}").json()
    st.write("👤", prof["username"])

    m = st.selectbox("Month", ["Jan","Feb","Mar","Apr","May","Jun",
                               "Jul","Aug","Sep","Oct","Nov","Dec"], key="dash_month")
    year = datetime.now().year

    # GET SALARY
    s = requests.get(f"{BACKEND}/salary_get/{st.session_state.email}/{m}/{year}").json()
    salary = s["salary"] if s.get("exists", False) else 0
    savings = s["savings"] if s.get("exists", False) else 0

    # GET EXPENSES
    g = requests.get(f"{BACKEND}/graph/{st.session_state.email}").json()
    df = pd.DataFrame(g)
    spent = df[df["month"] == m]["amount"].sum() if not df.empty else 0
    remaining = salary - savings - spent

    # Metrics
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Salary", f"₹{salary}")
    c2.metric("Spent", f"₹{spent}")
    c3.metric("Savings", f"₹{savings}")
    c4.metric("Remaining", f"₹{remaining}")

# ---------- ADD EXPENSE ----------
def add_expense():
    st.title("➕ Add Expense")
    desc = st.text_input("Description", key="desc")
    amt = st.number_input("Amount", key="amt")
    m = st.selectbox("Month", ["Jan","Feb","Mar","Apr","May","Jun",
                               "Jul","Aug","Sep","Oct","Nov","Dec"], key="add_month")
    if st.button("Add"):
        r = requests.post(f"{BACKEND}/predict", json={
            "email": st.session_state.email,
            "description": desc,
            "amount": amt,
            "month": m
        }).json()
        st.success(f"Category: {r['category']}")

# ---------- CATEGORY PIE CHART ----------
def pie_chart():
    st.title("🥧 Category Wise Spending")
    p = requests.get(f"{BACKEND}/category_pie/{st.session_state.email}").json()
    df = pd.DataFrame(p)
    if df.empty:
        st.info("No data")
        return

    fig, ax = plt.subplots()
    fig.set_size_inches(4,4)
    colors = ["#ff6384","#36a2eb","#ffce56","#4bc0c0","#9966ff","#ff9f40","#c9cbcf","#8dd17e","#ff6f91"]
    ax.pie(df["amount"], labels=df["category"], autopct="%1.1f%%", startangle=90,
           colors=colors[:len(df)])
    ax.set_title("Category Distribution")
    plt.tight_layout()
    st.pyplot(fig)

# ---------- INVESTMENT ----------
def investment():
    st.title("📈 Investment Suggestion")
    m = st.selectbox("Select Month", ["Jan","Feb","Mar","Apr","May","Jun",
                                     "Jul","Aug","Sep","Oct","Nov","Dec"], key="inv_month")
    year = datetime.now().year
    r = requests.get(f"{BACKEND}/investment/{st.session_state.email}/{m}/{year}")
    if r.status_code == 200:
        data = r.json()
        st.success(data.get("suggestion", "No suggestion available"))
    else:
        st.error("Error fetching investment suggestion")

# ---------- PROFILE ----------
def profile():
    st.title("👤 Profile")
    r = requests.get(f"{BACKEND}/profile/{st.session_state.email}").json()
    st.write("**Email:**", r["email"])
    st.write("**Username:**", r["username"])
    st.write("**DOB:**", r.get("dob",""))
    st.write("**Gender:**", r.get("gender",""))
    st.write("**Salary Day:**", r.get("salary_day",""))

    if st.button("Logout"):
        st.session_state.login = False
        st.session_state.email = ""
        st.rerun()

# ---------- MAIN ----------
if not st.session_state.login:
    tab1, tab2 = st.tabs(["Login","Signup"])
    with tab1: login()
    with tab2: signup()
else:
    salary_popup()
    menu = st.sidebar.radio("Menu", ["Dashboard","Add Expense","Category Chart","Investment","Profile"])
    if menu == "Dashboard": dashboard()
    elif menu == "Add Expense": add_expense()
    elif menu == "Category Chart": pie_chart()
    elif menu == "Investment": investment()
    elif menu == "Profile": profile()