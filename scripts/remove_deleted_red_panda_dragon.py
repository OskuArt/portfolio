#!/usr/bin/env python3
import json
from pathlib import Path

TARGET_ID = "213045385"
PROJECTS = Path("projects.json")
PREVIEW_DIR = Path("assets/project-previews")

items = json.loads(PROJECTS.read_text(encoding="utf-8"))
kept = [item for item in items if str(item.get("id")) != TARGET_ID]
removed = len(items) - len(kept)

if removed != 1:
    raise SystemExit(f"Expected to remove exactly 1 project {TARGET_ID}, removed {removed}")

PROJECTS.write_text(json.dumps(kept, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

if PREVIEW_DIR.exists():
    for path in PREVIEW_DIR.glob(f"{TARGET_ID}.*"):
        path.unlink()
        print(f"Deleted stale preview: {path}")

print(f"Removed Behance project {TARGET_ID}: Red Panda & Dragon")
