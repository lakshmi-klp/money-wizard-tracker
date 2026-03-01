from flask import Flask, render_template, redirect, url_for, request
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from collections import defaultdict

app = Flask(__name__)
app.config['SECRET_KEY'] = 'supersecretkey'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///money_wizard.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
import os
from werkzeug.utils import secure_filename

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
    budget = db.Column(db.Float, default=5000)



class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(100), nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ================= ROUTES =================

@app.route('/')
def home():
    return redirect(url_for('login'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':

        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')

        # Check if email already exists
        existing_user = User.query.filter_by(email=email).first()

        if existing_user:
            return render_template(
        "register.html",
        error="Email already registered.",
        show_login=True
        )

        hashed_password = generate_password_hash(password)

        new_user = User(
            username=username,
            email=email,
            password=hashed_password
        )

        db.session.add(new_user)
        db.session.commit()

        return redirect(url_for('login'))

    return render_template('register.html')



@app.route('/login', methods=['GET', 'POST'])
def login():
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

    return render_template('login.html')


@app.route('/dashboard')
@login_required
def dashboard():

    # Get selected month & year from query params
    selected_month = request.args.get('month', type=int)
    selected_year = request.args.get('year', type=int)

    now = datetime.now()

    if not selected_month:
        selected_month = now.month
    if not selected_year:
        selected_year = now.year

    # Filter expenses by month and year
    expenses = Expense.query.filter(
        Expense.user_id == current_user.id,
        db.extract('month', Expense.date) == selected_month,
        db.extract('year', Expense.date) == selected_year
    ).all()

    total = sum(exp.amount for exp in expenses)

    budget = current_user.budget
    remaining = budget - total
    percentage = (total / budget) * 100 if budget > 0 else 0

    category_totals = defaultdict(float)
    for exp in expenses:
        category_totals[exp.category] += exp.amount

    labels = list(category_totals.keys())
    values = list(category_totals.values())

    return render_template(
        'dashboard.html',
        expenses=expenses,
        total=total,
        budget=budget,
        remaining=remaining,
        percentage=percentage,
        labels=labels,
        values=values,
        selected_month=selected_month,
        selected_year=selected_year
    )
@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():

    if request.method == 'POST':

        # Update username
        current_user.username = request.form.get('username')

        # Update budget
        new_budget = request.form.get('budget')
        if new_budget:
            current_user.budget = float(new_budget)

        # Update password
        new_password = request.form.get('password')
        if new_password:
            current_user.password = generate_password_hash(new_password)

        # Profile picture upload
        file = request.files.get('profile_pic')
        if file and file.filename != '':
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            current_user.profile_pic = filename

        db.session.commit()
        return redirect(url_for('profile'))

    return render_template('profile.html')
@app.route('/delete_account', methods=['POST'])
@login_required
def delete_account():
    db.session.delete(current_user)
    db.session.commit()
    return redirect(url_for('register'))


@app.route('/add', methods=['GET', 'POST'])
@login_required
def add_expense():
    if request.method == 'POST':
        amount = float(request.form['amount'])
        category = request.form['category']

        new_expense = Expense(
            amount=amount,
            category=category,
            user_id=current_user.id
        )

        db.session.add(new_expense)
        db.session.commit()

        return redirect(url_for('dashboard'))

    return render_template('add_expense.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
