from flask import Flask, render_template, redirect, url_for, request, make_response, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask_mail import Mail, Message

from datetime import datetime
from collections import defaultdict

import os
import random
import logging

import matplotlib
import matplotlib.pyplot as plt
import numpy as np

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from io import BytesIO

matplotlib.use('Agg')

app = Flask(__name__)

# ==============================
# SECURITY CONFIG
# ==============================

app.config['SECRET_KEY'] = os.environ.get("SECRET_KEY", "fallback-dev-key")

# ==============================
# DATABASE CONFIG
# ==============================

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///money_wizard.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# ==============================
# MAIL CONFIG (GMAIL SMTP)
# ==============================

app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get("MAIL_USERNAME")
app.config['MAIL_PASSWORD'] = os.environ.get("MAIL_PASSWORD")
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get("MAIL_USERNAME")

# Suppress mail errors if credentials not configured
if not app.config['MAIL_USERNAME'] or not app.config['MAIL_PASSWORD']:
    app.config['MAIL_SUPPRESS_SEND'] = True

# ==============================
# INITIALIZE EXTENSIONS
# ==============================

db = SQLAlchemy(app)
mail = Mail(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# ==============================
# FILE UPLOAD
# ==============================

UPLOAD_FOLDER = 'static/profile_pics'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# ==============================
# MODULE-LEVEL OTP STORE
# (must be here, not inside any function)
# ==============================

otp_store = {}

# ================= MODELS =================

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100))
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(200))
    profile_pic = db.Column(db.String(200), default='default.png')
    budget = db.Column(db.Numeric(12, 2), default=5000)
    alert_sent = db.Column(db.Boolean, default=False)


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
    insights.append(f"Total spending: ₹{total:,.2f}")

    if total > float(user.budget):
        insights.append(f"You exceeded your budget by ₹{total - float(user.budget):,.2f}")
    else:
        insights.append("You are within budget. Great work!")

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
    if os.path.exists(bg):
        pdf.drawImage(bg, 0, 0, width=width, height=height)

    pdf.setFillColorRGB(0, 0, 0)
    pdf.setFillAlpha(0.60)
    pdf.rect(0, 0, width, height, fill=1, stroke=0)
    pdf.setFillAlpha(1)

    pdf.setFillColorRGB(1, 1, 1)
    pdf.setFont("Helvetica-Bold", 30)
    pdf.drawCentredString(width / 2, height - 60, "Money Wizard Report")

    pdf.setFont("Helvetica", 14)
    pdf.drawString(70, height - 110, f"User: {user.username}")
    pdf.drawString(70, height - 130, f"Budget: Rs.{float(user.budget):,.2f}")
    pdf.drawString(70, height - 150, f"Total Spent: Rs.{total:,.2f}")
    pdf.drawString(70, height - 170, f"Remaining: Rs.{remaining:,.2f}")

    pdf.setLineWidth(1)
    pdf.line(60, height - 190, width - 60, height - 190)

    pie_chart = "static/report_chart.png"
    month_chart = "static/month_chart.png"
    quarter_chart = "static/quarter_chart.png"
    budget_chart = "static/budget_chart.png"

    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(80, 500, "Expense Distribution")
    pdf.drawString(340, 500, "Monthly Trend")

    if os.path.exists(pie_chart):
        pdf.drawImage(pie_chart, 70, 320, width=250, height=170)
    if os.path.exists(month_chart):
        pdf.drawImage(month_chart, 330, 320, width=250, height=170)

    pdf.drawString(80, 290, "Quarterly Analysis")
    pdf.drawString(340, 290, "Budget vs Spending")

    if os.path.exists(quarter_chart):
        pdf.drawImage(quarter_chart, 70, 110, width=250, height=170)
    if os.path.exists(budget_chart):
        pdf.drawImage(budget_chart, 330, 110, width=250, height=170)

    insights = generate_ai_insights(user, expenses)
    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(80, 90, "AI Financial Insights")
    pdf.setFont("Helvetica", 12)
    y = 70
    for tip in insights:
        pdf.drawString(90, y, f"• {tip}")
        y -= 18

    pdf.save()
    buffer.seek(0)
    return buffer

# ================= BUDGET ALERT EMAIL =================

def send_budget_alert(user, total):
    """
    Send a budget-exceeded email with PDF report attached.
    Returns True on success, False on failure.
    """
    try:
        expenses = Expense.query.filter_by(user_id=user.id).all()
        pdf_buffer = generate_pdf_report(user, expenses)

        overage = total - float(user.budget)

        msg = Message(
            subject="⚠ Budget Limit Exceeded – Money Wizard",
            recipients=[user.email]
        )

        msg.body = f"""Hello {user.username},

Your total spending has exceeded your monthly budget.

  Budget:    ₹{float(user.budget):,.2f}
  Spent:     ₹{total:,.2f}
  Over by:   ₹{overage:,.2f}

A full expense report is attached to this email.
Log in to Money Wizard to review your spending details.

– The Money Wizard Team
"""
        msg.attach(
            "budget_report.pdf",
            "application/pdf",
            pdf_buffer.read()
        )

        mail.send(msg)
        logging.info(f"Budget alert email sent to {user.email}")
        return True

    except Exception as e:
        logging.error(f"Budget alert email failed for {user.email}: {e}")
        return False

# ================= HOME =================

@app.route('/')
def home():
    return redirect(url_for('login'))

# ================= REGISTER =================

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('An account with that email already exists.', 'error')
            return redirect(url_for('login'))

        hashed_password = generate_password_hash(password)
        new_user = User(username=username, email=email, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()

        # Generate OTP and store it at module level
        otp = random.randint(100000, 999999)
        otp_store[email] = otp

        try:
            msg = Message(
                subject="Money Wizard – Email Verification",
                recipients=[email]
            )
            msg.body = f"Hello {username},\n\nYour Money Wizard verification code is: {otp}\n\nThis code expires after use.\n\n– Money Wizard Team"
            mail.send(msg)
        except Exception as e:
            logging.error(f"Verification email failed: {e}")

        return redirect(url_for('verify_email', email=email))

    return render_template('register.html')

# ================= VERIFY EMAIL =================

@app.route('/verify/<email>', methods=['GET', 'POST'])
def verify_email(email):
    if request.method == 'POST':
        user_otp = request.form.get('otp')

        stored = otp_store.get(email)
        if stored and str(stored) == user_otp:
            otp_store.pop(email, None)
            flash('Email verified! You can now log in.', 'success')
            return redirect(url_for('login'))
        else:
            flash('Invalid code. Please try again.', 'error')

    return render_template("verify_email.html", email=email)

# ================= LOGIN =================

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        identifier = request.form.get('identifier')
        password = request.form.get('password')

        user = User.query.filter(
            (User.email == identifier) | (User.username == identifier)
        ).first()

        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid credentials. Please try again.', 'error')

    return render_template("login.html")

# ================= DASHBOARD =================

@app.route("/dashboard")
@login_required
def dashboard():
    selected_month = request.args.get("month", type=int) or datetime.now().month
    selected_year = request.args.get("year", type=int) or datetime.now().year

    expenses = Expense.query.filter(
        db.extract('month', Expense.date) == selected_month,
        db.extract('year', Expense.date) == selected_year,
        Expense.user_id == current_user.id
    ).all()

    total_spent = sum(exp.amount for exp in expenses)
    budget = float(current_user.budget)
    remaining = budget - total_spent
    percentage = (total_spent / budget * 100) if budget > 0 else 0

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

# ================= PROFILE =================

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        current_user.username = request.form.get('username')

        new_budget = request.form.get('budget')
        if new_budget:
            current_user.budget = round(float(new_budget), 2)
            # Reset alert flag when budget is updated
            current_user.alert_sent = False

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
        flash('Profile updated successfully.', 'success')
        return redirect(url_for('profile'))

    return render_template("profile.html")

# ================= REQUEST DELETE ACCOUNT =================

@app.route('/request-delete-account', methods=['POST'])
@login_required
def request_delete_account():
    email = current_user.email
    otp = random.randint(100000, 999999)
    otp_store[email] = otp

    try:
        msg = Message(
            subject="Money Wizard – Account Deletion Verification",
            recipients=[email]
        )
        msg.body = f"""Hello {current_user.username},

We received a request to permanently delete your Money Wizard account.

Verification Code: {otp}

Enter this code to confirm deletion. If you did not request this, please ignore this email.

– Money Wizard Security Team
"""
        mail.send(msg)
        flash('A verification code has been sent to your email.', 'success')
    except Exception as e:
        logging.error(f"Delete account email failed: {e}")
        flash('Could not send verification email. Please try again.', 'error')
        return redirect(url_for('profile'))

    return redirect(url_for('confirm_delete_account'))

# ================= CONFIRM DELETE ACCOUNT =================

@app.route('/confirm-delete-account', methods=['GET', 'POST'])
@login_required
def confirm_delete_account():
    if request.method == 'POST':
        user_otp = request.form.get("otp")
        stored = otp_store.get(current_user.email)

        if stored and str(stored) == user_otp:
            otp_store.pop(current_user.email, None)
            user_id = current_user.id

            Expense.query.filter_by(user_id=user_id).delete()
            User.query.filter_by(id=user_id).delete()
            db.session.commit()

            logout_user()
            return redirect(url_for('register'))
        else:
            flash('Invalid verification code. Please try again.', 'error')

    return render_template("confirm_delete.html")

# ================= ADD EXPENSE =================

@app.route('/add', methods=['GET', 'POST'])
@login_required
def add_expense():
    if request.method == 'POST':
        amount = float(request.form['amount'])
        category = request.form['category']

        # Get old total (current month) before adding
        now = datetime.now()
        old_expenses = Expense.query.filter(
            db.extract('month', Expense.date) == now.month,
            db.extract('year', Expense.date) == now.year,
            Expense.user_id == current_user.id
        ).all()
        old_total = sum(e.amount for e in old_expenses)

        # Save new expense
        exp = Expense(amount=amount, category=category, user_id=current_user.id)
        db.session.add(exp)
        db.session.commit()

        # New total (current month)
        new_total = old_total + amount
        budget = float(current_user.budget)

        # Only send alert the first time spending crosses the budget threshold
        if new_total > budget and not current_user.alert_sent:
            success = send_budget_alert(current_user, new_total)
            current_user.alert_sent = True
            db.session.commit()

            if success:
                flash(
                    f'⚠ You\'ve exceeded your budget of ₹{budget:,.2f}! '
                    f'You\'ve spent ₹{new_total:,.2f} this month. '
                    f'A detailed report has been sent to {current_user.email}.',
                    'budget_alert'
                )
            else:
                flash(
                    f'⚠ You\'ve exceeded your budget of ₹{budget:,.2f}! '
                    f'You\'ve spent ₹{new_total:,.2f} this month.',
                    'budget_alert'
                )
        elif new_total > budget:
            # Already over budget, just warn in-app without another email
            flash(
                f'⚠ You are ₹{new_total - budget:,.2f} over your budget.',
                'budget_warning'
            )

        return redirect(url_for('dashboard'))

    return render_template("add_expense.html")

# ================= DOWNLOAD PDF =================

@app.route('/download-pdf')
@login_required
def download_pdf():
    expenses = Expense.query.filter_by(user_id=current_user.id).all()
    pdf_buffer = generate_pdf_report(current_user, expenses)

    response = make_response(pdf_buffer.read())
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = 'attachment; filename=budget_report.pdf'
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
    # Migration: add alert_sent column if it doesn't exist yet
    try:
        with db.engine.connect() as conn:
            conn.execute(db.text("ALTER TABLE user ADD COLUMN alert_sent BOOLEAN DEFAULT 0"))
            conn.commit()
    except Exception:
        pass  # Column already exists, that's fine

# ================= RUN =================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
