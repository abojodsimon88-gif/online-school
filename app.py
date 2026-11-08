from flask import Flask, render_template_string, request, redirect, url_for, session
from flask_socketio import SocketIO, join_room, leave_room, emit
import sqlite3
import os

app = Flask(__name__)
app.secret_key = 'simon_secure_school_key'
socketio = SocketIO(app, cors_allowed_origins="*")

DATABASE = 'school.db'

def init_db():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_key TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            role TEXT NOT NULL,
            password TEXT NOT NULL
        )
    ''')
    conn.commit()
    
    cursor.execute("PRAGMA table_info(users)")
    columns = [column[1] for column in cursor.fetchall()]
    
    if "user_key" not in columns:
        cursor.execute("DROP TABLE IF EXISTS users")
        conn.commit()
        cursor.execute('''
            CREATE TABLE users (
                user_key TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                role TEXT NOT NULL,
                password TEXT NOT NULL
            )
        ''')
        conn.commit()

    cursor.execute('SELECT COUNT(*) FROM users')
    if cursor.fetchone()[0] == 0:
        default_users = [
            ("khader", "خضر", "المدير (Admin)", "1234"),
            ("bretta", "بريتا", "السكرتيرة (Secretary)", "1234"),
            ("fouad", "فؤاد", "المرشد الاجتماعي (Counselor)", "1234"),
            ("nizar", "نزار", "معلم", "1234"),
            ("mike", "مايك", "معلم", "1234"),
            ("ahmad", "أحمد", "معلم", "1234"),
            ("saba", "سابا", "معلم", "1234"),
            ("anders", "أندرس", "معلم", "1234"),
            ("waleed", "وليد", "معلم", "1234"),
            ("leila", "ليلى", "معلمة", "1234"),
            ("lana", "لانا", "معلمة", "1234"),
            ("nicole", "نيكول", "معلمة", "1234"),
            ("eva", "إيفا", "معلمة", "1234"),
            ("lord", "لورد", "معلمة", "1234"),
            ("noha", "نهى", "معلمة", "1234"),
            ("manal", "منال", "معلمة", "1234"),
            ("kheylaa", "خيلاء", "معلمة", "1234"),
            ("doaa", "دعاء", "معلمة", "1234"),
            ("celeste", "سيليستي", "معلمة", "1234"),
            ("noor", "نور", "معلمة", "1234"),
            ("razan", "رزان", "معلمة", "1234"),
            ("dalia", "داليا", "معلمة", "1234"),
            ("haidy", "هايدي", "معلمة", "1234"),
            ("nancy", "نانسي", "معلمة", "1234"),
            ("mary", "ميري", "معلمة", "1234"),
            ("rita", "ريتا", "معلمة", "1234"),
            ("ibtisam", "ابتسام", "معلمة", "1234")
        ]
        cursor.executemany('INSERT INTO users (user_key, name, role, password) VALUES (?, ?, ?, ?)', default_users)
        conn.commit()
    conn.close()

init_db()

CLASSES_DICT = {
    "first": "الصف الأول",
    "second": "الصف الثاني",
    "third": "الصف الثالث",
    "fourth_a": "الصف الرابع أ",
    "fourth_b": "الصف الرابع ب",
    "fifth_a": "الصف الخامس أ",
    "fifth_b": "الصف الخامس ب",
    "sixth_a": "الصف السادس أ",
    "sixth_b": "الصف السادس ب",
    "seventh_a": "الصف السابع أ",
    "seventh_b": "الصف السابع ب",
    "eighth_a": "الصف الثامن أ",
    "eighth_b": "الصف الثامن ب",
    "ninth": "الصف التاسع",
    "tenth_a": "الصف العاشر أ",
    "tenth_b": "الصف العاشر ب",
    "eleventh": "صف الـ 11",
    "twelfth": "صف الـ 12"
}

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    if request.method == 'POST':
        selected_user_key = request.form.get('user_key')
        password = request.form.get('password')
        student_name = request.form.get('student_name')
        
        # دخول طالب (بدون كلمة مرور)
        if selected_user_key == "student" and student_name:
            session['user_key'] = "student"
            session['username'] = student_name.strip()
            session['role'] = "طالب"
            return redirect(url_for('dashboard'))

        # دخول كادر أو معلمين
        cursor.execute('SELECT name, role, password FROM users WHERE user_key = ?', (selected_user_key,))
        user_row = cursor.fetchone()
        conn.close()
        
        if user_row and user_row[2] == password:
            session['user_key'] = selected_user_key
            session['username'] = user_row[0]
            session['role'] = user_row[1]
            return redirect(url_for('dashboard'))
        else:
            return "<html dir='rtl'><body style='font-family:Arial; text-align:center; margin-top:50px;'><h3 style='color:red;'>كلمة المرور غير صحيحة، حاول مجدداً!</h3><br><a href='/login'>العودة لصفحة الدخول</a></body></html>"
            
    cursor.execute('SELECT user_key, name, role FROM users')
    all_users = cursor.fetchall()
    conn.close()
    
    admin_opts = ""
    teacher_m_opts = ""
    teacher_f_opts = ""
    
    admin_keys = ["khader", "bretta", "fouad"]
    teacher_m_keys = ["nizar", "mike", "ahmad", "saba", "anders", "waleed"]
    
    for u in all_users:
        ukey, uname, urole = u[0], u[1], u[2]
        if ukey in admin_keys:
            admin_opts += f'<option value="{ukey}">{urole}: {uname}</option>'
        elif ukey in teacher_m_keys:
            teacher_m_opts += f'<option value="{ukey}">{uname}</option>'
        else:
            teacher_f_opts += f'<option value="{ukey}">{uname}</option>'

    return render_template_string('''
    <html dir="rtl">
    <head>
        <title>تسجيل الدخول - المنصة المدرسية</title>
        <script>
            function toggleStudentInput(val) {
                var box = document.getElementById("student_box");
                var passBox = document.getElementById("pass_box");
                if (val === "student") {
                    box.style.display = "block";
                    passBox.style.display = "none";
                    document.getElementById("pass_input").required = false;
                    document.getElementById("student_input").required = true;
                } else {
                    box.style.display = "none";
                    passBox.style.display = "block";
                    document.getElementById("pass_input").required = true;
                    document.getElementById("student_input").required = false;
                }
            }
        </script>
    </head>
    <body style="text-align: center; margin-top: 50px; font-family: Arial, sans-serif; background-color: #f4f6f9;">
        <h2>تسجيل الدخول - منصة الدراسة أونلاين</h2>
        <form method="POST" style="display: inline-block; text-align: right; border: 1px solid #ccc; padding: 25px; border-radius: 10px; width: 350px; background: white; box-shadow: 0 4px 8px rgba(0,0,0,0.1);">
            
            <label style="font-weight: bold;">اختر الحساب:</label><br>
            <select name="user_key" onchange="toggleStudentInput(this.value)" required style="width: 100%; padding: 10px; margin: 10px 0; border-radius: 5px; border: 1px solid #ccc; font-size: 14px;">
                <option value="" disabled selected>-- اختر الحساب --</option>
                <option value="student" style="color:#007bff; font-weight:bold;">--> دخول طالب (أدخل اسمك)</option>
                <optgroup label="الإدارة والكادر الإشرافي">{{ admin_opts | safe }}</optgroup>
                <optgroup label="المعلمون">{{ teacher_m_opts | safe }}</optgroup>
                <optgroup label="المعلمات">{{ teacher_f_opts | safe }}</optgroup>
            </select><br><br>

            <div id="student_box" style="display:none;">
                <label style="font-weight: bold;">اسم الطالب الكامل:</label><br>
                <input type="text" id="student_input" name="student_name" placeholder="أدخل اسمك الثلاثي" style="width: 93%; padding: 10px; margin: 10px 0; border-radius: 5px; border: 1px solid #ccc;"><br><br>
            </div>

            <div id="pass_box">
                <label style="font-weight: bold;">كلمة المرور:</label><br>
                <input type="password" id="pass_input" name="password" placeholder="أدخل كلمة المرور" style="width: 93%; padding: 10px; margin: 10px 0; border-radius: 5px; border: 1px solid #ccc;"><br><br>
            </div>

            <input type="submit" value="دخول إلى المنصة" style="width: 100%; padding: 12px; background-color: #007bff; color: white; border: none; border-radius: 5px; cursor: pointer; font-weight: bold; font-size: 15px;">
        </form>
    </body>
    </html>
    ''', admin_opts=admin_opts, teacher_m_opts=teacher_m_opts, teacher_f_opts=teacher_f_opts)

@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        return redirect(url_for('login'))
        
    username = session.get('username')
    role = session.get('role')
    user_key = session.get('user_key')
    
    classes_html = ""
    for class_id, class_name in CLASSES_DICT.items():
        classes_html += f'''
            <div style="background: #ffffff; border: 1px solid #ddd; padding: 15px; border-radius: 8px; text-align: center; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
                <h4 style="margin: 0 0 10px 0; color: #333;">{class_name}</h4>
                <a href="/classroom/{class_id}" style="padding: 8px 15px; background: #28a745; color: white; text-decoration: none; border-radius: 5px; font-size: 14px; display: inline-block;">دخول الغرفة الصوتية</a>
            </div>
        '''

    return render_template_string('''
    <html dir="rtl">
    <head><title>لوحة التحكم - المنصة المدرسية</title></head>
    <body style="font-family: Arial, sans-serif; background-color: #f4f6f9; margin: 0; padding: 20px;">
        <div style="max-width: 1000px; margin: auto;">
            <div style="background: #007bff; color: white; padding: 20px; border-radius: 10px; display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <h2 style="margin: 0;">مرحباً بك، {{ username }}</h2>
                    <p style="margin: 5px 0 0 0;">الصفة: <b>{{ role }}</b></p>
                </div>
                <div>
                    {% if user_key != 'student' %}
                    <a href="/change_password" style="background: #ffc107; color: black; padding: 10px 15px; text-decoration: none; border-radius: 5px; font-weight: bold; margin-left: 10px;">تغيير كلمة المرور</a>
                    {% endif %}
                    <a href="/login" style="background: #dc3545; color: white; padding: 10px 15px; text-decoration: none; border-radius: 5px; font-weight: bold;">تسجيل الخروج</a>
                </div>
            </div>
            
            <h3 style="margin-top: 30px; border-bottom: 2px solid #007bff; padding-bottom: 10px; color: #333;">صفوف المنصة الدراسية:</h3>
            
            <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 15px; margin-top: 20px;">
                {{ classes_html | safe }}
            </div>
        </div>
    </body>
    </html>
    ''', username=username, role=role, user_key=user_key, classes_html=classes_html)

@app.route('/classroom/<class_id>')
def classroom(class_id):
    if 'username' not in session:
        return redirect(url_for('login'))
        
    username = session.get('username')
    role = session.get('role')
    user_key = session.get('user_key')
    class_name = CLASSES_DICT.get(class_id, "الصف الدراسي")

    # تحديد نوع صلاحية الدخول:
    # 1. المدير خضر = دخول مباشر (admin)
    # 2. باقي المعلمين والإدارة = معلم (teacher)
    # 3. الطالب = يحتاج موافقة (student)
    is_admin = (user_key == 'khader')
    is_teacher = (role in ['معلم', 'معلمة'] or user_key in ['bretta', 'fouad'])
    
    return render_template_string('''
    <html dir="rtl">
    <head>
        <title>{{ class_name }} - الغرفة الصوتية</title>
        <script src="https://cdn.socket.io/4.5.4/socket.io.min.js"></script>
    </head>
    <body style="font-family: Arial, sans-serif; background-color: #f4f6f9; margin: 0; padding: 20px; text-align: center;">
        <div style="max-width: 750px; margin: auto; background: white; padding: 30px; border-radius: 10px; border: 1px solid #ccc; box-shadow: 0 4px 8px rgba(0,0,0,0.1);">
            <h2 style="color: #007bff; margin-top: 0;">{{ class_name }}</h2>
            <p style="font-size: 15px; color: #555;">المستخدم الحالي: <b>{{ username }}</b> ({{ role }})</p>

            <div id="status_box" style="background: #fff3cd; color: #856404; padding: 15px; border-radius: 8px; margin: 20px 0; font-weight: bold;">
                جاري الاتصال بالسيرفر...
            </div>

            <!-- لوحة تحكم المعلم لإدارة الطلبات -->
            {% if is_teacher or is_admin %}
            <div id="teacher_controls" style="display: none; border: 1px solid #28a745; background: #eafaf1; padding: 15px; border-radius: 8px; margin-bottom: 20px; text-align: right;">
                <h4 style="margin: 0 0 10px 0; color: #28a745;">طلبات دخول الطلاب بانتظار الإذن:</h4>
                <div id="requests_list">لا يوجد طلبات حالياً...</div>
            </div>
            {% endif %}

            <!-- منطقة الغرفة الصوتية (تظهر بعد الدخول) -->
            <div id="audio_room" style="display: none; background: #e9ecef; padding: 20px; border-radius: 8px; margin-bottom: 20px;">
                <h3 style="color: #28a745; margin-top:0;">أنت الآن داخل الغرفة الصوتية!</h3>
                <p style="color: #6c757d;">البث الصوتي فقط (بدون كاميرا) مفعل لضمان السرعة.</p>
                <button id="mic_btn" onclick="toggleMic()" style="padding: 10px 20px; background: #007bff; color: white; border: none; border-radius: 5px; font-weight: bold; cursor: pointer;">
                    تشغيل المايك
                </button>
            </div>

            <br>
            <a href="/dashboard" style="background: #6c757d; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; font-weight: bold;">خروج والعودة للوحة التحكم</a>
        </div>

        <script>
            const socket = io();
            const classId = "{{ class_id }}";
            const username = "{{ username }}";
            const userKey = "{{ user_key }}";
            const isAdmin = {{ 'true' if is_admin else 'false' }};
            const isTeacher = {{ 'true' if is_teacher else 'false' }};

            let micStream = null;

            socket.on('connect', () => {
                if (isAdmin) {
                    document.getElementById("status_box").style.background = "#d4edda";
                    document.getElementById("status_box").style.color = "#155724";
                    document.getElementById("status_box").innerText = "دخول مباشر كمدير (Admin Bypass)";
                    document.getElementById("audio_room").style.display = "block";
                    if (document.getElementById("teacher_controls")) document.getElementById("teacher_controls").style.display = "block";
                    socket.emit('join_class', {class_id: classId, username: username, role: 'admin'});
                } else if (isTeacher) {
                    document.getElementById("status_box").style.background = "#d4edda";
                    document.getElementById("status_box").style.color = "#155724";
                    document.getElementById("status_box").innerText = "أنت معلم هذه الغرفة - الغرفة جاهزة لاستقبال الطلاب";
                    document.getElementById("audio_room").style.display = "block";
                    document.getElementById("teacher_controls").style.display = "block";
                    socket.emit('join_class', {class_id: classId, username: username, role: 'teacher'});
                } else {
                    document.getElementById("status_box").innerText = "جاري إرسال طلب إذن دخول للمعلم...";
                    socket.emit('request_entry', {class_id: classId, username: username, socket_id: socket.id});
                }
            });

            // طلب دخول جديد للمعلم
            socket.on('new_entry_request', (data) => {
                if (isTeacher || isAdmin) {
                    const list = document.getElementById("requests_list");
                    if (list.innerText === "لا يوجد طلبات حالياً...") list.innerHTML = "";
                    
                    const item = document.createElement("div");
                    item.id = "req_" + data.socket_id;
                    item.style.cssText = "display: flex; justify-content: space-between; align-items: center; background: white; padding: 8px 12px; margin-bottom: 5px; border-radius: 5px; border: 1px solid #ccc;";
                    item.innerHTML = `
                        <span>الطالب: <b>${data.username}</b> يطلب الدخول</span>
                        <div>
                            <button onclick="approveStudent('${data.socket_id}')" style="background:#28a745; color:white; border:none; padding:5px 10px; border-radius:3px; cursor:pointer;">قبول</button>
                            <button onclick="rejectStudent('${data.socket_id}')" style="background:#dc3545; color:white; border:none; padding:5px 10px; border-radius:3px; cursor:pointer; margin-right:5px;">رفض</button>
                        </div>
                    `;
                    list.appendChild(item);
                }
            });

            function approveStudent(studentSocketId) {
                socket.emit('decision', {student_socket: studentSocketId, status: 'approved'});
                const reqItem = document.getElementById("req_" + studentSocketId);
                if (reqItem) reqItem.remove();
            }

            function rejectStudent(studentSocketId) {
                socket.emit('decision', {student_socket: studentSocketId, status: 'rejected'});
                const reqItem = document.getElementById("req_" + studentSocketId);
                if (reqItem) reqItem.remove();
            }

            // استقبال النتيجة عند الطالب
            socket.on('entry_response', (data) => {
                if (data.status === 'approved') {
                    document.getElementById("status_box").style.background = "#d4edda";
                    document.getElementById("status_box").style.color = "#155724";
                    document.getElementById("status_box").innerText = "تم قبول دخولك من قبل المعلم!";
                    document.getElementById("audio_room").style.display = "block";
                } else {
                    document.getElementById("status_box").style.background = "#f8d7da";
                    document.getElementById("status_box").style.color = "#721c24";
                    document.getElementById("status_box").innerText = "عذراً، رفض المعلم طلب دخولك للغرفة.";
                }
            });

            // التحكم بالمايكروفون (صوتي فقط)
            async function toggleMic() {
                const btn = document.getElementById("mic_btn");
                if (!micStream) {
                    try {
                        micStream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
                        btn.innerText = "كتم المايك";
                        btn.style.background = "#dc3545";
                    } catch (err) {
                        alert("يرجى إعطاء إذن استخدام المايكروفون في المتصفح!");
                    }
                } else {
                    micStream.getTracks().forEach(track => track.stop());
                    micStream = null;
                    btn.innerText = "تشغيل المايك";
                    btn.style.background = "#007bff";
                }
            }
        </script>
    </body>
    </html>
    ''', class_id=class_id, class_name=class_name, username=username, role=role, user_key=user_key, is_admin=is_admin, is_teacher=is_teacher)

@app.route('/change_password', methods=['GET', 'POST'])
def change_password():
    if 'username' not in session or session.get('user_key') == 'student':
        return redirect(url_for('login'))
        
    user_key = session.get('user_key')
    message = ""
    
    if request.method == 'POST':
        old_pass = request.form.get('old_pass')
        new_pass = request.form.get('new_pass')
        
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute('SELECT password FROM users WHERE user_key = ?', (user_key,))
        row = cursor.fetchone()
        
        if row and row[0] == old_pass:
            cursor.execute('UPDATE users SET password = ? WHERE user_key = ?', (new_pass, user_key))
            conn.commit()
            conn.close()
            message = "<p style='color:green; font-weight:bold;'>تم تغيير كلمة المرور بنجاح وحفظها بالقاعدة!</p>"
        else:
            conn.close()
            message = "<p style='color:red; font-weight:bold;'>كلمة المرور القديمة غير صحيحة!</p>"

    return render_template_string('''
    <html dir="rtl">
    <head><title>تغيير كلمة المرور</title></head>
    <body style="font-family: Arial, sans-serif; background-color: #f4f6f9; text-align: center; padding-top: 50px;">
        <div style="display: inline-block; background: white; padding: 30px; border-radius: 10px; border: 1px solid #ccc; width: 350px; box-shadow: 0 4px 8px rgba(0,0,0,0.1);">
            <h2>تغيير كلمة المرور</h2>
            {{ message | safe }}
            <form method="POST">
                <label style="font-weight: bold; display: block; text-align: right;">كلمة المرور القديمة:</label>
                <input type="password" name="old_pass" required style="width: 100%; padding: 10px; margin: 10px 0; border-radius: 5px; border: 1px solid #ccc;"><br>
                
                <label style="font-weight: bold; display: block; text-align: right;">كلمة المرور الجديدة:</label>
                <input type="password" name="new_pass" required style="width: 100%; padding: 10px; margin: 10px 0; border-radius: 5px; border: 1px solid #ccc;"><br><br>
                
                <input type="submit" value="حفظ التغيير" style="width: 100%; padding: 12px; background-color: #28a745; color: white; border: none; border-radius: 5px; cursor: pointer; font-weight: bold; font-size: 15px;">
            </form>
            <br>
            <a href="/dashboard" style="color: #007bff; text-decoration: none; font-weight: bold;">العودة إلى لوحة التحكم</a>
        </div>
    </body>
    </html>
    ''', message=message)

# أحداث الـ WebSockets وإدارة الغرف
@socketio.on('join_class')
def handle_join_class(data):
    room = data['class_id']
    join_room(room)

@socketio.on('request_entry')
def handle_request_entry(data):
    room = data['class_id']
    join_room(room)
    emit('new_entry_request', {'username': data['username'], 'socket_id': request.sid}, to=room)

@socketio.on('decision')
def handle_decision(data):
    student_socket = data['student_socket']
    status = data['status']
    emit('entry_response', {'status': status}, to=student_socket)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', debug=True, port=5000)
