# 🧙 Money Wizard – Smart Expense & Budget Tracker

Money Wizard is a smart personal finance management web application that helps users track expenses, monitor budgets, and receive intelligent financial insights. The system also generates automated PDF financial reports and sends budget alert emails when spending exceeds the defined limit.

---

## 🚀 Features

### 🔐 User Authentication
- Secure user registration
- Email OTP verification
- Password hashing for security
- Login using username or email

### 👤 Profile Management
- Update username
- Change password
- Upload profile picture
- Modify monthly budget

### 💰 Expense Tracking
- Add categorized expenses
- View expense history
- Monthly filtering system

### 📊 Financial Dashboard
- Summary cards (Total Spent, Budget, Remaining)
- Progress bar for budget usage
- Interactive charts using Chart.js:
  - Pie Chart – Expense distribution
  - Bar Chart – Category spending

### 📑 PDF Financial Reports
Automatically generated report including:
- Budget summary
- Spending charts
- Monthly trends
- Quarterly analysis
- AI-generated financial insights

### 📧 Smart Budget Alert System
When a user's spending exceeds their budget:
- Alert email is sent automatically
- Financial report is attached as PDF

### 🧠 AI Financial Insights
The system analyzes expenses and provides suggestions such as:
- Highest spending category
- Budget status
- Savings recommendations

### 🔐 Secure Account Deletion
- Email verification before deleting account

---

## 🛠️ Technologies Used

| Technology | Purpose |
|------------|--------|
| Python | Backend programming |
| Flask | Web framework |
| SQLAlchemy | Database ORM |
| SQLite | Database |
| HTML5 | Frontend structure |
| CSS3 | Styling |
| Bootstrap | UI components |
| Chart.js | Dashboard charts |
| Matplotlib | Report chart generation |
| ReportLab | PDF report generation |
| Flask-Mail | Email notifications |
| Git & GitHub | Version control |

---

## 📂 Project Structure

money-wizard-tracker
│
├── app.py
├── requirements.txt
├── Procfile
│
├── static
│ ├── styles.css
│ ├── report_chart.png
│ ├── budget_chart.png
│ ├── month_chart.png
│ ├── quarter_chart.png
│ ├── report_bg.png
│ ├── profile_pics
│ └── videos
│
├── templates
│ ├── base.html
│ ├── dashboard.html
│ ├── add_expense.html
│ ├── profile.html
│ ├── login.html
│ ├── register.html
│ ├── verify_email.html
│ ├── confirm_delete.html
│ └── report_template.html

## ⚙️ Installation

Clone the repository:

```bash
git clone https://github.com/lakshmi-klp/money-wizard-tracker.git

Move to the project folder:

cd money-wizard-tracker

Create virtual environment:

python -m venv venv

Activate environment:

Windows:

venv\Scripts\activate

Install dependencies:

pip install -r requirements.txt

Run the application:

python app.py

Open browser:

http://127.0.0.1:5000
📊 Example Dashboard

The dashboard provides:

Expense tracking

Budget monitoring

Graphical analytics

Monthly filtering

📄 Example PDF Report

The generated report includes:

User financial summary

Expense distribution charts

Monthly spending trends

Budget vs spending analysis

AI-based insights

🔒 Security Features

Password hashing

Email OTP verification

Account deletion confirmation

Secure login sessions

🚀 Future Improvements

Mobile application version

AI-based spending predictions

Savings goal tracking

Multi-user family accounts

Cloud database integration

👩‍💻 Author

Lakshmi
Computer Science & Engineering Student

GitHub:
https://github.com/lakshmi-klp

📜 License

This project is created for educational and research purposes.
