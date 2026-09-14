from pathlib import Path

p = Path("scripts/update_behance.py")
s = p.read_text(encoding="utf-8")

s = s.replace(
    "    Projects visible on the current profile page do not need an extra request.\n    This check is only used for existing projects that are no longer present on\n    that first profile page. Temporary Reader/network errors are treated as\n",
    "    Every saved Behance project is checked individually so profile-page or CDN\n    caches cannot leave a deleted project on the portfolio. Temporary Reader or\n    network errors are treated as\n",
    1,
)

s = s.replace(
    '                "X-Return-Format": "markdown",\n',
    '                "X-Return-Format": "markdown",\n                "X-No-Cache": "true",\n',
    1,
)

s = s.replace(
    '    discovered_ids = {found["id"] for found in discovered}\n\n    # The profile Reader is intentionally used only for the first page. Anything\n    # still visible there is definitely current. Older saved projects that are no\n    # longer on that first page are checked individually before being kept.\n',
    '    # Existing cards are verified against their own Behance URLs every day.\n    # The profile page is still used for discovering newly published projects.\n',
    1,
)

old = '        if not pid or pid in discovered_ids:\n            kept_existing.append(item)\n            continue\n'
new = '        if not pid:\n            kept_existing.append(item)\n            continue\n'
if old not in s:
    raise SystemExit("Existing-project verification marker not found")
s = s.replace(old, new, 1)

p.write_text(s, encoding="utf-8")
print("Updated Behance sync to verify every saved project")
