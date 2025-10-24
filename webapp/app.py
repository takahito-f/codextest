"""Flask application entry point."""

from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - fallback when python-dotenv is unavailable
    def load_dotenv(*_args, **_kwargs):
        return False
from flask import (
    Flask,
    flash,
    g,
    redirect,
    render_template,
    request,
    url_for,
)
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from auth import extract_principal
from billing_service import mask, query_billing
from database import Base, get_engine, init_engine, session_scope
from models import Role, TouchakuKanri
from storage import get_blob_client
from timeutil import configure_tz, now_jtc_naive
from validators import validate_billing_month, validate_operator_id

configure_tz()
load_dotenv(Path(__file__).resolve().parent / ".env")  # optional local override

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger(__name__)

MAX_FILE_SIZE = 10 * 1024 * 1024
ALLOWED_EXTENSIONS = {".csv"}
ALLOWED_MIME_TYPES = {"text/csv", "application/vnd.ms-excel"}
DEFAULT_STATUS = 0


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET_KEY", "dev-secret")

    db_url = os.environ.get("DB_URL")
    if not db_url:
        raise RuntimeError("DB_URL environment variable is required")
    init_engine(db_url)
    Base.metadata.create_all(bind=get_engine())
    seed_roles()

    @app.before_request
    def load_user() -> None:
        principal = extract_principal(request)
        g.user = principal

    @app.route("/")
    def index():
        return redirect(url_for("billing"))

    @app.get("/upload")
    def upload_form():
        return render_template("upload.html")

    @app.post("/upload")
    def upload_file():
        file = request.files.get("file")
        if not file:
            flash("ファイルを選択してください。", "error")
            return redirect(url_for("upload_form"))

        error = validate_upload(file)
        if error:
            flash(error, "error")
            return redirect(url_for("upload_form"))

        filename = secure_filename(file.filename)
        file.seek(0, os.SEEK_END)
        size = file.tell()
        file.seek(0)
        content = file.read()

        account_url = os.environ.get("AZURE_STORAGE_ACCOUNT_URL")
        container_name = os.environ.get("BLOB_CONTAINER", "kakinfiles")
        if not account_url:
            flash("ストレージ設定が不足しています。", "error")
            return redirect(url_for("upload_form"))

        try:
            blob_client = get_blob_client(account_url, container_name, filename)
            blob_client.upload_blob(content, overwrite=True, content_type="text/csv")
            blob_url = f"{account_url.rstrip('/')}/{container_name}/{filename}"

            juryo_nichiji = now_jtc_naive()
            file_sakusei_date = datetime.now().strftime("%Y%m%d%H%M%S")
            appurodo_moto = build_upload_source()

            with session_scope() as session:
                record = TouchakuKanri(
                    juryo_nichiji=juryo_nichiji,
                    jigyosha_id=request.form.get("operator_id", "").ljust(15)[:15],
                    kakin_getsu=request.form.get("billing_month", "").ljust(6)[:6],
                    file_name=filename,
                    file_sakusei_date=file_sakusei_date,
                    file_size=size,
                    sutoreji_path=blob_url,
                    appurodo_moto=appurodo_moto,
                    status=DEFAULT_STATUS,
                )
                session.merge(record)
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Upload failed: %s", exc)
            flash("アップロードに失敗しました。", "error")
            return redirect(url_for("upload_form"))

        logger.info("Uploaded file %s (%s bytes) to %s", filename, size, blob_url)
        flash("アップロードが完了しました。", "success")
        return redirect(url_for("upload_form"))

    @app.get("/billing")
    def billing():
        operator_id = request.args.get("operator_id", "")
        billing_month = request.args.get("billing_month", "")
        sort = request.args.get("sort", "juryo_nichiji")
        order = request.args.get("order", "desc")
        try:
            page = int(request.args.get("page", "1"))
        except ValueError:
            page = 1
        page = max(page, 1)

        errors = {}
        if operator_id:
            valid, msg = validate_operator_id(operator_id)
            if not valid:
                errors["operator_id"] = msg
        if billing_month:
            valid, msg = validate_billing_month(billing_month)
            if not valid:
                errors["billing_month"] = msg

        results: List[Dict[str, Any]] = []
        total = 0
        per_page = 50

        if billing_month and not errors:
            try:
                results, total = query_billing(operator_id, billing_month, sort, order, page, per_page)
                logger.info("Billing search operator=%s month=%s hits=%s", mask(operator_id), billing_month, total)
            except SQLAlchemyError as exc:
                logger.exception("Billing search failed: %s", exc)
                flash("検索中にエラーが発生しました。", "error")

        return render_template(
            "billing.html",
            operator_id=operator_id,
            billing_month=billing_month,
            results=results,
            errors=errors,
            sort=sort,
            order=order,
            page=page,
            per_page=per_page,
            total=total,
        )

    return app


def seed_roles() -> None:
    roles = {
        "admin": "管理者",
        "user": "一般ユーザ",
    }
    with session_scope() as session:
        existing = {name for (name,) in session.execute(select(Role.role_name)).all()}
        for name, desc in roles.items():
            if name not in existing:
                session.add(Role(role_name=name, description=desc))


def validate_upload(file: FileStorage) -> Optional[str]:
    filename = file.filename or ""
    if not filename:
        return "ファイル名を取得できません。"
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        return "CSVファイルのみアップロード可能です。"
    if file.mimetype and file.mimetype.lower() not in ALLOWED_MIME_TYPES:
        return "CSVファイルの形式ではありません。"
    file.seek(0, os.SEEK_END)
    size = file.tell()
    file.seek(0)
    if size > MAX_FILE_SIZE:
        return "ファイルサイズは10MB以内で指定してください。"
    return None


def build_upload_source() -> str:
    parts = []
    if request.remote_addr:
        parts.append(request.remote_addr)
    if g.get("user") and g.user.name:
        parts.append(g.user.name)
    return " / ".join(parts)[:100] if parts else "unknown"


app = create_app()
