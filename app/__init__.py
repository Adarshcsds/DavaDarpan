import os
from datetime import datetime, timedelta, timezone

from flask import Flask
from dotenv import load_dotenv

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
load_dotenv(os.path.join(BASE_DIR, ".env"))

from .config import Config
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
from .routes import initialize_database, register_routes

IST_TIMEZONE = timezone(timedelta(hours=5, minutes=30))


def create_app(config_class=Config):
    base_dir = BASE_DIR
    app = Flask(
        __name__,
        instance_relative_config=True,
        instance_path=os.path.join(base_dir, "instance"),
        template_folder=os.path.join(base_dir, "templates"),
        static_folder=os.path.join(base_dir, "static"),
    )
    app.config.from_object(config_class)
    app.config["REPORT_UPLOAD_FOLDER"] = os.path.join(
        app.instance_path, app.config["REPORT_UPLOAD_SUBDIR"]
    )
    app.config["PERSONAL_DOC_UPLOAD_FOLDER"] = os.path.join(
        app.instance_path, app.config["PERSONAL_DOC_UPLOAD_SUBDIR"]
    )
    os.makedirs(app.instance_path, exist_ok=True)

    db.init_app(app)
    register_routes(app)
    initialize_database(app)

    @app.template_filter("ist_datetime")
    def ist_datetime(value: datetime | None) -> str:
        if value is None:
            return "Not updated yet"
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(IST_TIMEZONE).strftime("%Y-%m-%d %I:%M:%S %p IST")

    @app.shell_context_processor
    def make_shell_context():
        return {
            "db": db,
            "PatientLogin": PatientLogin,
            "NurseLogin": NurseLogin,
            "PatientCareRecord": PatientCareRecord,
            "PatientCareUpdate": PatientCareUpdate,
            "PatientReport": PatientReport,
            "PatientExpense": PatientExpense,
            "PatientPersonalDocument": PatientPersonalDocument,
        }

    return app
