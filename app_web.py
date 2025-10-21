#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Evergreen Evolution — Flask app (Render-ready)
- SQLite DB at /opt/render/project/src/data/harvest.db (Render) or DB_DIR env
- Dashboard with worker assignment
- Add / Edit / Delete records
- Secure upload & download of DB for maintenance
"""

import os, json, sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path
from flask import (
    Flask, render_template_string, request, redirect, url_for,
    jsonify, make_response, Response, send_from_directory
)

# ---------- Optional dependencies ----------
try:
    from PIL import Image
    PIL_AVAILABLE = True
except Exception:
    PIL_AVAILABLE = False

try:
    from openai import OpenAI  # optional; used only if you wire Advisor later
except Exception:
    OpenAI = None

# ---------- Paths & storage ----------
APP_DIR = os.path.dirname(os.path.abspath(__file__))
RENDER_DATA_DIR = "/opt/render/project/src/data"
DB_DIR = RENDER_DATA_DIR if os.path.isdir(RENDER_DATA_DIR) else os.getenv("DB_DIR", APP_DIR)
Path(DB_DIR).mkdir(parents=True, exist_ok=True)
DB_PATH = os.path.join(DB_DIR, "harvest.db")

STATIC_DIR = os.path.join(DB_DIR, "static")
Path(STATIC_DIR).mkdir(parents=True, exist_ok=True)

# ---------- Helpers ----------
def get_db():
    con = sqlite3.connect(DB_PATH, check_same_thread=False)
    con.row_factory = sqlite3.Row
    return con

def ensure_schema():
    con = get_db()
    con.execute("""CREATE TABLE IF NOT EXISTS records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        room TEXT,
        plants INTEGER,
        strain TEXT,
        flower_date TEXT,
        week INTEGER,
        start_date TEXT,
        harvest_date TEXT,
        days_remaining INTEGER
    )""")
    con.execute("""CREATE TABLE IF NOT EXISTS workers (
        name TEXT PRIMARY KEY
    )""")
    con.execute("""CREATE TABLE IF NOT EXISTS room_workers (
        room TEXT PRIMARY KEY,
        worker TEXT
    )""")
    con.execute("""CREATE TABLE IF NOT EXISTS worker_actions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT DEFAULT (datetime('now')),
        worker TEXT,
        action TEXT,
        room TEXT,
        details TEXT
    )""")
    con.commit(); con.close()

def log_action(worker: str, action: str, room: str = "", details: str = ""):
    try:
        con = get_db()
        con.execute(
            "INSERT INTO worker_actions(worker, action, room, details) VALUES (?,?,?,?)",
            (worker or "", action or "", room or "", details or "")
        )
        con.commit(); con.close()
    except Exception:
        pass

def compute_week_from_date(flower_date_str):
    try:
        f = datetime.strptime(flower_date_str, "%Y-%m-%d").date()
        delta = (date.today() - f).days
        return max(1, min(9, (delta // 7) + 1))
    except Exception:
        return 1

def compute_dates_from_week(week: int):
    today = date.today()
    start = today - timedelta(days=(max(1, week) - 1) * 7)
    harvest = start + timedelta(weeks=9)
    days = (harvest - today).days
    return start, harvest, days

# ---------- Branding ----------
def _ensure_logo():
    """Copy/convert a logo to static/evergreen_logo.png if found nearby."""
    src_names = ["Evergreen Logo.png", "evergreen_logo.png", "logo.png"]
    for base in (APP_DIR, DB_DIR):
        for name in src_names:
            src = os.path.join(base, name)
            if os.path.exists(src):
                dst = os.path.join(STATIC_DIR, "evergreen_logo.png")
                if src.lower().endswith(".png"):
                    if not os.path.exists(dst):
                        try:
                            import shutil; shutil.copyfile(src, dst)
                        except Exception:
                            pass
                    return
                else:
                    if PIL_AVAILABLE:
                        try:
                            img = Image.open(src)
                            img.save(dst, "PNG")
                            return
                        except Exception:
                            pass

# ---------- I18N (minimal) ----------
LANG = {
    "en": {
        "title": "Harvest Dashboard", "add": "Add Record", "stats": "Analytics",
        "room": "Room", "plants": "Plants", "strain": "Strain", "flower_date": "Flower Date",
        "week": "Week", "harvest_date": "Harvest Date", "days_remaining": "Days Remaining",
        "save": "Save", "back": "Back", "add_worker": "Add Worker", "monitor": "Worker Monitor"
    },
    "zh": {
        "title": "收获仪表板", "add": "添加记录", "stats": "分析",
        "room": "房间", "plants": "植物数量", "strain": "品种", "flower_date": "开花日期",
        "week": "周数", "harvest_date": "收获日期", "days_remaining": "剩余天数",
        "save": "保存", "back": "返回", "add_worker": "添加员工", "monitor": "人员监控"
    }
}
def t(lang, key): return LANG.get(lang, LANG["en"]).get(key, key)

# ---------- Flask app ----------
flask_app = Flask(__name__)
flask_app.secret_key = os.getenv("SECRET_KEY", "fallback-secret-key")

# Serve static files from STATIC_DIR
@flask_app.route("/static/<path:filename>")
def static_file(filename):
    return send_from_directory(STATIC_DIR, filename)

# ---------- Simple health & DB diagnostics ----------
@flask_app.route("/health")
def health():
    return jsonify({"status": "ok"})

@flask_app.route("/db_check")
def db_check():
    ensure_schema()
    con = get_db()
    out = {"db_path": DB_PATH}
    cur = con.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
    out["tables"] = [r[0] for r in cur.fetchall()]
    if "records" in out["tables"]:
        cur.execute("SELECT COUNT(*) FROM records")
        out["records_count"] = cur.fetchone()[0]
    con.close()
    return jsonify(out)

# ---------- Home (list) ----------
INDEX_HTML = """
<html>
<head>
  <meta charset="utf-8">
  <title>{{ t(lang,'title') }}</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    body { font-family: Segoe UI, Arial, sans-serif; background:#0e1116; color:#e8e8e8; }
    a { color:#8fd48f }
    table { border-collapse: collapse; width:100%; max-width:1200px; }
    th, td { border:1px solid #2a2f3a; padding:6px 8px; }
    th { background:#1a1f28; }
    .container { max-width:1200px; margin: 0 auto; padding: 12px; }
    .topnav a { margin-right:12px; }
    button { cursor:pointer; }
  </style>
</head>
<body>
  <div class="container">
    <div style="display:flex;align-items:center;gap:14px;margin:10px 0 14px 0;">
      <div style="font-size:44px;line-height:44px;">🌲</div>
      <div style="font-family:Segoe UI,Arial,sans-serif;color:#3b5;">
        <div style="font-size:28px;font-weight:800;letter-spacing:1px;">EVERGREEN EVOLUTION</div>
        <div style="font-size:12px;opacity:0.85;">Grow Ops • Automation • Analytics</div>
      </div>
    </div>

    <div class="topnav">
      <a href="{{ url_for('add_record') }}">{{ t(lang,'add') }}</a>
      <a href="{{ url_for('workers') }}">{{ t(lang,'add_worker') }}</a>
      <a href="{{ url_for('monitor') }}">{{ t(lang,'monitor') }}</a>
      <a href="{{ url_for('db_check') }}">DB Check</a>
    </div>

    <h2 style="margin:10px 0;">{{ t(lang,'title') }}</h2>
    <table>
      <tr>
        <th>{{ t(lang,'room') }}</th><th>{{ t(lang,'plants') }}</th><th>{{ t(lang,'strain') }}</th>
        <th>{{ t(lang,'flower_date') }}</th><th>{{ t(lang,'week') }}</th>
        <th>{{ t(lang,'harvest_date') }}</th><th>{{ t(lang,'days_remaining') }}</th>
        <th>Worker</th><th>Edit</th><th>Delete</th>
      </tr>
      {% for r in rows %}
        <tr>
          <td>{{ r.room }}</td><td>{{ r.plants }}</td><td>{{ r.strain }}</td><td>{{ r.flower_date }}</td>
          <td>{{ r.week }}</td><td>{{ r.harvest_date }}</td><td>{{ r.days_remaining }}</td>
          <td>
            <form method="post" action="{{ url_for('assign_worker') }}">
              <input type="hidden" name="room" value="{{ r.room }}">
              <select name="worker">
                <option value="">-- unassigned --</option>
                {% for w in workers %}
                  <option value="{{ w }}" {% if assignments.get(r.room)==w %}selected{% endif %}>{{ w }}</option>
                {% endfor %}
              </select>
              <button type="submit">{{ t(lang,'save') }}</button>
            </form>
          </td>
          <td><a href="{{ url_for('edit_record', rid=r.id) }}">Edit</a></td>
          <td>
            <form method="post" action="{{ url_for('delete_record', rid=r.id) }}" onsubmit="return confirm('Delete this record?');">
              <button type="submit" style="background:#802;color:#fff;">X</button>
            </form>
          </td>
        </tr>
      {% endfor %}
    </table>
  </div>
</body>
</html>
"""

@flask_app.route("/")
def index():
    ensure_schema()
    con = get_db()
    rows = con.execute("SELECT * FROM records ORDER BY id DESC").fetchall()
    assignments = {rw["room"]: rw["worker"] for rw in con.execute("SELECT room, worker FROM room_workers").fetchall()}
    workers = [w["name"] for w in con.execute("SELECT name FROM workers ORDER BY name").fetchall()]
    con.close()
    lang = request.cookies.get("lang", "en")
    resp = make_response(render_template_string(
        INDEX_HTML, rows=rows, workers=workers, assignments=assignments,
        lang=lang, t=t
    ))
    resp.set_cookie("lang", lang)
    return resp

# ---------- Add ----------
ADD_HTML = """
<div class="container">
  <h2>{{ t(lang,'add') }}</h2>
  {% if error %}<p style='color:#ff6b6b;'>{{ error }}</p>{% endif %}
  <form method='post'>
    {{ t(lang,'room') }}:<input name='room'><br>
    {{ t(lang,'plants') }}:<input name='plants' type='number'><br>
    {{ t(lang,'strain') }}:<input name='strain'><br>
    {{ t(lang,'flower_date') }} (YYYY-MM-DD):<input name='flower_date'><br>
    <button type='submit'>{{ t(lang,'save') }}</button>
    <a href='{{ url_for("index") }}' style="margin-left:8px;">{{ t(lang,"back") }}</a>
  </form>
</div>
"""

@flask_app.route("/add", methods=["GET", "POST"])
def add_record():
    ensure_schema()
    lang = request.cookies.get("lang", "en")
    error = None
    if request.method == "POST":
        try:
            room = request.form["room"].strip()
            plants = int(request.form["plants"])
            strain = request.form["strain"].strip()
            flower_date = request.form["flower_date"].strip()
            week = compute_week_from_date(flower_date)
            start, harvest, days = compute_dates_from_week(week)
            con = get_db()
            con.execute("""INSERT INTO records
                        (room, plants, strain, flower_date, week, start_date, harvest_date, days_remaining)
                        VALUES (?,?,?,?,?,?,?,?)""",
                        (room, plants, strain, flower_date, week,
                         start.isoformat(), harvest.isoformat(), days))
            con.commit(); con.close()
            return redirect(url_for("index"))
        except Exception as e:
            error = f"{type(e).__name__}: {e}"
    return render_template_string(ADD_HTML, error=error, lang=lang, t=t)

# ---------- Edit ----------
EDIT_HTML = """
<div class="container">
  <h2>Edit Record #{{ rec.id }}</h2>
  {% if msg %}<p style='color:#8fd48f;'>{{ msg }}</p>{% endif %}
  {% if error %}<p style='color:#ff6b6b;'>{{ error }}</p>{% endif %}
  <form method="post">
    Room: <input name="room" value="{{ rec.room }}"><br>
    Plants: <input name="plants" type="number" value="{{ rec.plants }}"><br>
    Strain: <input name="strain" value="{{ rec.strain }}"><br>
    Flower Date (YYYY-MM-DD): <input name="flower_date" value="{{ rec.flower_date }}"><br>
    <button type="submit">Save</button>
    <a href="{{ url_for('index') }}" style="margin-left:8px;">{{ t(lang,'back') }}</a>
  </form>
</div>
"""

@flask_app.route("/edit/<int:rid>", methods=["GET", "POST"])
def edit_record(rid):
    ensure_schema()
    lang = request.cookies.get("lang", "en")
    con = get_db()
    rec = con.execute("SELECT * FROM records WHERE id = ?", (rid,)).fetchone()
    if not rec:
        con.close()
        return jsonify({"error": f"Record {rid} not found"}), 404

    msg = error = None
    if request.method == "POST":
        try:
            room = request.form.get("room", rec["room"]).strip()
            plants = int(request.form.get("plants", rec["plants"]) or rec["plants"])
            strain = request.form.get("strain", rec["strain"]).strip()
            flower_date = request.form.get("flower_date", rec["flower_date"]).strip()
            week = compute_week_from_date(flower_date)
            start, harvest, days = compute_dates_from_week(week)
            con.execute("""
                UPDATE records
                   SET room=?, plants=?, strain=?, flower_date=?, week=?,
                       start_date=?, harvest_date=?, days_remaining=?
                 WHERE id=?
            """, (room, plants, strain, flower_date, week,
                  start.isoformat(), harvest.isoformat(), days, rid))
            con.commit()
            msg = "Record updated."
            rec = con.execute("SELECT * FROM records WHERE id = ?", (rid,)).fetchone()
        except Exception as e:
            error = f"{type(e).__name__}: {e}"
    con.close()
    return render_template_string(EDIT_HTML, rec=rec, msg=msg, error=error, lang=lang, t=t)

# ---------- Delete ----------
@flask_app.route("/delete/<int:rid>", methods=["POST"])
def delete_record(rid):
    ensure_schema()
    con = get_db()
    con.execute("DELETE FROM records WHERE id = ?", (rid,))
    con.commit(); con.close()
    return redirect(url_for("index"))

# ---------- Workers & Assign ----------
WORKERS_HTML = """
<div class="container">
  <h2>{{ t(lang,'add_worker') }}</h2>
  {% if msg %}<p style='color:#8fd48f;'>{{ msg }}</p>{% endif %}
  <form method='post'>
    Name: <input name='name' placeholder='Grower name'>
    <button type='submit'>{{ t(lang,'save') }}</button>
  </form>
  <h3>Current Workers</h3>
  <ul>{% for w in rows %}<li>{{ w.name }}</li>{% endfor %}</ul>
  <p><a href='{{ url_for("index") }}'>{{ t(lang,"back") }}</a></p>
</div>
"""

@flask_app.route("/workers", methods=["GET", "POST"])
def workers():
    ensure_schema()
    lang = request.cookies.get("lang", "en")
    msg = None
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if name:
            try:
                con = get_db()
                con.execute("INSERT OR IGNORE INTO workers(name) VALUES (?)", (name,))
                con.commit(); con.close()
                msg = f"Added worker: {name}"
            except Exception as e:
                msg = f"Error: {e}"
        else:
            msg = "Name cannot be empty."
    con = get_db()
    rows = con.execute("SELECT name FROM workers ORDER BY name").fetchall()
    con.close()
    return render_template_string(WORKERS_HTML, rows=rows, msg=msg, lang=lang, t=t)

@flask_app.route("/assign_worker", methods=["POST"])
def assign_worker():
    ensure_schema()
    room = request.form.get("room", "").strip()
    worker = request.form.get("worker", "").strip()
    if not room:
        return redirect(url_for("index"))
    con = get_db()
    if worker:
        con.execute("INSERT OR REPLACE INTO room_workers(room, worker) VALUES (?,?)", (room, worker))
        log_action(worker=worker, action="Assign Worker", room=room, details="{}")
    else:
        con.execute("DELETE FROM room_workers WHERE room = ?", (room,))
        log_action(worker="", action="Unassign Worker", room=room, details="{}")
    con.commit(); con.close()
    return redirect(url_for("index"))

# ---------- Monitor ----------
MONITOR_HTML = """
<div class="container">
  <h2>Worker Action Monitor</h2>
  <form method="post" onsubmit="return confirm('Clear all logs?');">
    <input type="hidden" name="clear" value="1">
    <button type="submit">Clear Logs</button>
  </form>
  <table border="1" cellpadding="6" style="margin-top:10px; width:100%; max-width:1200px;">
    <tr><th>Timestamp (UTC)</th><th>Worker</th><th>Action</th><th>Room</th><th>Details</th></tr>
    {% for r in rows %}
      <tr>
        <td>{{ r.ts }}</td><td>{{ r.worker }}</td><td>{{ r.action }}</td><td>{{ r.room }}</td>
        <td><pre style="white-space:pre-wrap; margin:0;">{{ r.details }}</pre></td>
      </tr>
    {% endfor %}
  </table>
  <p><a href='{{ url_for("index") }}'>{{ t("en","back") }}</a></p>
</div>
"""

@flask_app.route("/monitor", methods=["GET", "POST"])
def monitor():
    ensure_schema()
    if request.method == "POST" and request.form.get("clear") == "1":
        con = get_db(); con.execute("DELETE FROM worker_actions"); con.commit(); con.close()
        return redirect(url_for("monitor"))
    con = get_db()
    rows = con.execute("SELECT ts, worker, action, room, details FROM worker_actions ORDER BY id DESC LIMIT 500").fetchall()
    con.close()
    return render_template_string(MONITOR_HTML, rows=rows, t=t)

# ---------- Maintenance: secure upload & download ----------
@flask_app.route("/upload_db", methods=["GET", "POST"])
def upload_db():
    key = request.args.get("key", "")
    expected = os.getenv("UPLOAD_KEY", "evergreen123")
    if key != expected:
        return "Unauthorized. Append ?key=evergreen123 or set UPLOAD_KEY env.", 403

    if request.method == "GET":
        return """
        <form method="post" enctype="multipart/form-data">
          <input type="file" name="file" />
          <button type="submit">Upload</button>
        </form>
        """, 200

    file = request.files.get("file")
    if not file:
        return "No file provided.", 400
    Path(DB_DIR).mkdir(parents=True, exist_ok=True)
    save_path = os.path.join(DB_DIR, "harvest.db")
    file.save(save_path)
    return f"Uploaded to {save_path}", 200

@flask_app.route("/download_db", methods=["GET"])
def download_db():
    key = request.args.get("key", "")
    expected = os.getenv("DOWNLOAD_KEY", "evergreen123")
    if key != expected:
        return "Unauthorized. Append ?key=evergreen123 or set DOWNLOAD_KEY env.", 403
    if not os.path.exists(DB_PATH):
        return "Database not found.", 404
    return send_from_directory(DB_DIR, "harvest.db", as_attachment=True)

# ---------- App factory ----------
def create_app():
    ensure_schema()
    _ensure_logo()
    return flask_app

# ---------- Local run ----------
if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    flask_app.run(host="0.0.0.0", port=port)
