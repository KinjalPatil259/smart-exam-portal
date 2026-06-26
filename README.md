# Smart Online Exam Management System

An industry-level, highly secure, and responsive online examination platform featuring glassmorphism layout controls, real-time timer tracking, anti-cheating proctor guards, performance analytics, and dynamic reporting.

---

## Technical Stack
- **Backend**: Python 3, Flask framework, Flask-SQLAlchemy ORM.
- **Database**: SQLite (local development mode) and MySQL (production config via `schema.sql`).
- **Frontend**: Vanilla HTML5, CSS3 Variables (theme switching support), JavaScript (dynamic Ajax options syncing), and Chart.js dashboards.
- **Reporting**: ReportLab (PDF printable card rendering) and OpenPyXL (Excel sheets builder).
- **Security**: custom session session state checks, password hashing via `werkzeug.security`, input sanitization, and SQL Injection prevention (via ORM parameters).

---

## Project Structure
```
d:/projects/Exam Management system/
├── app.py                      # Main Flask application driver & Seeding
├── config.py                   # App config, handles MySQL/SQLite switches
├── database/
│   ├── connection.py           # SQLAlchemy object initialization
│   └── schema.sql              # MySQL DDL Schema
├── models/                     # SQLAlchemy Models (User, Student, Admin, Exam, etc.)
├── routes/                     # Blueprint Routers (Auth, Student, Admin, Exam, Reports)
├── static/                     # Styling variables, proctor scripts, avatars uploads
├── templates/                  # Base layout master, auth pages, admin panels
├── tests/                      # Automated unit tests
├── requirements.txt            # Dependency configuration
└── README.md                   # This instruction file
```

---

## Installation & Setup Instructions

### 1. Initialize Virtual Environment
Open a terminal in the root workspace directory and run:
```bash
# Create virtual environment
python -m venv .venv

# Activate (Windows PowerShell)
.venv\Scripts\Activate.ps1

# Activate (macOS/Linux)
source .venv/bin/activate
```

### 2. Install Package Dependencies
Ensure pip is upgraded and install dependencies:
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Run the Application
Start the Flask development server:
```bash
python app.py
```
The application will boot at `http://127.0.0.1:5000/` and auto-generate the database:
- If `DB_TYPE` env variable is unset, it defaults to creating local SQLite database at `database/exam_system.db`.
- It will automatically execute schema creation and **seed a default admin account** and a mockup midterm exam to allow immediate testing!

---

## Default Test Accounts

### Administrator Account
- **Email**: `admin@example.com`
- **Password**: `admin123`
*Use this account to create subjects, schedule exams, add questions, view student score logs, and export Excel reports.*

### Student Account (Mockup Setup)
You can register a new student account using the **Register** link on the homepage.
- Registered students can instantly access active exams, navigate question cards, select answers, view results scorecard upon submit, and download PDF certificates.

---

## Security Implementations
1. **Password Hashing**: Stored using PBKDF2 with SHA256 hashes (`werkzeug.security`).
2. **Session Guards**: Direct session hijacking protection by setting unique cookie attributes.
3. **Role Enforcement**: Custom `@admin_required` and `@login_required` decorators restrict API and view path exposures.
4. **Anti-Cheating Monitor**: Active browser focus event listeners. Student departures from the workspace trigger warning pop-ups. Exceeding warnings triggers auto-submission.
5. **SQL Injection Security**: SQLAlchemy parameterization is used on all queries to mitigate SQL injections.
