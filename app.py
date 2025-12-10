from flask import Flask, render_template, redirect, request, session, url_for, jsonify
from google_auth_oauthlib.flow import Flow
from flask import session
import google.auth.transport.requests
from google.oauth2 import id_token
from datetime import timedelta
import os, json, hashlib
from flask import jsonify
import os, glob
import time
import threading
from datetime import datetime
#to crate excel file
from flask import send_file
import openpyxl
import io
import json
import os
import psycopg2

STUDENT_SUB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "student_submissions")


# -----------------------------
# Setup
# -----------------------------
app = Flask(__name__)
app.secret_key = "super_secret_key_123456789"
app.permanent_session_lifetime = timedelta(minutes=10)
#os files
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

#jsons
GOOGLE_CLIENT_ID = "709082344894-dlg893fucdfprg4q1b8qq0j1puj4ia5d.apps.googleusercontent.com"
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
CLIENT_SECRET_FILE = os.path.join(CURRENT_DIR, "surafelcheck.json")
ACCOUNTS_FILE = os.path.join(CURRENT_DIR, "accounts.json")
EXAMS_FILE = os.path.join(CURRENT_DIR, "hosted_exams.json")
STUDENT_SUB_FILE = os.path.join(CURRENT_DIR, "student_submissions")
EXAMS_DIR = os.path.join(CURRENT_DIR, "exams")
EXAMS_FOLDER = "exams"  # Change if your exam files are saved elsewhere
# -----------------------------
os.makedirs(EXAMS_DIR, exist_ok=True)
# Helper functions
# -----------------------------
#def for SQL

def get_db_connection():
    return psycopg2.connect(
        host="examsystem-surafelworku550-6d30.j.aivencloud.com",
        port=12650,
        dbname="defaultdb",
        user="avnadmin",
        password="AVNS_GptgMQPIjjD1UUZTqOW",
        sslmode="require"
    )

def load_accounts():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, name, email, password, login_type, picture, grade, section, phone, gender, verified FROM accounts")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    accounts = []
    for r in rows:
        accounts.append({
            "id": r[0],
            "name": r[1],
            "email": r[2],
            "password": r[3],
            "login_type": r[4],
            "picture": r[5],
            "grade": r[6],
            "section": r[7],
            "phone": r[8],
            "gender": r[9],
            "verified": r[10]
        })
    return accounts


def save_account(account):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO accounts (name, email, password, login_type, picture, grade, section, phone, gender, verified)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (email) DO NOTHING
        RETURNING id
    """, (
        account["name"],
        account["email"],
        account["password"],
        account["login_type"],
        account["picture"],
        account["grade"],
        account["section"],
        account["phone"],
        account["gender"],
        account["verified"]
    ))
    new_id = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    return new_id[0] if new_id else None

#--------------------------------------------------------------ok

# Define save_accounts to work with your PostgreSQL DB
def save_accounts(accounts):
    for account in accounts:
        save_account(account)

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def get_next_id(accounts):
    if not accounts:
        return 1
    return max(acc["id"] for acc in accounts) + 1
def load_exams():
    if not os.path.exists(EXAMS_FILE):
        return []
    with open(EXAMS_FILE, "r") as f:
        try:
            return json.load(f)
        except:
            return []

def save_exams(exams):
    with open(EXAMS_FILE, "w") as f:
        json.dump(exams, f, indent=4)
if not os.path.exists(STUDENT_SUB_FILE):
    os.makedirs(STUDENT_SUB_FILE)
#to delet exams in every 24 hours
def delete_old_exams():
    """Delete exam JSON files older than 24 hours automatically."""
    while True:
        now = time.time()
        if os.path.exists(EXAMS_FOLDER):
            for filename in os.listdir(EXAMS_FOLDER):
                file_path = os.path.join(EXAMS_FOLDER, filename)
                if os.path.isfile(file_path):
                    file_age = now - os.path.getmtime(file_path)
                    # 24 hours = 86400 seconds
                    if file_age > 86400:
                        try:
                            os.remove(file_path)
                            print(f"🗑️ Deleted old exam: {filename}")
                        except Exception as e:
                            print(f"⚠️ Could not delete {filename}: {e}")
        # Run every 1 hour
        time.sleep(3600)
# -----------------------------
# Routes
# -----------------------------
@app.route("/")
def index():
    if "google_id" in session or "email_id" in session:
        return redirect(url_for("dashboard"))
    return render_template("login.html")

# -----------------------------
# Dashboard
# -----------------------------
@app.route("/dashboard")
def dashboard():
    if "google_id" in session:
        login_type = "google"
        user_id = session["google_id"]
    elif "email_id" in session:
        login_type = "email"
        user_id = session["email_id"]
    else:
        return redirect(url_for("index"))

    # -----------------------------
    # Fetch current user from PostgreSQL instead of JSON
    # -----------------------------
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, name, email, password, login_type, picture, grade, section, phone, gender, verified
        FROM accounts
        WHERE id = %s AND login_type = %s
    """, (user_id, login_type))
    row = cur.fetchone()
    cur.close()
    conn.close()

    if not row:
        return redirect(url_for("index"))

    current_user = {
        "id": row[0],
        "name": row[1],
        "email": row[2],
        "password": row[3],
        "login_type": row[4],
        "picture": row[5],
        "grade": row[6],
        "section": row[7],
        "phone": row[8],
        "gender": row[9],
        "verified": row[10]
    }

    verified = current_user.get("verified", False)
    profile_complete = all(current_user.get(k) for k in ["grade", "section", "phone", "gender"])

    return render_template(
        "dashboard.html",
        name=current_user.get("name"),
        email=current_user.get("email"),
        picture=current_user.get("picture", ""),
        login_type=login_type,
        user_id=user_id,
        verified=verified,
        profile_complete=profile_complete,
        grade=current_user.get("grade", ""),
        section=current_user.get("section", ""),
        phone=current_user.get("phone", ""),
        roll=current_user.get("roll", "")
    )

# -----------------------------
# Google Login
# -----------------------------
@app.route("/login-google")
def login_google():
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRET_FILE,
        scopes=[
            "https://www.googleapis.com/auth/userinfo.profile",
            "https://www.googleapis.com/auth/userinfo.email",
            "openid"
        ],
        redirect_uri="https://take-exam-update-1.onrender.com/callback-google"
    )
    authorization_url, state = flow.authorization_url(prompt="consent")
    session["state"] = state
    return redirect(authorization_url)

@app.route("/callback-google")
def callback_google():
    if "state" not in session or session["state"] != request.args.get("state"):
        return "State mismatch error", 400

    flow = Flow.from_client_secrets_file(
        CLIENT_SECRET_FILE,
        scopes=[
            "https://www.googleapis.com/auth/userinfo.profile",
            "https://www.googleapis.com/auth/userinfo.email",
            "openid"
        ],
        redirect_uri="https://take-exam-update-1.onrender.com/callback-google"
    )
    flow.fetch_token(authorization_response=request.url)
    credentials = flow.credentials
    request_session = google.auth.transport.requests.Request()

    idinfo = id_token.verify_oauth2_token(credentials.id_token, request_session, GOOGLE_CLIENT_ID)

    accounts = load_accounts()
    existing = next((a for a in accounts if a["email"] == idinfo.get("email") and a["login_type"]=="google"), None)

    if existing:
        session["google_id"] = existing["id"]
    else:
        new_account = {
            "id": get_next_id(accounts),
            "name": idinfo.get("name"),
            "email": idinfo.get("email"),
            "password": "",
            "login_type": "google",
            "picture": idinfo.get("picture"),
            "verified": False,
            "grade": "",
            "section": "",
            "phone": "",
            "gender": ""
        }
        accounts.append(new_account)
        save_accounts(accounts)
        session["google_id"] = new_account["id"]

    session["name"] = idinfo.get("name")
    session["email"] = idinfo.get("email")
    session["picture"] = idinfo.get("picture", "")

    return redirect(url_for("dashboard"))

# -----------------------------
# Email Signup
# -----------------------------
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]

        conn = get_db_connection()
        cur = conn.cursor()

        # Check if email already exists
        cur.execute("SELECT id FROM accounts WHERE email = %s", (email,))
        existing = cur.fetchone()
        if existing:
            cur.close()
            conn.close()
            return "Email already exists"

        # Insert new account
        cur.execute("""
            INSERT INTO accounts (name, email, password, login_type, picture, verified, grade, section, phone, gender)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING id
        """, (
            name,
            email,
            hash_password(password),
            "email",
            "",
            False,
            "",
            "",
            "",
            ""
        ))

        new_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()

        return f"Signup successful! Your ID: {new_id} <a href='/login-email'>Login now</a>"

    return render_template("signup.html")


# -----------------------------
# Email Login
# -----------------------------
@app.route("/login-email", methods=["GET", "POST"])
def login_email():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        conn = get_db_connection()
        cur = conn.cursor()

        # Find user by email and login_type=email
        cur.execute("""
            SELECT id, name, email, password, picture
            FROM accounts
            WHERE email = %s AND login_type = 'email'
        """, (email,))
        user = cur.fetchone()
        cur.close()
        conn.close()

        if user and user[3] == hash_password(password):  # compare hashed password
            session["email_id"] = user[0]
            session["name"] = user[1]
            session["email"] = user[2]
            session["picture"] = user[4] or ""
            return redirect(url_for("dashboard"))

        return "Invalid credentials"

    return render_template("login.html")

# -----------------------------
# Save profile (student completes)
# -----------------------------
@app.route("/save_profile", methods=["POST"])
def save_profile():
    data = request.get_json()

    user_id = session.get("google_id") or session.get("email_id")
    if not user_id:
        return jsonify({"success": False, "message": "Not logged in"}), 403

    grade = data.get("grade", "")
    section = data.get("section", "")
    phone = data.get("phone", "")
    gender = data.get("gender", "")

    # Update PostgreSQL directly
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        UPDATE accounts
        SET grade = %s,
            section = %s,
            phone = %s,
            gender = %s
        WHERE id = %s
    """, (grade, section, phone, gender, user_id))
    conn.commit()
    cur.close()
    conn.close()

    return jsonify({"success": True})

    #exam rutes start
@app.route("/teacher")
def teacher():
    return render_template("teacher.html")

@app.route("/api/host_exam", methods=["POST"])
def host_exam():
    data = request.get_json()
    exam = data.get("exam")
    grade = data.get("grade")
    section = data.get("section")

    if not exam or not grade or not section:
        return jsonify({"success": False, "message": "Missing data"}), 400

    # Add grade and section into the exam JSON
    exam_with_info = exam.copy()  # Make a copy
    exam_with_info["grade"] = grade
    exam_with_info["section"] = section

    # Save in hosted_exams.json (existing behavior)
    exams = load_exams()
    exams.append({"exam": exam_with_info, "grade": grade, "section": section})
    save_exams(exams)

    # Save as separate file in exams folder
    EXAMS_DIR = os.path.join(CURRENT_DIR, "exams")
    os.makedirs(EXAMS_DIR, exist_ok=True)
    safe_title = "".join(c if c.isalnum() else "_" for c in exam.get("title", "exam"))
    filename = f"{safe_title}_grade_{grade}_section_{section}.json"
    filepath = os.path.join(EXAMS_DIR, filename)

    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(exam_with_info, f, indent=2, ensure_ascii=False)
    except Exception as e:
        return jsonify({"success": False, "message": f"Error saving file: {e}"}), 500

    return jsonify({"success": True})


#exam routes are end their
@app.route("/api/save_result", methods=["POST"])
def save_result():
    data = request.get_json()
    user_id = session.get("google_id") or session.get("email_id")
    if not user_id:
        return jsonify({"success": False, "message": "Not logged in"}), 403

    filename = os.path.join(STUDENT_SUB_FILE, f"{user_id}.json")

    # Load previous results if exist
    if os.path.exists(filename):
        with open(filename, "r") as f:
            try:
                results = json.load(f)
            except:
                results = []
    else:
        results = []

    # Append new result
    new_result = {
        "studentName": data.get("studentName"),
        "exam": data.get("exam"),
        "score": data.get("score"),
        "total": data.get("total"),
        "percentage": round(data.get("score")/data.get("total")*100,2)
    }

    results.append(new_result)

    # Save back all results
    with open(filename, "w") as f:
        json.dump(results, f, indent=4)

    return jsonify({"success": True})

# -----------------------------
@app.route("/api/student_info")
def api_student_info():
    user_id = session.get("google_id") or session.get("email_id")
    if not user_id:
        return jsonify({"success": False, "message": "Not logged in"}), 403

    accounts = load_accounts()
    student = next((a for a in accounts if a["id"] == user_id), None)
    if not student:
        return jsonify({"success": False, "message": "Account not found"}), 404

    return jsonify({
        "success": True,
        "name": student.get("name"),
        "grade": student.get("grade"),
        "section": student.get("section")
    })
#routes are there
@app.route("/api/get_exam")
def get_exam():
    grade = request.args.get("grade")
    section = request.args.get("section")

    if not grade or not section:
        return jsonify({"success": False, "message": "Grade or section missing"}), 400

    exams_dir = os.path.join(CURRENT_DIR, "exams")
    found_exams = []

    # Read every exam JSON file and match grade & section
    for filename in os.listdir(exams_dir):
        if not filename.endswith(".json"):
            continue

        filepath = os.path.join(exams_dir, filename)
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                file_grade = str(data.get("grade", "")).strip()
                file_section = str(data.get("section", "")).strip().upper()

                if file_grade == str(grade).strip() and file_section == str(section).strip().upper():
                    found_exams.append(data)  # ✅ return full exam, including questions
        except Exception as e:
            print(f"Error reading exam file {filename}: {e}")

    if not found_exams:
        return jsonify([])  # no exam

    return jsonify(found_exams)  # return list of full exam objects


# Admin & API
# -----------------------------
# Get all accounts
@app.route("/api/accounts")
def api_accounts():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, name, email, password, login_type, picture, grade, section, phone, gender, verified FROM accounts")
    rows = cur.fetchall()
    cur.close()
    conn.close()

    accounts = []
    for r in rows:
        accounts.append({
            "id": r[0],
            "name": r[1],
            "email": r[2],
            "password": r[3],
            "login_type": r[4],
            "picture": r[5],
            "grade": r[6],
            "section": r[7],
            "phone": r[8],
            "gender": r[9],
            "verified": r[10]
        })
    return jsonify(accounts)


# Update account by ID
@app.route("/api/accounts/<int:acc_id>", methods=["PUT"])
def api_update_account(acc_id):
    data = request.get_json()
    conn = get_db_connection()
    cur = conn.cursor()

    # Build dynamic SET part for SQL update
    fields = ["name", "email", "grade", "section", "phone", "gender"]
    set_clause = ", ".join(f"{f} = %s" for f in fields if f in data)
    values = [data[f] for f in fields if f in data]

    if set_clause:  # only run if there is something to update
        values.append(acc_id)
        cur.execute(f"UPDATE accounts SET {set_clause} WHERE id = %s RETURNING id", tuple(values))
        updated = cur.fetchone()
        conn.commit()
    else:
        updated = None

    cur.close()
    conn.close()

    if updated:
        return jsonify({"success": True})
    else:
        return jsonify({"success": False}), 404


# Verify account by ID
@app.route("/api/accounts/<int:acc_id>/verify", methods=["PUT"])
def api_verify_account(acc_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE accounts SET verified = TRUE WHERE id = %s RETURNING id", (acc_id,))
    updated = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()

    if updated:
        return jsonify({"success": True})
    else:
        return jsonify({"success": False}), 404

#to run the exam route
# Route to run exam
# -----------------------------
@app.route("/run_exam")
def run_exam():
    # Ensure the user is logged in
    user_id = session.get("google_id") or session.get("email_id")
    if not user_id:
        return redirect(url_for("index"))

    student_name = "Student"  # default fallback

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT name FROM accounts WHERE id = %s", (user_id,))
        result = cur.fetchone()
        cur.close()
        conn.close()

        if result:
            student_name = result[0] or "Student"

    except Exception as e:
        print("Error fetching student from SQL:", e)

    return render_template("run_exam.html", name=student_name)


@app.route("/api/student_results/<int:user_id>")
def student_results(user_id):
    filename = os.path.join(STUDENT_SUB_FILE, f"{user_id}.json")
    if not os.path.exists(filename):
        return jsonify({"success": False, "results": []})

    with open(filename, "r") as f:
        results = json.load(f)  # This is now a list of exam results

    return jsonify({"success": True, "results": results})
@app.route("/result")
def result_page():
    return render_template("result.html")

#export result routes are here
@app.route("/export_results")
def export_results():
    import pandas as pd
    from io import BytesIO

    all_results = []

    # Loop through all student JSON files
    for filename in os.listdir(STUDENT_SUB_FILE):
        if filename.endswith(".json"):
            filepath = os.path.join(STUDENT_SUB_FILE, filename)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    student_exams = json.load(f)
                    if isinstance(student_exams, list):
                        all_results.extend(student_exams)  # combine all exams
                    else:
                        print(f"File {filename} format is invalid")
            except Exception as e:
                print(f"Error reading {filename}: {e}")

    if not all_results:
        return "No results found!"

    # Convert combined data to DataFrame
    df = pd.DataFrame(all_results)

    # Create Excel file in memory
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Results')
    output.seek(0)

    # Send Excel file to client
    return send_file(
        output,
        download_name="all_students_results.xlsx",
        as_attachment=True,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
#result view last
#delet results in there
# DELETE all student exam results
@app.route("/api/delete_all_results", methods=["DELETE"])
def delete_all_results():
    try:
        # Folder where student results are stored
        results_folder = os.path.join(os.getcwd(), "student_submissions")

        if not os.path.exists(results_folder):
            return jsonify({"success": False, "message": "❌ Results folder not found!"})

        # Match all JSON files in the folder
        files = glob.glob(os.path.join(results_folder, "*.json"))
        if not files:
            return jsonify({"success": False, "message": "❌ No student results found!"})

        # Delete all files
        for file in files:
            os.remove(file)

        return jsonify({"success": True, "message": "✅ All student results deleted successfully!"})

    except Exception as e:
        return jsonify({"success": False, "message": f"❌ Error: {str(e)}"})
@app.route("/admin")
def admin():
    return render_template("admin.html")

# -----------------------------
@app.route("/crate")
def crate_exam_page():
    return render_template("crate.html")
# Logout
# -----------------------------
#to delete exams json saved in exam folder
@app.route("/delete_all_exams", methods=["POST"])
def delete_all_exams():
    exams_folder = os.path.join(CURRENT_DIR, "exams")

    if not os.path.exists(exams_folder):
        return jsonify({"success": False, "message": "❌ Exams folder not found!"})

    deleted_files = 0
    for filename in os.listdir(exams_folder):
        if filename.endswith(".json"):
            try:
                os.remove(os.path.join(exams_folder, filename))
                deleted_files += 1
            except Exception as e:
                print(f"Error deleting {filename}: {e}")

    return jsonify({
        "success": True,
        "message": f"✅ Deleted {deleted_files} exam file(s) successfully!"
    })
#logout option
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))
# Start background cleaner
cleaner_thread = threading.Thread(target=delete_old_exams, daemon=True)
cleaner_thread.start()

# -----------------------------
if __name__ == "__main__":
    app.run(debug=True)


