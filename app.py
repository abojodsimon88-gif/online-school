from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3

app = Flask(__name__)
app.secret_key = 'simon_secure_school_key'

def get_db_connection():
    conn = sqlite3.connect('school.db')
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    return "مرحباً بك في منصة المدرسة الإلكترونية الآمنة! السيرفر يعمل بنجاح."

if __name__ == '__main__':
    app.run(debug=True, port=5000)