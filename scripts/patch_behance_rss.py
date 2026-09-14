from pathlib import Path

p = Path("scripts/update_behance.py")
s = p.read_text(encoding="utf-8")

if 'RSS_URL = "https://www.behance.net/feeds/user?username=oskuhallaART"' not in s:
    marker = 'PROFILE_URL = "https://www.behance.net/oskuhallaART/projects"\n'
    if marker not in s:
        raise SystemExit("PROFILE_URL marker not found")
    s = s.replace(marker, marker + 'RSS_URL = "https://www.behance.net/feeds/user?username=oskuhallaART"\n', 1)

helper_marker = '\ndef extract_reader_title(markdown: str, fallback_url: str) -> str:\n'
helper = r'''

def discover_public_projects() -> tuple[list[dict], str]:
    """Return the freshest public-project window available.

    Behance's user RSS feed is requested directly first. Unlike the rendered
    profile proxy, it is designed as a publication feed and reflects public
    project removals quickly. If Behance blocks or retires that feed, fall back
    safely to the cache-busted Jina Reader profile used for discovery today.
    """
    try:
        log(f"RSS fetch: {RSS_URL}")
        response = SESSION.get(
            RSS_URL,
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True,
            headers={
                "Accept": "application/rss+xml,application/xml,text/xml,*/*",
                "Cache-Control": "no-cache",
                "Pragma": "no-cache",
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 Chrome/153 Safari/537.36"
                ),
            },
        )
        if response.status_code == 200 and len(response.text.strip()) >= 100:
            projects = extract_project_links(response.text)
            log("Fresh RSS project IDs: " + ", ".join(p["id"] for p in projects))
            return projects, "rss"
        log(f"RSS unavailable (HTTP {response.status_code}); using profile Reader fallback.")
    except Exception as exc:
        log(f"RSS discovery failed; using profile Reader fallback: {exc}")

    separator = "&" if "?" in PROFILE_URL else "?"
    profile_target = f"{PROFILE_URL}{separator}_portfolio_sync={int(time.time())}"
    profile_markdown = read_with_jina(profile_target)
    projects = extract_project_links(profile_markdown)
    log("Fresh Reader profile IDs: " + ", ".join(p["id"] for p in projects))
    return projects, "reader"
'''

if "def discover_public_projects()" not in s:
    if helper_marker not in s:
        raise SystemExit("Helper insertion marker not found")
    s = s.replace(helper_marker, helper + helper_marker, 1)

old = '''    # Give Jina Reader a unique target URL on every run. Behance ignores this\n    # harmless query parameter, while Jina treats it as a fresh cache key. This\n    # prevents a recently deleted/unpublished project from lingering in the\n    # cached profile response.\n    separator = "&" if "?" in PROFILE_URL else "?"\n    profile_target = f"{PROFILE_URL}{separator}_portfolio_sync={int(time.time())}"\n    profile_markdown = read_with_jina(profile_target)\n    discovered = extract_project_links(profile_markdown)\n    log("Fresh public profile IDs: " + ", ".join(found["id"] for found in discovered))\n    discovered_ids = {found["id"] for found in discovered}\n'''
new = '''    discovered, discovery_source = discover_public_projects()\n    discovered_ids = {found["id"] for found in discovered}\n    log(f"Deletion sync source: {discovery_source}")\n'''
if old not in s:
    if "discover_public_projects()" not in s.split("def main()", 1)[1]:
        raise SystemExit("Main discovery block not found")
else:
    s = s.replace(old, new, 1)

p.write_text(s, encoding="utf-8")
print("Patched Behance sync to prefer the public RSS feed")
