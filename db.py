from __future__ import annotations

import json
import os
from typing import Any

import pymysql
from pymysql.cursors import DictCursor

DB_CONFIG = {
    "host": os.environ.get("DB_HOST"),
    "port": int(os.environ.get("DB_PORT")),
    "user": os.environ.get("DB_USER", "weatherai_app"),
    "password": os.environ.get("DB_PASSWORD"),
    "database": os.environ.get("DB_NAME"),
    "cursorclass": DictCursor,
    "autocommit": True,
}


def get_connection():
    return pymysql.connect(**DB_CONFIG)


def _normalize_params(params: tuple[Any, ...] | None) -> tuple[Any, ...]:
    return params or ()


def _guard_query(query: str, params: tuple[Any, ...] | None) -> tuple[Any, ...]:
    normalized_query = query.strip()
    normalized_params = _normalize_params(params)
    placeholder_count = normalized_query.count("%s")

    if placeholder_count != len(normalized_params):
        raise ValueError("Query placeholder count does not match parameter count.")

    return normalized_params


def fetch_one(query: str, params: tuple[Any, ...] | None = None):
    normalized_params = _guard_query(query, params)
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, normalized_params)
            return cursor.fetchone()


def fetch_all(query: str, params: tuple[Any, ...] | None = None):
    normalized_params = _guard_query(query, params)
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, normalized_params)
            return cursor.fetchall()


def execute(query: str, params: tuple[Any, ...] | None = None) -> int:
    normalized_params = _guard_query(query, params)
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, normalized_params)
            return cursor.lastrowid


def execute_plain(query: str) -> None:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query)


def get_user_by_username(username: str):
    return fetch_one(
        "SELECT id, username, password_hash, role, is_active FROM users WHERE username = %s LIMIT 1",
        (username,),
    )


def user_exists(username: str) -> bool:
    return fetch_one("SELECT id FROM users WHERE username = %s", (username,)) is not None


def insert_user(username: str, password_hash: str, role: str = "user", is_active: int = 1) -> int:
    return execute(
        "INSERT INTO users (username, password_hash, role, is_active) VALUES (%s, %s, %s, %s)",
        (username, password_hash, role, is_active),
    )


def get_user_role(username: str) -> str | None:
    user = fetch_one("SELECT role FROM users WHERE username = %s LIMIT 1", (username,))
    if not user:
        return None
    return user.get("role")


def insert_auth_log(username: str, event_type: str, ip_address: str | None) -> int:
    return execute(
        "INSERT INTO auth_logs (username, event_type, ip_address) VALUES (%s, %s, %s)",
        (username, event_type, ip_address),
    )


def insert_sensor_reading(topic: str, temperature: float, humidity: float, soil: float, payload: dict) -> int:
    return execute(
        """
        INSERT INTO sensor_readings (topic, temperature, humidity, soil, payload_json)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (topic, temperature, humidity, soil, json.dumps(payload)),
    )


def insert_prediction_log(
    sensor_reading_id: int | None,
    forecast_temperature: float,
    forecast_precipitation_probability: float,
    prediction: str,
    status_message: str,
    mqtt_command: str,
    soil: float,
) -> int:
    return execute(
        """
        INSERT INTO prediction_logs (
            sensor_reading_id, forecast_temperature, forecast_precipitation_probability,
            prediction, status_message, mqtt_command, soil
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        (
            sensor_reading_id,
            forecast_temperature,
            forecast_precipitation_probability,
            prediction,
            status_message,
            mqtt_command,
            soil,
        ),
    )


def insert_disease_detection(topic: str, disease: dict, payload: dict) -> int:
    return execute(
        """
        INSERT INTO disease_detections (
            topic, kondisi_daun, tingkat_keyakinan, status_deteksi,
            camera_status, stream_status, model_status, detected_at, payload_json
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            topic,
            str(disease.get("kondisi_daun", "Belum ada data")),
            float(disease.get("tingkat_keyakinan", 0) or 0),
            str(disease.get("status_deteksi", "unknown")),
            str(disease.get("camera_status", "unknown")),
            str(disease.get("stream_status", "unknown")),
            str(disease.get("model_status", "unknown")),
            str(disease.get("detected_at", "-")),
            json.dumps(payload),
        ),
    )


def delete_old_logs(days: int = 7) -> None:
    retention_days = int(days)
    cleanup_statements = (
        ("DELETE FROM auth_logs WHERE created_at < NOW() - INTERVAL %s DAY", (retention_days,)),
        ("DELETE FROM disease_detections WHERE created_at < NOW() - INTERVAL %s DAY", (retention_days,)),
        ("DELETE FROM prediction_logs WHERE created_at < NOW() - INTERVAL %s DAY", (retention_days,)),
        ("DELETE FROM sensor_readings WHERE received_at < NOW() - INTERVAL %s DAY", (retention_days,)),
    )

    for query, params in cleanup_statements:
        execute(query, params)


def export_sensor_logs():
    return fetch_all(
        "SELECT id, topic, temperature, humidity, soil, received_at FROM sensor_readings ORDER BY received_at DESC"
    )


def export_prediction_logs():
    return fetch_all(
        """
        SELECT id, sensor_reading_id, forecast_temperature, forecast_precipitation_probability,
               prediction, status_message, mqtt_command, soil, created_at
        FROM prediction_logs
        ORDER BY created_at DESC
        """
    )


def export_disease_logs():
    return fetch_all(
        """
        SELECT id, topic, kondisi_daun, tingkat_keyakinan, status_deteksi,
               camera_status, stream_status, model_status, detected_at, created_at
        FROM disease_detections
        ORDER BY created_at DESC
        """
    )
