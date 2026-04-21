import json
import zipfile
from collections import Counter
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from xray_model import FEATURE_COUNT, IMAGE_SIZE, METRICS_PATH, MODEL_DIR, MODEL_PATH, extract_features_from_image


BASE_DIR = Path(__file__).resolve().parent
ARCHIVE_PATH = BASE_DIR / "archive.zip"
DATA_DIR = BASE_DIR / "data" / "xray_dataset"


def ensure_dataset_extracted() -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    marker = DATA_DIR / ".extracted"
    if marker.exists():
        return DATA_DIR

    with zipfile.ZipFile(ARCHIVE_PATH) as zf:
        zf.extractall(DATA_DIR)

    marker.write_text("ok", encoding="utf-8")
    return DATA_DIR


def discover_split_dirs(dataset_root: Path) -> dict[str, Path]:
    split_dirs: dict[str, Path] = {}
    for split in ("train", "test"):
        matches = list(dataset_root.rglob(split))
        matches = [path for path in matches if path.is_dir()]
        if not matches:
            raise RuntimeError(f"Could not find dataset split directory: {split}")
        split_dirs[split] = matches[0]
    val_matches = [path for path in dataset_root.rglob("val") if path.is_dir()]
    if val_matches:
        split_dirs["val"] = val_matches[0]
    return split_dirs


def discover_class_dirs(split_dir: Path) -> dict[str, Path]:
    class_dirs = {path.name.lower(): path for path in split_dir.iterdir() if path.is_dir()}
    required = {"fractured", "not fractured"}
    if not required.issubset(class_dirs.keys()):
        raise RuntimeError(
            f"Expected class folders {sorted(required)} in {split_dir}, found {sorted(class_dirs)}"
        )
    return class_dirs


def image_paths_for_split(split_dir: Path) -> list[tuple[Path, int]]:
    class_dirs = discover_class_dirs(split_dir)
    items: list[tuple[Path, int]] = []
    for label_name, label_value in (("not fractured", 0), ("fractured", 1)):
        for path in class_dirs[label_name].rglob("*"):
            if path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".bmp"}:
                continue
            items.append((path, label_value))
    return items


def compute_features(image_path: Path) -> np.ndarray:
    from PIL import Image

    image = Image.open(image_path)
    feature_vector, _ = extract_features_from_image(image)
    return feature_vector


def build_dataset(items: list[tuple[Path, int]]) -> tuple[np.ndarray, np.ndarray]:
    features = []
    labels = []
    for path, label in items:
        try:
            features.append(compute_features(path))
            labels.append(label)
        except Exception:
            continue
    if not features:
        return np.empty((0, FEATURE_COUNT), dtype=np.float32), np.asarray(labels, dtype=np.int64)
    return np.vstack(features), np.asarray(labels, dtype=np.int64)


def main() -> None:
    dataset_root = ensure_dataset_extracted()
    split_dirs = discover_split_dirs(dataset_root)

    train_items = image_paths_for_split(split_dirs["train"])
    val_items = image_paths_for_split(split_dirs["val"]) if "val" in split_dirs else []
    test_items = image_paths_for_split(split_dirs["test"])

    print("Split counts:")
    split_summaries = [("train", train_items), ("test", test_items)]
    if val_items:
        split_summaries.insert(1, ("val", val_items))
    for name, items in split_summaries:
        counts = Counter(label for _, label in items)
        print(name, "total", len(items), "normal", counts.get(0, 0), "fractured", counts.get(1, 0))

    x_train, y_train = build_dataset(train_items)
    x_test, y_test = build_dataset(test_items)
    if len(y_train) == 0 or len(y_test) == 0:
        raise RuntimeError("Not enough readable X-ray images were found to train and test the model.")

    if val_items:
        x_val, y_val = build_dataset(val_items)
        x_train_all = np.vstack([x_train, x_val])
        y_train_all = np.concatenate([y_train, y_val])
    else:
        x_val = np.empty((0, FEATURE_COUNT), dtype=np.float32)
        y_val = np.asarray([], dtype=np.int64)
        x_train_all = x_train
        y_train_all = y_train

    model = Pipeline(
        [
            ("scaler", StandardScaler()),
            (
                "classifier",
                LogisticRegression(
                    max_iter=400,
                    solver="liblinear",
                    class_weight="balanced",
                    random_state=42,
                ),
            ),
        ]
    )
    model.fit(x_train_all, y_train_all)

    test_predictions = model.predict(x_test)
    test_accuracy = accuracy_score(y_test, test_predictions)
    val_accuracy = None
    if len(y_val) > 0:
        val_predictions = model.predict(x_val)
        val_accuracy = accuracy_score(y_val, val_predictions)
    report = classification_report(
        y_test,
        test_predictions,
        target_names=["not_fractured", "fractured"],
        output_dict=True,
        zero_division=0,
    )

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    import joblib

    joblib.dump(model, MODEL_PATH)

    metrics = {
        "image_size": list(IMAGE_SIZE),
        "feature_count": int(x_train_all.shape[1]),
        "train_samples": int(len(y_train_all)),
        "validation_samples": int(len(y_val)),
        "test_samples": int(len(y_test)),
        "validation_accuracy": float(val_accuracy) if val_accuracy is not None else None,
        "test_accuracy": float(test_accuracy),
        "classification_report": report,
    }
    METRICS_PATH.write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    print("Saved model to", MODEL_PATH)
    print("Saved metrics to", METRICS_PATH)
    if val_accuracy is not None:
        print("Validation accuracy:", round(val_accuracy, 4))
    else:
        print("Validation accuracy: not available (no val split found)")
    print("Test accuracy:", round(test_accuracy, 4))


if __name__ == "__main__":
    main()
