
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Evergreen Evolution — Render-ready Flask app (updated)
- Single file (app_web.py)
- Uses SQLite with a Render-friendly default DB directory
- OpenAI integration optional (for Nutrient Advisor)
"""

import os, json, sqlite3
from datetime import date, datetime, timedelta
from flask import Flask, render_template_string, request, redirect, url_for, jsonify, make_response, Response

# Optional Pillow for converting non-PNG logos
try:
    from PIL import Image
    PIL_AVAILABLE = True
except Exception:
    PIL_AVAILABLE = False

# Optional OpenAI (used only in /advisor if configured)
try:
    from openai import OpenAI
except Exception:
    OpenAI = None

# ---------- Paths & storage ----------
APP_DIR = os.path.dirname(os.path.abspath(__file__))

# Prefer Render data dir if it exists; else honor DB_DIR env; else fall back to APP_DIR
RENDER_DATA_DIR = "/opt/render/project/src/data"
if os.path.isdir(RENDER_DATA_DIR):
    DB_DIR = RENDER_DATA_DIR
else:
    DB_DIR = os.getenv("DB_DIR", APP_DIR)

os.makedirs(DB_DIR, exist_ok=True)
DB_PATH = os.path.join(DB_DIR, "harvest.db")

# Static folder keeps logo; default to local static/, but prefer DB_DIR/static if DB_DIR provided
STATIC_DIR = os.path.join(DB_DIR, "static") if DB_DIR else os.path.join(APP_DIR, "static")
os.makedirs(STATIC_DIR, exist_ok=True)

# ---------- Helpers ----------
def load_api_key():
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if key:
        return key
    # Optional fallback: file drop next to app
    fp = os.path.join(APP_DIR, "OPENAI_API_KEY.txt")
    if os.path.exists(fp):
        try:
            with open(fp, "r", encoding="utf-8") as f:
                k = f.read().strip()
                if k:
                    return k
        except Exception:
            pass
    return None

def get_openai_client():
    key = load_api_key()
    if not key or OpenAI is None:
        return None
    try:
        return OpenAI(api_key=key)
    except Exception:
        return None

def get_db():
    con = sqlite3.connect(DB_PATH)
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
        worker TEXT,
        FOREIGN KEY(worker) REFERENCES workers(name)
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

def compute_week(flower_date_str):
    try:
        f = datetime.strptime(flower_date_str, "%Y-%m-%d").date()
        delta = (date.today() - f).days
        return max(1, min(9, delta // 7 + 1))
    except Exception:
        return 1

def compute_dates(week):
    today = date.today()
    start = today - timedelta(days=(week - 1) * 7)
    harvest = start + timedelta(weeks=9)
    days = (harvest - today).days
    return start, harvest, days

# ---------- Branding ----------
def _ensure_flask_logo():
    """Copy or convert a local logo to static/evergreen_logo.png if present."""
    src_names = ["Evergreen Logo.png", "evergreen_logo.png", "logo.png"]
    for name in src_names:
        # Check both APP_DIR and DB_DIR for convenience
        for base_dir in (APP_DIR, DB_DIR):
            src = os.path.join(base_dir, name)
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
                            im = Image.open(src); im.save(dst, "PNG"); return
                        except Exception:
                            pass
_ensure_flask_logo()
LOGO_EXISTS = os.path.exists(os.path.join(STATIC_DIR, "evergreen_logo.png"))

BRAND_HTML = """
<div style="display:flex;align-items:center;gap:14px;margin:10px 0 14px 0;">
  {% if logo_exists %}
    <img src="{{ url_for('static_file', filename='evergreen_logo.png') }}" alt="Evergreen Evolution" style="height:64px;">
  {% else %}
    <div style="font-size:44px;line-height:44px;">🌲</div>
  {% endif %}
  <div style="font-family:Segoe UI,Arial,sans-serif;color:#3b5; text-shadow:0 1px 0 #111;">
    <div style="font-size:28px;font-weight:800;letter-spacing:1px;">EVERGREEN EVOLUTION</div>
    <div style="font-size:12px;opacity:0.85;">Grow Ops • Automation • Analytics</div>
  </div>
</div>
"""

# ---------- I18N ----------
LANG = {
    "en": {
        "title": "Harvest Dashboard", "add": "Add Record", "stats": "Analytics", "advisor": "Nutrient Advisor",
        "room": "Room", "plants": "Plants", "strain": "Strain", "flower_date": "Flower Date", "week": "Week",
        "harvest_date": "Harvest Date", "days_remaining": "Days Remaining", "save": "Save", "back": "Back",
        "total": "Total Plants", "graph_title": "Days Remaining by Room", "select_room": "Select Room",
        "tank_size": "Tank Size (gal)", "lights": "Number of Lights", "notes": "Notes",
        "get_advice": "Get Advice", "add_worker": "Add Worker", "monitor":"Worker Monitor"
    },
    "zh": {
        "title": "收获仪表板", "add": "添加记录", "stats": "分析", "advisor": "营养顾问",
        "room": "房间", "plants": "植物数量", "strain": "品种", "flower_date": "开花日期", "week": "周数",
        "harvest_date": "收获日期", "days_remaining": "剩余天数", "save": "保存", "back": "返回",
        "total": "植物总数", "graph_title": "各房间剩余天数", "select_room": "选择房间",
        "tank_size": "营养桶容量(加仑)", "lights": "灯数量", "notes": "备注",
        "get_advice": "获取建议", "add_worker": "添加员工", "monitor":"人员监控"
    }
}
def t(lang, key): return LANG.get(lang, LANG["en"]).get(key, key)

# ---------- Flask app ----------
flask_app = Flask(__name__)

# Serve files from STATIC_DIR no matter where it lives
from flask import send_from_directory
@flask_app.route("/static/<path:filename>")
def static_file(filename):
    return send_from_directory(STATIC_DIR, filename)

@flask_app.route("/health")
def health():
    return jsonify({"status":"ok"})

@flask_app.route("/envtest")
def envtest():
    key = load_api_key()
    if key:
        masked = key[:6] + "…" + key[-4:] if len(key) > 10 else "***"
        return jsonify({"OPENAI_API_KEY_found": True, "sample": masked})
    else:
        return jsonify({"OPENAI_API_KEY_found": False, "hint": "Set env var or create OPENAI_API_KEY.txt next to app"})
    
@flask_app.route("/setlang/<lang>")
def set_lang(lang):
    resp = make_response(redirect(url_for("index")))
    resp.set_cookie("lang", lang)
    return resp

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
    .topnav a { margin-right:10px; }
    .container { max-width:1200px; margin: 0 auto; padding: 10px 14px; }
  </style>
</head>
<body>
  <div class="container">
    {{ brand_html|safe }}
    <div class="topnav">
      <a href="{{ url_for('add_record') }}">{{ t(lang,'add') }}</a>
      <a href="{{ url_for('workers') }}">{{ t(lang,'add_worker') }}</a>
      <a href="{{ url_for('stats') }}">{{ t(lang,'stats') }}</a>
      <a href="{{ url_for('advisor') }}">{{ t(lang,'advisor') }}</a>
      <a href="{{ url_for('monitor') }}">{{ t(lang,'monitor') }}</a>
      <a href="{{ url_for('set_lang', lang='en') }}">🇺🇸 EN</a>
      <a href="{{ url_for('set_lang', lang='zh') }}">🇨🇳 中文</a>
    </div>

    <h2 style="margin:10px 0;">{{ t(lang,'title') }}</h2>
    <table>
      <tr>
        <th>{{ t(lang,'room') }}</th><th>{{ t(lang,'plants') }}</th><th>{{ t(lang,'strain') }}</th>
        <th>{{ t(lang,'flower_date') }}</th><th>{{ t(lang,'week') }}</th>
        <th>{{ t(lang,'harvest_date') }}</th><th>{{ t(lang,'days_remaining') }}</th>
        <th>Worker</th>
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
    resp = make_response(render_template_string(INDEX_HTML,
        rows=rows, workers=workers, assignments=assignments, lang=lang, t=t,
        brand_html=BRAND_HTML, logo_exists=LOGO_EXISTS))
    resp.set_cookie("lang", lang)
    return resp

ADD_HTML = """
<div class="container">
  {{ brand_html|safe }}
  <h2>{{ t(lang,'add') }}</h2>
  {% if error %}<p style='color:#ff6b6b;'>{{ error }}</p>{% endif %}
  <form method='post'>
    {{ t(lang,'room') }}:<input name='room'><br>
    {{ t(lang,'plants') }}:<input name='plants' type='number'><br>
    {{ t(lang,'strain') }}:<input name='strain'><br>
    {{ t(lang,'flower_date') }} (YYYY-MM-DD):<input name='flower_date'><br>
    <button type='submit'>{{ t(lang,'save') }}</button>
  </form>
  <p><a href='{{ url_for("index") }}'>{{ t(lang,"back") }}</a></p>
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
            # compute week based on flower_date; also compute harvest + days remaining
            try:
                f = datetime.strptime(flower_date, "%Y-%m-%d").date()
                week = max(1, min(9, (date.today() - f).days // 7 + 1))
            except Exception:
                week = 1
            start, harvest, days = compute_dates(week)
            con = get_db()
            con.execute("""INSERT INTO records (room,plants,strain,flower_date,week,start_date,harvest_date,days_remaining)
                        VALUES (?,?,?,?,?,?,?,?)""",
                        (room,plants,strain,flower_date,week,start.isoformat(),harvest.isoformat(),days))
            con.commit(); con.close()
            log_action(worker="", action="Add Record", room=room,
                       details=json.dumps({"plants": plants, "strain": strain, "flower_date": flower_date}))
            return redirect(url_for("index"))
        except Exception as e:
            error = f"{type(e).__name__}: {e}"
    return render_template_string(ADD_HTML, error=error, lang=lang, t=t, brand_html=BRAND_HTML, logo_exists=LOGO_EXISTS)

WORKERS_HTML = """
<div class="container">
  {{ brand_html|safe }}
  <h2>{{ t(lang,'add_worker') }}</h2>
  {% if msg %}<p style='color:#8fd48f;'>{{ msg }}</p>{% endif %}
  <form method='post'>
    Name: <input name='name' placeholder='Grower name'>
    <button type='submit'>{{ t(lang,'save') }}</button>
  </form>
  <h3>Current Workers</h3>
  <ul>
    {% for w in rows %}<li>{{ w.name }}</li>{% endfor %}
  </ul>
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
                log_action(worker=name, action="Add Worker", room="", details="{}")
            except Exception as e:
                msg = f"Error: {e}"
        else:
            msg = "Name cannot be empty."
    con = get_db()
    rows = con.execute("SELECT name FROM workers ORDER BY name").fetchall()
    con.close()
    return render_template_string(WORKERS_HTML, rows=rows, msg=msg, lang=lang, t=t, brand_html=BRAND_HTML, logo_exists=LOGO_EXISTS)

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

STATS_HTML = """
<div class="container">
  {{ brand_html|safe }}
  <h2>{{ t(lang,'stats') }}</h2>
  <form method='get' style="margin-bottom:10px;">
    Filter by Worker:
    <select name='filter_worker' onchange='this.form.submit()'>
      <option value=''>-- all --</option>
      {% for w in workers %}
        <option value='{{ w }}' {% if filter_worker==w %}selected{% endif %}>{{ w }}</option>
      {% endfor %}
    </select>
    <noscript><button type='submit'>Apply</button></noscript>
  </form>

  <p>{{ t(lang,'total') }}: {{ total }}</p>
  <canvas id='chart' width='400' height='200'></canvas>
  <script src='https://cdn.jsdelivr.net/npm/chart.js'></script>
  <script>
  const ctx = document.getElementById('chart');
  new Chart(ctx,{type:'bar',data:{labels:{{ labels|tojson }},
    datasets:[{label:'{{ t(lang,"graph_title") }}',data:{{ data|tojson }} }]} });
  </script>

  <h3>Room → Worker</h3>
  <table border=1 cellpadding=6>
    <tr><th>Room</th><th>Assigned Worker</th></tr>
    {% for r in labels %}
      <tr><td>{{ r }}</td><td>{{ assignments.get(r,'') }}</td></tr>
    {% endfor %}
  </table>

  <p style="margin-top:10px;"><a href='{{ url_for("export_assignments") }}'>Export Assignments (CSV)</a></p>
  <p><a href='{{ url_for("index") }}'>{{ t(lang,"back") }}</a></p>
</div>
"""

@flask_app.route("/stats")
def stats():
    ensure_schema()
    lang = request.cookies.get("lang", "en")
    con = get_db()
    workers = [w["name"] for w in con.execute("SELECT name FROM workers ORDER BY name").fetchall()]
    assignments = {rw["room"]: rw["worker"] for rw in con.execute("SELECT room, worker FROM room_workers").fetchall()}
    filter_worker = request.args.get("filter_worker", "").strip()
    if filter_worker:
        rows = con.execute(
            "SELECT room, days_remaining FROM records WHERE room IN (SELECT room FROM room_workers WHERE worker=?) ORDER BY room",
            (filter_worker,)
        ).fetchall()
    else:
        rows = con.execute("SELECT room, days_remaining FROM records ORDER BY room").fetchall()
    total = con.execute("SELECT SUM(plants) AS total FROM records").fetchone()["total"] or 0
    con.close()
    labels = [r["room"] for r in rows]
    data = [r["days_remaining"] for r in rows]
    return render_template_string(STATS_HTML,
        labels=labels, data=data, total=total,
        workers=workers, assignments=assignments,
        filter_worker=filter_worker, lang=lang, t=t, brand_html=BRAND_HTML, logo_exists=LOGO_EXISTS)

@flask_app.route("/export_assignments")
def export_assignments():
    ensure_schema()
    con = get_db()
    assignments = {rw["room"]: rw["worker"] for rw in con.execute("SELECT room, worker FROM room_workers").fetchall()}
    rows = con.execute("""
        SELECT r1.room, r1.plants, r1.strain, r1.days_remaining
        FROM records r1
        JOIN (SELECT room, MAX(id) AS max_id FROM records GROUP BY room) latest
              ON latest.room = r1.room AND latest.max_id = r1.id
        ORDER BY r1.room
    """).fetchall()
    con.close()
    from io import StringIO
    import csv
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["room", "worker", "plants", "strain", "days_remaining"])
    for r in rows:
        writer.writerow([r["room"], assignments.get(r["room"], ""), r["plants"], r["strain"], r["days_remaining"]])
    csv_data = output.getvalue()
    return Response(csv_data, mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=room_worker_assignments.csv"})

ADVISOR_HTML = """
<div class="container">
  {{ brand_html|safe }}
  <h2>{{ t(lang,'advisor') }}</h2>

  <form method='get' style="margin-bottom:10px;">
    Filter by Worker:
    <select name='filter_worker' onchange='this.form.submit()'>
      <option value=''>-- all --</option>
      {% for w in workers %}
        <option value='{{ w }}' {% if filter_worker==w %}selected{% endif %}>{{ w }}</option>
      {% endfor %}
    </select>
    <noscript><button type='submit'>Apply</button></noscript>
  </form>

  <form method='post'>
    {{ t(lang,'select_room') }}:
    <select name='room_id'>
      {% for r in rows %}
        <option value='{{ r.id }}'>{{ r.room }} - {{ r.strain }} (wk {{ (r.days_remaining//7) if (r.days_remaining//7)>0 else 1 }})</option>
      {% endfor %}
    </select><br>

    Nutrient Brand:
    <select name='brand'>
      <option value='Athena' {% if brand=='Athena' %}selected{% endif %}>Athena</option>
      <option value='RAW NPK Sauce' {% if brand=='RAW NPK Sauce' %}selected{% endif %}>RAW NPK Sauce</option>
    </select><br>

    {{ t(lang,'tank_size') }}:<input name='tank'><br>
    {{ t(lang,'lights') }}:<input name='lights'><br>
    {{ t(lang,'notes') }}:<input name='notes'><br>
    <button type='submit'>{{ t(lang,'get_advice') }}</button>
  </form>

  {% if selected_worker_display %}
    <p><b>Assigned Grower:</b> {{ selected_worker_display }}</p>
  {% endif %}

  {% if advice %}
    <h3>AI Advice ({{ brand }}){% if filter_worker %} for {{ filter_worker }}{% endif %}:</h3>
    <pre>{{ advice }}</pre>
  {% endif %}

  <p><a href='{{ url_for("index") }}'>{{ t(lang,"back") }}</a></p>
</div>
"""

@flask_app.route("/advisor", methods=["GET", "POST"])
def advisor():
    ensure_schema()
    lang = request.cookies.get("lang", "en")
    con = get_db()
    workers = [w["name"] for w in con.execute("SELECT name FROM workers ORDER BY name").fetchall()]
    assignments = {rw["room"]: rw["worker"] for rw in con.execute("SELECT room, worker FROM room_workers").fetchall()}
    filter_worker = request.values.get("filter_worker", "").strip()
    if filter_worker:
        rows = con.execute(
            "SELECT id,room,plants,strain,days_remaining FROM records WHERE room IN (SELECT room FROM room_workers WHERE worker=?) ORDER BY room",
            (filter_worker,)
        ).fetchall()
    else:
        rows = con.execute("SELECT id,room,plants,strain,days_remaining FROM records ORDER BY room").fetchall()
    con.close()

    advice = None
    brand = request.form.get("brand", "Athena")
    selected_worker_display = ""

    if request.method == "POST":
        rid = request.form.get("room_id")
        tank = request.form.get("tank")
        lights = request.form.get("lights")
        notes = request.form.get("notes")
        brand = request.form.get("brand", "Athena")
        row = next((r for r in rows if str(r["id"]) == rid), None)
        if row:
            assigned_worker = assignments.get(row["room"], "")
            selected_worker_display = assigned_worker or ""
            nutrient_prompt = {
                "Athena": "Athena Bloom A and B nutrient system",
                "RAW NPK Sauce": "RAW NPK or salt-based formulation (e.g., CaNO3, KNO3, KH2PO4, MgSO4)"
            }.get(brand, "Athena Bloom A and B nutrient system")
            week_guess = max(1, min(9, row['days_remaining'] // 7))
            prompt = f"""
You are a cannabis cultivation expert using the {nutrient_prompt}.
The room is overseen by grower '{assigned_worker or "Unassigned"}'.
Recommend nutrient mixing instructions (use ml/gal for liquids or g/gal for salts), target EC and PPM,
for strain '{row['strain']}' in week {week_guess} of flower.
Room {row['room']} has {row['plants']} plants, {lights or 'unknown'} lights, and a {tank or 'unknown'} gal nutrient tank.
Return a concise step list and include both English and Simplified Chinese.
"""
            log_action(
                worker=assigned_worker,
                action="Run Advisor",
                room=row["room"],
                details=json.dumps({"brand": brand, "tank": tank, "lights": lights}, ensure_ascii=False)
            )
            client = get_openai_client()
            if client:
                try:
                    resp = client.chat.completions.create(
                        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                        messages=[{"role": "user", "content": prompt.strip()}],
                        temperature=0.3
                    )
                    advice = resp.choices[0].message.content
                except Exception as e:
                    advice = f"(AI error) {e}"
            else:
                advice = "(OpenAI not configured — set env var OPENAI_API_KEY or create OPENAI_API_KEY.txt next to app.)"

    return render_template_string(ADVISOR_HTML,
        rows=rows, workers=workers,
        advice=advice, brand=brand, filter_worker=filter_worker,
        selected_worker_display=selected_worker_display, lang=lang, t=t, brand_html=BRAND_HTML, logo_exists=LOGO_EXISTS)

MONITOR_HTML = """
<div class="container">
  {{ brand_html|safe }}
  <h2>Worker Action Monitor</h2>

  <form method="get" style="margin-bottom:10px;">
    Worker:
    <select name="worker" onchange="this.form.submit()">
      <option value="">-- all --</option>
      {% for w in worker_opts %}
        <option value="{{ w }}" {% if w==request.args.get('worker','') %}selected{% endif %}>{{ w }}</option>
      {% endfor %}
    </select>

    Action:
    <select name="action" onchange="this.form.submit()">
      <option value="">-- all --</option>
      {% for a in action_opts %}
        <option value="{{ a }}" {% if a==request.args.get('action','') %}selected{% endif %}>{{ a }}</option>
      {% endfor %}
    </select>
    <noscript><button type="submit">Apply</button></noscript>
  </form>

  <form method="post" onsubmit="return confirm('Clear all logs?');">
    <input type="hidden" name="clear" value="1">
    <button type="submit">Clear Logs</button>
  </form>

  <table border="1" cellpadding="6" style="margin-top:10px; width:100%; max-width:1200px;">
    <tr><th>Timestamp (UTC)</th><th>Worker</th><th>Action</th><th>Room</th><th>Details</th></tr>
    {% for r in rows %}
      <tr>
        <td>{{ r.ts }}</td>
        <td>{{ r.worker }}</td>
        <td>{{ r.action }}</td>
        <td>{{ r.room }}</td>
        <td><pre style="white-space:pre-wrap; margin:0;">{{ r.details }}</pre></td>
      </tr>
    {% endfor %}
  </table>

  <p><a href='{{ url_for("index") }}'>{{ t(request.cookies.get("lang","en"),"back") }}</a></p>
</div>
"""

@flask_app.route("/monitor", methods=["GET", "POST"])
def monitor():
    ensure_schema()
    if request.method == "POST" and request.form.get("clear") == "1":
        con = get_db()
        con.execute("DELETE FROM worker_actions")
        con.commit(); con.close()
        return redirect(url_for("monitor"))

    f_worker = request.args.get("worker", "").strip()
    f_action = request.args.get("action", "").strip()
    con = get_db()
    worker_opts = [r["worker"] for r in con.execute("SELECT DISTINCT worker FROM worker_actions ORDER BY worker").fetchall() if r["worker"]]
    action_opts = [r["action"] for r in con.execute("SELECT DISTINCT action FROM worker_actions ORDER BY action").fetchall() if r["action"]]

    base_q = "SELECT ts, worker, action, room, details FROM worker_actions"
    where = []
    params = []
    if f_worker:
        where.append("worker = ?"); params.append(f_worker)
    if f_action:
        where.append("action = ?"); params.append(f_action)
    if where:
        base_q += " WHERE " + " AND ".join(where)
    base_q += " ORDER BY id DESC LIMIT 500"
    rows = con.execute(base_q, params).fetchall()
    con.close()

    return render_template_string(MONITOR_HTML,
        rows=rows, worker_opts=worker_opts, action_opts=action_opts, t=t, brand_html=BRAND_HTML, logo_exists=LOGO_EXISTS)

@flask_app.route("/diag")
def diag():
    ensure_schema()
    con = get_db()
    cols = [dict(cid=r["cid"], name=r["name"], type=r["type"]) for r in con.execute("PRAGMA table_info(records)")]
    count = con.execute("SELECT COUNT(*) AS c FROM records").fetchone()["c"]
    con.close()
    return jsonify({"records_columns": cols, "records_count": count})

def create_app():
    ensure_schema()
    _ensure_flask_logo()
    return flask_app

# === TEMPORARY BACKUP DOWNLOAD ROUTE ===
from flask import send_from_directory
@flask_app.route("/download_db", methods=["GET"])
def download_db():
    db_path = os.path.join(DB_DIR, "harvest.db")
    if not os.path.exists(db_path):
        return "Database not found.", 404
    # Add simple password protection for safety
    key = request.args.get("key", "")
    expected = os.getenv("DOWNLOAD_KEY", "evergreen123")
    if key != expected:
        return "Unauthorized. Append ?key=evergreen123 to your URL.", 403
    return send_from_directory(DB_DIR, "harvest.db", as_attachment=True)
# === END TEMPORARY ROUTE ===

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    # Bind to all interfaces; Render uses PORT env var
    flask_app.run(host="0.0.0.0", port=port)
