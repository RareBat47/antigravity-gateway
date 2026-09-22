import urllib.request
import re
import json

req = urllib.request.Request(
    'https://arena.ai/direct',
    headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
)
html = urllib.request.urlopen(req).read().decode('utf-8', errors='ignore')

# Extract all matches where publicName is present
pattern = re.compile(r'\\"publicName\\":\\"([^"\\]+)\\"')
models = sorted(set(pattern.findall(html)))

# Try to find organization or capabilities for each
org_pattern = re.compile(r'\\"organization\\":\\"([^"\\]+)\\"[^}]*?\\"publicName\\":\\"([^"\\]+)\\"')
org_map = {}
for org, name in org_pattern.findall(html):
    org_map[name] = org

reverse_org_pattern = re.compile(r'\\"publicName\\":\\"([^"\\]+)\\"[^}]*?\\"organization\\":\\"([^"\\]+)\\"')
for name, org in reverse_org_pattern.findall(html):
    if name not in org_map:
        org_map[name] = org

print(f"TOTAL_MODELS_COUNT: {len(models)}")
data = []
for m in models:
    org = org_map.get(m, "Other / Independent")
    data.append({"model": m, "organization": org})

with open("D:/arena-gateway-workspace/arena_models.json", "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2)

# Print categorized
by_org = {}
for item in data:
    by_org.setdefault(item["organization"], []).append(item["model"])

for org, names in sorted(by_org.items()):
    print(f"\n### {org.upper()} ({len(names)} models)")
    for n in sorted(names):
        print(f"  - {n}")
