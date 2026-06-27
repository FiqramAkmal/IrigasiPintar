from __future__ import annotations

import json
import os
import ssl
from pathlib import Path
from time import time

import paho.mqtt.client as mqtt


BASE_DIR = Path(__file__).resolve().parent


def load_env_file(env_path: Path) -> None:
    if not env_path.exists():
        return

    for line in env_path.read_text(encoding="utf-8").splitlines():
        entry = line.strip()
        if not entry or entry.startswith("#") or "=" not in entry:
            continue

        key, value = entry.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


load_env_file(BASE_DIR / ".env")

latest_data = {}
mqtt_client = None
last_message_at = None

BROKER = os.environ.get("MQTT_BROKER", "localhost")
PORT = int(os.environ.get("MQTT_PORT", "8883"))
USERNAME = os.environ.get("MQTT_USERNAME", "")
PASSWORD = os.environ.get("MQTT_PASSWORD", "")
TOPIC = os.environ.get("MQTT_TOPIC", "SIC7/data")
DISEASE_TOPIC = os.environ.get("MQTT_DISEASE_TOPIC", "WTH/disease")


def on_connect(client, userdata, flags, rc):
    print("[MQTT] Connected with code:", rc)
    client.subscribe(TOPIC)
    if DISEASE_TOPIC != TOPIC:
        client.subscribe(DISEASE_TOPIC)


def on_message(client, userdata, msg):
    global last_message_at

    try:
        payload = msg.payload.decode()
        print("[MQTT] Received:", payload)

        data = json.loads(payload)
        latest_data[msg.topic] = data
        last_message_at = time()

    except Exception as exc:
        print("[MQTT] JSON Error:", exc)


def get_last_message_age() -> float | None:
    if last_message_at is None:
        return None

    return max(0.0, time() - last_message_at)


def start_mqtt():
    global mqtt_client

    client = mqtt.Client()

    if USERNAME:
        client.username_pw_set(USERNAME, PASSWORD)

    if PORT == 8883:
        client.tls_set(cert_reqs=ssl.CERT_NONE)
        client.tls_insecure_set(True)

    client.on_connect = on_connect
    client.on_message = on_message

    client.connect(BROKER, PORT, 60)
    client.loop_start()

    mqtt_client = client

    print("[MQTT] Started MQTT Listener")


def publish_data(topic, message):
    global mqtt_client

    if mqtt_client is None:
        print("[MQTT] ERROR: MQTT not started!")
        return False

    try:
        mqtt_client.publish(topic, message)
        print(f"[MQTT] Published -> {topic}: {message}")
        return True

    except Exception as exc:
        print("[MQTT] Publish Error:", exc)
        return False
