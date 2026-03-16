
import os
import secrets
import uuid
from base64 import b64encode
from datetime import datetime, timedelta, timezone   
from functools import wraps
from hashlib import sha256
from urllib.error import HTTPError
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from flask import (
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)
from sqlalchemy import text
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from .forms import (
    DeletePatientForm,
    NurseAddPatientForm,
    NurseLoginForm,
    NursePatientRecordForm,
    PatientExpenseForm,
    PatientHospitalCodeForm,
    PatientLoginForm,
    PatientRegisterForm,
    PatientReportUploadForm,
    PatientResetPasswordRequestForm,
    PatientResetPasswordVerifyForm,
)
from .models import (
    NurseLogin,
    PatientCareRecord,
    PatientCareUpdate,
    PatientExpense,
    PatientLogin,
    PatientPersonalDocument,
    PatientReport,
    db,
)


# Restrict route access to authenticated nurse sessions.
def nurse_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if session.get("role") != "nurse":
            flash("Staff desk login required.", "error")
            return redirect(url_for("nurse_login"))
        return view(*args, **kwargs)

    return wrapped


# Restrict route access to authenticated patient sessions.
def patient_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if session.get("role") != "patient":
            flash("Subject login required.", "error")
            return redirect(url_for("patient_login"))
        return view(*args, **kwargs)

    return wrapped


# Fetch or create the active care record for a patient.
def get_or_create_care_record(patient_id: int) -> PatientCareRecord:
    record = PatientCareRecord.query.filter_by(patient_id=patient_id).first()
    if record is None:
        record = PatientCareRecord(patient_id=patient_id)
        db.session.add(record)
        db.session.flush()
    return record


# Save uploaded reports as PDF (or convert image uploads to PDF).
def save_report_as_pdf(file_storage) -> tuple[str, str]:
    original_name = secure_filename(file_storage.filename or "report")
    extension = os.path.splitext(original_name)[1].lower()

    if extension == ".pdf":
        saved_filename = f"{uuid.uuid4().hex}.pdf"
        report_path = os.path.join(current_app.config["REPORT_UPLOAD_FOLDER"], saved_filename)
        file_storage.save(report_path)
        return original_name, saved_filename

    if extension in {".jpg", ".jpeg", ".png"}:
        try:
            from PIL import Image
        except ImportError as exc:
            raise RuntimeError("Install Pillow to upload camera images as PDF.") from exc

        saved_filename = f"{uuid.uuid4().hex}.pdf"
        report_path = os.path.join(current_app.config["REPORT_UPLOAD_FOLDER"], saved_filename)
        image = Image.open(file_storage.stream).convert("RGB")
        image.save(report_path, "PDF")
        return original_name, saved_filename

    raise ValueError("Unsupported file type.")


# Remove a shared report file from the report storage folder.
def remove_report_file(saved_filename: str) -> None:
    path = os.path.join(current_app.config["REPORT_UPLOAD_FOLDER"], saved_filename)
    if os.path.exists(path):
        os.remove(path)


# Remove a personal document file from the personal storage folder.
def remove_personal_document_file(saved_filename: str) -> None:
    path = os.path.join(current_app.config["PERSONAL_DOC_UPLOAD_FOLDER"], saved_filename)
    if os.path.exists(path):
        os.remove(path)


# Normalize phone numbers into a consistent international format.
def normalize_phone_number(value: str) -> str:
    raw = (value or "").strip()
    digits = "".join(ch for ch in raw if ch.isdigit())
    if raw.startswith("+") and digits:
        return f"+{digits}"
    if len(digits) == 10:
        return f"+91{digits}"
    if len(digits) == 12 and digits.startswith("91"):
        return f"+{digits}"
    if digits:
        return f"+{digits}"
    return raw


IST_TIMEZONE = timezone(timedelta(hours=5, minutes=30))


def generate_otp_code() -> str:
    return f"{secrets.randbelow(1000000):06d}"


def build_otp_digest(phone_number: str, otp_code: str) -> str:
    secret = current_app.config.get("SECRET_KEY", "")
    payload = f"{phone_number}:{otp_code}:{secret}".encode("utf-8")
    return sha256(payload).hexdigest()


def clear_reset_otp_session() -> None:
    session.pop("reset_phone_number", None)
    session.pop("reset_otp_hash", None)
    session.pop("reset_otp_expires_at", None)
    session.pop("reset_otp_attempts", None)


def send_sms_via_twilio(to_number: str, body: str) -> bool:
    account_sid = (current_app.config.get("TWILIO_ACCOUNT_SID") or "").strip()
    auth_token = (current_app.config.get("TWILIO_AUTH_TOKEN") or "").strip()
    from_number = normalize_phone_number(current_app.config.get("SMS_FROM_NUMBER") or "")
    to_number = normalize_phone_number(to_number)

    if not all([account_sid, auth_token, from_number, to_number]):
        current_app.logger.warning("SMS not sent: Twilio configuration is incomplete.")
        return False

    payload = urlencode(
        {
            "To": to_number,
            "From": from_number,
            "Body": body,
        }
    ).encode("utf-8")
    auth_value = b64encode(f"{account_sid}:{auth_token}".encode("utf-8")).decode("ascii")
    endpoint = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
    request_obj = Request(
        endpoint,
        data=payload,
        headers={
            "Authorization": f"Basic {auth_value}",
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        },
        method="POST",
    )

    try:
        with urlopen(request_obj, timeout=10) as response:
            if response.status in (200, 201):
                return True
            current_app.logger.warning("SMS failed with status code %s.", response.status)
            return False
    except HTTPError as exc:
        error_body = ""
        try:
            error_body = exc.read().decode("utf-8", errors="replace")
        except Exception:
            error_body = "<unable to read response body>"
        current_app.logger.warning(
            "SMS failed: status=%s reason=%s body=%s",
            exc.code,
            exc.reason,
            error_body,
        )
        return False
    except URLError as exc:
        current_app.logger.warning("SMS failed: %s", exc)
        return False
    except Exception as exc:
        current_app.logger.warning("SMS failed unexpectedly: %s", exc)
        return False


def get_alert_sms_number() -> str:
    return normalize_phone_number(current_app.config.get("SMS_ALERT_TO_NUMBER") or "")


def send_password_reset_otp(phone_number: str, otp_code: str) -> bool:
    return send_sms_via_twilio(
        get_alert_sms_number(),
        f"Your Hawkins Lab reset OTP is {otp_code}. It expires in 5 minutes.",
    )


# Send nurse-created patient onboarding alert SMS via Twilio when configured.
def send_registration_sms(patient_name: str, phone_number: str, room_number: str) -> None:
    ist_timestamp = datetime.now(IST_TIMEZONE).strftime("%Y-%m-%d %I:%M:%S %p IST")
    sms_sent = send_sms_via_twilio(
        get_alert_sms_number(),
        (
            "New patient added by nurse.\n"
            f"Patient Name: {patient_name}\n"
            f"Phone: {phone_number}\n"
            f"Room No: {room_number or 'N/A'}\n"
            f"Timestamp: {ist_timestamp}"
        ),
    )
    if not sms_sent:
        current_app.logger.warning("SMS notification failed for %s.", phone_number)


# Append only new nurse-entered text with IST timestamp metadata.
def append_timestamped_entry(
    existing_text: str | None, submitted_text: str | None, nurse_label: str
) -> str:
    existing = (existing_text or "").strip()
    submitted = (submitted_text or "").strip()
    if not submitted:
        return existing
    if not existing:
        stamp = datetime.now(IST_TIMEZONE).strftime("%Y-%m-%d %I:%M:%S %p IST")
        return f"[{stamp}] ({nurse_label}) {submitted}"
    if submitted == existing:
        return existing
    if submitted.startswith(existing):
        added = submitted[len(existing) :].strip()
        if not added:
            return existing
        stamp = datetime.now(IST_TIMEZONE).strftime("%Y-%m-%d %I:%M:%S %p IST")
        return f"{existing}\n[{stamp}] ({nurse_label}) {added}"
    stamp = datetime.now(IST_TIMEZONE).strftime("%Y-%m-%d %I:%M:%S %p IST")
    return f"{existing}\n[{stamp}] ({nurse_label}) {submitted}"


# Initialize DB tables, upload folders, schema updates, and seed nurse user.
def initialize_database(app) -> None:
    with app.app_context():
        os.makedirs(app.config["REPORT_UPLOAD_FOLDER"], exist_ok=True)
        os.makedirs(app.config["PERSONAL_DOC_UPLOAD_FOLDER"], exist_ok=True)
        db.create_all()
        columns = db.session.execute(text("PRAGMA table_info(patient_login)")).fetchall()
        column_names = {column[1] for column in columns}
        if "room_number" not in column_names:
            db.session.execute(
                text("ALTER TABLE patient_login ADD COLUMN room_number VARCHAR(20)")
            )
            db.session.commit()
        if "hospital_code" not in column_names:
            db.session.execute(
                text("ALTER TABLE patient_login ADD COLUMN hospital_code VARCHAR(30)")
            )
            db.session.commit()
        if "is_discharged" not in column_names:
            db.session.execute(
                text("ALTER TABLE patient_login ADD COLUMN is_discharged BOOLEAN NOT NULL DEFAULT 0")
            )
            db.session.commit()
        if "discharged_at" not in column_names:
            db.session.execute(
                text("ALTER TABLE patient_login ADD COLUMN discharged_at DATETIME")
            )
            db.session.commit()

        nurse_columns = db.session.execute(text("PRAGMA table_info(nurse_login)")).fetchall()
        nurse_column_names = {column[1] for column in nurse_columns}
        if "hospital_code" not in nurse_column_names:
            db.session.execute(
                text("ALTER TABLE nurse_login ADD COLUMN hospital_code VARCHAR(30)")
            )
            db.session.execute(
                text("UPDATE nurse_login SET hospital_code = '' WHERE hospital_code IS NULL")
            )
            db.session.commit()

        if NurseLogin.query.first() is None:
            nurse = NurseLogin(username="nurse1", hospital_code="")
            nurse.set_password("nurse123")
            db.session.add(nurse)
            db.session.commit()


# Register all public, patient, and nurse routes for this application.
def register_routes(app) -> None:
    # Landing page route with role-based dashboard redirection.
    @app.route("/")
    def home():
        if session.get("role") == "nurse":
            return redirect(url_for("nurse_dashboard"))
        if session.get("role") == "patient":
            return redirect(url_for("patient_dashboard"))
        return render_template("index.html")

    # Logout route that clears session and returns to home.
    @app.route("/logout")
    def logout():
        session.clear()
        flash("Exited the Hawkins system.", "success")
        return redirect(url_for("home"))

    # Patient registration route to create login and initial care record.
    @app.route("/patient/register", methods=["GET", "POST"])
    def patient_register():
        form = PatientRegisterForm()
        if form.validate_on_submit():
            phone_number = form.phone_number.data.strip()
            existing_user = PatientLogin.query.filter(
                (PatientLogin.phone_number == phone_number)
                | (PatientLogin.username == form.username.data.strip())
            ).first()
            if existing_user:
                flash("Username or contact number already exists.", "error")
                return render_template("patient_register.html", form=form)

            patient = PatientLogin(
                patient_name=form.patient_name.data.strip(),
                phone_number=phone_number,
                username=form.username.data.strip(),
            )
            patient.set_password(form.password.data)
            db.session.add(patient)
            db.session.flush()
            db.session.add(PatientCareRecord(patient_id=patient.id))
            db.session.commit()
            flash("Case file created. Please sign in.", "success")
            return redirect(url_for("patient_login"))
        if request.method == "POST" and form.errors:
            for _, errors in form.errors.items():
                for error in errors:
                    flash(error, "error")

        return render_template("patient_register.html", form=form)

    # Patient login route to authenticate and initialize patient session.
    @app.route("/patient/login", methods=["GET", "POST"])
    def patient_login():
        form = PatientLoginForm()
        if form.validate_on_submit():
            patient = PatientLogin.query.filter_by(username=form.username.data.strip()).first()
            if patient and patient.check_password(form.password.data):
                session.clear()
                session["role"] = "patient"
                session["patient_id"] = patient.id
                session["username"] = patient.username
                session["care_code_verified"] = False
                flash("Subject login successful.", "success")
                return redirect(url_for("patient_dashboard"))
            flash("Invalid credentials.", "error")

        return render_template("patient_login.html", form=form)

    # Password reset route using OTP sent to registered phone number.
    @app.route("/patient/reset-password", methods=["GET", "POST"])
    def patient_reset_password():
        otp_request_form = PatientResetPasswordRequestForm(prefix="otp_request")
        otp_verify_form = PatientResetPasswordVerifyForm(prefix="otp_verify")

        if otp_request_form.send_otp.data and otp_request_form.validate_on_submit():
            phone_number = otp_request_form.phone_number.data.strip()
            patient = PatientLogin.query.filter_by(phone_number=phone_number).first()
            if patient is None:
                flash("No subject found with this contact number.", "error")
                return render_template(
                    "patient_reset_password.html",
                    otp_request_form=otp_request_form,
                    otp_verify_form=otp_verify_form,
                    otp_step_active=False,
                )

            otp_code = generate_otp_code()
            sms_sent = send_password_reset_otp(phone_number, otp_code)
            if not sms_sent:
                flash("Unable to send OTP right now. Please try again shortly.", "error")
                return render_template(
                    "patient_reset_password.html",
                    otp_request_form=otp_request_form,
                    otp_verify_form=otp_verify_form,
                    otp_step_active=False,
                )

            session["reset_phone_number"] = phone_number
            session["reset_otp_hash"] = generate_password_hash(
                build_otp_digest(phone_number, otp_code)
            )
            session["reset_otp_expires_at"] = int(
                (datetime.utcnow() + timedelta(minutes=5)).timestamp()
            )
            session["reset_otp_attempts"] = 0
            otp_verify_form.phone_number.data = phone_number
            flash("OTP sent successfully. It is valid for 5 minutes.", "success")
            return render_template(
                "patient_reset_password.html",
                otp_request_form=otp_request_form,
                otp_verify_form=otp_verify_form,
                otp_step_active=True,
            )

        if otp_verify_form.reset_password.data and otp_verify_form.validate_on_submit():
            phone_number = otp_verify_form.phone_number.data.strip()
            otp_code = otp_verify_form.otp_code.data.strip()
            stored_phone = session.get("reset_phone_number")
            otp_hash = session.get("reset_otp_hash")
            expires_at = int(session.get("reset_otp_expires_at", 0))
            attempts = int(session.get("reset_otp_attempts", 0))
            now_timestamp = int(datetime.utcnow().timestamp())

            if not stored_phone or not otp_hash:
                flash("Please request OTP first.", "error")
                return render_template(
                    "patient_reset_password.html",
                    otp_request_form=otp_request_form,
                    otp_verify_form=otp_verify_form,
                    otp_step_active=False,
                )

            if phone_number != stored_phone:
                flash("Phone number does not match requested OTP number.", "error")
                return render_template(
                    "patient_reset_password.html",
                    otp_request_form=otp_request_form,
                    otp_verify_form=otp_verify_form,
                    otp_step_active=True,
                )

            if now_timestamp > expires_at:
                clear_reset_otp_session()
                flash("OTP expired. Please request a new OTP.", "error")
                return render_template(
                    "patient_reset_password.html",
                    otp_request_form=otp_request_form,
                    otp_verify_form=otp_verify_form,
                    otp_step_active=False,
                )

            if attempts >= 5:
                clear_reset_otp_session()
                flash("Too many invalid attempts. Please request OTP again.", "error")
                return render_template(
                    "patient_reset_password.html",
                    otp_request_form=otp_request_form,
                    otp_verify_form=otp_verify_form,
                    otp_step_active=False,
                )

            provided_digest = build_otp_digest(phone_number, otp_code)
            if not check_password_hash(otp_hash, provided_digest):
                attempts += 1
                session["reset_otp_attempts"] = attempts
                remaining = max(0, 5 - attempts)
                flash(f"Invalid OTP. {remaining} attempt(s) remaining.", "error")
                return render_template(
                    "patient_reset_password.html",
                    otp_request_form=otp_request_form,
                    otp_verify_form=otp_verify_form,
                    otp_step_active=True,
                )

            patient = PatientLogin.query.filter_by(phone_number=phone_number).first()
            if patient is None:
                clear_reset_otp_session()
                flash("No subject found with this contact number.", "error")
                return render_template(
                    "patient_reset_password.html",
                    otp_request_form=otp_request_form,
                    otp_verify_form=otp_verify_form,
                    otp_step_active=False,
                )

            patient.set_password(otp_verify_form.new_password.data)
            db.session.commit()
            clear_reset_otp_session()
            flash("Access code reset complete. Please sign in again.", "success")
            return redirect(url_for("patient_login"))

        if session.get("reset_phone_number"):
            otp_verify_form.phone_number.data = session["reset_phone_number"]

        return render_template(
            "patient_reset_password.html",
            otp_request_form=otp_request_form,
            otp_verify_form=otp_verify_form,
            otp_step_active=bool(session.get("reset_phone_number")),
        )

    # Patient dashboard route showing care summary and totals.
    @app.route("/patient/dashboard")
    @patient_required
    def patient_dashboard():
        patient = PatientLogin.query.get_or_404(session["patient_id"])
        care_record = get_or_create_care_record(patient.id)
        total_expense = round(sum(item.amount for item in patient.expenses), 2)
        delete_form = DeletePatientForm()
        last_updated_by_nurse = None
        if care_record.updated_by_nurse_id:
            nurse = NurseLogin.query.get(care_record.updated_by_nurse_id)
            if nurse:
                last_updated_by_nurse = f"{nurse.username} (ID {nurse.id})"
        return render_template(
            "patient_landing.html",
            patient=patient,
            care_record=care_record,
            total_expense=total_expense,
            report_count=len(patient.reports),
            delete_form=delete_form,
            last_updated_by_nurse=last_updated_by_nurse,
        )

    # Treatment route for hospital code verification and care log access.
    @app.route("/patient/treatment", methods=["GET", "POST"])
    @patient_required
    def patient_treatment():
        patient = PatientLogin.query.get_or_404(session["patient_id"])
        code_form = PatientHospitalCodeForm()
        shared_upload_form = PatientReportUploadForm(prefix="shared")
        personal_upload_form = PatientReportUploadForm(prefix="personal")
        last_updated_by_nurse = None
        is_verified = (
            session.get("care_code_verified") is True
            and session.get("patient_id") == patient.id
        )

        if not is_verified:
            if code_form.validate_on_submit():
                entered_code = code_form.hospital_code.data.strip()
                existing_code = (patient.hospital_code or "").strip()
                if existing_code and entered_code != existing_code:
                    flash("Invalid hospital code for this account.", "error")
                    return render_template(
                        "patient_treatment.html",
                        patient=patient,
                        care_record=None,
                        code_form=code_form,
                        shared_upload_form=shared_upload_form,
                        personal_upload_form=personal_upload_form,
                        reports=[],
                        personal_documents=[],
                        last_updated_by_nurse=last_updated_by_nurse,
                    )
                if not existing_code:
                    patient.hospital_code = entered_code
                    db.session.commit()
                    flash(
                        "Hospital code registered. You can now continue treatment tracking.",
                        "success",
                    )
                else:
                    flash("Hospital code verified.", "success")
                session["care_code_verified"] = True
                return redirect(url_for("patient_treatment"))

            return render_template(
                "patient_treatment.html",
                patient=patient,
                care_record=None,
                code_form=code_form,
                shared_upload_form=shared_upload_form,
                personal_upload_form=personal_upload_form,
                reports=[],
                personal_documents=[],
                last_updated_by_nurse=last_updated_by_nurse,
            )

        care_record = get_or_create_care_record(patient.id)
        if care_record.updated_by_nurse_id:
            nurse = NurseLogin.query.get(care_record.updated_by_nurse_id)
            if nurse:
                last_updated_by_nurse = f"{nurse.username} (ID {nurse.id})"
        return render_template(
            "patient_treatment.html",
            patient=patient,
            care_record=care_record,
            code_form=code_form,
            shared_upload_form=shared_upload_form,
            personal_upload_form=personal_upload_form,
            reports=patient.reports,
            personal_documents=patient.personal_documents,
            last_updated_by_nurse=last_updated_by_nurse,
        )

    # Expense route for adding and listing patient expense entries.
    @app.route("/patient/expenses", methods=["GET", "POST"])
    @patient_required
    def patient_expenses():
        patient = PatientLogin.query.get_or_404(session["patient_id"])
        form = PatientExpenseForm()

        if form.validate_on_submit():
            expense = PatientExpense(
                patient_id=patient.id,
                category=form.category.data.strip(),
                description=(form.description.data or "").strip(),
                amount=float(form.amount.data),
            )
            db.session.add(expense)
            db.session.commit()
            flash("Ledger entry added.", "success")
            return redirect(url_for("patient_expenses"))

        total_expense = round(sum(item.amount for item in patient.expenses), 2)
        return render_template(
            "patient_expenses.html",
            patient=patient,
            expenses=patient.expenses,
            total_expense=total_expense,
            form=form,
        )

    # Expense update route for editing a specific patient expense item.
    @app.route("/patient/expense/<int:expense_id>/update", methods=["GET", "POST"])
    @patient_required
    def patient_update_expense(expense_id: int):
        patient = PatientLogin.query.get_or_404(session["patient_id"])
        expense = PatientExpense.query.filter_by(id=expense_id, patient_id=patient.id).first_or_404()

        if request.method == "GET":
            return render_template("patient_expense_edit.html", patient=patient, expense=expense)

        category = (request.form.get("category") or "").strip()
        description = (request.form.get("description") or "").strip()
        amount_raw = (request.form.get("amount") or "").strip()

        if not category:
            flash("Supply type is required.", "error")
            return redirect(url_for("patient_expenses"))

        try:
            amount = float(amount_raw)
            if amount <= 0:
                raise ValueError
        except ValueError:
            flash("Amount must be greater than 0.", "error")
            return redirect(url_for("patient_expenses"))

        expense.category = category
        expense.description = description
        expense.amount = amount
        db.session.commit()
        flash("Ledger entry updated.", "success")
        return redirect(url_for("patient_expenses"))

    # Expense delete route for removing one patient expense item.
    @app.route("/patient/expense/<int:expense_id>/delete", methods=["POST"])
    @patient_required
    def patient_delete_expense(expense_id: int):
        patient = PatientLogin.query.get_or_404(session["patient_id"])
        expense = PatientExpense.query.filter_by(id=expense_id, patient_id=patient.id).first_or_404()
        db.session.delete(expense)
        db.session.commit()
        flash("Ledger entry deleted.", "success")
        return redirect(url_for("patient_expenses"))

    # Reports page route for personal document listing and upload form.
    @app.route("/patient/reports")
    @patient_required
    def patient_reports():
        patient = PatientLogin.query.get_or_404(session["patient_id"])
        personal_upload_form = PatientReportUploadForm(prefix="personal")
        return render_template(
            "patient_reports.html",
            patient=patient,
            personal_upload_form=personal_upload_form,
            personal_documents=patient.personal_documents,
        )

    # Shared report upload route (requires verified hospital code).
    @app.route("/patient/report/upload", methods=["POST"])
    @patient_required
    def patient_upload_report():
        patient = PatientLogin.query.get_or_404(session["patient_id"])
        is_verified = (
            session.get("care_code_verified") is True
            and session.get("patient_id") == patient.id
        )
        if not is_verified:
            flash("Enter and verify hospital code in Current Care Log first.", "error")
            return redirect(url_for("patient_treatment"))
        form = PatientReportUploadForm(prefix="shared")
        if not form.validate_on_submit():
            flash("Invalid report upload request.", "error")
            return redirect(url_for("patient_treatment"))

        try:
            original_name, saved_filename = save_report_as_pdf(form.report_file.data)
        except Exception as exc:
            flash(str(exc), "error")
            return redirect(url_for("patient_treatment"))

        report = PatientReport(
            patient_id=patient.id,
            original_filename=original_name,
            saved_filename=saved_filename,
        )
        db.session.add(report)
        db.session.commit()

        flash("Report uploaded to shared vault as PDF.", "success")
        return redirect(url_for("patient_treatment"))

    # Personal document upload route visible only to the patient.
    @app.route("/patient/personal-document/upload", methods=["POST"])
    @patient_required
    def patient_upload_personal_document():
        patient = PatientLogin.query.get_or_404(session["patient_id"])
        form = PatientReportUploadForm(prefix="personal")
        if not form.validate_on_submit():
            flash("Invalid personal document upload request.", "error")
            return redirect(url_for("patient_reports"))

        try:
            original_name, saved_filename = save_report_as_pdf(form.report_file.data)
        except Exception as exc:
            flash(str(exc), "error")
            return redirect(url_for("patient_reports"))

        source_path = os.path.join(current_app.config["REPORT_UPLOAD_FOLDER"], saved_filename)
        target_path = os.path.join(current_app.config["PERSONAL_DOC_UPLOAD_FOLDER"], saved_filename)
        os.replace(source_path, target_path)

        document = PatientPersonalDocument(
            patient_id=patient.id,
            original_filename=original_name,
            saved_filename=saved_filename,
        )
        db.session.add(document)
        db.session.commit()
        flash("Personal medical document uploaded (visible only to you).", "success")
        return redirect(url_for("patient_reports"))

    # Replace an existing shared report file with a new upload.
    @app.route("/patient/report/<int:report_id>/replace", methods=["POST"])
    @patient_required
    def patient_replace_report(report_id: int):
        patient = PatientLogin.query.get_or_404(session["patient_id"])
        report = PatientReport.query.filter_by(id=report_id, patient_id=patient.id).first_or_404()

        file_storage = request.files.get("report_file")
        if file_storage is None or not file_storage.filename:
            flash("Choose a report file to replace.", "error")
            return redirect(url_for("patient_reports"))

        try:
            original_name, saved_filename = save_report_as_pdf(file_storage)
        except Exception as exc:
            flash(str(exc), "error")
            return redirect(url_for("patient_reports"))

        old_saved_name = report.saved_filename
        report.original_filename = original_name
        report.saved_filename = saved_filename
        report.uploaded_at = datetime.utcnow()
        db.session.commit()
        remove_report_file(old_saved_name)
        flash("Report file replaced.", "success")
        return redirect(url_for("patient_reports"))

    # Delete a shared report record and its stored file.
    @app.route("/patient/report/<int:report_id>/delete", methods=["POST"])
    @patient_required
    def patient_delete_report(report_id: int):
        patient = PatientLogin.query.get_or_404(session["patient_id"])
        report = PatientReport.query.filter_by(id=report_id, patient_id=patient.id).first_or_404()
        saved_filename = report.saved_filename
        db.session.delete(report)
        db.session.commit()
        remove_report_file(saved_filename)
        flash("Report file deleted.", "success")
        return redirect(url_for("patient_reports"))

    # Delete a personal document record and its stored file.
    @app.route("/patient/personal-document/<int:document_id>/delete", methods=["POST"])
    @patient_required
    def patient_delete_personal_document(document_id: int):
        patient = PatientLogin.query.get_or_404(session["patient_id"])
        document = PatientPersonalDocument.query.filter_by(
            id=document_id, patient_id=patient.id
        ).first_or_404()
        saved_filename = document.saved_filename
        db.session.delete(document)
        db.session.commit()
        remove_personal_document_file(saved_filename)
        flash("Personal document deleted.", "success")
        return redirect(url_for("patient_reports"))

    # X-ray page route for the logged-in patient.
    @app.route("/patient/xray")
    @patient_required
    def patient_xray():
        patient = PatientLogin.query.get_or_404(session["patient_id"])
        return render_template("patient_xray.html", patient=patient)

    # Route allowing discharged patients to permanently delete records.
    @app.route("/patient/delete-records", methods=["POST"])
    @patient_required
    def patient_delete_records():
        patient = PatientLogin.query.get_or_404(session["patient_id"])
        form = DeletePatientForm()
        if not form.validate_on_submit():
            flash("Invalid delete request.", "error")
            return redirect(url_for("patient_dashboard"))

        if not patient.is_discharged:
            flash("Records can be deleted only after discharge.", "error")
            return redirect(url_for("patient_dashboard"))

        db.session.delete(patient)
        db.session.commit()
        session.clear()
        flash("Your records were deleted. You can register again with a new hospital code when admitted.", "success")
        return redirect(url_for("patient_register"))

    # Nurse login route that starts a nurse session with hospital code.
    @app.route("/nurse/login", methods=["GET", "POST"])
    def nurse_login():
        form = NurseLoginForm()
        if form.validate_on_submit():
            nurse = NurseLogin.query.filter_by(username=form.username.data.strip()).first()
            if nurse and nurse.check_password(form.password.data):
                session.clear()
                session["role"] = "nurse"
                session["nurse_id"] = nurse.id
                session["username"] = nurse.username
                session["hospital_code"] = form.hospital_code.data.strip()
                flash("Staff desk login successful.", "success")
                return redirect(url_for("nurse_dashboard"))
            flash("Invalid staff credentials.", "error")

        return render_template("nurse_login.html", form=form)

    # Nurse dashboard route filtered by active hospital code.
    @app.route("/nurse/dashboard")
    @nurse_required
    def nurse_dashboard():
        hospital_code = session["hospital_code"]
        patients = (
            PatientLogin.query.filter_by(hospital_code=hospital_code)
            .order_by(PatientLogin.is_discharged, PatientLogin.room_number, PatientLogin.patient_name)
            .all()
        )
        return render_template("nurse_dashboard.html", patients=patients, hospital_code=hospital_code)

    # Nurse route to create and onboard a new patient account.
    @app.route("/nurse/patient/new", methods=["GET", "POST"])
    @nurse_required
    def nurse_add_patient():
        form = NurseAddPatientForm()
        if form.validate_on_submit():
            phone_number = form.phone_number.data.strip()
            existing_user = PatientLogin.query.filter(
                PatientLogin.phone_number == phone_number
            ).first()
            if existing_user:
                flash("Contact number already exists.", "error")
                return render_template("nurse_add_patient.html", form=form)

            phone_digits = "".join(ch for ch in phone_number if ch.isdigit())
            username_base = f"pt{phone_digits[-10:]}" if phone_digits else f"pt{secrets.randbelow(10**10):010d}"
            username = username_base
            suffix = 1
            while PatientLogin.query.filter_by(username=username).first() is not None:
                username = f"{username_base}{suffix}"
                suffix += 1

            patient = PatientLogin(
                patient_name=form.patient_name.data.strip(),
                phone_number=phone_number,
                username=username,
                room_number=form.room_number.data.strip(),
                hospital_code=session["hospital_code"],
                is_discharged=False,
                discharged_at=None,
            )
            patient.set_password(secrets.token_urlsafe(24))
            db.session.add(patient)
            db.session.flush()

            record = PatientCareRecord(patient_id=patient.id)
            db.session.add(record)
            db.session.commit()
            send_registration_sms(
                patient.patient_name,
                patient.phone_number,
                patient.room_number,
            )

            flash("Subject file added successfully.", "success")
            return redirect(url_for("nurse_patient_detail", patient_id=patient.id))

        return render_template("nurse_add_patient.html", form=form)

    # Nurse patient detail route for viewing/updating care timeline.
    @app.route("/nurse/patient/<int:patient_id>", methods=["GET", "POST"])
    @nurse_required
    def nurse_patient_detail(patient_id: int):
        patient = PatientLogin.query.filter_by(
            id=patient_id, hospital_code=session["hospital_code"]
        ).first_or_404()
        care_record = get_or_create_care_record(patient.id)
        nurse = NurseLogin.query.get_or_404(session["nurse_id"])
        nurse_label = f"{nurse.username} (ID {nurse.id})"
        record_form = NursePatientRecordForm()
        delete_form = DeletePatientForm()

        if record_form.validate_on_submit():
            patient.room_number = record_form.room_number.data.strip()
            care_record.medications = append_timestamped_entry(
                care_record.medications, record_form.medications.data, nurse_label
            )
            care_record.injections = append_timestamped_entry(
                care_record.injections, record_form.injections.data, nurse_label
            )
            care_record.prescriptions = append_timestamped_entry(
                care_record.prescriptions, record_form.prescriptions.data, nurse_label
            )
            care_record.notes = (record_form.notes.data or "").strip()
            care_record.updated_at = datetime.utcnow()
            care_record.updated_by_nurse_id = session["nurse_id"]

            update_entry = PatientCareUpdate(
                patient_id=patient.id,
                nurse_id=session["nurse_id"],
                room_number=patient.room_number,
                medications=care_record.medications,
                injections=care_record.injections,
                prescriptions=care_record.prescriptions,
                notes=care_record.notes,
            )
            db.session.add(update_entry)
            patient.is_discharged = False
            patient.discharged_at = None
            db.session.commit()
            flash("Subject file updated with timeline timestamp.", "success")
            return redirect(url_for("nurse_patient_detail", patient_id=patient.id))

        if not record_form.is_submitted():
            record_form.room_number.data = patient.room_number or ""
            record_form.medications.data = care_record.medications or ""
            record_form.injections.data = care_record.injections or ""
            record_form.prescriptions.data = care_record.prescriptions or ""
            record_form.notes.data = care_record.notes or ""

        return render_template(
            "nurse_patient_detail.html",
            patient=patient,
            care_record=care_record,
            updates=patient.care_updates,
            reports=patient.reports,
            record_form=record_form,
            delete_form=delete_form,
        )

    # Nurse route to delete a patient record after form validation.
    @app.route("/nurse/patient/<int:patient_id>/delete", methods=["POST"])
    @nurse_required
    def nurse_delete_patient(patient_id: int):
        patient = PatientLogin.query.filter_by(
            id=patient_id, hospital_code=session["hospital_code"]
        ).first_or_404()
        form = DeletePatientForm()
        if form.validate_on_submit():
            db.session.delete(patient)
            db.session.commit()
            flash("Subject file deleted.", "success")
            return redirect(url_for("nurse_dashboard"))

        flash("Invalid delete request.", "error")
        return redirect(url_for("nurse_patient_detail", patient_id=patient_id))

    # Nurse route to discharge a patient and clear active room.
    @app.route("/nurse/patient/<int:patient_id>/discharge", methods=["POST"])
    @nurse_required
    def nurse_discharge_patient(patient_id: int):
        patient = PatientLogin.query.filter_by(
            id=patient_id, hospital_code=session["hospital_code"]
        ).first_or_404()
        form = DeletePatientForm()
        if not form.validate_on_submit():
            flash("Invalid discharge request.", "error")
            return redirect(url_for("nurse_patient_detail", patient_id=patient_id))

        patient.is_discharged = True
        patient.discharged_at = datetime.utcnow()
        patient.room_number = None
        db.session.commit()
        flash("Patient discharged. Records are retained until patient deletes them.", "success")
        return redirect(url_for("nurse_patient_detail", patient_id=patient_id))

    # Shared report file-serving route with role/ownership checks.
    @app.route("/reports/<filename>")
    def view_report(filename: str):
        report = PatientReport.query.filter_by(saved_filename=filename).first_or_404()
        role = session.get("role")
        if role == "patient" and session.get("patient_id") != report.patient_id:
            abort(403)
        if role not in {"patient", "nurse"}:
            abort(403)
        return send_from_directory(current_app.config["REPORT_UPLOAD_FOLDER"], filename)

    # Personal document file-serving route with ownership check.
    @app.route("/patient/personal-document/<filename>")
    @patient_required
    def view_personal_document(filename: str):
        document = PatientPersonalDocument.query.filter_by(saved_filename=filename).first_or_404()
        if session.get("patient_id") != document.patient_id:
            abort(403)
        return send_from_directory(current_app.config["PERSONAL_DOC_UPLOAD_FOLDER"], filename)
