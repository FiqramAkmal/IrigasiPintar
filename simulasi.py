from __future__ import annotations

import argparse
import json
import math
import os
import random
import ssl
import time
from pathlib import Path

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

BROKER = os.environ.get("MQTT_BROKER", "localhost")
PORT = int(os.environ.get("MQTT_PORT", "8883"))
USERNAME = os.environ.get("MQTT_USERNAME", "")
PASSWORD = os.environ.get("MQTT_PASSWORD", "")
TOPIC = os.environ.get("MQTT_TOPIC", "SIC7/data")


def build_client() -> mqtt.Client:
    client = mqtt.Client(client_id=f"weatherai-simulator-{random.randint(1000, 9999)}")

    if USERNAME:
        client.username_pw_set(USERNAME, PASSWORD)

    if PORT == 8883:
        client.tls_set(cert_reqs=ssl.CERT_NONE)
        client.tls_insecure_set(True)

    return client


def clamp(value: float, minimum: float, maximum: float) -> float:
    return min(max(value, minimum), maximum)


def generate_sensor_payload(step: int, profile: str) -> dict[str, str]:
    wave = math.sin(step / 3)
    swing = math.cos(step / 4)

    if profile == "dry":
        temperature = clamp(31 + wave * 1.8 + random.uniform(-0.4, 0.4), 26, 38)
        humidity = clamp(43 + swing * 5 + random.uniform(-1.2, 1.2), 30, 60)
        soil = clamp(18 + wave * 7 + random.uniform(-2, 2), 5, 35)
    elif profile == "wet":
        temperature = clamp(24 + wave * 1.5 + random.uniform(-0.4, 0.4), 20, 30)
        humidity = clamp(79 + swing * 6 + random.uniform(-1.5, 1.5), 60, 95)
        soil = clamp(82 + wave * 8 + random.uniform(-2, 2), 60, 100)
    else:
        temperature = clamp(27.5 + wave * 2.2 + random.uniform(-0.5, 0.5), 21, 34)
        humidity = clamp(66 + swing * 8 + random.uniform(-1.5, 1.5), 40, 90)
        soil = clamp(51 + wave * 14 + random.uniform(-3, 3), 10, 100)

    return {
        "temperature": f"{temperature:.2f}",
        "humidity": f"{humidity:.2f}",
        "soil": str(int(round(soil))),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Simulator data sensor WeatherAI ke MQTT.")
    parser.add_argument("--interval", type=float, default=1.5, help="Interval publish dalam detik. Default: 1.5")
    parser.add_argument("--count", type=int, default=0, help="Jumlah publish. 0 = tanpa batas.")
    parser.add_argument(
        "--profile",
        choices=["normal", "dry", "wet"],
        default="normal",
        help="Profil simulasi sensor.",
    )
    args = parser.parse_args()

    client = build_client()
    client.connect(BROKER, PORT, 60)
    client.loop_start()

    print(f"[SIM] Connected to MQTT {BROKER}:{PORT}")
    print(f"[SIM] Publishing to topic: {TOPIC}")
    print(f"[SIM] Profile: {args.profile} | Interval: {args.interval}s")

    step = 0
    sent = 0

    try:
        while True:
            payload = generate_sensor_payload(step, args.profile)
            payload_json = json.dumps(payload)
            client.publish(TOPIC, payload_json)
            print(f"[SIM] Published #{sent + 1}: {payload_json}")

            sent += 1
            step += 1

            if args.count and sent >= args.count:
                break

            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\n[SIM] Stopped by user")
    finally:
        client.loop_stop()
        client.disconnect()
        print("[SIM] Disconnected")


if __name__ == "__main__":
    main()
