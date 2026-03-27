import os


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "mysecret2310")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///hospital.db")
    if SQLALCHEMY_DATABASE_URI.startswith("postgres://"):
        SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace(
            "postgres://", "postgresql://", 1
        )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    REPORT_UPLOAD_SUBDIR = "reports"
    PERSONAL_DOC_UPLOAD_SUBDIR = "personal_docs"
    TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
    TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
    SMS_FROM_NUMBER = os.getenv("SMS_FROM_NUMBER")
    SMS_ALERT_TO_NUMBER = os.getenv("SMS_ALERT_TO_NUMBER")
