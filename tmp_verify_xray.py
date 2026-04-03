from pathlib import Path

from xray_model import METRICS_PATH, MODEL_PATH, predict_xray


def main() -> None:
    sample_root = Path("data") / "xray_dataset"
    sample_path = next(
        path
        for path in sample_root.rglob("*")
        if path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg", ".bmp"}
    )

    result = predict_xray(sample_path.read_bytes())
    print("model_exists", MODEL_PATH.exists())
    print("metrics_exists", METRICS_PATH.exists())
    print("sample", sample_path)
    print("label", result["label"])
    print("confidence", result["confidence"])
    print("fracture_probability", result["fracture_probability"])


if __name__ == "__main__":
    main()
