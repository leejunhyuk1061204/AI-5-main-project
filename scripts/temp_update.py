import re

with open('scripts/extra_targets_v3.txt', 'r', encoding='utf-16le') as f:
    extra_targets = f.read()

# Replace EXTRA_TARGETS with TARGETS
extra_targets = extra_targets.replace('EXTRA_TARGETS = [', 'TARGETS = [')

with open('scripts/download_bulk_manuals.py', 'r', encoding='utf-8') as f:
    original_code = f.read()

# Replace the TARGETS list block
# It starts at line 11 (TARGETS = [) and ends at line 898 (])
pattern = re.compile(r'TARGETS = \[.*?\]', re.DOTALL)
new_code = pattern.sub(extra_targets.strip(), original_code)

with open('scripts/download_bulk_manuals.py', 'w', encoding='utf-8') as f:
    f.write(new_code)

print("Update complete.")
