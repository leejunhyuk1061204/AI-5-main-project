import os
import glob
from collections import Counter

root = "ai/data/yolo/engine"
pattern = os.path.join(root, "*_merged", "labels", "*.txt")
files = glob.glob(pattern)

counter = Counter()
for f in files:
    with open(f, 'r') as fh:
        for line in fh:
            parts = line.split()
            if parts:
                counter[parts[0]] += 1

print("Class ID | Count")
print("----------|------")
for cid in sorted(counter.keys(), key=int):
    print(f"{cid:<8} | {counter[cid]}")
