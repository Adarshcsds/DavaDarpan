from pathlib import Path
import sys


path = Path(sys.argv[1])
start = int(sys.argv[2])
count = int(sys.argv[3])

lines = path.read_text().splitlines()
for idx in range(start - 1, min(start - 1 + count, len(lines))):
    print(f"{idx + 1}: {lines[idx]}")
