from pathlib import Path

p = Path("scripts/update_behance.py")
s = p.read_text(encoding="utf-8")

s = s.replace(
    'PROFILE_URL = "https://www.behance.net/oskuhallaART"',
    'PROFILE_URL = "https://www.behance.net/oskuhallaART/projects"',
    1,
)

reader_headers = '''            "X-Return-Format": "markdown",\n        },\n    )\n    text = response.text'''
reader_headers_new = '''            "X-Return-Format": "markdown",\n            "X-No-Cache": "true",\n        },\n    )\n    text = response.text'''
if reader_headers in s:
    s = s.replace(reader_headers, reader_headers_new, 1)
elif '"X-No-Cache": "true"' not in s.split('def load_existing', 1)[0]:
    raise SystemExit("Reader header marker not found")

old_block = '''    # Existing cards are verified against their own Behance URLs every day.\n    # The profile page is still used for discovering newly published projects.\n    kept_existing = []\n    removed_projects = []\n    for item in existing:\n        if str(item.get("source") or "").lower() != "behance":\n            kept_existing.append(item)\n            continue\n\n        pid = str(item.get("id") or "").strip()\n        if not pid:\n            kept_existing.append(item)\n            continue\n\n        if project_is_public(item):\n            kept_existing.append(item)\n        else:\n            removed_projects.append(item)\n            remove_local_previews(pid)\n            log(f"Removed deleted/private Behance project: {item.get('title', pid)} [{pid}]")\n\n        # Keep the unauthenticated Reader usage gentle.\n        time.sleep(0.5)\n\n    existing = kept_existing\n'''

new_block = '''    discovered_ids = {found["id"] for found in discovered}\n\n    # The fresh public Work page is the source of truth for the projects inside\n    # its visible newest-project window. This catches deleted/unpublished work\n    # even when an old direct project URL still resolves from a cache. Projects\n    # older than that window are verified individually so they are never removed\n    # merely because they have naturally fallen off the first profile page.\n    existing_positions = {\n        str(item.get("id")): index\n        for index, item in enumerate(existing)\n        if str(item.get("source") or "").lower() == "behance" and item.get("id")\n    }\n    matched_positions = [\n        existing_positions[found["id"]]\n        for found in discovered\n        if found["id"] in existing_positions\n    ]\n    visible_boundary = max(matched_positions) if matched_positions else -1\n\n    kept_existing = []\n    removed_projects = []\n    for index, item in enumerate(existing):\n        if str(item.get("source") or "").lower() != "behance":\n            kept_existing.append(item)\n            continue\n\n        pid = str(item.get("id") or "").strip()\n        if not pid:\n            kept_existing.append(item)\n            continue\n\n        missing_from_visible_profile = (\n            visible_boundary >= 0\n            and index <= visible_boundary\n            and pid not in discovered_ids\n        )\n\n        if missing_from_visible_profile:\n            removed_projects.append(item)\n            remove_local_previews(pid)\n            log(f"Removed project missing from public Behance profile: {item.get('title', pid)} [{pid}]")\n            continue\n\n        # Older projects outside the first-page window are checked by URL. A\n        # temporary Reader/network error keeps the card rather than deleting it.\n        if index > visible_boundary and not project_is_public(item):\n            removed_projects.append(item)\n            remove_local_previews(pid)\n            log(f"Removed unavailable Behance project: {item.get('title', pid)} [{pid}]")\n        else:\n            kept_existing.append(item)\n\n        time.sleep(0.35)\n\n    existing = kept_existing\n'''

if old_block not in s:
    raise SystemExit("Current existing-project sync block not found")
s = s.replace(old_block, new_block, 1)

p.write_text(s, encoding="utf-8")
print("Patched Behance sync to use the fresh public profile as source of truth")
