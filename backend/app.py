import joblib as jl
import os
import json
import firebase_admin
from firebase_admin import credentials, firestore
from flask import Flask, request, jsonify
from datetime import datetime

# -------- Load ML Models --------
embedder = jl.load('backend/embedder_compressed.pkl')
model = jl.load('backend/model_compressed.pkl')

def predict_category(text):
    vec = embedder.encode([text])
    return model.predict(vec)[0]

# -------- Firebase Setup --------
if not firebase_admin._apps:
    # Get JSON from environment variable
    cred_json = os.environ.get("FIREBASE_JSON")
    if not cred_json:
        raise ValueError("FIREBASE_JSON environment variable not set")

    cred_dict = json.loads(cred_json)
    cred = credentials.Certificate(cred_dict)
    firebase_admin.initialize_app(cred)

db = firestore.client()
print("✅ Firebase connected")

# -------- Flask App --------
app = Flask(__name__)

# ================= SIGNUP =================
@app.route("/signup", methods=["POST"])
def signup():
    d = request.get_json()

    email = d["email"]
    password = d["password"]
    dob = d.get("dob","")
    gender = d.get("gender", "")
    salary_day = d.get("salary_day",1)

    if db.collection("users").document(email).get().exists:
        return jsonify({"error":"User exists"})

    username = email.split("@")[0]

    db.collection("users").document(email).set({
        "email":email,
        "username":username,
        "password":password,
        "dob": dob,
        "gender": gender,
        "salary_day": salary_day
    })

    return jsonify({"message":"Signup success"})

# ================= LOGIN =================
@app.route("/login", methods=["POST"])
def login():
    d = request.get_json()
    doc = db.collection("users").document(d["email"]).get()

    if not doc.exists:
        return jsonify({"error":"User not found"})

    if doc.to_dict()["password"] != d["password"]:
        return jsonify({"error":"Wrong password"})

    return jsonify({"message":"Login success"})

# ================= PROFILE =================
@app.route("/profile/<email>")
def profile(email):
    doc=db.collection("users").document(email).get()
    if not doc.exists:
        return jsonify({"error":"User not found"})
    return jsonify(doc.to_dict())

# ================= SALARY SAVE =================
@app.route("/salary_update",methods=["POST"])
def salary_update():
    d=request.get_json()
    key=f'{d["email"]}_{d["month"]}_{d["year"]}'
    db.collection("salaries").document(key).set(d)
    return jsonify({"message":"Salary saved"})

# ================= SALARY CHECK =================
@app.route("/salary_check/<key>")
def salary_check(key):
    doc=db.collection("salaries").document(key).get()
    return jsonify({"exists":doc.exists})

# ================= GET SALARY =================
@app.route("/salary_get/<email>/<month>/<year>")
def salary_get(email,month,year):
    key=f"{email}_{month}_{year}"
    doc=db.collection("salaries").document(key).get()
    if not doc.exists:
        return jsonify({"exists":False})
    data = doc.to_dict()
    return jsonify({
        "exists":True,
        "salary":data["salary"],
        "savings":data["savings"]
    })

# ================= INVESTMENT =================
@app.route("/investment/<email>/<month>/<year>")
def investment(email,month,year):
    key=f"{email}_{month}_{year}"
    s = db.collection("salaries").document(key).get()
    if not s.exists:
        return jsonify({"suggestion":"Update salary first"})
    d = s.to_dict()
    sal = d["salary"]
    sav = d["savings"]
    if sav < sal*0.1:
        tip="Start emergency fund"
    elif sav < sal*0.3:
        tip="Start SIP mutual fund"
    else:
        tip="Stocks & ETFs"
    return jsonify({"suggestion":tip})

# ================= ADD EXPENSE =================
@app.route("/predict",methods=["POST"])
def add_expense():
    d=request.get_json()
    cat=predict_category(d["description"])
    db.collection("expenses").add({
        "email":d["email"],
        "description":d["description"],
        "amount":d["amount"],
        "month":d["month"],
        "category":cat
    })
    return jsonify({"category":cat})

# ================= CATEGORY PIE =================
@app.route("/category_pie/<email>")
def pie(email):
    exp=db.collection("expenses").where("email","==",email).stream()
    res={}
    for e in exp:
        d=e.to_dict()
        res[d["category"]] = res.get(d["category"],0) + d["amount"]
    out = [{"category":k,"amount":v} for k,v in res.items()]
    return jsonify(out)

# ================= GRAPH =================
@app.route("/graph/<email>")
def graph(email):
    exp=db.collection("expenses").where("email","==",email).stream()
    res={}
    for e in exp:
        d=e.to_dict()
        res[d["month"]] = res.get(d["month"],0) + d["amount"]
    out = [{"month":k,"amount":v} for k,v in res.items()]
    return jsonify(out)

# ================= AUTO ALERT =================
@app.route("/auto_alert/<email>/<month>")
def auto_alert(email, month):
    key = f"{email}_{month}_{datetime.now().year}"
    sal_doc = db.collection("salaries").document(key).get()
    if not sal_doc.exists:
        return jsonify({"alert": ""})
    salary = sal_doc.to_dict()["salary"]
    exp = db.collection("expenses").where("email","==",email).where("month","==",month).stream()
    total = sum(e.to_dict()["amount"] for e in exp)
    if total > salary * 0.8:
        return jsonify({"alert":"⚠ Overspending detected!"})
    return jsonify({"alert":""})

# ================= RUN =================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))  # fallback to 5000 for local testing
    app.run(host="0.0.0.0", port=port)
