
import os
import joblib
import firebase_admin

from sentence_transformers import SentenceTransformer
from firebase_admin import credentials, firestore
from flask import Flask, request, jsonify
from datetime import datetime

# ==========================================
# PATH CONFIGURATION
# ==========================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# ==========================================
# LOAD ML MODELS
# ==========================================

print("Loading embedding model...")

embedder = SentenceTransformer(
    "sentence-transformers/paraphrase-mpnet-base-v2"
)

model = joblib.load(os.path.join(BASE_DIR, "model.pkl"))

print("ML models loaded successfully!")

def predict_category(text):
    embeddings = embedder.encode([text])
    prediction = model.predict(embeddings)[0]
    return str(prediction)


# ==========================================
# FIREBASE CONFIGURATION
# ==========================================

firebase_key = os.getenv("FIREBASE_CREDENTIALS")

if not firebase_key or not os.path.isfile(firebase_key):
    raise FileNotFoundError("Firebase credentials not configured")

cred = credentials.Certificate(firebase_key)

db = firestore.client()

print("Firebase connected successfully!")


# ==========================================
# FLASK APPLICATION
# ==========================================

app = Flask(__name__)


# ==========================================
# HEALTH CHECK
# ==========================================

@app.route("/")
def home():
    return jsonify({
        "message": "Smart Expense Tracker API is running",
        "status": "success"
    })


# ==========================================
# SIGNUP
# ==========================================

@app.route("/signup", methods=["POST"])
def signup():

    try:
        d = request.get_json(silent=True) or {}

        email = d.get("email", "").strip().lower()
        password = d.get("password", "")
        dob = d.get("dob", "")
        gender = d.get("gender", "")
        salary_day = int(d.get("salary_day", 1))

        if not email or not password:
            return jsonify({"error": "Email and password are required"}), 400

        if not 1 <= salary_day <= 28:
            return jsonify({"error": "Invalid salary day"}), 400

        user_ref = db.collection("users").document(email)

        if user_ref.get().exists:
            return jsonify({"error": "User already exists"}), 409

        username = email.split("@")[0]

        user_ref.set({
            "email": email,
            "username": username,
            "password": password,
            "dob": dob,
            "gender": gender,
            "salary_day": salary_day
        })

        return jsonify({"message": "Signup success"}), 201

    except Exception as e:
        app.logger.exception("Signup error")
        return jsonify({"error": str(e)}), 500


# ==========================================
# LOGIN
# ==========================================

@app.route("/login", methods=["POST"])
def login():

    try:
        d = request.get_json(silent=True) or {}

        email = d.get("email", "").strip().lower()
        password = d.get("password", "")

        if not email or not password:
            return jsonify({"error": "Enter email and password"}), 400

        doc = db.collection("users").document(email).get()

        if not doc.exists:
            return jsonify({"error": "User not found"}), 404

        user = doc.to_dict()

        if user.get("password") != password:
            return jsonify({"error": "Wrong password"}), 401

        return jsonify({"message": "Login success"})

    except Exception as e:
        app.logger.exception("Login error")
        return jsonify({"error": str(e)}), 500


# ==========================================
# PROFILE
# ==========================================

@app.route("/profile/<path:email>")
def profile(email):

    try:
        doc = db.collection("users").document(email).get()

        if not doc.exists:
            return jsonify({"error": "User not found"}), 404

        return jsonify(doc.to_dict())

    except Exception as e:
        app.logger.exception("Profile error")
        return jsonify({"error": str(e)}), 500


# ==========================================
# SALARY UPDATE
# ==========================================

@app.route("/salary_update", methods=["POST"])
def salary_update():

    try:
        d = request.get_json(silent=True) or {}

        email = d.get("email")
        month = d.get("month")
        year = d.get("year")

        if not email or not month or year is None:
            return jsonify({"error": "Missing salary details"}), 400

        key = f"{email}_{month}_{year}"

        db.collection("salaries").document(key).set({
            "email": email,
            "month": month,
            "year": int(year),
            "salary": float(d.get("salary", 0)),
            "savings": float(d.get("savings", 0))
        })

        return jsonify({"message": "Salary saved"})

    except Exception as e:
        app.logger.exception("Salary update error")
        return jsonify({"error": str(e)}), 500


# ==========================================
# SALARY CHECK
# ==========================================

@app.route("/salary_check/<path:key>")
def salary_check(key):

    try:
        doc = db.collection("salaries").document(key).get()

        return jsonify({"exists": doc.exists})

    except Exception as e:
        app.logger.exception("Salary check error")
        return jsonify({"error": str(e)}), 500


# ==========================================
# GET SALARY
# ==========================================

@app.route("/salary_get/<path:email>/<month>/<year>")
def salary_get(email, month, year):

    try:
        key = f"{email}_{month}_{year}"

        doc = db.collection("salaries").document(key).get()

        if not doc.exists:
            return jsonify({"exists": False})

        data = doc.to_dict()

        return jsonify({
            "exists": True,
            "salary": data.get("salary", 0),
            "savings": data.get("savings", 0)
        })

    except Exception as e:
        app.logger.exception("Get salary error")
        return jsonify({"error": str(e)}), 500


# ==========================================
# INVESTMENT SUGGESTION
# ==========================================

@app.route("/investment/<path:email>/<month>/<year>")
def investment(email, month, year):

    try:
        key = f"{email}_{month}_{year}"

        doc = db.collection("salaries").document(key).get()

        if not doc.exists:
            return jsonify({
                "suggestion": "Update salary first"
            })

        d = doc.to_dict()

        salary = float(d.get("salary", 0))
        savings = float(d.get("savings", 0))

        if salary <= 0:
            tip = "Enter a valid salary first"

        elif savings < salary * 0.1:
            tip = "Start building an emergency fund"

        elif savings < salary * 0.3:
            tip = "Consider learning about SIP mutual funds"

        else:
            tip = "Explore diversified investment options"

        return jsonify({"suggestion": tip})

    except Exception as e:
        app.logger.exception("Investment error")
        return jsonify({"error": str(e)}), 500


# ==========================================
# ADD EXPENSE / ML PREDICTION
# ==========================================

@app.route("/predict", methods=["POST"])
def add_expense():

    try:
        d = request.get_json(silent=True) or {}

        email = d.get("email")
        description = d.get("description", "").strip()
        amount = d.get("amount")
        month = d.get("month")

        if not email or not description or amount is None or not month:
            return jsonify({
                "error": "All expense fields are required"
            }), 400

        amount = float(amount)

        if amount <= 0:
            return jsonify({"error": "Amount must be greater than zero"}), 400

        # Predict category using MPNet
        category = predict_category(description)

        # Save expense to Firestore
        db.collection("expenses").add({
            "email": email,
            "description": description,
            "amount": amount,
            "month": month,
            "category": category,
            "created_at": datetime.now().isoformat()
        })

        return jsonify({
            "success": True,
            "category": category,
            "message": "Expense added successfully"
        }), 200

    except Exception as e:
        app.logger.exception("Expense prediction/save error")

        return jsonify({
            "error": str(e)
        }), 500


# ==========================================
# CATEGORY PIE CHART
# ==========================================

@app.route("/category_pie/<path:email>")
def pie(email):

    try:
        expenses = db.collection("expenses").where(
            "email", "==", email
        ).stream()

        result = {}

        for expense in expenses:

            d = expense.to_dict()

            category = d.get("category", "Other")
            amount = float(d.get("amount", 0))

            result[category] = result.get(category, 0) + amount

        output = [
            {"category": k, "amount": v}
            for k, v in result.items()
        ]

        return jsonify(output)

    except Exception as e:
        app.logger.exception("Pie chart error")
        return jsonify({"error": str(e)}), 500


# ==========================================
# MONTHLY EXPENSE GRAPH
# ==========================================

@app.route("/graph/<path:email>")
def graph(email):

    try:
        expenses = db.collection("expenses").where(
            "email", "==", email
        ).stream()

        result = {}

        for expense in expenses:

            d = expense.to_dict()

            month = d.get("month")
            amount = float(d.get("amount", 0))

            result[month] = result.get(month, 0) + amount

        output = [
            {"month": k, "amount": v}
            for k, v in result.items()
        ]

        return jsonify(output)

    except Exception as e:
        app.logger.exception("Graph error")
        return jsonify({"error": str(e)}), 500


# ==========================================
# AUTOMATIC SPENDING ALERT
# ==========================================

@app.route("/auto_alert/<path:email>/<month>")
def auto_alert(email, month):

    try:
        key = f"{email}_{month}_{datetime.now().year}"

        salary_doc = db.collection("salaries").document(key).get()

        if not salary_doc.exists:
            return jsonify({"alert": ""})

        salary = float(salary_doc.to_dict().get("salary", 0))

        expenses = db.collection("expenses").where(
            "email", "==", email
        ).where(
            "month", "==", month
        ).stream()

        total = sum(
            float(e.to_dict().get("amount", 0))
            for e in expenses
        )

        if salary > 0 and total > salary * 0.8:
            return jsonify({
                "alert": "⚠ Overspending detected!"
            })

        return jsonify({"alert": ""})

    except Exception as e:
        app.logger.exception("Auto alert error")
        return jsonify({"error": str(e)}), 500


# ==========================================
# RUN SERVER
# ==========================================


if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True,
        use_reloader=False
    )

