from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField, FileRequired
from wtforms import DecimalField, PasswordField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, EqualTo, Length, NumberRange, Regexp


PHONE_REGEX = r"^\d{10}$"


class PatientRegisterRequestForm(FlaskForm):
    patient_name = StringField(
        "Patient Name",
        validators=[DataRequired(), Length(min=2, max=120)],
    )
    phone_number = StringField(
        "Phone Number",
        validators=[
            DataRequired(),
            Regexp(PHONE_REGEX, message="Phone number must be exactly 10 digits."),
        ],
    )
    username = StringField(
        "Username",
        validators=[DataRequired(), Length(min=3, max=80)],
    )
    password = PasswordField(
        "Password",
        validators=[DataRequired(), Length(min=6, max=128)],
    )
    confirm_password = PasswordField(
        "Confirm Password",
        validators=[
            DataRequired(),
            EqualTo("password", message="Passwords must match."),
        ],
    )
    send_otp = SubmitField("Send OTP")


class PatientRegisterVerifyForm(FlaskForm):
    phone_number = StringField(
        "Phone Number",
        validators=[
            DataRequired(),
            Regexp(PHONE_REGEX, message="Phone number must be exactly 10 digits."),
        ],
    )
    otp_code = StringField(
        "OTP",
        validators=[
            DataRequired(),
            Regexp(r"^\d{6}$", message="OTP must be exactly 6 digits."),
        ],
    )
    submit = SubmitField("Verify OTP & Register")


class PatientLoginForm(FlaskForm):
    username = StringField(
        "Username",
        validators=[DataRequired(), Length(min=3, max=80)],
    )
    password = PasswordField(
        "Password",
        validators=[DataRequired(), Length(min=6, max=128)],
    )
    submit = SubmitField("Login")


class PatientResetPasswordRequestForm(FlaskForm):
    phone_number = StringField(
        "Phone Number",
        validators=[
            DataRequired(),
            Regexp(PHONE_REGEX, message="Phone number must be exactly 10 digits."),
        ],
    )
    send_otp = SubmitField("Send OTP")


class PatientResetPasswordVerifyForm(FlaskForm):
    phone_number = StringField(
        "Phone Number",
        validators=[
            DataRequired(),
            Regexp(PHONE_REGEX, message="Phone number must be exactly 10 digits."),
        ],
    )
    otp_code = StringField(
        "OTP",
        validators=[
            DataRequired(),
            Regexp(r"^\d{6}$", message="OTP must be exactly 6 digits."),
        ],
    )
    new_password = PasswordField(
        "New Password",
        validators=[DataRequired(), Length(min=6, max=128)],
    )
    confirm_password = PasswordField(
        "Confirm New Password",
        validators=[
            DataRequired(),
            EqualTo("new_password", message="Passwords must match."),
        ],
    )
    reset_password = SubmitField("Verify OTP & Reset Password")


class NurseLoginForm(FlaskForm):
    hospital_code = StringField(
        "Hospital Code",
        validators=[DataRequired(), Length(min=3, max=30)],
    )
    username = StringField(
        "Username",
        validators=[DataRequired(), Length(min=3, max=80)],
    )
    password = PasswordField(
        "Password",
        validators=[DataRequired(), Length(min=6, max=128)],
    )
    submit = SubmitField("Login")


class NurseAddPatientForm(FlaskForm):
    patient_name = StringField(
        "Patient Name",
        validators=[DataRequired(), Length(min=2, max=120)],
    )
    room_number = StringField(
        "Room Number",
        validators=[DataRequired(), Length(min=1, max=20)],
    )
    phone_number = StringField(
        "Phone Number",
        validators=[
            DataRequired(),
            Regexp(PHONE_REGEX, message="Phone number must be exactly 10 digits."),
        ],
    )
    submit = SubmitField("Create Patient")


class NursePatientRecordForm(FlaskForm):
    room_number = StringField(
        "Room Number",
        validators=[DataRequired(), Length(min=1, max=20)],
    )
    medications = TextAreaField(
        "Medications",
        validators=[Length(max=2000)],
    )
    injections = TextAreaField(
        "Injections",
        validators=[Length(max=2000)],
    )
    prescriptions = TextAreaField(
        "Prescriptions",
        validators=[Length(max=2000)],
    )
    notes = TextAreaField(
        "Notes",
        validators=[Length(max=4000)],
    )
    submit = SubmitField("Save Details")


class DeletePatientForm(FlaskForm):
    submit = SubmitField("Delete Patient")


class PatientReportUploadForm(FlaskForm):
    report_file = FileField(
        "Upload Report (PDF/JPG/PNG)",
        validators=[
            FileRequired(),
            FileAllowed(
                ["pdf", "jpg", "jpeg", "png"],
                "Only PDF, JPG, JPEG, PNG files are allowed.",
            ),
        ],
    )
    submit = SubmitField("Upload Report")


class PatientXrayAnalysisForm(FlaskForm):
    xray_file = FileField(
        "Upload X-Ray (JPG/PNG)",
        validators=[
            FileRequired(),
            FileAllowed(
                ["jpg", "jpeg", "png"],
                "Only JPG, JPEG, and PNG X-ray images are allowed.",
            ),
        ],
    )
    submit = SubmitField("Analyze X-Ray")


class PatientExpenseForm(FlaskForm):
    category = StringField(
        "Category",
        validators=[DataRequired(), Length(min=2, max=120)],
    )
    description = StringField(
        "Description",
        validators=[Length(max=255)],
    )
    amount = DecimalField(
        "Amount",
        validators=[DataRequired(), NumberRange(min=0.01)],
        places=2,
    )
    submit = SubmitField("Add Expense")


class PatientHospitalCodeForm(FlaskForm):
    hospital_code = StringField(
        "Hospital Code",
        validators=[DataRequired(), Length(min=3, max=30)],
    )
    submit = SubmitField("Register Hospital Code")
