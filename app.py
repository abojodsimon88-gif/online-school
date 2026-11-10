import hmac
import os
import random
import secrets
from datetime import datetime, timedelta, timezone
from functools import wraps
from html import escape
from urllib.parse import urlparse

import pymysql
from pymysql.cursors import DictCursor
from flask import Flask, request, redirect, url_for, session, abort, g
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import generate_password_hash, check_password_hash

# ----------------------------------------------------------------------
# الإعدادات
# ----------------------------------------------------------------------
app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

ON_RENDER = bool(os.environ.get("RENDER"))

_secret = os.environ.get("SECRET_KEY")
if not _secret:
    if ON_RENDER:
        raise RuntimeError("يجب ضبط متغير البيئة SECRET_KEY على Render.")
    _secret = secrets.token_hex(32)
app.secret_key = _secret

app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=ON_RENDER,
    PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
    MAX_CONTENT_LENGTH=64 * 1024,
)

_missing = [n for n in ("DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD") if not os.environ.get(n)]
if _missing:
    raise RuntimeError("متغيرات البيئة التالية ناقصة: " + ", ".join(_missing))

DB_CONFIG = dict(
    host=os.environ["DB_HOST"],
    user=os.environ["DB_USER"],
    password=os.environ["DB_PASSWORD"],
    database=os.environ["DB_NAME"],
    port=int(os.environ.get("DB_PORT", "3306")),
    charset="utf8mb4",
    cursorclass=DictCursor,
    connect_timeout=10,
    autocommit=False,
)

MAX_LOGIN_ATTEMPTS = 5       # لكل (عنوان + اسم مستخدم)
MAX_IP_ATTEMPTS = 40         # لكل عنوان (المدرسة قد تشارك عنواناً واحداً)
MAX_CLASS_ATTEMPTS = 10      # لكل (عنوان + صف)
WINDOW_MINUTES = 15
MIN_PASSWORD_LEN = 8
MAX_PASSWORD_LEN = 128
CODE_LENGTH = 6
CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
PW_ALPHABET = CODE_ALPHABET + "abcdefghjkmnpqrstuvwxyz"
LOCKED = "!"  # حساب لم يُفعَّل بعد
ADMIN_KEY = "khader"
BLOCK_MSG = "محاولات كثيرة خاطئة. انتظر 15 دقيقة ثم حاول مرة أخرى."

CLASSES = [
    ("first", "الصف الأول"),
    ("second", "الصف الثاني"),
    ("third", "الصف الثالث"),
    ("fourth_a", "الصف الرابع أ"),
    ("fourth_b", "الصف الرابع ب"),
    ("fifth_a", "الصف الخامس أ"),
    ("fifth_b", "الصف الخامس ب"),
    ("sixth_a", "الصف السادس أ"),
    ("sixth_b", "الصف السادس ب"),
    ("seventh_a", "الصف السابع أ"),
    ("seventh_b", "الصف السابع ب"),
    ("eighth_a", "الصف الثامن أ"),
    ("eighth_b", "الصف الثامن ب"),
    ("ninth", "الصف التاسع"),
    ("tenth_a", "الصف العاشر أ"),
    ("tenth_b", "الصف العاشر ب"),
    ("eleventh", "الصف الـ 11"),
    ("twelfth", "الصف الـ 12"),
]

# (مفتاح الحساب، الاسم، الوصف الظاهر، نوع الصلاحية)
DEFAULT_USERS = [
    ("khader", "خضر", "المدير (Admin)", "admin"),
    ("bretta", "بريتا", "السكرتيرة (Secretary)", "secretary"),
    ("fouad", "فؤاد", "المرشد الاجتماعي (Counselor)", "counselor"),
    ("nizar", "نزار", "معلم", "teacher"),
    ("mike", "مايك", "معلم", "teacher"),
    ("ahmad", "أحمد", "معلم", "teacher"),
    ("saba", "سابا", "معلم", "teacher"),
    ("anders", "أندرس", "معلم", "teacher"),
    ("waleed", "وليد", "معلم", "teacher"),
    ("leila", "ليلى", "معلمة", "teacher"),
    ("lana", "لانا", "معلمة", "teacher"),
    ("nicole", "نيكول", "معلمة", "teacher"),
    ("eva", "إيفا", "معلمة", "teacher"),
    ("lord", "لورد", "معلمة", "teacher"),
    ("noha", "نهى", "معلمة", "teacher"),
    ("manal", "منال", "معلمة", "teacher"),
    ("kheylaa", "خيلاء", "معلمة", "teacher"),
    ("doaa", "دعاء", "معلمة", "teacher"),
    ("celeste", "سيليستي", "معلمة", "teacher"),
    ("noor", "نور", "معلمة", "teacher"),
    ("razan", "رزان", "معلمة", "teacher"),
    ("dalia", "داليا", "معلمة", "teacher"),
    ("haidy", "هايدي", "معلمة", "teacher"),
    ("nancy", "نانسي", "معلمة", "teacher"),
    ("mary", "ميري", "معلمة", "teacher"),
    ("rita", "ريتا", "معلمة", "teacher"),
    ("ibtisam", "ابتسام", "معلمة", "teacher"),
]


# ----------------------------------------------------------------------
# قاعدة البيانات
# ----------------------------------------------------------------------
def run(sql, params=(), fetch=None):
    """تنفيذ استعلام واحد. fetch: 'one' أو 'all' أو None (يرجع عدد الصفوف)."""
    conn = pymysql.connect(**DB_CONFIG)
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            if fetch == "one":
                result = cur.fetchone()
            elif fetch == "all":
                result = cur.fetchall()
            else:
                result = cur.rowcount
        conn.commit()
        return result
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def run_many(sql, rows):
    conn = pymysql.connect(**DB_CONFIG)
    try:
        with conn.cursor() as cur:
            cur.executemany(sql, rows)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def replace_teacher_classes(user_key, class_ids):
    """يستبدل صفوف المعلم دفعة واحدة (حذف + إضافة في عملية واحدة)."""
    conn = pymysql.connect(**DB_CONFIG)
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM teacher_classes WHERE user_key = %s", (user_key,))
            if class_ids:
                cur.executemany(
                    "INSERT INTO teacher_classes (user_key, class_id) VALUES (%s, %s)",
                    [(user_key, cid) for cid in class_ids],
                )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def new_code():
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))


def new_temp_password():
    return "".join(secrets.choice(PW_ALPHABET) for _ in range(10))


def ensure_column(table, column, ddl):
    """يضيف عموداً إلى جدول موجود إذا لم يكن موجوداً (للترقية بدون حذف بيانات)."""
    row = run("SHOW COLUMNS FROM " + table + " LIKE %s", (column,), fetch="one")
    if row is None:
        run("ALTER TABLE " + table + " ADD COLUMN " + column + " " + ddl)


def init_db():
    """ينشئ الجداول إن لم تكن موجودة، ويضيف البيانات الأولية مرة واحدة فقط."""
    tail = "ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"
    run(
        "CREATE TABLE IF NOT EXISTS users ("
        "user_key VARCHAR(50) NOT NULL PRIMARY KEY,"
        "name VARCHAR(100) NOT NULL,"
        "role_label VARCHAR(100) NOT NULL,"
        "role_type VARCHAR(20) NOT NULL,"
        "password_hash VARCHAR(255) NOT NULL,"
        "must_change TINYINT(1) NOT NULL DEFAULT 1"
        ") " + tail
    )
    run(
        "CREATE TABLE IF NOT EXISTS classes ("
        "class_id VARCHAR(50) NOT NULL PRIMARY KEY,"
        "name VARCHAR(100) NOT NULL,"
        "access_code VARCHAR(20) NOT NULL,"
        "sort_order INT NOT NULL DEFAULT 0,"
        "live_link VARCHAR(500) NOT NULL DEFAULT '',"
        "live_note VARCHAR(100) NOT NULL DEFAULT ''"
        ") " + tail
    )
    run(
        "CREATE TABLE IF NOT EXISTS teacher_classes ("
        "user_key VARCHAR(50) NOT NULL,"
        "class_id VARCHAR(50) NOT NULL,"
        "PRIMARY KEY (user_key, class_id)"
        ") " + tail
    )
    run(
        "CREATE TABLE IF NOT EXISTS login_attempts ("
        "id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,"
        "scope VARCHAR(150) NOT NULL,"
        "ts DATETIME NOT NULL,"
        "INDEX idx_scope_ts (scope, ts)"
        ") " + tail
    )

    # ترقية قاعدة موجودة من النسخة السابقة
    ensure_column("classes", "live_link", "VARCHAR(500) NOT NULL DEFAULT ''")
    ensure_column("classes", "live_note", "VARCHAR(100) NOT NULL DEFAULT ''")

    # الصفوف: رمز عشوائي لكل صف
    existing = run("SELECT COUNT(*) AS c FROM classes", fetch="one")["c"]
    if existing < len(CLASSES):
        run_many(
            "INSERT IGNORE INTO classes (class_id, name, access_code, sort_order) "
            "VALUES (%s, %s, %s, %s)",
            [(cid, name, new_code(), i) for i, (cid, name) in enumerate(CLASSES)],
        )

    # المستخدمون: فقط المدير يحصل على كلمة مرور مؤقتة، والباقي ينتظر التفعيل
    if run("SELECT COUNT(*) AS c FROM users", fetch="one")["c"] == 0:
        env_pw = os.environ.get("ADMIN_INITIAL_PASSWORD")
        admin_pw = env_pw or new_temp_password()
        rows = []
        for key, name, label, rtype in DEFAULT_USERS:
            pw_hash = generate_password_hash(admin_pw) if key == ADMIN_KEY else LOCKED
            rows.append((key, name, label, rtype, pw_hash))
        run_many(
            "INSERT IGNORE INTO users "
            "(user_key, name, role_label, role_type, password_hash, must_change) "
            "VALUES (%s, %s, %s, %s, %s, 1)",
            rows,
        )
        if not env_pw:
            print("=== كلمة مرور المدير المؤقتة (khader): " + admin_pw + " ===", flush=True)


# ----------------------------------------------------------------------
# كلمات المرور وتحديد المحاولات
# ----------------------------------------------------------------------
DUMMY_HASH = generate_password_hash(secrets.token_hex(8))


def verify_password(stored, password):
    if not stored or stored.startswith(LOCKED):
        return False
    try:
        return check_password_hash(stored, password)
    except ValueError:
        return False


def client_ip():
    return (request.remote_addr or "unknown")[:45]


def scope_for(kind, ident):
    return kind + ":" + client_ip() + ":" + ident[:50]


def is_blocked(scope, limit):
    since = utcnow() - timedelta(minutes=WINDOW_MINUTES)
    row = run(
        "SELECT COUNT(*) AS c FROM login_attempts WHERE scope = %s AND ts > %s",
        (scope, since),
        fetch="one",
    )
    return row["c"] >= limit


def record_failure(scope):
    run("INSERT INTO login_attempts (scope, ts) VALUES (%s, %s)", (scope, utcnow()))
    if random.random() < 0.02:
        run("DELETE FROM login_attempts WHERE ts < %s", (utcnow() - timedelta(days=1),))


def clear_failures(scope):
    run("DELETE FROM login_attempts WHERE scope = %s", (scope,))


# ----------------------------------------------------------------------
# CSRF والجلسات والأمان
# ----------------------------------------------------------------------
def csrf_token():
    if "csrf" not in session:
        session["csrf"] = secrets.token_hex(16)
    return session["csrf"]


def csrf_field():
    return '<input type="hidden" name="csrf" value="' + escape(csrf_token(), quote=True) + '">'


@app.before_request
def csrf_protect():
    if request.method == "POST":
        sent = (request.form.get("csrf") or "").encode()
        expected = (session.get("csrf") or "").encode()
        if not expected or not hmac.compare_digest(sent, expected):
            abort(400)


def current_user():
    if not hasattr(g, "user"):
        g.user = None
        key = session.get("user_key")
        if key:
            g.user = run(
                "SELECT user_key, name, role_label, role_type, must_change "
                "FROM users WHERE user_key = %s",
                (key,),
                fetch="one",
            )
            if g.user is None:
                session.pop("user_key", None)
    return g.user


@app.before_request
def force_password_change():
    user = current_user()
    if user and user["must_change"]:
        if request.endpoint not in ("change_password", "logout", "static"):
            return redirect(url_for("change_password"))


@app.after_request
def security_headers(resp):
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "same-origin"
    resp.headers["Cache-Control"] = "no-store"
    resp.headers["Content-Security-Policy"] = (
        "default-src 'self'; style-src 'self' 'unsafe-inline'; "
        "frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
    )
    if ON_RENDER:
        resp.headers["Strict-Transport-Security"] = "max-age=31536000"
    return resp


def staff_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not current_user():
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapper


def admin_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        user = current_user()
        if not user:
            return redirect(url_for("login"))
        if user["role_type"] != "admin":
            abort(403)
        return view(*args, **kwargs)
    return wrapper


def can_manage_class(user, class_id):
    """المدير يدير كل الصفوف، والمعلم يدير الصفوف المعيّنة له فقط."""
    if user["role_type"] == "admin":
        return True
    if user["role_type"] != "teacher":
        return False
    row = run(
        "SELECT 1 AS ok FROM teacher_classes WHERE user_key = %s AND class_id = %s",
        (user["user_key"], class_id),
        fetch="one",
    )
    return row is not None


def clean_link(raw):
    """يقبل روابط https الكاملة فقط."""
    link = (raw or "").strip()
    if not link or len(link) > 500:
        return None
    if any(ch.isspace() or ord(ch) < 32 for ch in link):
        return None
    parts = urlparse(link)
    if parts.scheme != "https" or not parts.netloc or "@" in parts.netloc:
        return None
    return link


# رسائل قصيرة تظهر مرة واحدة بعد التحويل
def flash_msg(text, ok=True):
    session["flash"] = ["ok" if ok else "error", text]


def pop_flash():
    data = session.pop("flash", None)
    if not data:
        return ""
    css = "message ok" if data[0] == "ok" else "message error"
    return '<p class="' + css + '">' + escape(data[1]) + "</p>"


# ----------------------------------------------------------------------
# القالب
# ----------------------------------------------------------------------
PAGE_CSS = """
body { font-family: Arial, sans-serif; background:#f4f6f9; margin:0; padding:20px; }
.container { max-width:1000px; margin:30px auto; }
.panel { background:white; padding:25px; border:1px solid #ddd; border-radius:10px;
         box-shadow:0 3px 12px rgba(0,0,0,.06); }
.narrow { max-width:420px; margin:40px auto; }
input, select { box-sizing:border-box; width:100%; padding:11px; margin:8px 0 16px;
                border:1px solid #ccc; border-radius:6px; }
input[type=checkbox] { width:auto; margin:0 0 0 10px; transform:scale(1.3); }
.check { display:block; padding:8px 0; border-bottom:1px solid #eee; }
button, .button { display:inline-block; border:0; border-radius:6px; padding:11px 16px;
                  background:#007bff; color:white; text-decoration:none; cursor:pointer;
                  font-size:15px; }
.danger { background:#dc3545; } .success { background:#28a745; }
.warning { background:#ffc107; color:#222; }
.grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(190px,1fr)); gap:14px; }
.class-card { background:white; border:1px solid #ddd; border-radius:8px; padding:18px; text-align:center; }
.actions { display:flex; gap:10px; flex-wrap:wrap; align-items:center; }
.message { padding:10px; border-radius:6px; background:#eef5ff; margin:12px 0; }
.error { background:#fdecea; color:#b00020; }
.ok { background:#e8f5e9; color:#1b5e20; }
.hint { color:#666; font-size:14px; }
.badge { display:inline-block; background:#e8f5e9; color:#1b5e20; border-radius:12px;
         padding:2px 10px; font-size:13px; margin-bottom:8px; }
.tablewrap { overflow-x:auto; }
table { width:100%; border-collapse:collapse; margin:10px 0 20px; }
th, td { border:1px solid #ddd; padding:8px; text-align:right; font-size:14px; }
.ltr { direction:ltr; unicode-bidi:plaintext; display:inline-block; font-family:monospace;
       word-break:break-all; }
"""


def page(content, title="المنصة المدرسية"):
    return (
        '<!doctype html>\n<html lang="ar" dir="rtl">\n<head>\n'
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        "<title>" + escape(title) + "</title>\n"
        "<style>" + PAGE_CSS + "</style>\n</head>\n"
        '<body><main class="container">' + content + "</main></body></html>"
    )


def logout_form():
    return (
        '<form method="post" action="' + url_for("logout") + '" style="margin:0">'
        + csrf_field()
        + '<button class="danger" type="submit">تسجيل الخروج</button></form>'
    )


def error_page(message, status):
    content = (
        '<section class="panel narrow"><h2>' + escape(message) + "</h2>"
        '<a class="button" href="/">العودة للرئيسية</a></section>'
    )
    return page(content, message), status


@app.errorhandler(400)
def bad_request(_e):
    return error_page("طلب غير صالح. أعد تحميل الصفحة وحاول مرة أخرى.", 400)


@app.errorhandler(403)
def forbidden(_e):
    return error_page("ليس لديك صلاحية لهذه الصفحة.", 403)


@app.errorhandler(404)
def not_found(_e):
    return error_page("الصفحة غير موجودة.", 404)


@app.errorhandler(413)
def too_large(_e):
    return error_page("الطلب كبير جداً.", 413)


@app.errorhandler(500)
def server_error(_e):
    return error_page("حدث خطأ غير متوقع. حاول لاحقاً.", 500)


# ----------------------------------------------------------------------
# تسجيل الدخول للكادر
# ----------------------------------------------------------------------
@app.route("/")
def index():
    if current_user():
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user():
        return redirect(url_for("dashboard"))

    error = ""
    if request.method == "POST":
        key = (request.form.get("user_key") or "").strip().lower()[:50]
        password = (request.form.get("password") or "")[:MAX_PASSWORD_LEN]
        scope = scope_for("login", key)
        ip_scope = "ip:" + client_ip()

        if is_blocked(scope, MAX_LOGIN_ATTEMPTS) or is_blocked(ip_scope, MAX_IP_ATTEMPTS):
            error = BLOCK_MSG
        else:
            user = run(
                "SELECT user_key, password_hash FROM users WHERE user_key = %s",
                (key,),
                fetch="one",
            )
            stored = user["password_hash"] if user else DUMMY_HASH
            valid = verify_password(stored, password)
            if user and valid:
                clear_failures(scope)
                session.clear()
                session.permanent = True
                session["user_key"] = user["user_key"]
                return redirect(url_for("dashboard"))
            record_failure(scope)
            record_failure(ip_scope)
            error = "اسم المستخدم أو كلمة المرور غير صحيحة."

    error_html = '<p class="message error">' + escape(error) + "</p>" if error else ""
    content = (
        '<section class="panel narrow"><h2>تسجيل دخول الكادر</h2>'
        + error_html
        + '<form method="post">'
        + csrf_field()
        + "<label>اسم المستخدم</label>"
        '<input type="text" name="user_key" required autocomplete="username" '
        'autocapitalize="none" dir="ltr">'
        "<label>كلمة المرور</label>"
        '<input type="password" name="password" required autocomplete="current-password">'
        '<button type="submit" style="width:100%">دخول</button></form>'
        '<p class="hint">الطلاب: ادخلوا من رابط صفكم واكتبوا رمز الصف.</p></section>'
    )
    return page(content, "تسجيل الدخول - المنصة المدرسية")


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/change_password", methods=["GET", "POST"])
@staff_required
def change_password():
    user = current_user()
    message = ""

    if request.method == "POST":
        old_pass = (request.form.get("old_pass") or "")[:MAX_PASSWORD_LEN]
        new_pass = (request.form.get("new_pass") or "")[:MAX_PASSWORD_LEN]
        confirm = (request.form.get("confirm") or "")[:MAX_PASSWORD_LEN]
        scope = scope_for("chpw", user["user_key"])

        if is_blocked(scope, MAX_LOGIN_ATTEMPTS):
            message = BLOCK_MSG
        else:
            row = run(
                "SELECT password_hash FROM users WHERE user_key = %s",
                (user["user_key"],),
                fetch="one",
            )
            if not row or not verify_password(row["password_hash"], old_pass):
                record_failure(scope)
                message = "كلمة المرور الحالية غير صحيحة."
            elif len(new_pass) < MIN_PASSWORD_LEN:
                message = "كلمة المرور الجديدة يجب ألا تقل عن %d أحرف." % MIN_PASSWORD_LEN
            elif new_pass != confirm:
                message = "تأكيد كلمة المرور غير مطابق."
            elif new_pass == old_pass:
                message = "اختر كلمة مرور مختلفة عن الحالية."
            else:
                run(
                    "UPDATE users SET password_hash = %s, must_change = 0 WHERE user_key = %s",
                    (generate_password_hash(new_pass), user["user_key"]),
                )
                clear_failures(scope)
                return redirect(url_for("dashboard"))

    msg_html = '<p class="message error">' + escape(message) + "</p>" if message else ""
    forced = ""
    if user["must_change"]:
        forced = '<p class="message">يجب تغيير كلمة المرور المؤقتة قبل المتابعة.</p>'
    back = ""
    if not user["must_change"]:
        back = '<p><a href="' + url_for("dashboard") + '">العودة إلى لوحة التحكم</a></p>'

    content = (
        '<section class="panel narrow"><h2>تغيير كلمة المرور</h2>'
        + forced
        + msg_html
        + '<form method="post">'
        + csrf_field()
        + "<label>كلمة المرور الحالية</label>"
        '<input type="password" name="old_pass" required autocomplete="current-password">'
        "<label>كلمة المرور الجديدة (8 أحرف على الأقل)</label>"
        '<input type="password" name="new_pass" required minlength="8" autocomplete="new-password">'
        "<label>تأكيد كلمة المرور الجديدة</label>"
        '<input type="password" name="confirm" required minlength="8" autocomplete="new-password">'
        '<button class="success" type="submit" style="width:100%">حفظ التغيير</button></form>'
        + back
        + "<hr>"
        + logout_form()
        + "</section>"
    )
    return page(content, "تغيير كلمة المرور")


# ----------------------------------------------------------------------
# لوحة التحكم والصفوف
# ----------------------------------------------------------------------
@app.route("/dashboard")
@staff_required
def dashboard():
    user = current_user()
    classes = run("SELECT class_id, name FROM classes ORDER BY sort_order", fetch="all")

    mine = set()
    if user["role_type"] == "teacher":
        rows = run(
            "SELECT class_id FROM teacher_classes WHERE user_key = %s",
            (user["user_key"],),
            fetch="all",
        )
        mine = {r["class_id"] for r in rows}
        classes = sorted(classes, key=lambda c: c["class_id"] not in mine)

    cards = ""
    for c in classes:
        link = url_for("classroom", class_id=c["class_id"])
        badge = '<div class="badge">صفّي</div>' if c["class_id"] in mine else ""
        cards += (
            '<div class="class-card">' + badge + "<h3>" + escape(c["name"]) + "</h3>"
            '<a class="button success" href="' + link + '">دخول الصف</a></div>'
        )

    note = ""
    if user["role_type"] == "teacher" and not mine:
        note = '<p class="message">لم يتم تعيين صفوف لك بعد. اطلب من المدير تعيينها.</p>'

    admin_btn = ""
    if user["role_type"] == "admin":
        admin_btn = '<a class="button" style="background:#6f42c1" href="' + url_for("admin_panel") + '">إدارة الحسابات والصفوف</a>'

    content = (
        '<section class="panel">'
        + pop_flash()
        + '<div class="actions" style="justify-content:space-between;background:#007bff;'
        'color:white;padding:18px;border-radius:8px;">'
        "<div><h2>مرحباً بك، " + escape(user["name"]) + "</h2>"
        "<p>الصلاحية: <b>" + escape(user["role_label"]) + "</b></p></div>"
        '<div class="actions">' + admin_btn
        + '<a class="button warning" href="' + url_for("change_password") + '">تغيير كلمة المرور</a>'
        + logout_form()
        + "</div></div>"
        + note
        + "<h3>قائمة الصفوف الدراسية</h3>"
        '<div class="grid">' + cards + "</div></section>"
    )
    return page(content, "لوحة التحكم - المنصة المدرسية")


@app.route("/classroom/<class_id>", methods=["GET", "POST"])
def classroom(class_id):
    cls = run(
        "SELECT class_id, name, access_code, live_link, live_note "
        "FROM classes WHERE class_id = %s",
        (class_id,),
        fetch="one",
    )
    if cls is None:
        abort(404)

    user = current_user()
    allowed = bool(user) or session.get("student_class") == class_id
    error = ""

    if not allowed and request.method == "POST":
        scope = scope_for("class", class_id)
        if is_blocked(scope, MAX_CLASS_ATTEMPTS):
            error = BLOCK_MSG
        else:
            raw = (request.form.get("code") or "")[:40]
            code = "".join(ch for ch in raw.upper() if ch.isalnum())
            if hmac.compare_digest(code.encode(), cls["access_code"].encode()):
                clear_failures(scope)
                session.permanent = True
                session["student_class"] = class_id
                return redirect(url_for("classroom", class_id=class_id))
            record_failure(scope)
            error = "رمز الصف غير صحيح."

    if not allowed:
        error_html = '<p class="message error">' + escape(error) + "</p>" if error else ""
        content = (
            '<section class="panel narrow" style="text-align:center">'
            "<h2>" + escape(cls["name"]) + "</h2>"
            "<p>اكتب رمز الصف للدخول.</p>"
            + error_html
            + '<form method="post">'
            + csrf_field()
            + '<input type="text" name="code" required autocomplete="off" '
            'autocapitalize="characters" dir="ltr" style="text-align:center;font-size:20px">'
            '<button type="submit" style="width:100%">دخول</button></form></section>'
        )
        return page(content, cls["name"] + " - دخول")

    # --- الحصة المباشرة (تظهر للطلاب والكادر) ---
    live_link = cls["live_link"] or ""
    live_note = cls["live_note"] or ""
    if live_link:
        note_html = "<p>" + escape(live_note) + "</p>" if live_note else ""
        live_html = (
            '<div class="message ok"><b>الحصة المباشرة</b>' + note_html
            + '<a class="button success" href="' + escape(live_link, quote=True)
            + '" target="_blank" rel="noopener noreferrer">انضم للحصة</a></div>'
        )
    else:
        live_html = '<p class="message">لا توجد حصة مباشرة حالياً.</p>'

    extra = ""
    manage_html = ""
    if user:
        link = request.host_url.rstrip("/") + url_for("classroom", class_id=class_id)
        extra = (
            '<p class="message">رابط الصف: <span class="ltr">' + escape(link) + "</span><br>"
            'رمز الصف: <b class="ltr">' + escape(cls["access_code"]) + "</b></p>"
        )
        if can_manage_class(user, class_id):
            action = url_for("set_live_link", class_id=class_id)
            manage_html = (
                '<div style="text-align:right"><h3>إدارة رابط الحصة المباشرة</h3>'
                '<form method="post" action="' + action + '">'
                + csrf_field()
                + "<label>وصف الحصة (اختياري، مثال: رياضيات الساعة 10)</label>"
                '<input type="text" name="live_note" maxlength="100" value="'
                + escape(live_note, quote=True) + '">'
                "<label>رابط الحصة (Zoom أو Meet، يبدأ بـ https://)</label>"
                '<input type="url" name="live_link" maxlength="500" dir="ltr" value="'
                + escape(live_link, quote=True) + '">'
                '<div class="actions">'
                '<button class="success" type="submit" name="action" value="save">حفظ الرابط</button>'
                '<button class="danger" type="submit" name="action" value="clear" formnovalidate>'
                "حذف الرابط</button></div></form></div>"
            )
        elif user["role_type"] == "teacher":
            manage_html = (
                '<p class="hint">لإضافة رابط الحصة لهذا الصف، اطلب من المدير تعيينه لك.</p>'
            )
        footer = '<a class="button" href="' + url_for("dashboard") + '">العودة إلى لوحة التحكم</a>'
    else:
        footer = logout_form()

    content = (
        '<section class="panel" style="max-width:700px;margin:auto;text-align:center;">'
        + pop_flash()
        + "<h2>" + escape(cls["name"]) + "</h2>"
        + live_html
        + extra
        + manage_html
        + '<div style="margin-top:20px">' + footer + "</div>"
        + "</section>"
    )
    return page(content, cls["name"] + " - الصف")


@app.route("/classroom/<class_id>/live", methods=["POST"])
@staff_required
def set_live_link(class_id):
    user = current_user()
    exists = run("SELECT class_id FROM classes WHERE class_id = %s", (class_id,), fetch="one")
    if exists is None:
        abort(404)
    if not can_manage_class(user, class_id):
        abort(403)

    if request.form.get("action") == "clear":
        run("UPDATE classes SET live_link = '', live_note = '' WHERE class_id = %s", (class_id,))
        flash_msg("تم حذف رابط الحصة.")
    else:
        link = clean_link(request.form.get("live_link"))
        if link is None:
            flash_msg("الرابط غير صالح. لازم يكون رابطاً كاملاً يبدأ بـ https://", ok=False)
        else:
            note = (request.form.get("live_note") or "").strip()[:100]
            run(
                "UPDATE classes SET live_link = %s, live_note = %s WHERE class_id = %s",
                (link, note, class_id),
            )
            flash_msg("تم حفظ رابط الحصة. الطلاب سيرونه فوراً.")
    return redirect(url_for("classroom", class_id=class_id))


# ----------------------------------------------------------------------
# إدارة الحسابات والصفوف (للمدير فقط)
# ----------------------------------------------------------------------
def credentials_notice(items):
    rows = ""
    for name, key, pw in items:
        rows += (
            "<tr><td>" + escape(name) + '</td><td><span class="ltr">' + escape(key)
            + '</span></td><td><b class="ltr">' + escape(pw) + "</b></td></tr>"
        )
    return (
        '<div class="message ok"><b>كلمات المرور المؤقتة (تظهر مرة واحدة فقط، انسخها أو صوّرها الآن):</b>'
        '<div class="tablewrap"><table><tr><th>الاسم</th><th>اسم المستخدم</th>'
        "<th>كلمة المرور المؤقتة</th></tr>" + rows + "</table></div>"
        "المستخدم سيُطلب منه تغييرها عند أول دخول.</div>"
    )


def render_admin(notice_html=""):
    users = run(
        "SELECT u.user_key, u.name, u.role_label, u.role_type, u.must_change, "
        "(u.password_hash = %s) AS pending, "
        "(SELECT COUNT(*) FROM teacher_classes t WHERE t.user_key = u.user_key) AS n_classes "
        "FROM users u ORDER BY u.role_type, u.name",
        (LOCKED,),
        fetch="all",
    )
    classes = run(
        "SELECT class_id, name, access_code FROM classes ORDER BY sort_order", fetch="all"
    )
    base = request.host_url.rstrip("/")

    user_rows = ""
    for u in users:
        if u["pending"]:
            status = "بانتظار التفعيل"
        elif u["must_change"]:
            status = "كلمة مؤقتة"
        else:
            status = "مفعّل"
        action = url_for("admin_reset", user_key=u["user_key"])
        if u["role_type"] == "teacher":
            count_cell = str(u["n_classes"])
            classes_btn = (
                '<a class="button" href="' + url_for("admin_teacher", user_key=u["user_key"])
                + '">الصفوف</a>'
            )
        else:
            count_cell = "-"
            classes_btn = ""
        user_rows += (
            "<tr><td>" + escape(u["name"]) + "</td><td>" + escape(u["role_label"])
            + '</td><td><span class="ltr">' + escape(u["user_key"]) + "</span></td><td>"
            + status + "</td><td>" + count_cell + "</td><td>"
            '<div class="actions">' + classes_btn
            + '<form method="post" action="' + action + '" style="margin:0">'
            + csrf_field()
            + '<button class="warning" type="submit">كلمة مؤقتة</button></form>'
            "</div></td></tr>"
        )

    class_rows = ""
    for c in classes:
        link = base + url_for("classroom", class_id=c["class_id"])
        action = url_for("admin_class_code", class_id=c["class_id"])
        class_rows += (
            "<tr><td>" + escape(c["name"]) + '</td><td><b class="ltr">' + escape(c["access_code"])
            + '</b></td><td><span class="ltr">' + escape(link) + "</span></td><td>"
            '<form method="post" action="' + action + '" style="margin:0">'
            + csrf_field()
            + '<button type="submit">رمز جديد</button></form></td></tr>'
        )

    pending_action = url_for("admin_reset_pending")
    codes_action = url_for("admin_codes_all")
    content = (
        '<section class="panel"><div class="actions" style="justify-content:space-between">'
        "<h2>إدارة الحسابات والصفوف</h2>"
        '<a class="button" href="' + url_for("dashboard") + '">العودة</a></div>'
        + pop_flash()
        + notice_html
        + "<h3>الحسابات</h3>"
        '<form method="post" action="' + pending_action + '">'
        + csrf_field()
        + '<button class="success" type="submit">تفعيل كل الحسابات التي بانتظار التفعيل</button></form>'
        '<div class="tablewrap"><table><tr><th>الاسم</th><th>الدور</th><th>اسم المستخدم</th>'
        "<th>الحالة</th><th>عدد الصفوف</th><th></th></tr>" + user_rows + "</table></div>"
        "<h3>الصفوف ورموز الدخول</h3>"
        '<form method="post" action="' + codes_action + '">'
        + csrf_field()
        + '<button class="danger" type="submit" '
        'onclick="return confirm(\'سيتم تغيير رموز كل الصفوف. متأكد؟\')">'
        "تغيير رموز كل الصفوف</button></form>"
        '<div class="tablewrap"><table><tr><th>الصف</th><th>الرمز</th><th>الرابط</th><th></th></tr>'
        + class_rows + "</table></div></section>"
    )
    return page(content, "الإدارة - المنصة المدرسية")


@app.route("/admin")
@admin_required
def admin_panel():
    return render_admin()


@app.route("/admin/teacher/<user_key>", methods=["GET", "POST"])
@admin_required
def admin_teacher(user_key):
    teacher = run(
        "SELECT user_key, name, role_type FROM users WHERE user_key = %s",
        (user_key,),
        fetch="one",
    )
    if teacher is None or teacher["role_type"] != "teacher":
        abort(404)

    classes = run("SELECT class_id, name FROM classes ORDER BY sort_order", fetch="all")
    valid_ids = {c["class_id"] for c in classes}

    if request.method == "POST":
        chosen = [cid for cid in request.form.getlist("classes") if cid in valid_ids]
        replace_teacher_classes(user_key, chosen)
        flash_msg("تم حفظ صفوف " + teacher["name"] + " (" + str(len(chosen)) + ").")
        return redirect(url_for("admin_panel"))

    rows = run(
        "SELECT class_id FROM teacher_classes WHERE user_key = %s", (user_key,), fetch="all"
    )
    current = {r["class_id"] for r in rows}

    boxes = ""
    for c in classes:
        checked = " checked" if c["class_id"] in current else ""
        boxes += (
            '<label class="check"><input type="checkbox" name="classes" value="'
            + escape(c["class_id"], quote=True) + '"' + checked + ">"
            + escape(c["name"]) + "</label>"
        )

    content = (
        '<section class="panel narrow"><h2>صفوف ' + escape(teacher["name"]) + "</h2>"
        '<p class="hint">المعلم بيقدر يضيف رابط الحصة المباشرة للصفوف المعلّمة هون فقط.</p>'
        '<form method="post">' + csrf_field() + boxes
        + '<div class="actions" style="margin-top:16px">'
        '<button class="success" type="submit">حفظ</button>'
        '<a class="button" style="background:#6c757d" href="' + url_for("admin_panel")
        + '">رجوع</a></div></form></section>'
    )
    return page(content, "صفوف المعلم - المنصة المدرسية")


@app.route("/admin/reset/<user_key>", methods=["POST"])
@admin_required
def admin_reset(user_key):
    row = run(
        "SELECT user_key, name FROM users WHERE user_key = %s", (user_key,), fetch="one"
    )
    if row is None:
        abort(404)
    temp = new_temp_password()
    run(
        "UPDATE users SET password_hash = %s, must_change = 1 WHERE user_key = %s",
        (generate_password_hash(temp), user_key),
    )
    return render_admin(credentials_notice([(row["name"], row["user_key"], temp)]))


@app.route("/admin/reset_pending", methods=["POST"])
@admin_required
def admin_reset_pending():
    pending = run(
        "SELECT user_key, name FROM users WHERE password_hash = %s", (LOCKED,), fetch="all"
    )
    if not pending:
        return render_admin('<p class="message">لا توجد حسابات بانتظار التفعيل.</p>')
    items = []
    updates = []
    for u in pending:
        temp = new_temp_password()
        items.append((u["name"], u["user_key"], temp))
        updates.append((generate_password_hash(temp), u["user_key"]))
    run_many("UPDATE users SET password_hash = %s, must_change = 1 WHERE user_key = %s", updates)
    return render_admin(credentials_notice(items))


@app.route("/admin/class_code/<class_id>", methods=["POST"])
@admin_required
def admin_class_code(class_id):
    exists = run("SELECT class_id FROM classes WHERE class_id = %s", (class_id,), fetch="one")
    if exists is None:
        abort(404)
    run("UPDATE classes SET access_code = %s WHERE class_id = %s", (new_code(), class_id))
    return redirect(url_for("admin_panel"))


@app.route("/admin/codes_all", methods=["POST"])
@admin_required
def admin_codes_all():
    classes = run("SELECT class_id FROM classes", fetch="all")
    run_many(
        "UPDATE classes SET access_code = %s WHERE class_id = %s",
        [(new_code(), c["class_id"]) for c in classes],
    )
    return redirect(url_for("admin_panel"))


init_db()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)