from __future__ import annotations

from functools import lru_cache
from io import BytesIO
from pathlib import Path

import joblib
import numpy as np
from PIL import Image, ImageChops, ImageFilter, ImageOps, ImageStat


BASE_DIR = Path(__file__).resolve().parent
MODEL_DIR = BASE_DIR / "models"
MODEL_PATH = MODEL_DIR / "fracture_classifier.joblib"
METRICS_PATH = MODEL_DIR / "fracture_classifier_metrics.json"
IMAGE_SIZE = (96, 96)
COARSE_SIZE = (24, 24)
FEATURE_COUNT = 16 + (COARSE_SIZE[0] * COARSE_SIZE[1] * 2)
CLASS_NAMES = {0: "Not fractured", 1: "Fractured"}


def extract_features_from_image(image: Image.Image) -> tuple[np.ndarray, dict[str, float]]:
    grayscale = ImageOps.autocontrast(image.convert("L").resize(IMAGE_SIZE))
    width, height = grayscale.size

    edge_image = grayscale.filter(ImageFilter.FIND_EDGES)
    left_half = grayscale.crop((0, 0, width // 2, height))
    right_half = grayscale.crop((width // 2, 0, width, height)).transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    asymmetry_image = ImageChops.difference(left_half, right_half)

    base = np.asarray(grayscale, dtype=np.float32) / 255.0
    edges = np.asarray(edge_image, dtype=np.float32) / 255.0

    vertical_profile = base.mean(axis=1)
    horizontal_profile = base.mean(axis=0)
    edge_vertical = edges.mean(axis=1)
    edge_horizontal = edges.mean(axis=0)

    stats = ImageStat.Stat(grayscale)
    edge_stats = ImageStat.Stat(edge_image)
    asym_stats = ImageStat.Stat(asymmetry_image)

    features = [
        float(stats.mean[0]),
        float(stats.stddev[0]),
        float(edge_stats.mean[0]),
        float(edge_stats.stddev[0]),
        float(asym_stats.mean[0]),
        float(asym_stats.stddev[0]),
        float(base[: height // 2, :].mean()),
        float(base[height // 2 :, :].mean()),
        float(base[:, : width // 2].mean()),
        float(base[:, width // 2 :].mean()),
        float(edges[: height // 2, :].mean()),
        float(edges[height // 2 :, :].mean()),
        float(vertical_profile.std()),
        float(horizontal_profile.std()),
        float(edge_vertical.std()),
        float(edge_horizontal.std()),
    ]

    coarse = grayscale.resize(COARSE_SIZE)
    coarse_edges = edge_image.resize(COARSE_SIZE)
    features.extend((np.asarray(coarse, dtype=np.float32) / 255.0).flatten().tolist())
    features.extend((np.asarray(coarse_edges, dtype=np.float32) / 255.0).flatten().tolist())

    metrics = {
        "brightness": round(float(stats.mean[0]), 1),
        "contrast": round(float(stats.stddev[0]), 1),
        "edge_strength": round(float(edge_stats.mean[0]), 1),
        "asymmetry": round(float(asym_stats.mean[0]), 1),
    }
    return np.asarray(features, dtype=np.float32), metrics


def extract_features_from_bytes(file_bytes: bytes) -> tuple[np.ndarray, dict[str, float], tuple[int, int]]:
    try:
        image = Image.open(BytesIO(file_bytes))
        image.load()
    except Exception as exc:
        raise RuntimeError("Could not read the uploaded X-ray image.") from exc

    feature_vector, metrics = extract_features_from_image(image)
    return feature_vector, metrics, image.size


@lru_cache(maxsize=1)
def load_xray_model():
    if not MODEL_PATH.exists():
        raise RuntimeError(
            "X-ray model not found. Run `python train_xray_model.py` to train and save it first."
        )
    return joblib.load(MODEL_PATH)


def predict_xray(file_bytes: bytes) -> dict[str, str | int | float]:
    feature_vector, metrics, image_size = extract_features_from_bytes(file_bytes)
    model = load_xray_model()

    probabilities = model.predict_proba(feature_vector.reshape(1, -1))[0]
    predicted_index = int(probabilities.argmax())
    fracture_probability = float(probabilities[1])
    confidence = float(probabilities[predicted_index])

    if predicted_index == 1:
        label = "Fractured"
        summary = (
            "The trained classifier found fracture-like patterns in this X-ray. "
            "A clinician should review the image."
        )
        tone = "high"
    else:
        label = "Not fractured"
        summary = (
            "The trained classifier found the image closer to the non-fractured examples "
            "in the training dataset."
        )
        tone = "low"

    return {
        "width": int(image_size[0]),
        "height": int(image_size[1]),
        "brightness": metrics["brightness"],
        "contrast": metrics["contrast"],
        "edge_strength": metrics["edge_strength"],
        "asymmetry": metrics["asymmetry"],
        "label": label,
        "summary": summary,
        "tone": tone,
        "predicted_class": CLASS_NAMES[predicted_index],
        "confidence": round(confidence * 100, 1),
        "fracture_probability": round(fracture_probability * 100, 1),
        "normal_probability": round(float(probabilities[0]) * 100, 1),
    }
