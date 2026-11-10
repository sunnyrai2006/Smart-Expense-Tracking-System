
import streamlit as st
import requests
import pandas as pd
import matplotlib.pyplot as plt

from datetime import datetime, date

# ==========================================
# CONFIGURATION
# ==========================================

BACKEND = "http://127.0.0.1:5000"

MONTHS = [
    "Jan", "Feb", "Mar", "Apr",
    "May", "Jun", "Jul", "Aug",
    "Sep", "Oct", "Nov", "Dec"
]

CURRENT_MONTH_INDEX = datetime.now().month - 1
CURRENT_MONTH = MONTHS[CURRENT_MONTH_INDEX]
CURRENT_YEAR = datetime.now().year

st.set_page_config(
    page_title="Smart Expense Tracker",
    page_icon="💰",
    layout="wide"
)


# ==========================================
# API HELPER
# ==========================================

def api_request(method, endpoint, **kwargs):

    try:
        response = requests.request(
            method,
            f"{BACKEND}{endpoint}",
            timeout=30,
            **kwargs
        )

        try:
            data = response.json()
        except ValueError:
            st.error("Backend returned an invalid response.")
            st.code(response.text[:2000])
            return None

        if not response.ok:
            error = data.get("error", "Unknown backend error") if isinstance(data, dict) else data
            st.error(f"Backend Error ({response.status_code}): {error}")
            return None

        return data

    except requests.exceptions.ConnectionError:
        st.error("Cannot connect to Flask backend. Please start backend/app.py.")
        return None

    except requests.exceptions.Timeout:
        st.error("Backend request timed out.")
        return None

    except requests.exceptions.RequestException as e:
        st.error(f"Request failed: {e}")
        return None


# ==========================================
# SESSION STATE
# ==========================================

if "login" not in st.session_state:
    st.session_state.login = False

if "email" not in st.session_state:
    st.session_state.email = ""

if "menu" not in st.session_state:
    st.session_state.menu = "Dashboard"


# ==========================================
# LOGIN
# ==========================================

def login():

    st.title("🔐 Login")
    st.write("Welcome back to Smart Expense Tracker!")

    email = st.text_input("Email", key="login_email")
    password = st.text_input(
        "Password",
        type="password",
        key="login_pass"
    )

    if st.button("Login", use_container_width=True):

        if not email.strip() or not password:
            st.warning("Please enter email and password.")
            return

        r = api_request(
            "POST",
            "/login",
            json={
                "email": email.strip().lower(),
                "password": password
            }
        )

        if r is not None:

            if "error" in r:
                st.error(r["error"])

            else:
                st.session_state.login = True
                st.session_state.email = email.strip().lower()

                # Dashboard becomes home page
                st.session_state.menu = "Dashboard"

                st.success("Login successful!")
                st.rerun()


# ==========================================
# SIGNUP
# ==========================================

def signup():

    st.title("📝 Create Account")

    email = st.text_input("Email", key="signup_email")

    password = st.text_input(
        "Password",
        type="password",
        key="signup_pass"
    )

    dob = st.date_input(
        "Date of Birth",
        min_value=date(1900, 1, 1),
        max_value=date.today(),
        key="signup_dob"
    )

    gender = st.selectbox(
        "Gender",
        ["Male", "Female", "Other"],
        key="signup_gender"
    )

    salary_day = st.number_input(
        "Salary Day",
        min_value=1,
        max_value=28,
        value=1,
        key="signup_salary_day"
    )

    if st.button("Signup", use_container_width=True):

        if not email.strip() or not password:
            st.warning("Please enter email and password.")
            return

        r = api_request(
            "POST",
            "/signup",
            json={
                "email": email.strip().lower(),
                "password": password,
                "dob": str(dob),
                "gender": gender,
                "salary_day": int(salary_day)
            }
        )

        if r is not None:

            if "error" in r:
                st.error(r["error"])

            else:
                st.success("Signup successful! Please login.")
                st.balloons()


# ==========================================
# SALARY POPUP
# ==========================================

def salary_popup():

    prof = api_request(
        "GET",
        f"/profile/{st.session_state.email}"
    )

    if prof is None or "error" in prof:
        return

    salary_day = int(prof.get("salary_day", 1))

    today = datetime.now()

    month = today.strftime("%b")
    year = today.year

    # Show popup only on salary day
    if today.day != salary_day:
        return

    key = f"{st.session_state.email}_{month}_{year}"

    chk = api_request(
        "GET",
        f"/salary_check/{key}"
    )

    if chk is None or chk.get("exists", False):
        return

    st.warning("💰 It's Salary Day! Enter your salary and savings.")

    salary_input = st.number_input(
        "Salary",
        min_value=0.0,
        key=f"salary_input_{month}_{year}"
    )

    savings_input = st.number_input(
        "Savings",
        min_value=0.0,
        key=f"savings_input_{month}_{year}"
    )

    if st.button("Save Salary"):

        if savings_input > salary_input:
            st.error("Savings cannot exceed salary.")
            return

        result = api_request(
            "POST",
            "/salary_update",
            json={
                "email": st.session_state.email,
                "month": month,
                "year": year,
                "salary": salary_input,
                "savings": savings_input
            }
        )

        if result is not None:
            st.success("Salary and savings saved!")
            st.rerun()


# ==========================================
# DASHBOARD / HOME PAGE
# ==========================================

def dashboard():

    st.title("📊 Dashboard")
    st.caption("Welcome to your Smart Expense Tracker.")

    prof = api_request(
        "GET",
        f"/profile/{st.session_state.email}"
    )

    if prof is None or "error" in prof:
        return

    st.subheader(f"Hello, {prof.get('username', 'User')} 👋")

    # Current month automatically selected
    m = st.selectbox(
        "Select Month",
        MONTHS,
        index=CURRENT_MONTH_INDEX,
        key="dash_month"
    )

    year = CURRENT_YEAR

    # Get salary
    salary_data = api_request(
        "GET",
        f"/salary_get/{st.session_state.email}/{m}/{year}"
    )

    if salary_data is None:
        return

    salary = float(salary_data.get("salary", 0))
    savings = float(salary_data.get("savings", 0))

    # Get expenses
    expenses = api_request(
        "GET",
        f"/graph/{st.session_state.email}"
    )

    if expenses is None:
        return

    df = pd.DataFrame(expenses)

    if not df.empty:
        spent = float(
            df.loc[df["month"] == m, "amount"].sum()
        )
    else:
        spent = 0.0

    remaining = salary - savings - spent

    # Metrics
    c1, c2, c3, c4 = st.columns(4)

    c1.metric("💰 Salary", f"₹{salary:,.2f}")
    c2.metric("💸 Spent", f"₹{spent:,.2f}")
    c3.metric("🏦 Savings", f"₹{savings:,.2f}")
    c4.metric("💵 Remaining", f"₹{remaining:,.2f}")

    st.divider()

    # Spending alert
    alert = api_request(
        "GET",
        f"/auto_alert/{st.session_state.email}/{m}"
    )

    if alert and alert.get("alert"):
        st.warning(alert["alert"])

    st.subheader("Monthly Overview")

    if spent == 0:
        st.info("No expenses recorded for this month yet.")

    else:
        st.progress(
            min(spent / salary, 1.0) if salary > 0 else 0.0
        )

        if salary > 0:
            st.write(
                f"You have spent {spent / salary * 100:.1f}% of your salary."
            )


# ==========================================
# ADD EXPENSE
# ==========================================

def add_expense():

    st.title("➕ Add Expense")

    desc = st.text_input(
        "Description",
        key="desc"
    )

    amt = st.number_input(
        "Amount",
        min_value=0.0,
        key="amt"
    )

    # Automatically select current month
    m = st.selectbox(
        "Month",
        MONTHS,
        index=CURRENT_MONTH_INDEX,
        key="add_month"
    )

    if st.button("Add", use_container_width=False):

        if not desc.strip():
            st.warning("Please enter expense description.")
            return

        if amt <= 0:
            st.warning("Please enter a valid amount.")
            return

        r = api_request(
            "POST",
            "/predict",
            json={
                "email": st.session_state.email,
                "description": desc.strip(),
                "amount": float(amt),
                "month": m
            }
        )

        if r is not None:

            if "category" in r:

                st.success(
                    f"Expense added successfully! Category: {r['category']}"
                )

                st.balloons()

            elif "error" in r:
                st.error(r["error"])

            else:
                st.error("Unexpected response from backend.")


# ==========================================
# CATEGORY PIE CHART
# ==========================================

def pie_chart():

    st.title("🥧 Category Wise Spending")

    p = api_request(
        "GET",
        f"/category_pie/{st.session_state.email}"
    )

    if p is None:
        return

    df = pd.DataFrame(p)

    if df.empty:
        st.info("No expense data available.")
        return

    fig, ax = plt.subplots(figsize=(6, 5))

    colors = [
        "#ff6384", "#36a2eb", "#ffce56",
        "#4bc0c0", "#9966ff", "#ff9f40",
        "#c9cbcf", "#8dd17e", "#ff6f91"
    ]

    ax.pie(
        df["amount"],
        labels=df["category"],
        autopct="%1.1f%%",
        startangle=90,
        colors=colors[:len(df)]
    )

    ax.set_title("Category Distribution")

    plt.tight_layout()

    st.pyplot(fig)

    plt.close(fig)

    st.subheader("Category Details")

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True
    )


# ==========================================
# INVESTMENT
# ==========================================

def investment():

    st.title("📈 Investment Suggestions")

    m = st.selectbox(
        "Select Month",
        MONTHS,
        index=CURRENT_MONTH_INDEX,
        key="inv_month"
    )

    year = CURRENT_YEAR

    r = api_request(
        "GET",
        f"/investment/{st.session_state.email}/{m}/{year}"
    )

    if r is not None:
        st.success(
            r.get("suggestion", "No suggestion available")
        )


# ==========================================
# PROFILE
# ==========================================

def profile():

    st.title("👤 My Profile")

    r = api_request(
        "GET",
        f"/profile/{st.session_state.email}"
    )

    if r is None or "error" in r:
        return

    st.write("**Email:**", r.get("email", ""))
    st.write("**Username:**", r.get("username", ""))
    st.write("**Date of Birth:**", r.get("dob", ""))
    st.write("**Gender:**", r.get("gender", ""))
    st.write("**Salary Day:**", r.get("salary_day", ""))

    st.divider()

    if st.button("Logout"):

        st.session_state.login = False
        st.session_state.email = ""
        st.session_state.menu = "Dashboard"

        st.rerun()


# ==========================================
# MAIN APPLICATION
# ==========================================

if not st.session_state.login:

    st.title("💰 Smart Expense Tracker")

    st.write(
        "Track your expenses, understand your spending "
        "and manage your savings intelligently."
    )

    tab1, tab2 = st.tabs(["Login", "Signup"])

    with tab1:
        login()

    with tab2:
        signup()

else:

    # Salary popup
    salary_popup()

    # Dashboard is the default home page
    menu = st.sidebar.radio(
        "Menu",
        [
            "Dashboard",
            "Add Expense",
            "Category Chart",
            "Investment",
            "Profile"
        ],
        index=0,
        key="menu"
    )

    st.sidebar.divider()

    st.sidebar.caption(
        f"Logged in as: {st.session_state.email}"
    )

    if menu == "Dashboard":
        dashboard()

    elif menu == "Add Expense":
        add_expense()

    elif menu == "Category Chart":
        pie_chart()

    elif menu == "Investment":
        investment()

    elif menu == "Profile":
        profile()
