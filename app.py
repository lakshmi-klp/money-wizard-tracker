from flask import Flask, render_template, redirect, url_for, request, make_response, flash, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask_mail import Mail, Message

from datetime import datetime, timedelta
from collections import defaultdict

import os
import random
import logging

import matplotlib
import matplotlib.pyplot as plt
import numpy as np

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.lib.utils import ImageReader
from io import BytesIO

matplotlib.use('Agg')

app = Flask(__name__)

# ==============================
# CONFIG
# ==============================

app.config['SECRET_KEY'] = os.environ.get("SECRET_KEY", "fallback-dev-key")
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///money_wizard.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get("MAIL_USERNAME")
app.config['MAIL_PASSWORD'] = os.environ.get("MAIL_PASSWORD")
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get("MAIL_USERNAME")

if not app.config['MAIL_USERNAME'] or not app.config['MAIL_PASSWORD']:
    app.config['MAIL_SUPPRESS_SEND'] = True

# ==============================
# EXTENSIONS
# ==============================

db = SQLAlchemy(app)
mail = Mail(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

UPLOAD_FOLDER = 'static/profile_pics'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Module-level OTP store
otp_store = {}

# ==============================
# MODELS
# ==============================

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100))
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(200))
    profile_pic = db.Column(db.String(200), default='default.png')
    budget = db.Column(db.Numeric(12, 2), default=5000)
    alert_sent = db.Column(db.Boolean, default=False)
    is_admin = db.Column(db.Boolean, default=False)
    last_login = db.Column(db.DateTime)
    reports_downloaded = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(100), nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# ==============================
# ADMIN PROTECTION DECORATOR
# ==============================

from functools import wraps

def admin_required(f):
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated

# ==============================
# CHART GENERATORS (per-user, in-memory)
# ==============================

CHART_COLORS = [
    '#a78bfa', '#60a5fa', '#34d399', '#f472b6',
    '#fbbf24', '#fb923c', '#f87171', '#4ade80',
    '#38bdf8', '#c084fc'
]
DARK_BG = '#0f0c29'
TEXT_COLOR = 'white'


def _save_fig(fig):
    """Save matplotlib figure to BytesIO and return it."""
    buf = BytesIO()
    fig.savefig(buf, format='png', dpi=110, bbox_inches='tight', facecolor=DARK_BG)
    buf.seek(0)
    plt.close(fig)
    return buf


def chart_category_pie(expenses):
    """Pie/donut chart of spending by category for this user's expenses."""
    totals = defaultdict(float)
    for e in expenses:
        totals[e.category] += e.amount

    if not totals:
        return None

    labels = list(totals.keys())
    values = list(totals.values())
    colors = (CHART_COLORS * 4)[:len(values)]

    fig, ax = plt.subplots(figsize=(3.2, 2.6), facecolor=DARK_BG)
    ax.set_facecolor(DARK_BG)
    wedges, texts, autotexts = ax.pie(
        values, labels=None, autopct='%1.0f%%',
        colors=colors, startangle=140,
        wedgeprops=dict(width=0.6, edgecolor='none'),
        pctdistance=0.75
    )
    for at in autotexts:
        at.set_color(TEXT_COLOR)
        at.set_fontsize(7)
    ax.legend(labels, loc='lower center', bbox_to_anchor=(0.5, -0.22),
              ncol=3, fontsize=6.5, frameon=False,
              labelcolor=TEXT_COLOR)
    fig.tight_layout()
    return _save_fig(fig)


def chart_monthly_trend(user_id, year):
    """Line chart: monthly spending across 12 months for this user."""
    monthly = []
    for m in range(1, 13):
        exps = Expense.query.filter(
            db.extract('month', Expense.date) == m,
            db.extract('year', Expense.date) == year,
            Expense.user_id == user_id
        ).all()
        monthly.append(sum(e.amount for e in exps))

    month_names = ['Jan','Feb','Mar','Apr','May','Jun',
                   'Jul','Aug','Sep','Oct','Nov','Dec']

    fig, ax = plt.subplots(figsize=(3.2, 2.4), facecolor=DARK_BG)
    ax.set_facecolor(DARK_BG)
    ax.plot(month_names, monthly, color='#a78bfa', linewidth=2, marker='o',
            markersize=4, markerfacecolor='#7c3aed')
    ax.fill_between(range(12), monthly, alpha=0.15, color='#a78bfa')
    ax.set_xticks(range(12))
    ax.set_xticklabels(month_names, fontsize=6.5, color=TEXT_COLOR, rotation=45)
    ax.tick_params(axis='y', colors=TEXT_COLOR, labelsize=7)
    ax.spines[['top','right']].set_visible(False)
    ax.spines[['left','bottom']].set_color('rgba(255,255,255,0.2)')
    ax.spines['left'].set_color('#444')
    ax.spines['bottom'].set_color('#444')
    ax.yaxis.label.set_color(TEXT_COLOR)
    ax.xaxis.label.set_color(TEXT_COLOR)
    fig.tight_layout()
    return _save_fig(fig)


def chart_quarterly(user_id, year):
    """Bar chart: quarterly spending for this user."""
    quarters = {'Q1': 0, 'Q2': 0, 'Q3': 0, 'Q4': 0}
    for m in range(1, 13):
        exps = Expense.query.filter(
            db.extract('month', Expense.date) == m,
            db.extract('year', Expense.date) == year,
            Expense.user_id == user_id
        ).all()
        total = sum(e.amount for e in exps)
        if m <= 3:   quarters['Q1'] += total
        elif m <= 6: quarters['Q2'] += total
        elif m <= 9: quarters['Q3'] += total
        else:        quarters['Q4'] += total

    fig, ax = plt.subplots(figsize=(3.2, 2.4), facecolor=DARK_BG)
    ax.set_facecolor(DARK_BG)
    bars = ax.bar(list(quarters.keys()), list(quarters.values()),
                  color=CHART_COLORS[:4], edgecolor='none', width=0.5)
    ax.tick_params(colors=TEXT_COLOR, labelsize=7)
    ax.spines[['top','right']].set_visible(False)
    ax.spines['left'].set_color('#444')
    ax.spines['bottom'].set_color('#444')
    for bar in bars:
        h = bar.get_height()
        if h > 0:
            ax.text(bar.get_x() + bar.get_width()/2, h + h*0.03,
                    f'₹{h:,.0f}', ha='center', va='bottom',
                    fontsize=6.5, color=TEXT_COLOR)
    fig.tight_layout()
    return _save_fig(fig)


def chart_budget_vs_spending(user, expenses):
    """Horizontal bar: budget vs actual spending."""
    total = sum(e.amount for e in expenses)
    budget = float(user.budget)

    fig, ax = plt.subplots(figsize=(3.2, 1.8), facecolor=DARK_BG)
    ax.set_facecolor(DARK_BG)

    ax.barh(['Budget'], [budget], color='#a78bfa', height=0.4)
    color = '#f87171' if total > budget else '#34d399'
    ax.barh(['Spent'], [total], color=color, height=0.4)

    ax.tick_params(colors=TEXT_COLOR, labelsize=7)
    ax.spines[['top','right','left']].set_visible(False)
    ax.spines['bottom'].set_color('#444')
    ax.set_xlabel('₹ Amount', color=TEXT_COLOR, fontsize=7)

    for i, val in enumerate([budget, total]):
        ax.text(val + budget * 0.02, i, f'₹{val:,.0f}',
                va='center', fontsize=7, color=TEXT_COLOR)

    fig.tight_layout()
    return _save_fig(fig)

# ==============================
# AI INSIGHTS
# ==============================

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
    insights.append(f"Highest spending category: {top} (₹{category_totals[top]:,.2f})")
    insights.append(f"Total spending this period: ₹{total:,.2f}")

    budget = float(user.budget)
    if total > budget:
        insights.append(f"Over budget by ₹{total - budget:,.2f}. Consider cutting discretionary spending.")
    else:
        savings = budget - total
        insights.append(f"Within budget — ₹{savings:,.2f} available. Great discipline!")

    if len(category_totals) > 1:
        avg = total / len(category_totals)
        over_avg = [k for k, v in category_totals.items() if v > avg * 1.5]
        if over_avg:
            insights.append(f"High spend in: {', '.join(over_avg)}. Worth reviewing.")

    insights.append("Tip: Saving 20% of income monthly builds a 6-month emergency fund in 3 years.")
    return insights

# ==============================
# PDF REPORT — FULLY DYNAMIC PER USER
# ==============================

def generate_pdf_report(user, expenses):
    buffer = BytesIO()
    pdf = rl_canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    total = sum(e.amount for e in expenses)
    remaining = float(user.budget) - total

    # --- Background ---
    bg_path = "static/report_bg.png"
    if os.path.exists(bg_path):
        pdf.drawImage(bg_path, 0, 0, width=width, height=height)
    else:
        pdf.setFillColorRGB(0.06, 0.05, 0.16)
        pdf.rect(0, 0, width, height, fill=1, stroke=0)

    pdf.setFillColorRGB(0, 0, 0)
    pdf.setFillAlpha(0.60)
    pdf.rect(0, 0, width, height, fill=1, stroke=0)
    pdf.setFillAlpha(1)

    # --- Header ---
    pdf.setFillColorRGB(1, 1, 1)
    pdf.setFont("Helvetica-Bold", 28)
    pdf.drawCentredString(width / 2, height - 55, "Money Wizard Report")

    pdf.setFont("Helvetica", 13)
    pdf.drawString(55, height - 90,  f"User:          {user.username}")
    pdf.drawString(55, height - 108, f"Email:         {user.email}")
    pdf.drawString(55, height - 126, f"Budget:        Rs.{float(user.budget):,.2f}")
    pdf.drawString(55, height - 144, f"Total Spent:   Rs.{total:,.2f}")
    pdf.drawString(55, height - 162, f"Remaining:     Rs.{remaining:,.2f}")

    generated_on = datetime.now().strftime("%d %b %Y, %I:%M %p")
    pdf.setFont("Helvetica", 9)
    pdf.setFillColorRGB(0.7, 0.7, 0.7)
    pdf.drawRightString(width - 55, height - 162, f"Generated: {generated_on}")

    pdf.setFillColorRGB(1, 1, 1)
    pdf.setLineWidth(0.5)
    pdf.line(50, height - 175, width - 50, height - 175)

    # --- Generate charts dynamically for this user ---
    year = datetime.now().year
    pie_buf     = chart_category_pie(expenses)
    month_buf   = chart_monthly_trend(user.id, year)
    quarter_buf = chart_quarterly(user.id, year)
    budget_buf  = chart_budget_vs_spending(user, expenses)

    # Row 1: Pie + Monthly
    row1_y = height - 390
    pdf.setFont("Helvetica-Bold", 14)
    pdf.setFillColorRGB(0.75, 0.6, 1)
    pdf.drawString(55,  row1_y + 185, "Expense Distribution")
    pdf.drawString(315, row1_y + 185, "Monthly Trend")

    if pie_buf:
        pdf.drawImage(ImageReader(pie_buf),  50, row1_y, width=240, height=175)
    else:
        pdf.setFillColorRGB(0.5, 0.5, 0.5)
        pdf.setFont("Helvetica", 10)
        pdf.drawString(100, row1_y + 80, "No expense data")

    if month_buf:
        pdf.drawImage(ImageReader(month_buf), 310, row1_y, width=240, height=175)

    # Row 2: Quarterly + Budget
    row2_y = row1_y - 210
    pdf.setFillColorRGB(0.75, 0.6, 1)
    pdf.drawString(55,  row2_y + 185, "Quarterly Analysis")
    pdf.drawString(315, row2_y + 185, "Budget vs Spending")

    if quarter_buf:
        pdf.drawImage(ImageReader(quarter_buf), 50, row2_y, width=240, height=175)
    if budget_buf:
        pdf.drawImage(ImageReader(budget_buf), 310, row2_y, width=240, height=175)

    # --- AI Insights ---
    insights = generate_ai_insights(user, expenses)
    insight_y = row2_y - 30

    pdf.setFont("Helvetica-Bold", 14)
    pdf.setFillColorRGB(0.75, 0.6, 1)
    pdf.drawString(55, insight_y, "AI Financial Insights")

    pdf.setFont("Helvetica", 10)
    pdf.setFillColorRGB(1, 1, 1)
    y = insight_y - 18
    for tip in insights:
        pdf.drawString(65, y, f"• {tip}")
        y -= 15
        if y < 20:
            break

    pdf.save()
    buffer.seek(0)
    return buffer

# ==============================
# BUDGET ALERT EMAIL
# ==============================

def send_budget_alert(user, total):
    try:
        expenses = Expense.query.filter_by(user_id=user.id).all()
        pdf_buffer = generate_pdf_report(user, expenses)
        overage = total - float(user.budget)

        msg = Message(
            subject="⚠ Budget Limit Exceeded – Money Wizard",
            recipients=[user.email]
        )
        msg.body = (
            f"Hello {user.username},\n\n"
            f"Your total spending has exceeded your monthly budget.\n\n"
            f"  Budget:   ₹{float(user.budget):,.2f}\n"
            f"  Spent:    ₹{total:,.2f}\n"
            f"  Over by:  ₹{overage:,.2f}\n\n"
            f"A full expense report with your personalised charts is attached.\n\n"
            f"– The Money Wizard Team"
        )
        msg.attach("budget_report.pdf", "application/pdf", pdf_buffer.read())
        mail.send(msg)
        logging.info(f"Budget alert sent to {user.email}")
        return True
    except Exception as e:
        logging.error(f"Budget alert failed for {user.email}: {e}")
        return False

# ==============================
# HOME
# ==============================

@app.route('/')
def home():
    return redirect(url_for('login'))

# ==============================
# REGISTER
# ==============================

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')

        if User.query.filter_by(email=email).first():
            flash('An account with that email already exists.', 'error')
            return redirect(url_for('login'))

        new_user = User(
            username=username,
            email=email,
            password=generate_password_hash(password)
        )
        db.session.add(new_user)
        db.session.commit()

        otp = random.randint(100000, 999999)
        otp_store[email] = otp

        try:
            msg = Message(subject="Money Wizard – Email Verification",
                          recipients=[email])
            msg.body = (f"Hello {username},\n\n"
                        f"Your verification code is: {otp}\n\n"
                        f"– Money Wizard Team")
            mail.send(msg)
        except Exception as e:
            logging.error(f"Verification email failed: {e}")

        return redirect(url_for('verify_email', email=email))

    return render_template('register.html')

# ==============================
# VERIFY EMAIL
# ==============================

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

# ==============================
# LOGIN
# ==============================

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
            user.last_login = datetime.utcnow()
            db.session.commit()
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid credentials. Please try again.', 'error')

    return render_template("login.html")

# ==============================
# DASHBOARD
# ==============================

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

    return render_template(
        "dashboard.html",
        expenses=expenses,
        total_spent=total_spent,
        budget=budget,
        remaining=remaining,
        percentage=percentage,
        labels=list(category_totals.keys()),
        values=list(category_totals.values()),
        selected_month=selected_month,
        selected_year=selected_year
    )

# ==============================
# PROFILE
# ==============================

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        current_user.username = request.form.get('username')
        new_budget = request.form.get('budget')
        if new_budget:
            current_user.budget = round(float(new_budget), 2)
            current_user.alert_sent = False  # reset on budget change

        new_password = request.form.get('password')
        if new_password:
            current_user.password = generate_password_hash(new_password)

        file = request.files.get('profile_pic')
        if file and file.filename != "":
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            current_user.profile_pic = filename

        db.session.commit()
        flash('Profile updated successfully.', 'success')
        return redirect(url_for('profile'))

    return render_template("profile.html")

# ==============================
# REQUEST DELETE ACCOUNT
# ==============================

@app.route('/request-delete-account', methods=['POST'])
@login_required
def request_delete_account():
    email = current_user.email
    otp = random.randint(100000, 999999)
    otp_store[email] = otp

    try:
        msg = Message(subject="Money Wizard – Account Deletion Verification",
                      recipients=[email])
        msg.body = (f"Hello {current_user.username},\n\n"
                    f"Verification Code: {otp}\n\n"
                    f"If you did not request this, ignore this email.\n\n"
                    f"– Money Wizard Security Team")
        mail.send(msg)
        flash('A verification code has been sent to your email.', 'success')
    except Exception as e:
        logging.error(f"Delete account email failed: {e}")
        flash('Could not send verification email. Please try again.', 'error')
        return redirect(url_for('profile'))

    return redirect(url_for('confirm_delete_account'))

# ==============================
# CONFIRM DELETE ACCOUNT
# ==============================

@app.route('/confirm-delete-account', methods=['GET', 'POST'])
@login_required
def confirm_delete_account():
    if request.method == 'POST':
        stored = otp_store.get(current_user.email)
        if stored and str(stored) == request.form.get("otp"):
            otp_store.pop(current_user.email, None)
            user_id = current_user.id
            Expense.query.filter_by(user_id=user_id).delete()
            User.query.filter_by(id=user_id).delete()
            db.session.commit()
            logout_user()
            return redirect(url_for('register'))
        else:
            flash('Invalid verification code.', 'error')

    return render_template("confirm_delete.html")

# ==============================
# ADD EXPENSE
# ==============================

@app.route('/add', methods=['GET', 'POST'])
@login_required
def add_expense():
    if request.method == 'POST':
        amount = float(request.form['amount'])
        category = request.form['category']
        now = datetime.now()

        old_expenses = Expense.query.filter(
            db.extract('month', Expense.date) == now.month,
            db.extract('year', Expense.date) == now.year,
            Expense.user_id == current_user.id
        ).all()
        old_total = sum(e.amount for e in old_expenses)

        exp = Expense(amount=amount, category=category, user_id=current_user.id)
        db.session.add(exp)
        db.session.commit()

        new_total = old_total + amount
        budget = float(current_user.budget)

        if new_total > budget and not current_user.alert_sent:
            success = send_budget_alert(current_user, new_total)
            current_user.alert_sent = True
            db.session.commit()
            if success:
                flash(
                    f'⚠ Budget exceeded! You\'ve spent ₹{new_total:,.2f} of your ₹{budget:,.2f} budget. '
                    f'A personalised report with your charts has been emailed to {current_user.email}.',
                    'budget_alert'
                )
            else:
                flash(
                    f'⚠ Budget exceeded! You\'ve spent ₹{new_total:,.2f} of your ₹{budget:,.2f} budget.',
                    'budget_alert'
                )
        elif new_total > budget:
            flash(
                f'⚠ You are ₹{new_total - budget:,.2f} over budget.',
                'budget_warning'
            )

        return redirect(url_for('dashboard'))

    return render_template("add_expense.html")

# ==============================
# DOWNLOAD PDF
# ==============================

@app.route('/download-pdf')
@login_required
def download_pdf():
    expenses = Expense.query.filter_by(user_id=current_user.id).all()
    pdf_buffer = generate_pdf_report(current_user, expenses)

    current_user.reports_downloaded = (current_user.reports_downloaded or 0) + 1
    db.session.commit()

    response = make_response(pdf_buffer.read())
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = 'attachment; filename=budget_report.pdf'
    return response

# ==============================
# LOGOUT
# ==============================

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# ==============================
# ADMIN LOGIN
# ==============================

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if current_user.is_authenticated and current_user.is_admin:
        return redirect(url_for('admin_dashboard'))

    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            if user.is_admin:
                login_user(user)
                user.last_login = datetime.utcnow()
                db.session.commit()
                return redirect(url_for('admin_dashboard'))
            else:
                flash('Access denied. This account does not have admin privileges.', 'error')
        else:
            flash('Invalid admin credentials.', 'error')

    return render_template('admin/login.html')

# ==============================
# ADMIN DASHBOARD
# ==============================

@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    now = datetime.utcnow()
    week_ago = now - timedelta(days=7)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    total_users = User.query.filter_by(is_admin=False).count()
    active_users = User.query.filter(
        User.is_admin == False,
        User.last_login >= week_ago
    ).count()
    total_expenses = Expense.query.count()
    total_downloads = db.session.query(
        db.func.coalesce(db.func.sum(User.reports_downloaded), 0)
    ).scalar()
    new_users_month = User.query.filter(
        User.is_admin == False,
        User.created_at >= month_start
    ).count()

    sort_by = request.args.get('sort', 'newest')
    users_query = User.query.filter_by(is_admin=False)

    if sort_by == 'most_active':
        users_query = users_query.order_by(User.last_login.desc().nullslast())
    elif sort_by == 'most_expenses':
        users_query = users_query.outerjoin(Expense).group_by(User.id).order_by(
            db.func.count(Expense.id).desc()
        )
    else:
        users_query = users_query.order_by(User.created_at.desc())

    users = users_query.all()

    # Attach per-user expense count
    user_stats = []
    for u in users:
        expense_count = Expense.query.filter_by(user_id=u.id).count()
        user_stats.append({
            'user': u,
            'expense_count': expense_count
        })

    # Monthly registration data for chart (last 6 months)
    monthly_reg = []
    monthly_labels = []
    for i in range(5, -1, -1):
        d = now - timedelta(days=30 * i)
        count = User.query.filter(
            User.is_admin == False,
            db.extract('month', User.created_at) == d.month,
            db.extract('year', User.created_at) == d.year
        ).count()
        monthly_reg.append(count)
        monthly_labels.append(d.strftime('%b %Y'))

    inactive_users = max(total_users - active_users, 0)

    return render_template(
        'admin/dashboard.html',
        total_users=total_users,
        active_users=active_users,
        inactive_users=inactive_users,
        total_expenses=total_expenses,
        total_downloads=int(total_downloads),
        new_users_month=new_users_month,
        user_stats=user_stats,
        sort_by=sort_by,
        monthly_reg=monthly_reg,
        monthly_labels=monthly_labels,
        now=now
    )

# ==============================
# ADMIN LOGOUT
# ==============================

@app.route('/admin/logout')
@login_required
def admin_logout():
    logout_user()
    return redirect(url_for('admin_login'))

# ==============================
# 403 HANDLER
# ==============================

@app.errorhandler(403)
def forbidden(e):
    return render_template('403.html'), 403

# ==============================
# DATABASE SETUP & MIGRATIONS
# ==============================

with app.app_context():
    db.create_all()

    # Run migrations for columns added after initial schema
    new_columns = [
        ("ALTER TABLE user ADD COLUMN alert_sent BOOLEAN DEFAULT 0"),
        ("ALTER TABLE user ADD COLUMN is_admin BOOLEAN DEFAULT 0"),
        ("ALTER TABLE user ADD COLUMN last_login DATETIME"),
        ("ALTER TABLE user ADD COLUMN reports_downloaded INTEGER DEFAULT 0"),
        ("ALTER TABLE user ADD COLUMN created_at DATETIME"),
    ]
    for stmt in new_columns:
        try:
            with db.engine.connect() as conn:
                conn.execute(db.text(stmt))
                conn.commit()
        except Exception:
            pass  # Column already exists

    # Seed default admin account if none exists
    admin_email = os.environ.get("ADMIN_EMAIL", "admin@moneywizard.com")
    admin_password = os.environ.get("ADMIN_PASSWORD", "Admin@1234")

    try:
        existing_admin = User.query.filter_by(is_admin=True).first()
        if not existing_admin:
            admin = User(
                username="Admin",
                email=admin_email,
                password=generate_password_hash(admin_password),
                is_admin=True,
                created_at=datetime.utcnow()
            )
            db.session.add(admin)
            db.session.commit()
            print(f"[Money Wizard] Admin created — Email: {admin_email} | Password: {admin_password}")
        else:
            # Ensure existing admin has is_admin flag set correctly
            if not existing_admin.is_admin:
                existing_admin.is_admin = True
                db.session.commit()
    except Exception as e:
        db.session.rollback()
        logging.error(f"Admin seed failed: {e}")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
