from pathlib import Path
import sys


path = Path(sys.argv[1])
needle = sys.argv[2].lower()
lines = path.read_text().splitlines()

for idx, line in enumerate(lines, start=1):
    if needle in line.lower():
        start = max(1, idx - 8)
        end = min(len(lines), idx + 20)
        for line_no in range(start, end + 1):
            print(f"{line_no}: {lines[line_no - 1]}")
        print("-" * 60)
