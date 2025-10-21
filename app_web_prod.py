import os
import json
import sqlite3
from pathlib import Path
from flask import Flask, jsonify, render_template, request, redirect, url_for, flash, send_file

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "fallback-secret-key")

# =========================================================
# 1) Persistent storage & database configuration
#    - Works on Render and locally on Windows
# =========================================================

# Prefer explicit DB_PATH, else DB_DIR/DISK_PATH, else default Render mount path
DB_DIR = (
    os.getenv("DB_DIR")
    or os.getenv("DISK_PATH")
    or "/opt/render/project/src/data"  # your disk mount shown in screenshots
)
Path(DB_DIR).mkdir(parents=True, exist_ok=True)

# Local Windows fallback (adjust if you keep a local copy there)
LOCAL_DB_PATH = r"C:\OKC Data\Evergreen Evolution\Evergreen_Complete\Evergreen_Complete\harvest.db"

DB_PATH = os.getenv("DB_PATH") or os.path.join(DB_DIR, "harvest.db")
if not os.path.exists(DB_PATH) and os.path.exists(LOCAL_DB_PATH):
    # If running locally and the Render path doesn't exist, fall back to your local file
    DB_PATH = LOCAL_DB_PATH

# Legacy JSON files (if you still use them anywhere)
DATA_FILE = os.path.join(DB_DIR, "data_checklist.json")
LOG_FILE  = os.path.join(DB_DIR, "app_log.txt")

# =========================================================
# 2) Helpers
# =========================================================
def get_db():
    """Open a SQLite connection to the configured DB_PATH."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def log_event(message: str):
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(message.rstrip() + "\n")
    except Exception:
        pass

# If you use the checklist UI
CHECKLIST_ITEMS = [
    "Articles of Incorporation / Operating Agreement",
    "Owner Affidavits (each owner)",
    "Ownership structure summary (names, %, roles)",
    "Oklahoma residency proof for applicable owners",
    "Land ownership / Lease for grow site",
    "Site plan (map/diagram)",
    "Certificate of Occupancy for buildings in use",
    "Security plan (cameras, fencing, access, alarms)",
    "Inventory tracking plan (seed→sale)",
    "Waste disposal plan",
    "OMMA grower license (proof or application)",
    "OBNDD registration (proof or in-process)",
    "Photo IDs of owners/managers attending interview"
]

def load_state():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"checked": []}
    return {"checked": []}

def save_state(state: dict):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

# =========================================================
# 3) Routes (minimal, practical set)
# =========================================================

@app.route("/")
def home():
    return jsonify({
        "message": "App running ✅",
        "db_dir": DB_DIR,
        "db_path": DB_PATH,
        "tips": "Use /db_check, /get_records, /download_db"
    })

@app.route("/checklist", methods=["GET", "POST"])
def checklist():
    state = load_state()
    if request.method == "POST":
        checked = request.form.getlist("item")
        state["checked"] = checked
        save_state(state)
        flash("Checklist saved successfully!", "success")
        log_event(f"Checklist updated: {len(checked)} items checked")
        return redirect(url_for("checklist"))
    # Render only if you have templates; otherwise return JSON
    try:
        return render_template("checklist.html", items=CHECKLIST_ITEMS, state=state)
    except Exception:
        return jsonify({"items": CHECKLIST_ITEMS, "state": state})

@app.route("/db_check")
def db_check():
    """Confirm DB is reachable and show a quick row count from 'records' if present."""
    out = {"db_path": DB_PATH}
    try:
        conn = get_db()
        cur = conn.cursor()
        # Check table presence
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        tables = [r[0] for r in cur.fetchall()]
        out["tables"] = tables

        if "records" in tables:
            cur.execute("SELECT COUNT(*) FROM records")
            out["records_count"] = cur.fetchone()[0]
        conn.close()
        return jsonify(out)
    except Exception as e:
        out["error"] = str(e)
        return jsonify(out), 500

@app.route("/get_records")
def get_records():
    """Return all rows from 'records' table as JSON (handy for quick checks)."""
    try:
        conn = get_db()
        cur = conn.cursor()
        # Will raise if table doesn't exist
        cur.execute("SELECT * FROM records")
        rows = [dict(zip([c[0] for c in cur.description], r)) for r in cur.fetchall()]
        conn.close()
        return jsonify(rows)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/download_db")
def download_db():
    """One-time utility to download the live DB file for backup."""
    try:
        return send_file(DB_PATH, as_attachment=True, download_name="harvest.db")
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# =========================================================
# 4) Main entry
# =========================================================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))