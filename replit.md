# Money Wizard

A Flask-based personal finance tracker with expense management, budget tracking, PDF reports, and AI-powered financial insights.

## Features

- User registration and login with email verification (OTP)
- Expense tracking by category
- Budget management with alerts
- Dashboard with charts and analytics
- PDF report generation
- Profile management with photo uploads
- Budget alert emails via Gmail SMTP

## Tech Stack

- **Framework**: Flask (Python)
- **Database**: SQLite (via Flask-SQLAlchemy)
- **Auth**: Flask-Login
- **Email**: Flask-Mail (Gmail SMTP)
- **Charts**: Matplotlib
- **PDF**: ReportLab
- **Server**: Gunicorn

## Environment Variables

- `SECRET_KEY`: Flask secret key (set in shared env)
- `MAIL_USERNAME`: Gmail address for sending emails (optional)
- `MAIL_PASSWORD`: Gmail app password (optional)

## Running

The app runs via Gunicorn on port 5000:
```
gunicorn app:app --bind 0.0.0.0:5000 --timeout 120 --workers 2
```

## Project Structure

- `app.py` — Main Flask application with all routes and models
- `templates/` — Jinja2 HTML templates
- `static/` — CSS, images, chart outputs, profile pictures, videos
- `requirements.txt` — Python dependencies
