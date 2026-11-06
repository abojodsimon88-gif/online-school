import os
from flask import Flask, render_template_string

app = Flask(__name__)

# الصفحة الرئيسية للمنصة المدرسية
@app.route('/')
def home():
    html_content = """
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <title>منصة المدرسة الإلكترونية</title>
        <style>
            body { font-family: Tahoma, sans-serif; background-color: #f4f7f6; text-align: center; padding: 50px; }
            h1 { color: #2c3e50; }
            p { color: #7f8c8d; font-size: 18px; }
            .box { background: white; padding: 30px; border-radius: 10px; box-shadow: 0px 4px 10px rgba(0,0,0,0.1); display: inline-block; }
        </style>
    </head>
    <body>
        <div class="box">
            <h1>مرحباً بك في منصة المدرسة الإلكترونية 🚀</h1>
            <p>النظام أونلاين 24/7 وجاهز لإدارة الحصص الافتراضية والصفوف الدراسية.</p>
        </div>
    </body>
    </html>
    """
    return render_template_string(html_content)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
