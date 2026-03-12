from flask import Flask, render_template, redirect, url_for, request, make_response
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask_mail import Mail, Message

from datetime import datetime
from collections import defaultdict

import os
import random

import matplotlib
import matplotlib.pyplot as plt
import numpy as np

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from io import BytesIO

matplotlib.use('Agg')

app = Flask(__name__)

app.config['SECRET_KEY'] = 'supersecretkey'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///money_wizard.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# ================= MAIL CONFIG =================

app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'l72727663@gmail.com'
app.config['MAIL_PASSWORD'] = 'yugd amse lfpa uihk'

mail = Mail(app)

otp_store = {}

# ================= FILE UPLOAD =================

UPLOAD_FOLDER = 'static/profile_pics'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# ================= MODELS =================

class User(UserMixin, db.Model):

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100))
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(200))
    profile_pic = db.Column(db.String(200), default='default.png')
    budget = db.Column(db.Numeric(12,2), default=5000)


class Expense(db.Model):

    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(100), nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# ================= AI INSIGHTS =================

def generate_ai_insights(user, expenses):

    insights = []

    total = sum(e.amount for e in expenses)

    if total == 0:
        insights.append("No expenses recorded this month.")
        return insights

    category_totals = defaultdict(float)

    for e in expenses:
        category_totals[e.category] += e.amount

    top = max(category_totals, key=category_totals.get)

    insights.append(f"Highest spending category: {top}")
    insights.append(f"Total spending: ₹{total}")

    if total > float(user.budget):
        insights.append(f"You exceeded your budget by ₹{total-float(user.budget):,.2f}")
    else:
        insights.append(f"You are within budget.")

    insights.append("Reducing expenses by 10% can significantly improve savings.")

    return insights

# ================= PDF GENERATOR =================

def generate_pdf_report(user, expenses):

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)

    width, height = A4

    total = sum(e.amount for e in expenses)
    remaining = float(user.budget) - float(total)

    bg = "static/report_bg.png"

    # ---------- BACKGROUND ----------
    if os.path.exists(bg):
        pdf.drawImage(bg, 0, 0, width=width, height=height)

    # Dark overlay
    pdf.setFillColorRGB(0,0,0)
    pdf.setFillAlpha(0.60)
    pdf.rect(0,0,width,height,fill=1,stroke=0)
    pdf.setFillAlpha(1)

    # ---------- TITLE ----------
    pdf.setFillColorRGB(1,1,1)
    pdf.setFont("Helvetica-Bold",30)
    pdf.drawCentredString(width/2, height-60, "Money Wizard Report")

    # ---------- SUMMARY ----------
    pdf.setFont("Helvetica",14)

    pdf.drawString(70, height-110, f"User: {user.username}")
    pdf.drawString(70, height-130, f"Budget: ₹{float(user.budget):,.2f}")
    pdf.drawString(70, height-150, f"Total Spent: ₹{total:,.2f}")
    pdf.drawString(70, height-170, f"Remaining: ₹{remaining:,.2f}")

    # Divider line
    pdf.setLineWidth(1)
    pdf.line(60, height-190, width-60, height-190)

    # ---------- CHART FILE PATHS ----------
    pie_chart = "static/report_chart.png"
    month_chart = "static/month_chart.png"
    quarter_chart = "static/quarter_chart.png"
    budget_chart = "static/budget_chart.png"

    # ---------- ROW 1 ----------
    pdf.setFont("Helvetica-Bold",18)

    pdf.drawString(80, 500, "Expense Distribution")
    pdf.drawString(340, 500, "Monthly Trend")

    if os.path.exists(pie_chart):
        pdf.drawImage(pie_chart, 70, 320, width=250, height=170)

    if os.path.exists(month_chart):
        pdf.drawImage(month_chart, 330, 320, width=250, height=170)

    # ---------- ROW 2 ----------
    pdf.drawString(80, 290, "Quarterly Analysis")
    pdf.drawString(340, 290, "Budget vs Spending")

    if os.path.exists(quarter_chart):
        pdf.drawImage(quarter_chart, 70, 110, width=250, height=170)

    if os.path.exists(budget_chart):
        pdf.drawImage(budget_chart, 330, 110, width=250, height=170)

    # ---------- AI INSIGHTS ----------
    insights = generate_ai_insights(user, expenses)

    pdf.setFont("Helvetica-Bold",18)
    pdf.drawString(80, 90, "AI Financial Insights")

    pdf.setFont("Helvetica",12)

    y = 70
    for tip in insights:
        pdf.drawString(90, y, f"• {tip}")
        y -= 18

   

    # ---------- SAVE ----------
    pdf.save()

    buffer.seek(0)

    return buffer
# ================= BUDGET ALERT EMAIL =================

def send_budget_alert(user, total):

    expenses = Expense.query.filter_by(user_id=user.id).all()

    pdf_buffer = generate_pdf_report(user, expenses)

    msg = Message(
        "⚠ Budget Limit Exceeded – Money Wizard",
        sender=app.config['MAIL_USERNAME'],
        recipients=[user.email]
    )

    msg.body = f"""

Hello {user.username},

This is an automated notification from Money Wizard.

Our system detected that your current monthly spending has exceeded your predefined budget.

Budget Set: ₹{user.budget}
Current Spending: ₹{total}

To help you stay on track with your financial goals, we recommend reviewing your expenses and identifying categories where spending can be reduced.

A detailed budget analysis report is attached to this email for your reference.

Stay financially smart with Money Wizard.

Regards,
Money Wizard Team
Smart Budget • Better Decisions
"""

    msg.attach(
    "budget_report.pdf",
    "application/pdf",
    pdf_buffer.read()
)

    mail.send(msg)

# ================= HOME =================

@app.route('/')
def home():
    return redirect(url_for('login'))

# ================= REGISTER =================

@app.route('/register', methods=['GET', 'POST'])
def register():

    bg_video = "videos/main.mp4"

    if request.method == 'POST':

        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')

        existing_user = User.query.filter_by(email=email).first()

        if existing_user:
            return redirect(url_for('login'))

        hashed_password = generate_password_hash(password)

        new_user = User(
            username=username,
            email=email,
            password=hashed_password
        )

        db.session.add(new_user)
        db.session.commit()

        # ===== SEND OTP =====

        otp = random.randint(100000, 999999)
        otp_store[email] = otp

        msg = Message(
            "Money Wizard Email Verification",
            sender=app.config['MAIL_USERNAME'],
            recipients=[email]
        )

        msg.body = f"Your Money Wizard verification code is: {otp}"

        mail.send(msg)

        return redirect(url_for('verify_email', email=email))

    return render_template('register.html', bg_video=bg_video)


# ================= VERIFY EMAIL =================

@app.route('/verify/<email>', methods=['GET', 'POST'])
def verify_email(email):

    if request.method == 'POST':

        user_otp = request.form.get('otp')

        if str(otp_store.get(email)) == user_otp:

            otp_store.pop(email)

            return redirect(url_for('login'))

    return render_template("verify_email.html", email=email)

# ================= LOGIN =================

@app.route('/login', methods=['GET','POST'])
def login():

    bg_video = "videos/main.mp4"

    if request.method == 'POST':

        identifier = request.form.get('identifier')
        password = request.form.get('password')

        user = User.query.filter(
            (User.email == identifier) |
            (User.username == identifier)
        ).first()

        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('dashboard'))

    return render_template("login.html", bg_video=bg_video)


# ================= DASHBOARD =================

@app.route("/dashboard")
@login_required
def dashboard():

    selected_month = request.args.get("month", type=int)
    selected_year = request.args.get("year", type=int)

    if not selected_month:
        selected_month = datetime.now().month

    if not selected_year:
        selected_year = datetime.now().year

    expenses = Expense.query.filter(
        db.extract('month', Expense.date) == selected_month,
        db.extract('year', Expense.date) == selected_year,
        Expense.user_id == current_user.id
    ).all()

    # ✅ CALCULATE VALUES
    total_spent = sum(exp.amount for exp in expenses)

    budget = float(current_user.budget)

    remaining = budget - total_spent

    percentage = 0
    if budget > 0:
        percentage = (total_spent / budget) * 100

    # Chart data
    category_totals = defaultdict(float)

    for exp in expenses:
        category_totals[exp.category] += exp.amount

    labels = list(category_totals.keys())
    values = list(category_totals.values())

    return render_template(
        "dashboard.html",
        expenses=expenses,
        total_spent=total_spent,
        budget=budget,
        remaining=remaining,
        percentage=percentage,
        labels=labels,
        values=values,
        selected_month=selected_month,
        selected_year=selected_year
    )
@app.route('/profile', methods=['GET','POST'])
@login_required
def profile():

    bg_video = "videos/main.mp4"

    if request.method == 'POST':

        current_user.username = request.form.get('username')

        new_budget = request.form.get('budget')
        if new_budget:
           current_user.budget = round(float(new_budget), 2)

        new_password = request.form.get('password')
        if new_password:
            current_user.password = generate_password_hash(new_password)

        file = request.files.get('profile_pic')

        if file and file.filename != "":
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)

            current_user.profile_pic = filename

        db.session.commit()

        return redirect(url_for('profile'))

    return render_template(
        "profile.html",
        bg_video=bg_video
    )
@app.route('/request-delete-account', methods=['POST'])
@login_required
def request_delete_account():

    email = current_user.email

    otp = random.randint(100000,999999)
    otp_store[email] = otp

    msg = Message(
        "Money Wizard Account Deletion Verification",
        sender=app.config['MAIL_USERNAME'],
        recipients=[email]
    )

    msg.body = f"""
Hello {current_user.username},

We received a request to permanently delete your Money Wizard account.

Verification Code: {otp}

Enter this code to confirm account deletion.

If you did not request this, please ignore this email.

Money Wizard Security Team
"""

    mail.send(msg)

    return redirect(url_for('confirm_delete_account'))

@app.route('/confirm-delete-account', methods=['GET','POST'])
@login_required
def confirm_delete_account():

    if request.method == 'POST':

        user_otp = request.form.get("otp")

        if str(otp_store.get(current_user.email)) == user_otp:

            otp_store.pop(current_user.email)

            user_id = current_user.id

            Expense.query.filter_by(user_id=user_id).delete()
            User.query.filter_by(id=user_id).delete()

            db.session.commit()

            logout_user()

            return redirect(url_for('register'))

    return render_template("confirm_delete.html")


# ================= ADD EXPENSE =================

@app.route('/add',methods=['GET','POST'])
@login_required
def add_expense():

    if request.method == 'POST':

        amount = float(request.form['amount'])
        category = request.form['category']

        exp = Expense(
            amount=amount,
            category=category,
            user_id=current_user.id
        )

        db.session.add(exp)
        db.session.commit()

        # ===== CHECK BUDGET =====

        expenses = Expense.query.filter_by(user_id=current_user.id).all()

        total = sum(e.amount for e in expenses)

        if total > float(current_user.budget):

            send_budget_alert(current_user, total)

        return redirect(url_for('dashboard'))

    return render_template("add_expense.html")

# ================= DOWNLOAD PDF =================

@app.route('/download-pdf')
@login_required
def download_pdf():

    expenses = Expense.query.filter_by(user_id=current_user.id).all()

    pdf_buffer = generate_pdf_report(current_user, expenses)

    response = make_response(pdf_buffer.read())

    response.headers['Content-Type']='application/pdf'
    response.headers['Content-Disposition']='attachment; filename=budget_report.pdf'

    return response

# ================= LOGOUT =================

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# ================= DATABASE =================

with app.app_context():
    db.create_all()

# ================= RUN =================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)