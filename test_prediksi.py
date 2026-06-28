from __future__ import annotations

import argparse
import os
from pathlib import Path

import joblib
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_MODEL = BASE_DIR / os.environ.get("MODEL_FILENAME", "WeatherAI.joblib")
REQUIRED_COLUMNS = ["precipitation", "humidity", "temperature"]


def load_model(model_path: Path):
    if not model_path.exists():
        raise FileNotFoundError(f"Model tidak ditemukan: {model_path}")
    return joblib.load(model_path)


def validate_frame(frame: pd.DataFrame) -> pd.DataFrame:
    missing = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(f"Kolom wajib tidak ada: {', '.join(missing)}")

    validated = frame[REQUIRED_COLUMNS].copy()
    for column in REQUIRED_COLUMNS:
        validated[column] = pd.to_numeric(validated[column], errors="raise")
    return validated


def predict_single(model, precipitation: float, humidity: float, temperature: float) -> str:
    features = pd.DataFrame(
        [{
            "precipitation": precipitation,
            "humidity": humidity,
            "temperature": temperature,
        }]
    )
    prediction = model.predict(features)[0]
    return str(prediction)


def predict_csv(model, csv_path: Path, output_path: Path | None) -> pd.DataFrame:
    source = pd.read_csv(csv_path)
    features = validate_frame(source)
    result = source.copy()
    result["prediction"] = model.predict(features)

    if output_path is not None:
        result.to_csv(output_path, index=False)

    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Tes prediksi WeatherAI dari data manual atau file CSV."
    )
    parser.add_argument(
        "--model",
        default=str(DEFAULT_MODEL),
        help="Path model .joblib. Default ambil dari MODEL_FILENAME atau WeatherAI.joblib",
    )
    parser.add_argument("--precipitation", type=float, help="Nilai precipitation")
    parser.add_argument("--humidity", type=float, help="Nilai humidity")
    parser.add_argument("--temperature", type=float, help="Nilai temperature")
    parser.add_argument("--csv", help="Path CSV input untuk batch prediction")
    parser.add_argument("--output", help="Path CSV output hasil prediksi batch")
    return parser


if __name__ == "__main__":
    parser = build_parser()
    args = parser.parse_args()
    model = load_model(Path(args.model))

    if args.csv:
        csv_path = Path(args.csv)
        output_path = Path(args.output) if args.output else None
        result = predict_csv(model, csv_path, output_path)
        print(result.to_string(index=False))
        if output_path is not None:
            print(f"\nHasil disimpan ke: {output_path}")
    else:
        required_args = [args.precipitation, args.humidity, args.temperature]
        if any(value is None for value in required_args):
            parser.error("Untuk prediksi manual, isi --precipitation, --humidity, dan --temperature.")

        prediction = predict_single(
            model,
            precipitation=float(args.precipitation),
            humidity=float(args.humidity),
            temperature=float(args.temperature),
        )
        print("Input:")
        print(f"- precipitation: {args.precipitation}")
        print(f"- humidity: {args.humidity}")
        print(f"- temperature: {args.temperature}")
        print(f"Prediksi: {prediction}")
