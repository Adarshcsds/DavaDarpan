# DavaDarpan

Flask hospital/patient portal with patient login, nurse workflows, reports, expenses, and Twilio-based SMS/OTP support.

## Local setup

1. Create and activate a virtual environment.
2. Install the project dependencies, including `python-dotenv`.

```bash
pip install flask flask-sqlalchemy flask-wtf werkzeug python-dotenv
```

3. Create a `.env` file in the project root by copying `.env.example`.
4. Fill in your real Twilio credentials and phone numbers in `.env`.
5. Run the app locally.

```bash
python hospital.py
```

## Environment variables

Create a `.env` file in the project root with values like these:

```env
TWILIO_ACCOUNT_SID=your_twilio_account_sid
TWILIO_AUTH_TOKEN=your_twilio_auth_token
SMS_FROM_NUMBER=+1234567890
SMS_ALERT_TO_NUMBER=+919876543210
```

Optional app settings:

```env
SECRET_KEY=replace-this-in-production
DATABASE_URL=sqlite:///hospital.db
```

## Twilio SMS and OTP

The app does not store Twilio secrets in source code anymore. SMS and OTP features now read:

- `TWILIO_ACCOUNT_SID`
- `TWILIO_AUTH_TOKEN`
- `SMS_FROM_NUMBER`
- `SMS_ALERT_TO_NUMBER`

from environment variables loaded through `.env` during local development.

If these values are missing, the app will skip Twilio sends and log a warning instead of exposing secrets in the repository.
