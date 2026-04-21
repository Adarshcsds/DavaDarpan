# DavaDarpan

Flask hospital/patient portal with patient login, nurse workflows, reports, expenses, and password-based patient access.

## Local setup

1. Create and activate a virtual environment.
2. Install the project dependencies, including `python-dotenv`.

```bash
pip install flask flask-sqlalchemy flask-wtf werkzeug python-dotenv
```

3. Create a `.env` file in the project root by copying `.env.example`.
4. Fill in the app settings you need.
5. Run the app locally.

```bash
python hospital.py
```

## Environment variables

Create a `.env` file in the project root with values like these:

```env
SECRET_KEY=replace-this-in-production
DATABASE_URL=sqlite:///hospital.db
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-2.5-flash
```

Patient registration and login use normal username/password authentication. OTP, Twilio SMS, and reset-password flows have been removed.
