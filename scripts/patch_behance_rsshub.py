from pathlib import Path

p = Path("scripts/update_behance.py")
s = p.read_text(encoding="utf-8")

if 'RSSHUB_URL = "https://rsshub.app/behance/oskuhallaART/projects"' not in s:
    marker = 'GRAPHQL_URL = "https://www.behance.net/v3/graphql"\n'
    if marker not in s:
        raise SystemExit("GRAPHQL_URL marker not found")
    s = s.replace(marker, marker + 'RSSHUB_URL = "https://rsshub.app/behance/oskuhallaART/projects"\n', 1)

needle = '''    except Exception as exc:\n        log(f"GraphQL discovery failed; trying RSS fallback: {exc}")\n\n    try:\n        log(f"RSS fetch: {RSS_URL}")\n'''
replacement = '''    except Exception as exc:\n        log(f"GraphQL discovery failed; trying RSSHub fallback: {exc}")\n\n    try:\n        rsshub_target = f"{RSSHUB_URL}?_portfolio_sync={int(time.time())}"\n        log(f"RSSHub fetch: {rsshub_target}")\n        response = SESSION.get(\n            rsshub_target,\n            timeout=REQUEST_TIMEOUT,\n            allow_redirects=True,\n            headers={\n                "Accept": "application/rss+xml,application/atom+xml,application/xml,text/xml,*/*",\n                "Cache-Control": "no-cache",\n                "User-Agent": "Mozilla/5.0 portfolio-sync/1.0",\n            },\n        )\n        if response.status_code == 200 and len(response.text.strip()) >= 100:\n            projects = extract_project_links(response.text)\n            log("Fresh RSSHub project IDs: " + ", ".join(p["id"] for p in projects))\n            return projects, "rsshub"\n        log(f"RSSHub unavailable (HTTP {response.status_code}); trying Behance RSS.")\n    except Exception as exc:\n        log(f"RSSHub discovery failed; trying Behance RSS: {exc}")\n\n    try:\n        log(f"RSS fetch: {RSS_URL}")\n'''
if needle not in s:
    if 'return projects, "rsshub"' not in s:
        raise SystemExit("GraphQL fallback marker not found")
else:
    s = s.replace(needle, replacement, 1)

main_old = '''    if discovery_source == "graphql":\n        # GraphQL is paginated through the full public profile, so absence here\n        # means the project is no longer publicly listed by this Behance user.\n        for item in existing:\n            if str(item.get("source") or "").lower() != "behance":\n                kept_existing.append(item)\n                continue\n\n            pid = str(item.get("id") or "").strip()\n            if not pid or pid in discovered_ids:\n                kept_existing.append(item)\n                continue\n\n            removed_projects.append(item)\n            remove_local_previews(pid)\n            log(f"Removed project no longer public on Behance: {item.get('title', pid)} [{pid}]")\n    else:\n        # RSS/Reader responses are useful for finding new work but may be partial\n        # or cached, so they are never allowed to delete existing cards.\n        kept_existing = existing\n        log("Deletion skipped because the authoritative GraphQL listing was unavailable.")\n'''
main_new = '''    if discovery_source == "graphql":\n        # GraphQL is paginated through the full public profile, so absence here\n        # means the project is no longer publicly listed by this Behance user.\n        for item in existing:\n            if str(item.get("source") or "").lower() != "behance":\n                kept_existing.append(item)\n                continue\n\n            pid = str(item.get("id") or "").strip()\n            if not pid or pid in discovered_ids:\n                kept_existing.append(item)\n                continue\n\n            removed_projects.append(item)\n            remove_local_previews(pid)\n            log(f"Removed project no longer public on Behance: {item.get('title', pid)} [{pid}]")\n    elif discovery_source == "rsshub":\n        # RSSHub reads Behance's live GraphQL profile but exposes the newest\n        # project window only. It is authoritative inside that visible window,\n        # while older cards are kept rather than guessed away.\n        existing_positions = {\n            str(item.get("id")): index\n            for index, item in enumerate(existing)\n            if str(item.get("source") or "").lower() == "behance" and item.get("id")\n        }\n        matched_positions = [\n            existing_positions[found["id"]]\n            for found in discovered\n            if found["id"] in existing_positions\n        ]\n        visible_boundary = max(matched_positions) if matched_positions else -1\n\n        for index, item in enumerate(existing):\n            if str(item.get("source") or "").lower() != "behance":\n                kept_existing.append(item)\n                continue\n            pid = str(item.get("id") or "").strip()\n            if not pid:\n                kept_existing.append(item)\n                continue\n            if visible_boundary >= 0 and index <= visible_boundary and pid not in discovered_ids:\n                removed_projects.append(item)\n                remove_local_previews(pid)\n                log(f"Removed project missing from live Behance window: {item.get('title', pid)} [{pid}]")\n            else:\n                kept_existing.append(item)\n    else:\n        # Direct RSS/Reader responses may be partial or cached, so they are never\n        # allowed to delete existing cards.\n        kept_existing = existing\n        log("Deletion skipped because no trustworthy live listing was available.")\n'''
if main_old not in s:
    if 'discovery_source == "rsshub"' not in s:
        raise SystemExit("Main deletion policy marker not found")
else:
    s = s.replace(main_old, main_new, 1)

p.write_text(s, encoding="utf-8")
print("Patched Behance sync to use RSSHub live profile fallback")
