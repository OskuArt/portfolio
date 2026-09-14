from pathlib import Path

p = Path("scripts/update_behance.py")
s = p.read_text(encoding="utf-8")

old_policy = "- Existing projects are NEVER removed automatically."
new_policy = "- Existing Behance projects are checked daily and removed from the site when their Behance project is no longer public."
if old_policy in s:
    s = s.replace(old_policy, new_policy, 1)
elif new_policy not in s:
    raise SystemExit("Sync policy marker not found")

insert_marker = "\ndef maybe_write_keepalive() -> None:\n"
helper = r'''

def project_is_public(item: dict) -> bool:
    """Safely verify that an older Behance project still exists.

    Projects visible on the current profile page do not need an extra request.
    This check is only used for existing projects that are no longer present on
    that first profile page. Temporary Reader/network errors are treated as
    inconclusive and keep the project, so a transient outage cannot wipe cards.
    """
    pid = str(item.get("id") or "").strip()
    url = str(item.get("url") or "").strip()
    if not pid or not url:
        return True

    log(f"Existence check: {url}")
    try:
        response = SESSION.get(
            reader_url(url),
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True,
            headers={
                "Accept": "text/plain",
                "X-Return-Format": "markdown",
            },
        )
    except requests.RequestException as exc:
        log(f"Could not verify project {pid}; keeping it: {exc}")
        return True

    if response.status_code in {404, 410}:
        log(f"Project {pid} is no longer public (HTTP {response.status_code}).")
        return False

    if response.status_code != 200:
        log(
            f"Project {pid} returned HTTP {response.status_code}; "
            "keeping it until a later sync can verify it."
        )
        return True

    text = response.text.strip()
    head = text[:2500].lower()
    not_found_markers = (
        "page not found",
        "project not found",
        "project is no longer available",
        "this project is no longer available",
        "content is no longer available",
        "404 not found",
    )
    if any(marker in head for marker in not_found_markers):
        log(f"Project {pid} is no longer available according to Behance Reader.")
        return False

    if len(text) < 100:
        log(f"Project {pid} returned too little content to verify; keeping it.")
        return True

    return True


def remove_local_previews(pid: str) -> None:
    if not PREVIEW_DIR.exists():
        return
    for path in PREVIEW_DIR.glob(f"{pid}.*"):
        try:
            path.unlink()
            log(f"Deleted stale local preview: {path}")
        except OSError as exc:
            log(f"Could not delete stale preview {path}: {exc}")
'''

if "def project_is_public(item: dict) -> bool:" not in s:
    if insert_marker not in s:
        raise SystemExit("Keepalive function marker not found")
    s = s.replace(insert_marker, helper + insert_marker, 1)

old_main = r'''def main() -> int:
    existing = load_existing()
    existing_ids = {str(item.get("id")) for item in existing if item.get("id")}

    profile_markdown = read_with_jina(PROFILE_URL)
    discovered = extract_project_links(profile_markdown)

    new_projects = []
    for found in discovered:
        if found["id"] in existing_ids:
            continue

        project = build_new_project(found)
        new_projects.append(project)
        log(f"New project: {project['title']} [{project['category']}]")

        # Keep the unauthenticated Reader usage gentle.
        time.sleep(1)

    if new_projects:
        # Reader/profile order is newest first. Prepending preserves that order.
        updated = new_projects + existing
        PROJECTS_FILE.write_text(
            json.dumps(updated, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        log(f"Added {len(new_projects)} project(s). Total: {len(updated)}")
    else:
        log("No new public Behance projects found.")

    maybe_write_keepalive()
    return 0
'''

new_main = r'''def main() -> int:
    existing = load_existing()

    profile_markdown = read_with_jina(PROFILE_URL)
    discovered = extract_project_links(profile_markdown)
    discovered_ids = {found["id"] for found in discovered}

    # The profile Reader is intentionally used only for the first page. Anything
    # still visible there is definitely current. Older saved projects that are no
    # longer on that first page are checked individually before being kept.
    kept_existing = []
    removed_projects = []
    for item in existing:
        if str(item.get("source") or "").lower() != "behance":
            kept_existing.append(item)
            continue

        pid = str(item.get("id") or "").strip()
        if not pid or pid in discovered_ids:
            kept_existing.append(item)
            continue

        if project_is_public(item):
            kept_existing.append(item)
        else:
            removed_projects.append(item)
            remove_local_previews(pid)
            log(f"Removed deleted/private Behance project: {item.get('title', pid)} [{pid}]")

        # Keep the unauthenticated Reader usage gentle.
        time.sleep(0.5)

    existing = kept_existing
    existing_ids = {str(item.get("id")) for item in existing if item.get("id")}

    new_projects = []
    for found in discovered:
        if found["id"] in existing_ids:
            continue

        project = build_new_project(found)
        new_projects.append(project)
        log(f"New project: {project['title']} [{project['category']}]")

        # Keep the unauthenticated Reader usage gentle.
        time.sleep(1)

    if new_projects or removed_projects:
        # Reader/profile order is newest first. Prepending preserves that order.
        updated = new_projects + existing
        PROJECTS_FILE.write_text(
            json.dumps(updated, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        log(
            f"Portfolio synced: +{len(new_projects)} / -{len(removed_projects)}. "
            f"Total: {len(updated)}"
        )
    else:
        log("No Behance portfolio changes found.")

    maybe_write_keepalive()
    return 0
'''

if old_main in s:
    s = s.replace(old_main, new_main, 1)
elif "removed_projects = []" not in s:
    raise SystemExit("Main sync block marker not found")

p.write_text(s, encoding="utf-8")
print("Patched scripts/update_behance.py")
