from pathlib import Path

p = Path("scripts/update_behance.py")
s = p.read_text(encoding="utf-8")

old = '''    profile_markdown = read_with_jina(PROFILE_URL)\n    discovered = extract_project_links(profile_markdown)\n'''
new = '''    # Give Jina Reader a unique target URL on every run. Behance ignores this\n    # harmless query parameter, while Jina treats it as a fresh cache key. This\n    # prevents a recently deleted/unpublished project from lingering in the\n    # cached profile response.\n    separator = "&" if "?" in PROFILE_URL else "?"\n    profile_target = f"{PROFILE_URL}{separator}_portfolio_sync={int(time.time())}"\n    profile_markdown = read_with_jina(profile_target)\n    discovered = extract_project_links(profile_markdown)\n    log("Fresh public profile IDs: " + ", ".join(found["id"] for found in discovered))\n'''

if old not in s:
    if "_portfolio_sync=" in s:
        print("Cache-busting profile fetch already present")
    else:
        raise SystemExit("Profile fetch marker not found")
else:
    s = s.replace(old, new, 1)

p.write_text(s, encoding="utf-8")
print("Patched Behance profile fetch with per-run cache busting")
