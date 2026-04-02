import importlib.util
import zipfile
from collections import Counter


def main() -> None:
    with zipfile.ZipFile("archive.zip") as zf:
        names = zf.namelist()
        for name in names[:200]:
            print(name)
        print("TOTAL", len(names))
        parts = ["/".join(name.split("/")[:5]) for name in names if not name.endswith("/")]
        counts = Counter(parts)
        for item, count in counts.most_common(20):
            print("PATH", item, count)

    for mod in ["tensorflow", "torch", "sklearn", "numpy", "PIL"]:
        print(mod, bool(importlib.util.find_spec(mod)))


if __name__ == "__main__":
    main()
