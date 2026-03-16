from datetime import datetime

from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

db = SQLAlchemy()


class PatientLogin(db.Model):
    __tablename__ = "patient_login"

    id = db.Column(db.Integer, primary_key=True)
    patient_name = db.Column(db.String(120), nullable=False)
    phone_number = db.Column(db.String(15), unique=True, nullable=False)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    room_number = db.Column(db.String(20), nullable=True)
    hospital_code = db.Column(db.String(30), nullable=True, index=True)
    is_discharged = db.Column(db.Boolean, nullable=False, default=False)
    discharged_at = db.Column(db.DateTime, nullable=True)

    care_record = db.relationship(
        "PatientCareRecord",
        backref="patient",
        uselist=False,
        cascade="all, delete-orphan",
    )
    care_updates = db.relationship(
        "PatientCareUpdate",
        backref="patient",
        cascade="all, delete-orphan",
        order_by="PatientCareUpdate.edited_at.desc()",
    )
    reports = db.relationship(
        "PatientReport",
        backref="patient",
        cascade="all, delete-orphan",
        order_by="PatientReport.uploaded_at.desc()",
    )
    expenses = db.relationship(
        "PatientExpense",
        backref="patient",
        cascade="all, delete-orphan",
        order_by="PatientExpense.created_at.desc()",
    )
    personal_documents = db.relationship(
        "PatientPersonalDocument",
        backref="patient",
        cascade="all, delete-orphan",
        order_by="PatientPersonalDocument.uploaded_at.desc()",
    )

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class NurseLogin(db.Model):
    __tablename__ = "nurse_login"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    hospital_code = db.Column(db.String(30), nullable=False, index=True)
    updates = db.relationship("PatientCareUpdate", backref="nurse")

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class PatientCareRecord(db.Model):
    __tablename__ = "patient_care_record"

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(
        db.Integer, db.ForeignKey("patient_login.id"), nullable=False, unique=True
    )
    medications = db.Column(db.Text, nullable=True)
    injections = db.Column(db.Text, nullable=True)
    prescriptions = db.Column(db.Text, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_by_nurse_id = db.Column(db.Integer, db.ForeignKey("nurse_login.id"))


class PatientCareUpdate(db.Model):
    __tablename__ = "patient_care_update"

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey("patient_login.id"), nullable=False)
    nurse_id = db.Column(db.Integer, db.ForeignKey("nurse_login.id"), nullable=False)
    room_number = db.Column(db.String(20), nullable=True)
    medications = db.Column(db.Text, nullable=True)
    injections = db.Column(db.Text, nullable=True)
    prescriptions = db.Column(db.Text, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    edited_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class PatientReport(db.Model):
    __tablename__ = "patient_report"

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey("patient_login.id"), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    saved_filename = db.Column(db.String(255), nullable=False, unique=True)
    uploaded_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class PatientExpense(db.Model):
    __tablename__ = "patient_expense"

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey("patient_login.id"), nullable=False)
    category = db.Column(db.String(120), nullable=False)
    description = db.Column(db.String(255), nullable=True)
    amount = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )


class PatientPersonalDocument(db.Model):
    __tablename__ = "patient_personal_document"

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey("patient_login.id"), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    saved_filename = db.Column(db.String(255), nullable=False, unique=True)
    uploaded_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
