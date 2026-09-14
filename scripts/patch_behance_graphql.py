from pathlib import Path

p = Path("scripts/update_behance.py")
s = p.read_text(encoding="utf-8")

if "import uuid\n" not in s:
    s = s.replace("import time\n", "import time\nimport uuid\n", 1)

if 'GRAPHQL_URL = "https://www.behance.net/v3/graphql"' not in s:
    marker = 'RSS_URL = "https://www.behance.net/feeds/user?username=oskuhallaART"\n'
    if marker not in s:
        raise SystemExit("RSS_URL marker not found")
    addition = '''GRAPHQL_URL = "https://www.behance.net/v3/graphql"\nGRAPHQL_PROFILE_QUERY = r"""\nquery GetProfileProjects($username: String, $after: String) {\n  user(username: $username) {\n    profileProjects(first: 12, after: $after) {\n      pageInfo { endCursor hasNextPage }\n      nodes {\n        id\n        name\n        slug\n        url\n        isPrivate\n        isHiddenFromWorkTab\n        privacyLevel\n      }\n    }\n  }\n}\n"""\n'''
    s = s.replace(marker, marker + addition, 1)

start = s.index("def discover_public_projects() -> tuple[list[dict], str]:")
end = s.index("\ndef extract_reader_title", start)
old_func = s[start:end]
new_func = r'''def discover_public_projects() -> tuple[list[dict], str]:
    """Return public Behance projects, preferring Behance's live GraphQL data.

    The same public GraphQL endpoint used by Behance-facing feed tools exposes
    the profile's project list without a login. It can be paginated, which makes
    it authoritative for both additions and removals. If that endpoint is ever
    unavailable, discovery falls back safely to RSS and then Jina Reader, but
    deletion is disabled for those incomplete fallbacks in main().
    """
    try:
        projects: list[dict] = []
        seen: set[str] = set()
        after = ""

        for page in range(1, 21):
            bcp = str(uuid.uuid4())
            log(f"GraphQL public-project fetch: page {page}")
            response = SESSION.post(
                GRAPHQL_URL,
                timeout=REQUEST_TIMEOUT,
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "Origin": "https://www.behance.net",
                    "Referer": PROFILE_URL,
                    "X-BCP": bcp,
                    "X-Requested-With": "XMLHttpRequest",
                    "Cookie": (
                        f"gk_suid={str(uuid.uuid4().int)[:8]}; gki=; "
                        f"originalReferrer=; bcp={bcp}"
                    ),
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/153.0.0.0 Safari/537.36"
                    ),
                },
                json={
                    "query": GRAPHQL_PROFILE_QUERY,
                    "variables": {"username": "oskuhallaART", "after": after},
                },
            )
            if response.status_code != 200:
                raise RuntimeError(f"GraphQL HTTP {response.status_code}")

            payload = response.json()
            if payload.get("errors"):
                raise RuntimeError(f"GraphQL errors: {payload['errors'][:1]}")

            profile = (((payload.get("data") or {}).get("user") or {}).get("profileProjects") or {})
            nodes = profile.get("nodes") or []
            for node in nodes:
                if node.get("isPrivate") or node.get("isHiddenFromWorkTab"):
                    continue
                pid = str(node.get("id") or "").strip()
                url = str(node.get("url") or "").strip()
                if not pid or not url or pid in seen:
                    continue
                seen.add(pid)
                projects.append({"id": pid, "url": url})

            page_info = profile.get("pageInfo") or {}
            if not page_info.get("hasNextPage"):
                break
            after = str(page_info.get("endCursor") or "")
            if not after:
                raise RuntimeError("GraphQL pagination hasNextPage without endCursor")

        if not projects:
            raise RuntimeError("GraphQL returned no public Behance projects")

        log("Live GraphQL public project IDs: " + ", ".join(p["id"] for p in projects))
        return projects, "graphql"
    except Exception as exc:
        log(f"GraphQL discovery failed; trying RSS fallback: {exc}")

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
        log(f"RSS unavailable (HTTP {response.status_code}); using Reader fallback.")
    except Exception as exc:
        log(f"RSS discovery failed; using Reader fallback: {exc}")

    separator = "&" if "?" in PROFILE_URL else "?"
    profile_target = f"{PROFILE_URL}{separator}_portfolio_sync={int(time.time())}"
    profile_markdown = read_with_jina(profile_target)
    projects = extract_project_links(profile_markdown)
    log("Fresh Reader profile IDs: " + ", ".join(p["id"] for p in projects))
    return projects, "reader"
'''
s = s[:start] + new_func + s[end:]

main_start = s.index("def main() -> int:")
existing_end = s.index("    existing_ids = {str(item.get(\"id\")) for item in existing if item.get(\"id\")}\n", main_start)
existing_end += len("    existing_ids = {str(item.get(\"id\")) for item in existing if item.get(\"id\")}\n")
old_main_prefix = s[main_start:existing_end]
new_main_prefix = r'''def main() -> int:
    existing = load_existing()

    discovered, discovery_source = discover_public_projects()
    discovered_ids = {found["id"] for found in discovered}
    log(f"Deletion sync source: {discovery_source}")

    kept_existing = []
    removed_projects = []

    if discovery_source == "graphql":
        # GraphQL is paginated through the full public profile, so absence here
        # means the project is no longer publicly listed by this Behance user.
        for item in existing:
            if str(item.get("source") or "").lower() != "behance":
                kept_existing.append(item)
                continue

            pid = str(item.get("id") or "").strip()
            if not pid or pid in discovered_ids:
                kept_existing.append(item)
                continue

            removed_projects.append(item)
            remove_local_previews(pid)
            log(f"Removed project no longer public on Behance: {item.get('title', pid)} [{pid}]")
    else:
        # RSS/Reader responses are useful for finding new work but may be partial
        # or cached, so they are never allowed to delete existing cards.
        kept_existing = existing
        log("Deletion skipped because the authoritative GraphQL listing was unavailable.")

    existing = kept_existing
    existing_ids = {str(item.get("id")) for item in existing if item.get("id")}
'''
s = s[:main_start] + new_main_prefix + s[existing_end:]

s = s.replace(
    "GitHub-hosted runners can receive HTTP 403 from behance.net directly.\nThis script therefore asks Jina Reader to render/read the public Behance pages\nand parses the returned Markdown. No Behance login, API token, or secret is\nrequired.",
    "The sync uses Behance's public GraphQL profile listing as the authoritative\nsource for additions and removals. Jina Reader remains a safe fallback for\nreading project pages and extracting preview assets. No Behance login, API\ntoken, or secret is required.",
    1,
)
s = s.replace(
    "- New public projects found on the first Behance profile page are prepended.\n  (New Behance projects appear on the first profile page, which is exactly what\n  the daily sync needs.)",
    "- The full public Behance project list is paginated daily, so deleted or\n  unpublished projects are removed and newly published projects are prepended.",
    1,
)

p.write_text(s, encoding="utf-8")
print("Patched Behance sync to use live paginated GraphQL data")
