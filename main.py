from __future__ import annotations

import base64
import bcrypt
import csv
import hashlib
import hmac
import io
import json
import os
from datetime import datetime
from pathlib import Path
from threading import Lock
from time import time
from urllib.parse import urlparse

import joblib
import openmeteo_requests
import pandas as pd
import requests_cache
from flask import Flask, Response, jsonify, make_response, redirect, render_template, request, url_for
from retry_requests import retry

import db
import mqtt_handler

BASE_DIR = Path(__file__).resolve().parent
MODEL_PATH = BASE_DIR / os.environ.get("MODEL_FILENAME", "WeatherAIv2.joblib")
MQTT_TOPIC_DATA = mqtt_handler.TOPIC
MQTT_TOPIC_DISEASE = mqtt_handler.DISEASE_TOPIC
MQTT_TOPIC_COMMAND = os.environ.get("MQTT_COMMAND_TOPIC", "SIC7/command")
ENV_PATH = BASE_DIR / ".env"
JWT_COOKIE_NAME = os.environ.get("JWT_COOKIE_NAME", "weatherai_token")
JWT_ALGORITHM = os.environ.get("JWT_ALGORITHM", "HS256")
JWT_EXPIRES_SECONDS = int(os.environ.get("JWT_EXPIRES_SECONDS", str(60 * 60 * 8)))
MQTT_LIVE_THRESHOLD_SECONDS = int(os.environ.get("MQTT_LIVE_THRESHOLD_SECONDS", "15"))
WEATHER_API_URL = os.environ.get("WEATHER_API_URL", "https://api.open-meteo.com/v1/forecast")
WEATHER_LATITUDE = float(os.environ.get("WEATHER_LATITUDE", "-6.925220804796202"))
WEATHER_LONGITUDE = float(os.environ.get("WEATHER_LONGITUDE", "107.7742369649253"))
FLASK_HOST = os.environ.get("FLASK_HOST", "0.0.0.0")
FLASK_PORT = int(os.environ.get("FLASK_PORT", "5000"))
FLASK_DEBUG = os.environ.get("FLASK_DEBUG", "true").lower() == "true"
UI_REFRESH_INTERVAL_MS = int(os.environ.get("UI_REFRESH_INTERVAL_MS", "5000"))
PI_MJPEG_URL = os.environ.get("PI_MJPEG_URL", "")
PI_DETECTION_IMAGE_URL = os.environ.get("PI_DETECTION_IMAGE_URL", "")
PI_STREAM_LABEL = os.environ.get("PI_STREAM_LABEL", "Live Camera Monitor")
PI_DETECTION_LABEL = os.environ.get("PI_DETECTION_LABEL", "Plant Disease Detection")
PI_SNAPSHOT_REFRESH_MS = int(os.environ.get("PI_SNAPSHOT_REFRESH_MS", "5000"))


def load_env_file(env_path: Path) -> None:
    if not env_path.exists():
        return

    for line in env_path.read_text(encoding="utf-8").splitlines():
        entry = line.strip()
        if not entry or entry.startswith("#") or "=" not in entry:
            continue

        key, value = entry.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


load_env_file(ENV_PATH)

JWT_SECRET = os.environ.get("JWT_SECRET", "change-this-secret-key")
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")

app = Flask(__name__)

cache_session = requests_cache.CachedSession(str(BASE_DIR / ".cache"), expire_after=3600)
retry_session = retry(cache_session, retries=5, backoff_factor=0.2)
openmeteo = openmeteo_requests.Client(session=retry_session)
model = None
model_load_error = None

_mqtt_lock = Lock()
_mqtt_started = False
_control_lock = Lock()
_maintenance_lock = Lock()
_control_state = {
    "mode": "auto",
    "manual_command": "off",
    "last_effective_command": "off",
    "updated_by": None,
    "updated_at": None,
}
_last_cleanup_at = None
_last_disease_log_key = None


def b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("utf-8")


def b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def create_jwt(payload: dict) -> str:
    header = {"alg": JWT_ALGORITHM, "typ": "JWT"}
    header_segment = b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_segment = b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header_segment}.{payload_segment}".encode("utf-8")
    signature = hmac.new(JWT_SECRET.encode("utf-8"), signing_input, hashlib.sha256).digest()
    return f"{header_segment}.{payload_segment}.{b64url_encode(signature)}"


def decode_jwt(token: str) -> dict | None:
    try:
        header_segment, payload_segment, signature_segment = token.split(".")
        signing_input = f"{header_segment}.{payload_segment}".encode("utf-8")
        expected_signature = hmac.new(JWT_SECRET.encode("utf-8"), signing_input, hashlib.sha256).digest()
        provided_signature = b64url_decode(signature_segment)

        if not hmac.compare_digest(expected_signature, provided_signature):
            return None

        payload = json.loads(b64url_decode(payload_segment).decode("utf-8"))
        if float(payload.get("exp", 0)) < time():
            return None

        return payload
    except Exception:
        return None


def create_auth_token(username: str) -> str:
    now = int(time())
    role = db.get_user_role(username) or "user"
    payload = {
        "sub": username,
        "role": role,
        "iat": now,
        "exp": now + JWT_EXPIRES_SECONDS,
    }
    return create_jwt(payload)


def get_current_user() -> str | None:
    token = request.cookies.get(JWT_COOKIE_NAME)
    if not token:
        return None

    payload = decode_jwt(token)
    if not payload:
        return None

    return payload.get("sub")


def get_current_role() -> str | None:
    username = get_current_user()
    if not username:
        return None

    try:
        return db.get_user_role(username)
    except Exception:
        return None


def is_safe_next_url(target: str | None) -> bool:
    if not target:
        return False

    parsed = urlparse(target)
    return not parsed.netloc and parsed.path.startswith("/")


def require_auth():
    user = get_current_user()
    if user:
        return user

    if request.path.startswith("/api/"):
        return jsonify({"error": "Unauthorized"}), 401

    next_url = request.full_path if request.query_string else request.path
    return redirect(url_for("login", next=next_url))


def require_admin():
    auth_result = require_auth()
    if not isinstance(auth_result, str):
        return auth_result

    if get_current_role() != "admin":
        return jsonify({"error": "Forbidden"}), 403

    return auth_result


def ensure_mqtt_started() -> None:
    global _mqtt_started

    if _mqtt_started:
        return

    with _mqtt_lock:
        if not _mqtt_started:
            mqtt_handler.start_mqtt()
            _mqtt_started = True


def maybe_run_weekly_cleanup() -> None:
    global _last_cleanup_at

    with _maintenance_lock:
        now = datetime.now()
        if _last_cleanup_at is not None and (now - _last_cleanup_at).days < 7:
            return

        try:
            db.delete_old_logs(days=7)
            _last_cleanup_at = now
        except Exception:
            return


def get_control_state() -> dict:
    with _control_lock:
        return dict(_control_state)


def update_control_state(*, mode: str | None = None, manual_command: str | None = None, updated_by: str | None = None) -> dict:
    with _control_lock:
        if mode is not None:
            _control_state["mode"] = mode
        if manual_command is not None:
            _control_state["manual_command"] = manual_command
        if updated_by is not None:
            _control_state["updated_by"] = updated_by
            _control_state["updated_at"] = datetime.now().isoformat()
        return dict(_control_state)


def set_effective_command(command: str) -> None:
    with _control_lock:
        _control_state["last_effective_command"] = command


def get_model():
    global model, model_load_error

    if model is not None:
        return model

    if model_load_error is not None:
        raise RuntimeError(model_load_error)

    try:
        model = joblib.load(MODEL_PATH)
        return model
    except Exception as exc:
        model_load_error = (
            "Model gagal dimuat. Biasanya ini karena versi `numpy` dan `scikit-learn` tidak cocok dengan file model. "
            f"Detail asli: {exc}"
        )
        raise RuntimeError(model_load_error) from exc


def get_weather() -> pd.DataFrame:
    url = WEATHER_API_URL
    params = {
        "latitude": WEATHER_LATITUDE,
        "longitude": WEATHER_LONGITUDE,
        "forecast_days": 1,
        "hourly": [
            "temperature_2m",
            "relative_humidity_2m",
            "precipitation_probability",
            "precipitation",
        ],
    }

    responses = openmeteo.weather_api(url, params=params)
    response = responses[0]
    hourly = response.Hourly()

    hourly_data = {
        "date": pd.date_range(
            start=pd.to_datetime(hourly.Time(), unit="s", utc=True),
            end=pd.to_datetime(hourly.TimeEnd(), unit="s", utc=True),
            freq=pd.Timedelta(seconds=hourly.Interval()),
            inclusive="left",
        ),
        "temperature_2m": hourly.Variables(0).ValuesAsNumpy(),
        "humidity": hourly.Variables(1).ValuesAsNumpy(),
        "precipitation_probability": hourly.Variables(2).ValuesAsNumpy(),
        "precipitation": hourly.Variables(3).ValuesAsNumpy(),
    }

    return pd.DataFrame(hourly_data)


def get_sensor_data() -> dict[str, float]:
    mqtt_data = mqtt_handler.latest_data.get(MQTT_TOPIC_DATA, {})

    return {
        "temperature": float(mqtt_data.get("temperature", 0) or 0),
        "humidity": float(mqtt_data.get("humidity", 0) or 0),
        "soil": float(mqtt_data.get("soil", 0) or 0),
    }


def get_disease_data() -> dict:
    mqtt_data = mqtt_handler.latest_data.get(MQTT_TOPIC_DISEASE, {})

    return {
        "kondisi_daun": mqtt_data.get("kondisi_daun", "Belum ada data"),
        "tingkat_keyakinan": float(mqtt_data.get("tingkat_keyakinan", 0) or 0),
        "status_deteksi": mqtt_data.get("status_deteksi", "unknown"),
        "camera_status": mqtt_data.get("camera_status", "unknown"),
        "stream_status": mqtt_data.get("stream_status", "unknown"),
        "model_status": mqtt_data.get("model_status", "unknown"),
        "detected_at": mqtt_data.get("detected_at", "-"),
    }


def store_sensor_reading(sensor_data: dict[str, float], raw_payload: dict) -> int | None:
    try:
        return db.insert_sensor_reading(
            MQTT_TOPIC_DATA,
            sensor_data["temperature"],
            sensor_data["humidity"],
            sensor_data["soil"],
            raw_payload,
        )
    except Exception:
        return None


def store_prediction_log(
    sensor_reading_id: int | None,
    forecast_temperature: float,
    forecast_precipitation_probability: float,
    prediction: str,
    watering: dict[str, str | bool],
    soil: float,
) -> None:
    try:
        db.insert_prediction_log(
            sensor_reading_id,
            forecast_temperature,
            forecast_precipitation_probability,
            prediction,
            str(watering["message"]),
            str(watering["command"]),
            soil,
        )
    except Exception:
        return


def find_user_by_username(username: str):
    return db.get_user_by_username(username)


def store_disease_log(disease_data: dict, raw_payload: dict) -> None:
    global _last_disease_log_key

    detected_at = str(disease_data.get("detected_at", "-"))
    kondisi_daun = str(disease_data.get("kondisi_daun", "Belum ada data"))

    if detected_at == "-" and kondisi_daun == "Belum ada data":
        return

    log_key = (detected_at, kondisi_daun, str(disease_data.get("status_deteksi", "unknown")))
    if _last_disease_log_key == log_key:
        return

    try:
        db.insert_disease_detection(MQTT_TOPIC_DISEASE, disease_data, raw_payload)
        _last_disease_log_key = log_key
    except Exception:
        return


def verify_login(username: str, password: str) -> bool:
    try:
        user = find_user_by_username(username)
    except Exception:
        return False

    if not user or not user.get("is_active"):
        return False

    try:
        return bcrypt.checkpw(password.encode("utf-8"), user["password_hash"].encode("utf-8"))
    except Exception:
        return False


def log_auth_event(username: str, event_type: str) -> None:
    try:
        db.insert_auth_log(username, event_type, request.remote_addr)
    except Exception:
        return


def get_prediction(sensor_data: dict[str, float], weather_df: pd.DataFrame) -> str:
    now = pd.Timestamp.now(tz="UTC").floor("h")
    forecast = weather_df.copy()
    forecast["date"] = pd.to_datetime(forecast["date"], utc=True)
    upcoming = forecast[forecast["date"] >= now].reset_index(drop=True)

    if upcoming.empty:
        raise ValueError("Forecast cuaca tidak tersedia.")

    forecast_index = min(2, len(upcoming) - 1)
    features = pd.DataFrame(
        [
            {
                "precipitation": float(upcoming.loc[forecast_index, "precipitation"]),
                "humidity": sensor_data["humidity"],
                "temperature": sensor_data["temperature"],
            }
        ]
    )

    loaded_model = get_model()
    return loaded_model.predict(features)[0]


def build_watering_status(rain_prob: str, soil: float) -> dict[str, str | bool]:
    if rain_prob == "Tidak Disiram":
        return {
            "message": "Tidak perlu disiram, prediksi hujan.",
            "variant": "good",
            "command": "off",
            "buzzer": False,
        }

    if rain_prob == "Disiram Sedikit" and soil >= 60:
        return {
            "message": "Tidak perlu disiram, tanah masih lembab.",
            "variant": "good",
            "command": "off",
            "buzzer": False,
        }

    if rain_prob == "Disiram Banyak" and soil < 10:
        return {
            "message": "Perlu disiram banyak.",
            "variant": "danger",
            "command": "on",
            "buzzer": True,
        }

    if rain_prob == "Disiram Normal" and soil > 30:
        return {
            "message": "Penyiraman bisa dipertimbangkan.",
            "variant": "warn",
            "command": "on",
            "buzzer": True,
        }

    return {
        "message": "Siram normal saja.",
        "variant": "info",
        "command": "on",
        "buzzer": True,
    }


def build_dashboard_context() -> dict:
    ensure_mqtt_started()
    maybe_run_weekly_cleanup()

    raw_payload = mqtt_handler.latest_data.get(MQTT_TOPIC_DATA, {})
    raw_disease_payload = mqtt_handler.latest_data.get(MQTT_TOPIC_DISEASE, {})
    last_message_age = mqtt_handler.get_last_message_age()
    is_sensor_live = last_message_age is not None and last_message_age <= MQTT_LIVE_THRESHOLD_SECONDS
    sensor_data = get_sensor_data()
    disease_data = get_disease_data()
    store_disease_log(disease_data, raw_disease_payload)
    sensor_reading_id = store_sensor_reading(sensor_data, raw_payload)
    weather_df = get_weather()
    weather_view = weather_df.copy()
    weather_view["date"] = pd.to_datetime(weather_view["date"], utc=True).dt.tz_convert("Asia/Jakarta")
    weather_view["date_label"] = weather_view["date"].dt.strftime("%H:%M")
    now_jakarta = pd.Timestamp.now(tz="Asia/Jakarta").floor("h")
    upcoming_weather = weather_view[weather_view["date"] >= now_jakarta].reset_index(drop=True)
    summary_source = upcoming_weather if not upcoming_weather.empty else weather_view

    if summary_source.empty:
        forecast_summary = {
            "temperature": 0.0,
            "precipitation_probability": 0.0,
            "time_label": "-",
        }
    else:
        forecast_summary = {
            "temperature": round(float(summary_source.iloc[0]["temperature_2m"]), 2),
            "precipitation_probability": round(float(summary_source.iloc[0]["precipitation_probability"]), 2),
            "time_label": str(summary_source.iloc[0]["date_label"]),
        }

    prediction = get_prediction(sensor_data, weather_df)
    watering = build_watering_status(prediction, sensor_data["soil"])
    current_role = get_current_role() or "user"
    control_state = get_control_state()
    effective_command = watering["command"]

    if current_role == "admin":
        if control_state["mode"] == "auto":
            store_prediction_log(
                sensor_reading_id,
                forecast_summary["temperature"],
                forecast_summary["precipitation_probability"],
                prediction,
                watering,
                sensor_data["soil"],
            )
            mqtt_handler.publish_data(MQTT_TOPIC_COMMAND, watering["command"])
            effective_command = str(watering["command"])
        else:
            effective_command = str(control_state["manual_command"])
            mqtt_handler.publish_data(MQTT_TOPIC_COMMAND, effective_command)
            watering = {
                **watering,
                "message": f"Manual mode aktif. Command saat ini: {effective_command.upper()}.",
                "command": effective_command,
                "variant": "info" if effective_command == "off" else "warn",
            }
    else:
        watering = {
            **watering,
            "message": f"{watering['message']} Monitoring only.",
            "command": "monitor-only",
            "buzzer": False,
        }
        effective_command = "monitor-only"

    set_effective_command(effective_command)
    control_state = get_control_state()

    return {
        "generated_at": datetime.now(),
        "current_role": current_role,
        "ui_refresh_interval_ms": UI_REFRESH_INTERVAL_MS,
        "pi_mjpeg_url": PI_MJPEG_URL,
        "pi_detection_image_url": PI_DETECTION_IMAGE_URL,
        "pi_stream_label": PI_STREAM_LABEL,
        "pi_detection_label": PI_DETECTION_LABEL,
        "pi_snapshot_refresh_ms": PI_SNAPSHOT_REFRESH_MS,
        "sensor_status": {
            "state": "live" if is_sensor_live else "offline",
            "label": "Live" if is_sensor_live else "Offline",
            "last_message_age": last_message_age,
        },
        "control_state": control_state,
        "sensor": sensor_data,
        "forecast_summary": forecast_summary,
        "disease": disease_data,
        "prediction": prediction,
        "watering": watering,
        "weather_labels": weather_view["date_label"].tolist(),
        "temperature_series": [round(float(value), 2) for value in weather_view["temperature_2m"].tolist()],
        "precipitation_probability_series": [round(float(value), 2) for value in weather_view["precipitation_probability"].tolist()],
        "weather_rows": weather_view[["date_label", "temperature_2m", "humidity", "precipitation_probability", "precipitation"]]
        .round(2)
        .to_dict(orient="records"),
    }


@app.route("/")
def index():
    auth_result = require_auth()
    if not isinstance(auth_result, str):
        return auth_result

    try:
        context = build_dashboard_context()
        context["current_user"] = auth_result
        context["current_role"] = get_current_role() or "user"
        return render_template("index.html", **context)
    except Exception as exc:
        return render_template("error.html", error_message=str(exc)), 500


@app.route("/api/status")
def api_status():
    auth_result = require_auth()
    if not isinstance(auth_result, str):
        return auth_result

    try:
        context = build_dashboard_context()
        return jsonify(
            {
                "generated_at": context["generated_at"].isoformat(),
                "sensor": context["sensor"],
                "forecast_summary": context["forecast_summary"],
                "disease": context["disease"],
                "sensor_status": context["sensor_status"],
                "prediction": context["prediction"],
                "watering": context["watering"],
                "current_role": context["current_role"],
                "control_state": context["control_state"],
                "ui_refresh_interval_ms": context["ui_refresh_interval_ms"],
                "pi_mjpeg_url": context["pi_mjpeg_url"],
                "pi_detection_image_url": context["pi_detection_image_url"],
                "pi_stream_label": context["pi_stream_label"],
                "pi_detection_label": context["pi_detection_label"],
                "pi_snapshot_refresh_ms": context["pi_snapshot_refresh_ms"],
                "weather_labels": context["weather_labels"],
                "temperature_series": context["temperature_series"],
                "precipitation_probability_series": context["precipitation_probability_series"],
                "weather_rows": context["weather_rows"],
            }
        )
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/login", methods=["GET", "POST"])
def login():
    if get_current_user():
        return redirect(url_for("index"))

    error_message = None
    next_url = request.args.get("next") or request.form.get("next") or url_for("index")

    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""

        if verify_login(username, password):
            response = make_response(redirect(next_url if is_safe_next_url(next_url) else url_for("index")))
            response.set_cookie(
                JWT_COOKIE_NAME,
                create_auth_token(username),
                max_age=JWT_EXPIRES_SECONDS,
                httponly=True,
                samesite="Lax",
            )
            log_auth_event(username, "login_success")
            return response

        log_auth_event(username or "unknown", "login_failed")
        error_message = "Username atau password salah."

    return render_template("login.html", error_message=error_message, next_url=next_url)


@app.route("/register", methods=["GET", "POST"])
def register():
    if get_current_user():
        return redirect(url_for("index"))

    error_message = None
    success_message = None

    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        confirm_password = request.form.get("confirm_password") or ""

        if len(username) < 3:
            error_message = "Username minimal 3 karakter."
        elif len(password) < 8:
            error_message = "Password minimal 8 karakter."
        elif password != confirm_password:
            error_message = "Konfirmasi password tidak cocok."
        elif db.user_exists(username):
            error_message = "Username sudah terdaftar."
        else:
            password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
            db.insert_user(username, password_hash, "user", 1)
            log_auth_event(username, "register_success")
            success_message = "Registrasi berhasil. Silakan login."

    return render_template("register.html", error_message=error_message, success_message=success_message)


@app.route("/api/control", methods=["POST"])
def api_control():
    auth_result = require_admin()
    if not isinstance(auth_result, str):
        return auth_result

    payload = request.get_json(silent=True) or {}
    mode = payload.get("mode")
    manual_command = payload.get("manual_command")

    if mode not in {"auto", "manual", None}:
        return jsonify({"error": "Invalid mode"}), 400

    if manual_command not in {"on", "off", None}:
        return jsonify({"error": "Invalid manual_command"}), 400

    state = get_control_state()

    if mode == "auto":
        state = update_control_state(mode="auto", updated_by=auth_result)
    elif mode == "manual":
        state = update_control_state(mode="manual", updated_by=auth_result)

    if manual_command is not None:
        state = get_control_state()
        if state["mode"] != "manual":
            return jsonify({"error": "Manual command only allowed in manual mode"}), 409
        mqtt_handler.publish_data(MQTT_TOPIC_COMMAND, manual_command)
        state = update_control_state(manual_command=manual_command, updated_by=auth_result)
        set_effective_command(manual_command)

    return jsonify({"ok": True, "control_state": get_control_state()})


def _csv_response(filename: str, rows: list[dict]) -> Response:
    output = io.StringIO()
    if rows:
        writer = csv.DictWriter(output, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    else:
        output.write("no_data\n")

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.route("/export/sensor-logs.csv")
def export_sensor_logs_csv():
    auth_result = require_admin()
    if not isinstance(auth_result, str):
        return auth_result

    return _csv_response("sensor_logs.csv", db.export_sensor_logs())


@app.route("/export/prediction-logs.csv")
def export_prediction_logs_csv():
    auth_result = require_admin()
    if not isinstance(auth_result, str):
        return auth_result

    return _csv_response("prediction_logs.csv", db.export_prediction_logs())


@app.route("/export/disease-logs.csv")
def export_disease_logs_csv():
    auth_result = require_admin()
    if not isinstance(auth_result, str):
        return auth_result

    return _csv_response("disease_logs.csv", db.export_disease_logs())


@app.route("/logout", methods=["POST"])
def logout():
    username = get_current_user() or "unknown"
    log_auth_event(username, "logout")
    response = make_response(redirect(url_for("login")))
    response.delete_cookie(JWT_COOKIE_NAME)
    return response


if __name__ == "__main__":
    ensure_mqtt_started()
    app.run(debug=FLASK_DEBUG, host=FLASK_HOST, port=FLASK_PORT)
