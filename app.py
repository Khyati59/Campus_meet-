import csv, io, os, secrets, sqlite3
from datetime import datetime
from functools import wraps
from flask import (Flask, g, render_template, request, redirect, url_for,
                   session, flash, send_file, Response, abort)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import qrcode

BASE = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-change-me")
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024        # 5 MB uploads
UPLOADS = os.path.join(BASE, "static", "uploads")
ALLOWED = {"png", "jpg", "jpeg", "webp"}
ADMIN_CODE = os.environ.get("ADMIN_CODE", "VESIT-ADMIN")           # needed to create an admin account
DB = os.path.join(BASE, "vesit.db")

def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db

@app.teardown_appcontext
def close_db(_):
    d = g.pop("db", None)
    if d: d.close()

def q(sql, args=(), one=False):
    rows = db().execute(sql, args).fetchall()
    return (rows[0] if rows else None) if one else rows

def run(sql, args=()):
    cur = db().execute(sql, args); db().commit(); return cur.lastrowid

@app.template_filter("fmt")
def fmt(v):
    try: return datetime.strptime(v, "%Y-%m-%dT%H:%M").strftime("%d %b %Y, %I:%M %p")
    except Exception: return v

@app.template_filter("day")
def day(v): return fmt(v)[:2]
@app.template_filter("mon")
def mon(v): return fmt(v)[3:6]

def login_required(role):
    def deco(f):
        @wraps(f)
        def w(*a, **kw):
            if session.get("role") != role:
                session["next"] = request.path
                flash(f"Please log in as {role} to continue.", "error")
                return redirect(url_for("login", role=role))
            return f(*a, **kw)
        return w
    return deco

def save_banner(file):
    if not file or not file.filename: return None
    ext = secure_filename(file.filename).rsplit(".", 1)[-1].lower()
    if ext not in ALLOWED: return None
    name = secrets.token_hex(8) + "." + ext
    file.save(os.path.join(UPLOADS, name))
    return name

# ---------- Public / auth ----------
@app.route("/")
def index():
    upcoming = q("""SELECT e.*, c.name category FROM events e LEFT JOIN categories c ON c.id=e.category_id
                    ORDER BY start_time LIMIT 3""")
    stats = (q("SELECT COUNT(*) n FROM events", one=True)["n"],
             q("SELECT COUNT(*) n FROM users WHERE role='student'", one=True)["n"],
             q("SELECT COUNT(*) n FROM certificates WHERE status='approved'", one=True)["n"])
    return render_template("index.html", upcoming=upcoming, stats=stats)

@app.route("/signup/<role>", methods=["GET", "POST"])
def signup(role):
    if role not in ("admin", "student"): abort(404)
    if request.method == "POST":
        f = request.form
        if role == "admin" and f.get("code") != ADMIN_CODE:
            flash("Invalid admin access code.", "error")
        elif q("SELECT 1 FROM users WHERE email=?", (f["email"].lower(),), one=True):
            flash("That email is already registered. Log in instead.", "error")
        else:
            run("""INSERT INTO users(name,email,password_hash,role,department_id,roll_no,year)
                   VALUES(?,?,?,?,?,?,?)""",
                (f["name"], f["email"].lower(), generate_password_hash(f["password"]), role,
                 f.get("department_id") or None, f.get("roll_no") or None, f.get("year") or None))
            flash("Account created. Please log in.", "ok")
            return redirect(url_for("login", role=role))
    return render_template("auth.html", role=role, mode="signup", admin_code=ADMIN_CODE,
                           departments=q("SELECT * FROM departments"))

@app.route("/login/<role>", methods=["GET", "POST"])
def login(role):
    if role not in ("admin", "student"): abort(404)
    if request.method == "POST":
        u = q("SELECT * FROM users WHERE email=? AND role=?", (request.form["email"].lower(), role), one=True)
        if u and check_password_hash(u["password_hash"], request.form["password"]):
            session.update(user_id=u["id"], name=u["name"], role=role)
            return redirect(session.pop("next", None) or url_for(role))
        flash("Wrong email or password.", "error")
    return render_template("auth.html", role=role, mode="login")

@app.route("/logout")
def logout():
    session.clear(); return redirect(url_for("index"))

# ---------- Admin ----------
@app.route("/admin")
@login_required("admin")
def admin():
    uid = session["user_id"]
    events = q("""SELECT e.*, c.name category,
        (SELECT COUNT(*) FROM registrations WHERE event_id=e.id) reg,
        (SELECT COUNT(*) FROM attendance a JOIN registrations r ON r.id=a.registration_id WHERE r.event_id=e.id) att
        FROM events e LEFT JOIN categories c ON c.id=e.category_id
        WHERE e.created_by=? ORDER BY e.start_time""", (uid,))
    pending = q("""SELECT COUNT(*) n FROM certificates ce JOIN attendance a ON a.id=ce.attendance_id
        JOIN registrations r ON r.id=a.registration_id JOIN events e ON e.id=r.event_id
        WHERE ce.status='pending' AND e.created_by=?""", (uid,), one=True)["n"]
    return render_template("admin.html", events=events, pending=pending,
        total_reg=sum(e["reg"] for e in events), total_att=sum(e["att"] for e in events))

@app.route("/admin/event/new", methods=["GET", "POST"])
@login_required("admin")
def new_event():
    if request.method == "POST":
        f = request.form
        run("""INSERT INTO events(title,description,category_id,venue,start_time,capacity,banner,qr_token,created_by)
               VALUES(?,?,?,?,?,?,?,?,?)""",
            (f["title"], f["description"], f["category_id"], f["venue"], f["start_time"],
             f.get("capacity") or 100, save_banner(request.files.get("banner")),
             secrets.token_hex(4).upper(), session["user_id"]))
        flash("Event published. Display its QR code at the venue.", "ok")
        return redirect(url_for("admin"))
    return render_template("event_form.html", categories=q("SELECT * FROM categories"))

def own_event(eid):
    return q("""SELECT e.*, c.name category FROM events e LEFT JOIN categories c ON c.id=e.category_id
                WHERE e.id=? AND e.created_by=?""", (eid, session["user_id"]), one=True) or abort(404)

@app.route("/admin/event/<int:eid>")
@login_required("admin")
def admin_event(eid):
    e = own_event(eid)
    regs = q("""SELECT r.id rid, u.name, u.email, u.roll_no, a.marked_at, ce.id cid, ce.status
        FROM registrations r JOIN users u ON u.id=r.user_id
        LEFT JOIN attendance a ON a.registration_id=r.id
        LEFT JOIN certificates ce ON ce.attendance_id=a.id
        WHERE r.event_id=? ORDER BY a.marked_at IS NULL, a.marked_at""", (eid,))
    return render_template("admin_event.html", e=e, regs=regs,
        present=sum(1 for r in regs if r["marked_at"]),
        pending=sum(1 for r in regs if r["status"] == "pending"))

@app.route("/admin/event/<int:eid>/delete", methods=["POST"])
@login_required("admin")
def delete_event(eid):
    own_event(eid); run("DELETE FROM events WHERE id=?", (eid,))
    flash("Event deleted.", "ok"); return redirect(url_for("admin"))

@app.route("/admin/event/<int:eid>/qr.png")
@login_required("admin")
def qr_png(eid):
    e = own_event(eid)
    return qr_response(url_for("attend", token=e["qr_token"], _external=True))

def qr_response(url):
    buf = io.BytesIO(); qrcode.make(url, box_size=10, border=2).save(buf, format="PNG"); buf.seek(0)
    return send_file(buf, mimetype="image/png")

@app.route("/admin/event/<int:eid>/export.csv")
@login_required("admin")
def export(eid):
    own_event(eid)
    rows = q("""SELECT u.name, u.email, u.roll_no, a.marked_at, ce.status FROM registrations r
        JOIN users u ON u.id=r.user_id LEFT JOIN attendance a ON a.registration_id=r.id
        LEFT JOIN certificates ce ON ce.attendance_id=a.id WHERE r.event_id=?""", (eid,))
    out = io.StringIO(); w = csv.writer(out)
    w.writerow(["Name", "Email", "Roll no", "Attendance", "Marked at", "Certificate"])
    for r in rows:
        w.writerow([r["name"], r["email"], r["roll_no"] or "", "Present" if r["marked_at"] else "Absent",
                    r["marked_at"] or "", r["status"] or ""])
    return Response(out.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment; filename=attendance_{eid}.csv"})

@app.route("/admin/event/<int:eid>/approve", methods=["POST"])
@login_required("admin")
def approve(eid):
    own_event(eid)
    cid = request.form.get("cid")                    # one certificate, or all pending if empty
    sql = """UPDATE certificates SET status='approved', approved_by=?, approved_at=CURRENT_TIMESTAMP
             WHERE status='pending' AND attendance_id IN (SELECT a.id FROM attendance a
             JOIN registrations r ON r.id=a.registration_id WHERE r.event_id=?)"""
    args = [session["user_id"], eid]
    if cid: sql += " AND id=?"; args.append(cid)
    run(sql, args)
    flash("Certificate(s) approved.", "ok")
    return redirect(url_for("admin_event", eid=eid))

# ---------- Student ----------
@app.route("/student")
@login_required("student")
def student():
    uid, cat = session["user_id"], request.args.get("cat")
    sql = """SELECT e.*, c.name category,
        (SELECT COUNT(*) FROM registrations WHERE event_id=e.id) taken,
        r.id rid, a.marked_at, ce.id ceid, ce.status cstatus
        FROM events e LEFT JOIN categories c ON c.id=e.category_id
        LEFT JOIN registrations r ON r.event_id=e.id AND r.user_id=?
        LEFT JOIN attendance a ON a.registration_id=r.id
        LEFT JOIN certificates ce ON ce.attendance_id=a.id"""
    args = [uid]
    if cat: sql += " WHERE c.name=?"; args.append(cat)
    events = q(sql + " ORDER BY e.start_time", args)
    mine = q("""SELECT COUNT(r.id) reg, COUNT(a.id) att, COUNT(CASE WHEN ce.status='approved' THEN 1 END) certs
        FROM registrations r LEFT JOIN attendance a ON a.registration_id=r.id
        LEFT JOIN certificates ce ON ce.attendance_id=a.id WHERE r.user_id=?""", (uid,), one=True)
    return render_template("student.html", events=events, mine=mine, cat=cat,
                           categories=q("SELECT * FROM categories"))

@app.route("/register/<int:eid>", methods=["POST"])
@login_required("student")
def register(eid):
    e = q("SELECT * FROM events WHERE id=?", (eid,), one=True) or abort(404)
    taken = q("SELECT COUNT(*) n FROM registrations WHERE event_id=?", (eid,), one=True)["n"]
    if taken >= e["capacity"]: flash("Sorry, this event is full.", "error")
    else:
        run("INSERT OR IGNORE INTO registrations(event_id,user_id) VALUES(?,?)", (eid, session["user_id"]))
        flash(f"You are registered for {e['title']}.", "ok")
    return redirect(url_for("student"))

@app.route("/attend", methods=["POST"])
@login_required("student")
def attend_code():
    return redirect(url_for("attend", token=request.form["code"].strip().upper()))

@app.route("/attend/<token>")
@login_required("student")
def attend(token):
    e = q("SELECT * FROM events WHERE qr_token=?", (token,), one=True)
    status, msg = "error", "This code does not match any event."
    if e:
        r = q("SELECT id FROM registrations WHERE event_id=? AND user_id=?", (e["id"], session["user_id"]), one=True)
        if not r:
            msg = "You have not registered for this event. Register first, then scan again."
        elif q("SELECT 1 FROM attendance WHERE registration_id=?", (r["id"],), one=True):
            status, msg = "ok", "Your attendance was already marked."
        else:
            aid = run("INSERT INTO attendance(registration_id) VALUES(?)", (r["id"],))
            run("INSERT INTO certificates(attendance_id,verify_code) VALUES(?,?)",
                (aid, "VES-" + secrets.token_hex(5).upper()))
            status, msg = "ok", "Attendance marked. Your certificate will be available once the organizer approves it."
    return render_template("attend.html", e=e, status=status, msg=msg)

CERT_SQL = """SELECT ce.*, e.title, e.venue, e.start_time, u.name student, u.roll_no, d.name dept,
      org.name organizer FROM certificates ce JOIN attendance a ON a.id=ce.attendance_id
      JOIN registrations r ON r.id=a.registration_id JOIN events e ON e.id=r.event_id
      JOIN users u ON u.id=r.user_id LEFT JOIN departments d ON d.id=u.department_id
      JOIN users org ON org.id=e.created_by WHERE ce.status='approved' AND """

@app.route("/certificate/<int:cid>")
@login_required("student")
def certificate(cid):
    c = q(CERT_SQL + "ce.id=? AND r.user_id=?", (cid, session["user_id"]), one=True)
    if not c:
        flash("This certificate is not available yet. It needs admin approval.", "error")
        return redirect(url_for("student"))
    return render_template("certificate.html", c=c)

@app.route("/verify/<code>")
def verify(code):
    return render_template("verify.html", c=q(CERT_SQL + "ce.verify_code=?", (code,), one=True), code=code)

@app.route("/verify/<code>/qr.png")
def verify_qr(code):
    return qr_response(url_for("verify", code=code, _external=True))

with app.app_context():
    db().executescript(open(os.path.join(BASE, "schema.sql")).read())

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=os.environ.get("FLASK_DEBUG") == "1")
