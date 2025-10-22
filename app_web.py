
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Evergreen — MERGED
- Robust SQLite path detection
- Multilingual UI (EN/ES/中文/VI)
- Dashboard (future-only toggle)
- Records: Add / Edit / Delete
- Workers: Add / List
- Tasks: Add / Edit / Delete, assign to workers
- Daily Monitor log
- Clone demand: quick + analytics + CSV (current/future weeks only)
- Nutrient Advisor (OpenAI optional; local heuristic fallback)
- DB Check
"""

import os, sqlite3
from datetime import datetime, timedelta, date
from pathlib import Path
from flask import Flask, render_template_string, request, redirect, url_for, jsonify, make_response

# Optional OpenAI (Advisor)
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except Exception:
    OPENAI_AVAILABLE = False

# ---------- App ----------
flask_app = Flask(__name__)
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

# ---------- Robust DB path ----------
env_db_path = os.environ.get("DB_PATH")
env_db_dir  = os.environ.get("DB_DIR")
render_data_dir = Path("/opt/render/project/src/data")
local_side_by_side = BASE_DIR / "harvest.db"
default_dir = BASE_DIR / "data"
default_path = default_dir / "harvest.db"

if env_db_path:
    DB_PATH = Path(env_db_path); DB_DIR = DB_PATH.parent
elif env_db_dir and (Path(env_db_dir) / "harvest.db").exists():
    DB_DIR = Path(env_db_dir); DB_PATH = DB_DIR / "harvest.db"
elif render_data_dir.exists() and (render_data_dir / "harvest.db").exists():
    DB_DIR = render_data_dir; DB_PATH = DB_DIR / "harvest.db"
elif local_side_by_side.exists():
    DB_DIR = BASE_DIR; DB_PATH = local_side_by_side
else:
    DB_DIR = default_dir; DB_DIR.mkdir(parents=True, exist_ok=True); DB_PATH = default_path

STATIC_DIR.mkdir(parents=True, exist_ok=True)
print(">>> Using DB at:", DB_PATH)

# ---------- i18n ----------
LANG = {
    "en": {
        "title":"Harvest Dashboard","home":"Home",
        "add":"Add Record","stats":"Analytics","room":"Room","plants":"Plants","strain":"Strain",
        "flower_date":"Flower Date","harvest_date":"Harvest Date","days_remaining":"Days Remaining",
        "plan":"Plan","save":"Save","back":"Back","today":"Today",
        "workers":"Workers","add_worker":"Add Worker","monitor":"Monitor","advisor":"Advisor",
        "tasks":"Tasks","add_task":"Add Task","assignee":"Assignee","due":"Due","status":"Status","title_label":"Title",
        "pending":"Pending","doing":"Doing","done":"Done",
        "clones":"Clones","clone_quick":"Clone Demand — Quick","+20%":"+20%",
        "clone_full":"Clone Demand — Full Analytics","clone_week":"Week Start","clone_harvest":"Harvest Week",
        "clone_view_full":"View Full Analytics","clone_chart_title":"Predictive Clone Demand (9-Week Cycle)",
        "clone_x":"Clone Start Week","clone_y":"Clones Needed","clone_download":"Download Forecast (CSV)",
        "db_check":"DB Check","upload":"Upload","db_upload":"Upload DB",
        "advisor_title":"Nutrient Advisor","advisor_desc":"Get week-by-week nutrient guidance.",
        "program":"Program","athena":"Athena","salts":"Salts","week":"Flower Week","notes":"Notes / Context",
        "submit":"Submit","result":"Result","no_key":"No OpenAI key configured; using local heuristic."
    },
    "es": {"title":"Panel de Cosecha","home":"Inicio","add":"Agregar Registro","stats":"Analítica","room":"Cuarto","plants":"Plantas","strain":"Variedad",
        "flower_date":"Fecha de Floración","harvest_date":"Fecha de Cosecha","days_remaining":"Días Restantes",
        "plan":"Plan","save":"Guardar","back":"Atrás","today":"Hoy",
        "workers":"Trabajadores","add_worker":"Agregar Trabajador","monitor":"Monitoreo","advisor":"Asesor",
        "tasks":"Tareas","add_task":"Agregar Tarea","assignee":"Asignado","due":"Vence","status":"Estado","title_label":"Título",
        "pending":"Pendiente","doing":"En progreso","done":"Hecho",
        "clones":"Clones","clone_quick":"Demanda de Clones — Rápido","+20%":"+20%",
        "clone_full":"Demanda de Clones — Analítica Completa","clone_week":"Inicio de Semana","clone_harvest":"Semana de Cosecha",
        "clone_view_full":"Ver Analítica Completa","clone_chart_title":"Demanda de Clones (Ciclo 9 Semanas)",
        "clone_x":"Semana de inicio de clones","clone_y":"Clones necesarios","clone_download":"Descargar pronóstico (CSV)",
        "db_check":"Revisar BD","upload":"Subir","db_upload":"Subir BD",
        "advisor_title":"Asesor de Nutrientes","advisor_desc":"Guía de nutrientes por semana.",
        "program":"Programa","athena":"Athena","salts":"Sales","week":"Semana de Floración","notes":"Notas / Contexto",
        "submit":"Enviar","result":"Resultado","no_key":"Sin OpenAI Key; heurística local."
    },
    "zh": {"title":"收获仪表板","home":"首页","add":"添加记录","stats":"分析","room":"房间","plants":"株数","strain":"品系",
        "flower_date":"开花日期","harvest_date":"收获日期","days_remaining":"剩余天数",
        "plan":"计划","save":"保存","back":"返回","today":"今天",
        "workers":"员工","add_worker":"添加员工","monitor":"监控","advisor":"营养顾问",
        "tasks":"任务","add_task":"添加任务","assignee":"负责人","due":"到期","status":"状态","title_label":"标题",
        "pending":"待办","doing":"进行中","done":"完成",
        "clones":"克隆","clone_quick":"克隆需求 — 快速","+20%":"+20%",
        "clone_full":"克隆需求 — 全量分析","clone_week":"周开始","clone_harvest":"收获周",
        "clone_view_full":"查看完整分析","clone_chart_title":"克隆需求（9周周期）",
        "clone_x":"克隆开始周","clone_y":"所需克隆数","clone_download":"下载预测 (CSV)",
        "db_check":"数据库检查","upload":"上传","db_upload":"上传数据库",
        "advisor_title":"营养顾问","advisor_desc":"按周提供营养指导。",
        "program":"方案","athena":"Athena","salts":"盐类","week":"开花周数","notes":"备注 / 背景",
        "submit":"提交","result":"结果","no_key":"未配置 OpenAI 密钥；使用本地启发式。"
    },
    "vi": {"title":"Bảng Điều Khiển Thu Hoạch","home":"Trang Chủ","add":"Thêm Bản Ghi","stats":"Phân Tích","room":"Phòng","plants":"Cây","strain":"Giống",
        "flower_date":"Ngày Vào Hoa","harvest_date":"Ngày Thu Hoạch","days_remaining":"Ngày Còn Lại",
        "plan":"Kế hoạch","save":"Lưu","back":"Quay lại","today":"Hôm nay",
        "workers":"Công Nhân","add_worker":"Thêm Công Nhân","monitor":"Theo dõi","advisor":"Cố Vấn Dinh Dưỡng",
        "tasks":"Tác vụ","add_task":"Thêm Tác vụ","assignee":"Người phụ trách","due":"Hạn","status":"Trạng thái","title_label":"Tiêu đề",
        "pending":"Chờ xử lý","doing":"Đang làm","done":"Hoàn thành",
        "clones":"Clone","clone_quick":"Nhu Cầu Clone — Nhanh","+20%":"+20%",
        "clone_full":"Nhu Cầu Clone — Phân Tích","clone_week":"Tuần Bắt Đầu","clone_harvest":"Tuần Thu Hoạch",
        "clone_view_full":"Xem Phân Tích Đầy Đủ","clone_chart_title":"Nhu cầu clone (chu kỳ 9 tuần)",
        "clone_x":"Tuần bắt đầu clone","clone_y":"Số clone cần","clone_download":"Tải dự báo (CSV)",
        "db_check":"Kiểm Tra CSDL","upload":"Tải lên","db_upload":"Tải CSDL",
        "advisor_title":"Cố Vấn Dinh Dưỡng","advisor_desc":"Hướng dẫn dinh dưỡng theo tuần.",
        "program":"Chương trình","athena":"Athena","salts":"Muối","week":"Tuần hoa","notes":"Ghi chú / Ngữ cảnh",
        "submit":"Gửi","result":"Kết quả","no_key":"Chưa có OpenAI key; dùng quy tắc nội bộ."
    }
}

def t(lang, key): return LANG.get(lang, LANG["en"]).get(key, key)

def lang_dropdown(current):
    codes = [("en","EN"),("es","ES"),("zh","中文"),("vi","VI")]
    links = []
    for code,label in codes:
        style = "font-weight:700;" if code==current else ""
        links.append(f"<a style='{style}' href='{url_for('set_lang', code=code)}'>{label}</a>")
    return " | ".join(links)

@flask_app.route("/lang/<code>")
def set_lang(code):
    if code not in LANG: code = "en"
    resp = make_response(redirect(request.referrer or url_for("index")))
    resp.set_cookie("lang", code, max_age=60*60*24*365)
    return resp

# ---------- DB helpers ----------
def get_db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con

def ensure_schema():
    con = get_db()
    try:
        con.execute("""
        CREATE TABLE IF NOT EXISTS records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room TEXT, plants INTEGER, strain TEXT, flower_date TEXT
        )""")
        con.execute("""
        CREATE TABLE IF NOT EXISTS workers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT
        )""")
        con.execute("""
        CREATE TABLE IF NOT EXISTS daily (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT, room TEXT, action TEXT, note TEXT
        )""")
        con.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT, assignee_id INTEGER, due_date TEXT, status TEXT,
            FOREIGN KEY(assignee_id) REFERENCES workers(id)
        )""")
        con.commit()
    finally:
        con.close()

# ---------- Clone demand helpers ----------
NINE_WEEKS = 9

def _table_exists(con, name: str) -> bool:
    cur = con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,))
    return cur.fetchone() is not None

def _parse_date_ymd(s: str):
    try:
        return datetime.strptime(str(s).split()[0], "%Y-%m-%d").date()
    except Exception:
        return None

def get_clone_source_rows():
    con = get_db()
    rows = []
    try:
        if _table_exists(con, "records"):
            for r in con.execute("SELECT flower_date, plants FROM records"):
                try:
                    flower = _parse_date_ymd(r["flower_date"]); pl = int(r["plants"] or 0)
                except Exception:
                    flower = _parse_date_ymd(r[0]); pl = int(r[1] or 0)
                if flower and pl: rows.append((flower, pl))
        elif _table_exists(con, "harvest"):
            for r in con.execute('SELECT "Flower Date", plants FROM harvest'):
                flower = _parse_date_ymd(r[0]); pl = int(r[1] or 0)
                if flower and pl: rows.append((flower, pl))
    finally:
        con.close()
    return rows

def compute_clone_demand_grouped():
    raw = get_clone_source_rows()
    if not raw: return []
    today = date.today()
    buckets = {}
    for flower_date, plants in raw:
        harvest = flower_date + timedelta(weeks=NINE_WEEKS)
        clone_start = harvest - timedelta(weeks=NINE_WEEKS)
        week_start = clone_start - timedelta(days=clone_start.weekday())
        if week_start >= today:
            buckets[week_start] = buckets.get(week_start, 0) + plants
    out = []
    for wk, total in sorted(buckets.items()):
        out.append({
            "week": wk.isoformat(),
            "harvest_week": (wk + timedelta(weeks=NINE_WEEKS)).isoformat(),
            "plants": int(total),
            "p5":  int(round(total*1.05)),
            "p10": int(round(total*1.10)),
            "p15": int(round(total*1.15)),
            "p20": int(round(total*1.20)),
        })
    return out

# ---------- Advisor logic ----------
def local_heuristic_advice(program: str, week: int, notes: str) -> str:
    w = max(1, min(int(week or 1), 10))
    base = {
        "athena":[
            "Transplant support, low EC 1.6–1.8, silica light, no heavy PK.",
            "Ramp EC 1.8–2.1, maintain Ca/Mg, monitor runoff.",
            "EC 2.0–2.2; maintain VPD 1.1–1.3; early defoliate if dense.",
            "Hold EC ~2.2; introduce slight PK bump; watch tip burn.",
            "PK push begins; EC 2.2–2.4; ensure drain 10–20%.",
            "Peak PK; watch K/Ca balance; keep pH 5.7–6.1 (hydro) / 5.9–6.3 (coco).",
            "Begin taper 5–10%; reduce N; maintain K and Mg.",
            "Further taper; prep flush strategy; IPM only if needed.",
            "Flush or low EC; finishers only; reduce humidity to avoid mold.",
            "Harvest window; keep temps lower at night; darkness optional."
        ],
        "salts":[
            "Low EC start 1.6–1.8; Ca/Mg 150–200 ppm; silica minimal.",
            "EC 1.9–2.1; keep N:P:K balanced; record runoff.",
            "EC 2.0–2.2; watch deficiency; increase airflow.",
            "Hold EC ~2.2; slight PK; ensure distribution.",
            "Increase PK; EC 2.2–2.4; avoid overwatering.",
            "Peak PK; ensure sulfur for terps; monitor leaves.",
            "Start taper 5–10%; lower N; keep K steady.",
            "Taper more; watch fade; avoid late N spikes.",
            "Flush/finishers; target runoff EC ~ input.",
            "Harvest; avoid foliar; prep dry room."
        ]
    }
    table = base["athena" if program=="athena" else "salts"]
    tip = table[w-1]
    extra = ""
    if notes:
        n = notes.lower()
        if "burn" in n: extra += "\n• Tip burn: drop EC by 0.2–0.3, increase runoff to ~20%."
        if "pale" in n or "yellow" in n: extra += "\n• Pale leaves: check N & Mg, add 30–50 ppm Mg."
        if "lockout" in n or "high ec" in n: extra += "\n• Lockout: reset low EC feed; verify pH/runoff."
    return f"Program: {program.capitalize()} | Week {w}\n{tip}{extra}"

def run_advisor(program: str, week: int, notes: str) -> str:
    api_key = os.environ.get("OPENAI_API_KEY")
    if OPENAI_AVAILABLE and api_key:
        try:
            client = OpenAI(api_key=api_key)
            prompt = f"Give concise nutrient actions for cannabis flower Week {week} using {program}. Context: {notes}."
            resp = client.responses.create(model="gpt-4o-mini", input=prompt)
            return resp.output_text.strip()
        except Exception as e:
            return f"[OpenAI fallback] {local_heuristic_advice(program, week, notes)}\n\n(Error: {e})"
    else:
        return f"[{t('en','no_key')}] {local_heuristic_advice(program, week, notes)}"

# ---------- Templates (HTML) ----------
NAV_BAR = """
<div class="topnav">
  <a href="{{ url_for('index') }}">{{ t(lang,'home') }}</a>
  <a href="{{ url_for('add_record') }}">{{ t(lang,'add') }}</a>
  <a href="{{ url_for('workers') }}">{{ t(lang,'workers') }}</a>
  <a href="{{ url_for('tasks') }}">{{ t(lang,'tasks') }}</a>
  <a href="{{ url_for('monitor') }}">{{ t(lang,'monitor') }}</a>
  <a href="{{ url_for('advisor') }}">{{ t(lang,'advisor') }}</a>
  <a href="{{ url_for('clones_home') }}">{{ t(lang,'clones') }}</a>
  <a href="{{ url_for('db_check') }}">{{ t(lang,'db_check') }}</a>
  <span style="float:right;">{{ lang_dropdown|safe }}</span>
</div>
"""

INDEX_HTML = """
<html>
<head>
<meta charset="utf-8"><title>{{ t(lang,'title') }}</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
body{font-family:Segoe UI,Arial,sans-serif;background:#0e1116;color:#e8e8e8}
a{color:#8fd48f}
table{border-collapse:collapse;width:100%;max-width:1250px}
th,td{border:1px solid #2a2f3a;padding:6px 8px}
th{background:#1a1f28}
.container{max-width:1250px;margin:0 auto;padding:12px}
</style>
</head>
<body>
<div class="container">
  """ + NAV_BAR + """
  <h2 style="margin:10px 0;">{{ t(lang,'title') }}</h2>
  <div style="opacity:.8;font-size:12px;">
    {{ t(lang,'today') }}: {{ today }}
    {% if future_only %} • future only (<a href='?future=0'>show all</a>)
    {% else %} • show all (<a href='?future=1'>future only</a>)
    {% endif %}
  </div>
  <table>
    <tr>
      <th>{{ t(lang,'room') }}</th><th>{{ t(lang,'plants') }}</th><th>{{ t(lang,'strain') }}</th>
      <th>{{ t(lang,'flower_date') }}</th><th>{{ t(lang,'harvest_date') }}</th><th>{{ t(lang,'days_remaining') }}</th>
      <th>{{ t(lang,'plan') }}</th><th>✏️</th><th>🗑️</th>
    </tr>
    {% for r in rows %}
    <tr>
      <td>{{ r.room }}</td><td>{{ r.plants }}</td><td>{{ r.strain }}</td>
      <td>{{ r.flower_date }}</td><td>{{ r.harvest }}</td><td>{{ r.days }}</td>
      <td><a href="#">{{ t(lang,'plan') }}</a></td>
      <td><a href="{{ url_for('edit_record', rid=r.id) }}">✏️</a></td>
      <td><a href="{{ url_for('delete_record', rid=r.id) }}">🗑️</a></td>
    </tr>
    {% endfor %}
  </table>
</div>
</body>
</html>
"""

ADD_HTML = """
<html><head><meta charset="utf-8"><title>{{ t(lang,'add') }}</title></head>
<body style="font-family:Segoe UI,Arial,sans-serif;background:#0e1116;color:#e8e8e8;">
<div class="container" style="max-width:720px;margin:20px auto;">""" + NAV_BAR + """
<h3>{{ t(lang,'add') }}</h3>
<form method="post">
  <div>{{ t(lang,'room') }} <input name="room" required></div>
  <div>{{ t(lang,'plants') }} <input type="number" name="plants" min="0" required></div>
  <div>{{ t(lang,'strain') }} <input name="strain"></div>
  <div>{{ t(lang,'flower_date') }} <input name="flower_date" placeholder="YYYY-MM-DD" required></div>
  <button type="submit">{{ t(lang,'save') }}</button> <a href="{{ url_for('index') }}">{{ t(lang,'back') }}</a>
</form>
</div></body></html>
"""

EDIT_HTML = """
<html><head><meta charset="utf-8"><title>✏️</title></head>
<body style="font-family:Segoe UI,Arial,sans-serif;background:#0e1116;color:#e8e8e8;">
<div class="container" style="max-width:720px;margin:20px auto;">""" + NAV_BAR + """
<h3>✏️</h3>
<form method="post">
  <div>{{ t(lang,'room') }} <input name="room" value="{{ r['room'] }}" required></div>
  <div>{{ t(lang,'plants') }} <input type="number" name="plants" min="0" value="{{ r['plants'] }}" required></div>
  <div>{{ t(lang,'strain') }} <input name="strain" value="{{ r['strain'] }}"></div>
  <div>{{ t(lang,'flower_date') }} <input name="flower_date" placeholder="YYYY-MM-DD" value="{{ r['flower_date'] }}" required></div>
  <button type="submit">{{ t(lang,'save') }}</button> <a href="{{ url_for('index') }}">{{ t(lang,'back') }}</a>
</form>
</div></body></html>
"""

WORKERS_HTML = """
<html><head><meta charset="utf-8"><title>{{ t(lang,'workers') }}</title></head>
<body style="font-family:Segoe UI,Arial,sans-serif;background:#0e1116;color:#e8e8e8;">
<div class="container" style="max-width:900px;margin:20px auto;">""" + NAV_BAR + """
<h3>{{ t(lang,'workers') }}</h3>
<form method="post" style="display:flex;gap:8px;">
  <input name="name" placeholder="{{ t(lang,'add_worker') }}">
  <button type="submit">+</button>
</form>
<table style="margin-top:10px;">
<tr><th>ID</th><th>{{ t(lang,'workers') }}</th></tr>
{% for r in rows %}<tr><td>{{ r['id'] }}</td><td>{{ r['name'] }}</td></tr>{% endfor %}
</table>
<p><a href="{{ url_for('index') }}">{{ t(lang,'back') }}</a></p>
</div></body></html>
"""

TASKS_HTML = """
<html><head><meta charset="utf-8"><title>{{ t(lang,'tasks') }}</title></head>
<body style="font-family:Segoe UI,Arial,sans-serif;background:#0e1116;color:#e8e8e8;">
<div class="container" style="max-width:1000px;margin:20px auto;">""" + NAV_BAR + """
<h3>{{ t(lang,'tasks') }}</h3>
<form method="post" style="display:grid;grid-template-columns:2fr 1fr 1fr 1fr auto;gap:8px;align-items:center;">
  <input name="title" placeholder="{{ t(lang,'title_label') }}" required>
  <select name="assignee_id">
    <option value="">{{ t(lang,'assignee') }}</option>
    {% for w in workers %}<option value="{{ w['id'] }}">{{ w['name'] }}</option>{% endfor %}
  </select>
  <input name="due_date" placeholder="{{ t(lang,'due') }} (YYYY-MM-DD)">
  <select name="status">
    <option value="pending">{{ t(lang,'pending') }}</option>
    <option value="doing">{{ t(lang,'doing') }}</option>
    <option value="done">{{ t(lang,'done') }}</option>
  </select>
  <button type="submit">{{ t(lang,'add_task') }}</button>
</form>

<table style="margin-top:12px;">
<tr><th>ID</th><th>{{ t(lang,'title_label') }}</th><th>{{ t(lang,'assignee') }}</th><th>{{ t(lang,'due') }}</th><th>{{ t(lang,'status') }}</th><th>✏️</th><th>🗑️</th></tr>
{% for r in rows %}
<tr>
  <td>{{ r['id'] }}</td>
  <td>{{ r['title'] }}</td>
  <td>{{ r['assignee_name'] or '' }}</td>
  <td>{{ r['due_date'] or '' }}</td>
  <td>{{ r['status'] or '' }}</td>
  <td><a href="{{ url_for('edit_task', tid=r['id']) }}">✏️</a></td>
  <td><a href="{{ url_for('delete_task', tid=r['id']) }}">🗑️</a></td>
</tr>
{% endfor %}
</table>
<p><a href="{{ url_for('index') }}">{{ t(lang,'back') }}</a></p>
</div></body></html>
"""

EDIT_TASK_HTML = """
<html><head><meta charset="utf-8"><title>✏️ {{ t(lang,'tasks') }}</title></head>
<body style="font-family:Segoe UI,Arial,sans-serif;background:#0e1116;color:#e8e8e8;">
<div class="container" style="max-width:720px;margin:20px auto;">""" + NAV_BAR + """
<h3>✏️ {{ t(lang,'tasks') }}</h3>
<form method="post" style="display:grid;grid-template-columns:2fr 1fr 1fr 1fr;gap:8px;">
  <input name="title" value="{{ r['title'] }}" required>
  <select name="assignee_id">
    <option value="">{{ t(lang,'assignee') }}</option>
    {% for w in workers %}
      <option value="{{ w['id'] }}" {% if r['assignee_id']==w['id'] %}selected{% endif %}>{{ w['name'] }}</option>
    {% endfor %}
  </select>
  <input name="due_date" value="{{ r['due_date'] or '' }}">
  <select name="status">
    <option value="pending" {% if r['status']=='pending' %}selected{% endif %}>{{ t(lang,'pending') }}</option>
    <option value="doing" {% if r['status']=='doing' %}selected{% endif %}>{{ t(lang,'doing') }}</option>
    <option value="done" {% if r['status']=='done' %}selected{% endif %}>{{ t(lang,'done') }}</option>
  </select>
  <button type="submit">{{ t(lang,'save') }}</button>
</form>
<p><a href="{{ url_for('tasks') }}">{{ t(lang,'back') }}</a></p>
</div></body></html>
"""

CLONES_QUICK_HTML = """
<!doctype html><html><head><meta charset="utf-8"><title>{{ t(lang,'clone_quick') }}</title>
<style>
body{font-family:Segoe UI,Arial,sans-serif;background:#0e1116;color:#e8e8e8;margin:0}
.container{max-width:1250px;margin:0 auto;padding:12px}
a{color:#8fd48f}
table{border-collapse:collapse;width:100%;max-width:1250px;background:#11161f}
th,td{border:1px solid #2a2f3a;padding:6px 8px;text-align:center}
th{background:#1a1f28}
.btn{display:inline-block;padding:6px 10px;background:#294d2b;color:#fff;border-radius:6px}
</style></head><body>
  <div class="container">""" + NAV_BAR + """
    <h2 style="margin:10px 0;">{{ t(lang,'clone_quick') }}</h2>
    <div style="opacity:0.8;font-size:12px;">{{ t(lang,'today') }}: {{ today }}</div>
    <table>
      <tr><th>{{ t(lang,'clone_week') }}</th><th>+20%</th></tr>
      {% for r in rows %}<tr><td>{{ r.week }}</td><td>{{ r.p20 }}</td></tr>{% endfor %}
    </table>
    <p><a class="btn" href="{{ url_for('clones_analytics') }}">{{ t(lang,'clone_view_full') }}</a></p>
    <p><a href="{{ url_for('index') }}">{{ t(lang,'back') }}</a></p>
  </div>
</body></html>
"""

CLONES_ANALYTICS_HTML = """
<!doctype html><html><head><meta charset="utf-8"><title>{{ t(lang,'clone_full') }}</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
body{font-family:Segoe UI,Arial,sans-serif;background:#0e1116;color:#e8e8e8;margin:0}
.container{max-width:1250px;margin:0 auto;padding:12px}
a{color:#8fd48f}
table{border-collapse:collapse;width:100%;max-width:1250px;background:#11161f}
th,td{border:1px solid #2a2f3a;padding:6px 8px;text-align:center}
th{background:#1a1f28}
button{cursor:pointer;background:#294d2b;color:#fff;border:none;padding:8px 12px;border-radius:6px}
canvas{max-width:100%;height:400px}
</style></head><body>
  <div class="container">""" + NAV_BAR + """
    <div style="display:flex;justify-content:space-between;align-items:center;">
      <h2 style="margin:10px 0;">{{ t(lang,'clone_chart_title') }}</h2>
    </div>
    <canvas id="cloneChart"></canvas>
    <script>
      const labels = {{ labels|safe }};
      const datasets = {{ datasets|safe }};
      const ctx = document.getElementById('cloneChart');
      new Chart(ctx, {
        type: 'line',
        data: { labels: labels, datasets: datasets },
        options: {
          responsive:true,
          plugins:{ title:{display:true,text:'{{ t(lang,"clone_chart_title") }}'}, legend:{position:'bottom'} },
          scales:{ x:{title:{display:true,text:'{{ t(lang,"clone_x") }}'}}, y:{title:{display:true,text:'{{ t(lang,"clone_y") }}'}} }
        }
      });
    </script>

    <form action="{{ url_for('clones_download') }}" method="get" style="margin:10px 0;">
      <button type="submit">{{ t(lang,'clone_download') }}</button>
    </form>

    <table>
      <tr>
        <th>{{ t(lang,'clone_week') }}</th><th>{{ t(lang,'clone_harvest') }}</th>
        <th>0%</th><th>+5%</th><th>+10%</th><th>+15%</th><th>+20%</th>
      </tr>
      {% for r in rows %}
        <tr>
          <td>{{ r.week }}</td><td>{{ r.harvest }}</td>
          <td>{{ r.plants }}</td><td>{{ r.p5 }}</td><td>{{ r.p10 }}</td><td>{{ r.p15 }}</td><td>{{ r.p20 }}</td>
        </tr>
      {% endfor %}
    </table>
    <p><a href="{{ url_for('clones_home') }}">{{ t(lang,'back') }}</a> | <a href="{{ url_for('index') }}">{{ t(lang,'title') }}</a></p>
  </div>
</body></html>
"""

ADVISOR_HTML = """
<!doctype html><html><head><meta charset="utf-8"><title>{{ t(lang,'advisor_title') }}</title>
<style>
body{font-family:Segoe UI,Arial,sans-serif;background:#0e1116;color:#e8e8e8;margin:0}
.container{max-width:900px;margin:0 auto;padding:12px}
label{display:block;margin:8px 0 4px 0}
input,select,textarea{width:100%;padding:8px;border:1px solid #2a2f3a;background:#11161f;color:#e8e8e8;border-radius:6px}
button{margin-top:10px;padding:8px 12px;border:0;background:#294d2b;color:#fff;border-radius:6px;cursor:pointer}
a{color:#8fd48f}
</style></head><body>
  <div class="container">""" + NAV_BAR + """
    <h2>{{ t(lang,'advisor_title') }}</h2>
    <p>{{ t(lang,'advisor_desc') }}</p>
    <form method="post">
      <label>{{ t(lang,'program') }}</label>
      <select name="program"><option value="athena">{{ t(lang,'athena') }}</option><option value="salts">{{ t(lang,'salts') }}</option></select>
      <label>{{ t(lang,'week') }}</label><input name="week" type="number" min="1" max="10" value="1"/>
      <label>{{ t(lang,'notes') }}</label><textarea name="notes" rows="5" placeholder="room, EC/PPM, runoff, symptoms..."></textarea>
      <button type="submit">{{ t(lang,'submit') }}</button>
    </form>
    {% if result %}<h3 style="margin-top:16px;">{{ t(lang,'result') }}</h3>
      <pre style="white-space:pre-wrap;background:#0b0f16;border:1px solid #2a2f3a;padding:10px;border-radius:6px;">{{ result }}</pre>{% endif %}
    <p><a href="{{ url_for('index') }}">{{ t(lang,'back') }}</a></p>
  </div>
</body></html>
"""

# ---------- Routes ----------
@flask_app.route('/')
def index():
    ensure_schema()
    lang = request.cookies.get("lang", "en")
    con = get_db(); rows = []
    try:
        for r in con.execute("SELECT id, room, plants, strain, flower_date FROM records ORDER BY id DESC"):
            fd = r[4]
            try: fdate = datetime.strptime(fd.split()[0], "%Y-%m-%d").date()
            except Exception: fdate = None
            harvest = fdate + timedelta(weeks=9) if fdate else None
            days_rem = (harvest - date.today()).days if harvest else ''
            rows.append({"id":r[0],"room":r[1],"plants":r[2],"strain":r[3],"flower_date":fd,
                        "harvest":harvest.isoformat() if harvest else "","days":days_rem})
    finally:
        con.close()
    future_only = request.args.get('future','1')=='1'
    if future_only:
        rows = [r for r in rows if r.get('days','')=='' or (isinstance(r.get('days'),int) and r['days']>=0)]
    return render_template_string(INDEX_HTML, rows=rows, today=date.today().isoformat(), future_only=future_only,
                                  lang=lang, t=t, lang_dropdown=lang_dropdown(lang))

# Records CRUD
@flask_app.route('/add', methods=['GET','POST'])
def add_record():
    ensure_schema()
    lang = request.cookies.get("lang", "en")
    if request.method == 'POST':
        room = request.form.get('room','').strip()
        plants = int(request.form.get('plants','0') or 0)
        strain = request.form.get('strain','').strip()
        flower_date = request.form.get('flower_date','').strip()
        con = get_db()
        try:
            con.execute("INSERT INTO records(room,plants,strain,flower_date) VALUES(?,?,?,?)",(room,plants,strain,flower_date))
            con.commit()
        finally:
            con.close()
        return redirect(url_for('index'))
    return render_template_string(ADD_HTML, lang=lang, t=t, lang_dropdown=lang_dropdown(lang))

@flask_app.route('/edit/<int:rid>', methods=['GET','POST'])
def edit_record(rid):
    ensure_schema()
    lang = request.cookies.get("lang", "en")
    con = get_db(); row = None
    try:
        row = con.execute("SELECT id,room,plants,strain,flower_date FROM records WHERE id=?", (rid,)).fetchone()
    finally:
        con.close()
    if not row: return redirect(url_for('index'))
    if request.method == 'POST':
        room = request.form.get('room','').strip()
        plants = int(request.form.get('plants','0') or 0)
        strain = request.form.get('strain','').strip()
        flower_date = request.form.get('flower_date','').strip()
        con = get_db()
        try:
            con.execute("UPDATE records SET room=?,plants=?,strain=?,flower_date=? WHERE id=?",
                        (room,plants,strain,flower_date,rid))
            con.commit()
        finally:
            con.close()
        return redirect(url_for('index'))
    return render_template_string(EDIT_HTML, r=row, lang=lang, t=t, lang_dropdown=lang_dropdown(lang))

@flask_app.route('/delete/<int:rid>')
def delete_record(rid):
    con = get_db()
    try:
        con.execute("DELETE FROM records WHERE id=?", (rid,)); con.commit()
    finally:
        con.close()
    return redirect(url_for('index'))

# Workers
@flask_app.route('/workers', methods=['GET','POST'])
def workers():
    ensure_schema()
    lang = request.cookies.get("lang", "en")
    con = get_db()
    if request.method == 'POST':
        name = request.form.get('name','').strip()
        if name:
            try:
                con.execute("INSERT INTO workers(name) VALUES(?)", (name,)); con.commit()
            except Exception:
                pass
    rows = con.execute("SELECT id,name FROM workers ORDER BY id DESC").fetchall()
    con.close()
    return render_template_string(WORKERS_HTML, rows=rows, lang=lang, t=t, lang_dropdown=lang_dropdown(lang))

# Tasks CRUD
@flask_app.route('/tasks', methods=['GET','POST'])
def tasks():
    ensure_schema()
    lang = request.cookies.get("lang", "en")
    con = get_db()
    if request.method == 'POST':
        title = request.form.get('title','').strip()
        assignee_id = request.form.get('assignee_id') or None
        due_date = request.form.get('due_date','').strip() or None
        status = request.form.get('status','pending')
        if title:
            con.execute("INSERT INTO tasks(title, assignee_id, due_date, status) VALUES(?,?,?,?)",
                        (title, assignee_id, due_date, status))
            con.commit()
    workers = con.execute("SELECT id,name FROM workers ORDER BY name").fetchall()
    rows = con.execute("""
        SELECT t.id, t.title, t.assignee_id, t.due_date, t.status, w.name as assignee_name
        FROM tasks t LEFT JOIN workers w ON w.id=t.assignee_id
        ORDER BY COALESCE(t.due_date,'9999-12-31'), t.id DESC
    """).fetchall()
    con.close()
    return render_template_string(TASKS_HTML, rows=rows, workers=workers, lang=lang, t=t, lang_dropdown=lang_dropdown(lang))

@flask_app.route('/tasks/edit/<int:tid>', methods=['GET','POST'])
def edit_task(tid):
    ensure_schema()
    lang = request.cookies.get("lang", "en")
    con = get_db()
    row = con.execute("SELECT id,title,assignee_id,due_date,status FROM tasks WHERE id=?", (tid,)).fetchone()
    workers = con.execute("SELECT id,name FROM workers ORDER BY name").fetchall()
    if not row:
        con.close(); return redirect(url_for('tasks'))
    if request.method == 'POST':
        title = request.form.get('title','').strip()
        assignee_id = request.form.get('assignee_id') or None
        due_date = request.form.get('due_date','').strip() or None
        status = request.form.get('status','pending')
        con.execute("UPDATE tasks SET title=?, assignee_id=?, due_date=?, status=? WHERE id=?",
                    (title, assignee_id, due_date, status, tid))
        con.commit(); con.close()
        return redirect(url_for('tasks'))
    con.close()
    return render_template_string(EDIT_TASK_HTML, r=row, workers=workers, lang=lang, t=t, lang_dropdown=lang_dropdown(lang))

@flask_app.route('/tasks/delete/<int:tid>')
def delete_task(tid):
    con = get_db()
    try:
        con.execute("DELETE FROM tasks WHERE id=?", (tid,)); con.commit()
    finally:
        con.close()
    return redirect(url_for('tasks'))

# Monitor
@flask_app.route('/monitor', methods=['GET','POST'])
def monitor():
    ensure_schema()
    lang = request.cookies.get("lang", "en")
    con = get_db()
    if request.method == 'POST':
        dt = request.form.get('date', date.today().isoformat())
        room = request.form.get('room','').strip()
        action = request.form.get('action','').strip()
        note = request.form.get('note','').strip()
        if room and action:
            con.execute("INSERT INTO daily(date,room,action,note) VALUES(?,?,?,?)", (dt,room,action,note))
            con.commit()
    rows = con.execute("SELECT date,room,action,note FROM daily ORDER BY id DESC LIMIT 200").fetchall()
    con.close()
    MONITOR_HTML = """
    <html><head><meta charset="utf-8"><title>{{ t(lang,'monitor') }}</title></head>
    <body style="font-family:Segoe UI,Arial,sans-serif;background:#0e1116;color:#e8e8e8;">
    <div class="container" style="max-width:980px;margin:20px auto;">""" + NAV_BAR + """
    <h3>{{ t(lang,'monitor') }}</h3>
    <form method="post" style="display:flex;gap:8px;flex-wrap:wrap;">
      <input name="date" placeholder="YYYY-MM-DD" value="{{ '%s' % (request.form.get('date') or '') }}">
      <input name="room" placeholder="{{ t(lang,'room') }}">
      <select name="action">
        <option value="water">{{ t(lang,'water') }}</option>
        <option value="nutrient">{{ t(lang,'nutrient') }}</option>
        <option value="ipm">{{ t(lang,'ipm') }}</option>
        <option value="defol">{{ t(lang,'defol') }}</option>
      </select>
      <input name="note" placeholder="Note">
      <button type="submit">+</button>
    </form>
    <table>
      <tr><th>{{ t(lang,'week') }}</th><th>{{ t(lang,'room') }}</th><th>{{ t(lang,'action') }}</th><th>{{ t(lang,'note') }}</th></tr>
      {% for r in rows %}<tr><td>{{ r['date'] }}</td><td>{{ r['room'] }}</td><td>{{ r['action'] }}</td><td>{{ r['note'] }}</td></tr>{% endfor %}
    </table>
    <p><a href="{{ url_for('index') }}">{{ t(lang,'back') }}</a></p>
    </div></body></html>
    """
    return render_template_string(MONITOR_HTML, rows=rows, lang=lang, t=t, lang_dropdown=lang_dropdown(lang))

# Clones routes
@flask_app.route('/clones')
def clones_home():
    ensure_schema()
    lang = request.cookies.get("lang", "en")
    grouped = compute_clone_demand_grouped()
    data = [{"week": g["week"], "p20": g["p20"]} for g in grouped]
    return render_template_string(CLONES_QUICK_HTML, rows=data, today=date.today().isoformat(),
                                  lang=lang, t=t, lang_dropdown=lang_dropdown(lang))

@flask_app.route('/clones/analytics')
def clones_analytics():
    ensure_schema()
    lang = request.cookies.get("lang", "en")
    rows = []
    grouped = compute_clone_demand_grouped()
    for g in grouped:
        rows.append({
            "week": g["week"], "harvest": g["harvest_week"],
            "plants": g["plants"], "p5": g["p5"], "p10": g["p10"], "p15": g["p15"], "p20": g["p20"]
        })
    labels = [r["week"] for r in rows]
    datasets = [
        {"label":"0%","data":[r["plants"] for r in rows],"fill":False},
        {"label":"+5%","data":[r["p5"] for r in rows],"fill":False},
        {"label":"+10%","data":[r["p10"] for r in rows],"fill":False},
        {"label":"+15%","data":[r["p15"] for r in rows],"fill":False},
        {"label":"+20%","data":[r["p20"] for r in rows],"fill":False},
    ]
    return render_template_string(CLONES_ANALYTICS_HTML, rows=rows, labels=labels, datasets=datasets,
                                  lang=lang, t=t, lang_dropdown=lang_dropdown(lang))

@flask_app.route("/clones/download")
def clones_download():
    ensure_schema()
    from io import StringIO
    import csv
    si = StringIO(); writer = csv.writer(si)
    writer.writerow(["week","harvest_week","plants","+5%","+10%","+15%","+20%"])
    for g in compute_clone_demand_grouped():
        writer.writerow([g["week"], g["harvest_week"], g["plants"], g["p5"], g["p10"], g["p15"], g["p20"]])
    output = si.getvalue()
    resp = make_response(output)
    resp.headers["Content-Type"] = "text/csv"
    resp.headers["Content-Disposition"] = "attachment; filename=clone_demand_forecast.csv"
    return resp

# Advisor
@flask_app.route('/advisor', methods=['GET','POST'])
def advisor():
    ensure_schema()
    lang = request.cookies.get("lang", "en")
    result = ""
    if request.method == "POST":
        program = (request.form.get("program") or "athena").lower().strip()
        week = int((request.form.get("week") or "1").strip() or "1")
        notes = request.form.get("notes") or ""
        result = run_advisor(program, week, notes)
    return render_template_string(ADVISOR_HTML, result=result, lang=lang, t=t, lang_dropdown=lang_dropdown(lang))

# DB check
@flask_app.route('/db/check')
def db_check():
    ensure_schema()
    con = get_db()
    try:
        tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        counts = {}
        for tname in tables:
            try:
                counts[tname] = con.execute(f"SELECT COUNT(*) FROM {tname}").fetchone()[0]
            except Exception:
                counts[tname] = None
        return jsonify({"db": str(DB_PATH), "tables": tables, "counts": counts})
    finally:
        con.close()

# ---------- Main ----------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000)); host = os.environ.get("HOST", "0.0.0.0")
    print("DB:", DB_PATH)
    flask_app.run(host=host, port=port, debug=True)
