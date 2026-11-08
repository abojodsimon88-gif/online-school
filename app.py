from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
import os

app = Flask(__name__)
app.secret_key = 'simon_secure_school_key'

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

# قائمة الصفوف والشعب (دخول مفتوح وغير محدود لأي عدد من الطلاب)
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

    return f'''
    <html dir="rtl">
    <head><title>تسجيل الدخول - المنصة المدرسية</title></head>
    <body style="text-align: center; margin-top: 50px; font-family: Arial, sans-serif; background-color: #f4f6f9;">
        <h2>تسجيل الدخول - منصة المدرسة الإلكترونية</h2>
        <form method="POST" style="display: inline-block; text-align: right; border: 1px solid #ccc; padding: 25px; border-radius: 10px; width: 350px; background: white; box-shadow: 0 4px 8px rgba(0,0,0,0.1);">
            
            <label style="font-weight: bold;">اختر الاسم والدور:</label><br>
            <select name="user_key" required style="width: 100%; padding: 10px; margin: 10px 0; border-radius: 5px; border: 1px solid #ccc; font-size: 14px;">
                <option value="" disabled selected>-- اختر الحساب --</option>
                <optgroup label="الإدارة والكادر الإشرافي">{admin_opts}</optgroup>
                <optgroup label="المعلمون">{teacher_m_opts}</optgroup>
                <optgroup label="المعلمات">{teacher_f_opts}</optgroup>
            </select><br><br>

            <label style="font-weight: bold;">كلمة المرور:</label><br>
            <input type="password" name="password" placeholder="أدخل كلمة المرور" required style="width: 93%; padding: 10px; margin: 10px 0; border-radius: 5px; border: 1px solid #ccc;"><br><br>

            <input type="submit" value="دخول إلى المنصة" style="width: 100%; padding: 12px; background-color: #007bff; color: white; border: none; border-radius: 5px; cursor: pointer; font-weight: bold; font-size: 15px;">
        </form>
    </body>
    </html>
    '''

@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        return redirect(url_for('login'))
        
    username = session.get('username')
    role = session.get('role')
    
    classes_html = ""
    for class_id, class_name in CLASSES_DICT.items():
        classes_html += f'''
            <div style="background: #ffffff; border: 1px solid #ddd; padding: 15px; border-radius: 8px; text-align: center; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
                <h4 style="margin: 0 0 10px 0; color: #333;">{class_name}</h4>
                <a href="/classroom/{class_id}" style="padding: 8px 15px; background: #28a745; color: white; text-decoration: none; border-radius: 5px; font-size: 14px; display: inline-block;">دخول الصف الصوتي</a>
            </div>
        '''

    return f'''
    <html dir="rtl">
    <head><title>لوحة التحكم - المنصة المدرسية</title></head>
    <body style="font-family: Arial, sans-serif; background-color: #f4f6f9; margin: 0; padding: 20px;">
        <div style="max-width: 1000px; margin: auto;">
            <div style="background: #007bff; color: white; padding: 20px; border-radius: 10px; display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <h2 style="margin: 0;">مرحباً بك، {username}</h2>
                    <p style="margin: 5px 0 0 0;">الصلاحية: <b>{role}</b></p>
                </div>
                <div>
                    <a href="/change_password" style="background: #ffc107; color: black; padding: 10px 15px; text-decoration: none; border-radius: 5px; font-weight: bold; margin-left: 10px;">تغيير كلمة المرور</a>
                    <a href="/login" style="background: #dc3545; color: white; padding: 10px 15px; text-decoration: none; border-radius: 5px; font-weight: bold;">تسجيل الخروج</a>
                </div>
            </div>
            
            <h3 style="margin-top: 30px; border-bottom: 2px solid #007bff; padding-bottom: 10px; color: #333;">قائمة الصفوف الدراسية (دخول مفتوح وغير محدود):</h3>
            
            <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 15px; margin-top: 20px;">
                {classes_html}
            </div>
        </div>
    </body>
    </html>
    '''

@app.route('/classroom/<class_id>')
def classroom(class_id):
    if 'username' not in session:
        return redirect(url_for('login'))
        
    username = session.get('username')
    role = session.get('role')
    
    class_name = CLASSES_DICT.get(class_id, "الصف الدراسي")

    return f'''
    <html dir="rtl">
    <head><title>{class_name} - الغرفة الصوتية</title></head>
    <body style="font-family: Arial, sans-serif; background-color: #f4f6f9; margin: 0; padding: 20px; text-align: center;">
        <div style="max-width: 700px; margin: auto; background: white; padding: 30px; border-radius: 10px; border: 1px solid #ccc; box-shadow: 0 4px 8px rgba(0,0,0,0.1);">
            <h2 style="color: #007bff; margin-top: 0;">{class_name}</h2>
            <p style="font-size: 16px; color: #555;">أنت الآن داخل الغرفة الصوتية المفتوحة لهذا الصف.</p>
            <p style="font-size: 14px; color: #28a745; font-weight: bold;">[ السعة: غير محدودة لتسع جميع طلاب الصف ]</p>
            <hr style="border: 0; border-top: 1px solid #eee; margin: 20px 0;">
            <div style="background: #e9ecef; padding: 20px; border-radius: 8px; margin-bottom: 20px;">
                <p style="font-weight: bold; margin: 0;">الحالة: جاهز لبدء البث الصوتي الجماعي</p>
                <span style="display: inline-block; width: 12px; height: 12px; background: #28a745; border-radius: 50%; margin-top: 10px;"></span> النظام المحلي يعمل بكفاءة
            </div>
            <br>
            <a href="/dashboard" style="background: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; font-weight: bold;">العودة إلى لوحة التحكم</a>
        </div>
    </body>
    </html>
    '''

@app.route('/change_password', methods=['GET', 'POST'])
def change_password():
    if 'username' not in session:
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

    return f'''
    <html dir="rtl">
    <head><title>تغيير كلمة المرور</title></head>
    <body style="font-family: Arial, sans-serif; background-color: #f4f6f9; text-align: center; padding-top: 50px;">
        <div style="display: inline-block; background: white; padding: 30px; border-radius: 10px; border: 1px solid #ccc; width: 350px; box-shadow: 0 4px 8px rgba(0,0,0,0.1);">
            <h2>تغيير كلمة المرور</h2>
            {message}
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
    '''

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True, port=5000)
