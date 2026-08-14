#!/usr/bin/env python3
"""
Daily Behance -> projects.json synchronizer for Kseniia Smirnova's portfolio.

What it does:
1. Reads all public project links from the Behance profile, following pagination.
2. Keeps the existing hand-edited title/category/meta for known projects.
3. Adds newly published projects automatically.
4. Tries to save a high-quality first project image locally in
   assets/project-previews/.
5. Removes projects that are no longer public ONLY after a safety check confirms
   that the scraper found most of the previous portfolio.
6. Writes a monthly keepalive state file so GitHub's scheduled workflow does not
   go dormant after a long period without portfolio changes.

No API keys or secrets are required.
"""

from __future__ import annotations

import json
import mimetypes
import os
import re
import sys
import time
from datetime import datetime, timezone, timedelta
from html import unescape
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

PROFILE_URL = "https://www.behance.net/oskuhallaART"
PROJECTS_FILE = Path("projects.json")
PREVIEW_DIR = Path("assets/project-previews")
STATE_FILE = Path(".behance-sync-state.json")

MAX_PROFILE_PAGES = 10
REQUEST_TIMEOUT = 30
MIN_SAFE_RATIO = 0.65

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/151.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
})

CATEGORY_META = {
    "branding": "Brand identity · Behance project",
    "packaging": "Packaging · Behance project",
    "illustration": "Illustration · Behance project",
    "digital": "Digital design · Behance project",
    "editorial": "Editorial / print · Behance project",
    "other": "Creative project · Behance",
}

def log(message: str) -> None:
    print(f"[behance-sync] {message}", flush=True)

def get(url: str, *, binary: bool = False) -> requests.Response:
    last_error = None
    for attempt in range(1, 4):
        try:
            response = SESSION.get(url, timeout=REQUEST_TIMEOUT, allow_redirects=True)
            if response.status_code == 200:
                return response
            last_error = RuntimeError(f"HTTP {response.status_code} for {url}")
        except requests.RequestException as exc:
            last_error = exc

        if attempt < 3:
            time.sleep(attempt * 2)

    raise RuntimeError(f"Failed to fetch {url}: {last_error}")

def normalize_project_url(url: str) -> str | None:
    absolute = urljoin(PROFILE_URL, url)
    match = re.search(r"https?://(?:www\.)?behance\.net/gallery/(\d+)/([^?#]+)", absolute)
    if not match:
        return None
    return f"https://www.behance.net/gallery/{match.group(1)}/{match.group(2).rstrip('/')}"

def project_id(url: str) -> str:
    match = re.search(r"/gallery/(\d+)/", url)
    if not match:
        raise ValueError(f"Not a Behance project URL: {url}")
    return match.group(1)

def load_existing() -> list[dict]:
    if not PROJECTS_FILE.exists():
        return []
    data = json.loads(PROJECTS_FILE.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise RuntimeError("projects.json must contain a JSON array")
    return data

def discover_profile_projects() -> list[dict]:
    """
    Returns public projects in the same order as the Behance profile
    (newest first). Behance currently paginates profiles with ?after=...
    cursors, so the next cursor is discovered from the page itself rather
    than hard-coded.
    """
    discovered: list[dict] = []
    seen_ids: set[str] = set()
    seen_pages: set[str] = set()
    current_url = PROFILE_URL

    for page_no in range(1, MAX_PROFILE_PAGES + 1):
        if current_url in seen_pages:
            break
        seen_pages.add(current_url)

        log(f"Reading profile page {page_no}: {current_url}")
        page = get(current_url).text
        soup = BeautifulSoup(page, "html.parser")

        found_on_page = 0
        for anchor in soup.find_all("a", href=True):
            normalized = normalize_project_url(anchor.get("href", ""))
            if not normalized:
                continue

            pid = project_id(normalized)
            if pid in seen_ids:
                continue

            title = " ".join(anchor.stripped_strings).strip()
            if not title or title.lower() in {"image", "open project"}:
                title = ""

            discovered.append({
                "id": pid,
                "url": normalized,
                "profile_title": title,
            })
            seen_ids.add(pid)
            found_on_page += 1

        log(f"Found {found_on_page} new project links on page {page_no}")

        # Behance's server-rendered profile exposes the next page as ?after=...
        next_url = None
        for anchor in soup.find_all("a", href=True):
            href = urljoin(current_url, anchor["href"])
            parsed = urlparse(href)
            if parsed.netloc.endswith("behance.net") and parsed.path.rstrip("/") == urlparse(PROFILE_URL).path.rstrip("/"):
                if "after=" in parsed.query:
                    next_url = href
                    break

        if not next_url:
            break

        current_url = next_url
        time.sleep(0.6)

    if not discovered:
        raise RuntimeError(
            "Behance returned no project links. The site layout may have changed "
            "or the request may have been temporarily blocked. Existing data was NOT overwritten."
        )

    return discovered

def meta_content(soup: BeautifulSoup, *, prop: str | None = None, name: str | None = None) -> str:
    selector = {"property": prop} if prop else {"name": name}
    tag = soup.find("meta", attrs=selector)
    return (tag.get("content") or "").strip() if tag else ""

def clean_behance_title(title: str) -> str:
    title = re.sub(r"\s*::\s*Behance\s*$", "", title, flags=re.I)
    title = re.sub(r"\s*on Behance\s*$", "", title, flags=re.I)
    return title.strip()

def extract_first_project_image(page_html: str, soup: BeautifulSoup) -> str:
    """
    Prefer the first actual project-module image, not a tiny profile thumbnail.
    Falls back to Open Graph/Twitter preview metadata.
    """
    candidates: list[str] = []

    for tag in soup.find_all(["img", "source"]):
        for attr in ("src", "data-src", "srcset"):
            value = tag.get(attr)
            if not value:
                continue
            pieces = re.split(r"[\s,]+", value)
            for piece in pieces:
                if "mir-s3-cdn-cf.behance.net/project_modules/" in piece:
                    candidates.append(piece)

    # Some module URLs live inside serialized JSON rather than rendered img tags.
    normalized_html = page_html.replace("\\/", "/")
    candidates.extend(re.findall(
        r'https://mir-s3-cdn-cf\.behance\.net/project_modules/[^"\'<>\s\\]+',
        normalized_html
    ))

    for candidate in candidates:
        candidate = unescape(candidate).strip().rstrip(",")
        if candidate.startswith("https://"):
            return candidate

    return (
        meta_content(soup, prop="og:image")
        or meta_content(soup, name="twitter:image")
    )

def fetch_project_details(url: str, profile_title: str = "") -> dict:
    log(f"Reading new project: {url}")
    page = get(url).text
    soup = BeautifulSoup(page, "html.parser")

    title = clean_behance_title(
        meta_content(soup, prop="og:title")
        or meta_content(soup, name="twitter:title")
        or profile_title
        or url.rstrip("/").split("/")[-1].replace("-", " ")
    )

    description = (
        meta_content(soup, prop="og:description")
        or meta_content(soup, name="description")
        or ""
    )

    preview = extract_first_project_image(page, soup)

    return {
        "title": title,
        "description": description,
        "preview": preview,
    }

def infer_category(title: str, description: str) -> str:
    text = f"{title} {description}".lower()

    keyword_groups = [
        ("packaging", (
            "packaging", "package", "label", "bottle", "perfume", "parfum",
            "cosmetic", "cider", "nuts", "box", "tube", "jar", "упаков",
            "парфюм", "этикет"
        )),
        ("branding", (
            "branding", "brand identity", "identity", "logo", "brandbook",
            "brand book", "бренд", "логотип", "айдентик"
        )),
        ("digital", (
            "ux", "ui", "app", "application", "website", "web design",
            "landing", "interface", "digital", "presentation", "mobile"
        )),
        ("editorial", (
            "editorial", "postcard", "postcards", "artbook", "art book",
            "book", "brochure", "magazine", "catalog", "print series",
            "открытк", "книга", "журнал"
        )),
        ("illustration", (
            "illustration", "character", "tattoo", "sticker", "art ",
            "drawing", "figure", "game", "animal", "illustrat",
            "иллюстрац", "тату", "персонаж", "игра"
        )),
    ]

    for category, keywords in keyword_groups:
        if any(keyword in text for keyword in keywords):
            return category
    return "other"

def image_url_candidates(url: str) -> list[str]:
    if not url:
        return []

    url = unescape(url).replace("\\/", "/").strip()
    url = url.split("?")[0]

    candidates = []
    # Behance CDN paths usually encode a size segment such as max_1200, 1400, disp, fs.
    match = re.search(
        r"(https://mir-s3-cdn-cf\.behance\.net/(?:project_modules|projects)/)([^/]+)(/.*)",
        url
    )
    if match:
        prefix, _size, suffix = match.groups()
        candidates.extend([
            prefix + "original" + suffix,
            prefix + "max_1200" + suffix,
            url,
            prefix + "max_808" + suffix,
        ])
    else:
        candidates.append(url)

    unique = []
    for candidate in candidates:
        if candidate not in unique:
            unique.append(candidate)
    return unique

def extension_from_response(response: requests.Response, url: str) -> str:
    content_type = (response.headers.get("Content-Type") or "").split(";")[0].strip().lower()
    by_type = {
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "image/gif": ".gif",
    }
    if content_type in by_type:
        return by_type[content_type]

    suffix = Path(urlparse(url).path).suffix.lower()
    if suffix in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
        return ".jpg" if suffix == ".jpeg" else suffix
    return ".jpg"

def existing_local_preview(project: dict) -> str | None:
    preview = project.get("preview", "")
    if preview.startswith("assets/"):
        path = Path(preview)
        if path.exists() and path.is_file():
            return preview
    return None

def download_preview(project: dict, source_url: str) -> str:
    """
    Keep any existing hand-approved local image. Otherwise try to download
    the best Behance CDN version and store it in the repository.
    """
    already_local = existing_local_preview(project)
    if already_local:
        return already_local

    pid = project["id"]
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)

    # If a local file for this project already exists under another extension, reuse it.
    matches = sorted(PREVIEW_DIR.glob(f"{pid}.*"))
    if matches:
        return matches[0].as_posix()

    for candidate in image_url_candidates(source_url):
        try:
            response = get(candidate, binary=True)
        except Exception as exc:
            log(f"Preview candidate failed: {candidate} ({exc})")
            continue

        content_type = (response.headers.get("Content-Type") or "").lower()
        if "image/" not in content_type:
            continue

        data = response.content
        if len(data) < 8_000:
            continue

        # Avoid committing a single enormous original. If original is too large,
        # the loop continues to max_1200.
        if len(data) > 18 * 1024 * 1024:
            log(f"Skipping oversized preview ({len(data)/1024/1024:.1f} MB): {candidate}")
            continue

        ext = extension_from_response(response, candidate)
        target = PREVIEW_DIR / f"{pid}{ext}"
        target.write_bytes(data)
        log(f"Saved preview: {target} ({len(data)/1024:.0f} KB)")
        return target.as_posix()

    log(f"Could not localize preview for project {pid}; keeping remote URL")
    return source_url

def maybe_write_keepalive() -> None:
    """
    Public-repo scheduled workflows can be disabled after 60 days with no repo
    activity. A tiny keepalive commit at most once every 30 days prevents that.
    """
    now = datetime.now(timezone.utc)
    last = None

    if STATE_FILE.exists():
        try:
            state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            value = state.get("last_keepalive_utc")
            if value:
                last = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except Exception:
            last = None

    if last is None or now - last >= timedelta(days=30):
        STATE_FILE.write_text(
            json.dumps(
                {"last_keepalive_utc": now.isoformat().replace("+00:00", "Z")},
                indent=2
            ) + "\n",
            encoding="utf-8"
        )
        log("Updated monthly GitHub Actions keepalive state")

def main() -> int:
    existing = load_existing()
    existing_by_id = {str(item.get("id")): item for item in existing if item.get("id")}
    discovered = discover_profile_projects()

    # Fail safely if Behance suddenly returns only a fraction of the old profile.
    if existing:
        safe_minimum = max(3, int(len(existing) * MIN_SAFE_RATIO))
        if len(discovered) < safe_minimum:
            raise RuntimeError(
                f"Safety stop: found only {len(discovered)} projects, but "
                f"projects.json currently contains {len(existing)}. "
                "Existing data was NOT overwritten."
            )

    new_list: list[dict] = []

    for found in discovered:
        pid = found["id"]

        if pid in existing_by_id:
            project = dict(existing_by_id[pid])
            project["url"] = found["url"]

            # Convert old remote previews to local files opportunistically.
            current_preview = project.get("preview", "")
            fallback = project.get("preview_fallback", "")
            source = current_preview or fallback

            if source and source.startswith("http"):
                local = download_preview(project, source)
                project["preview"] = local
                if local.startswith("assets/"):
                    project["preview_fallback"] = fallback or source

            new_list.append(project)
            continue

        details = fetch_project_details(found["url"], found.get("profile_title", ""))
        category = infer_category(details["title"], details["description"])

        project = {
            "id": pid,
            "title": details["title"],
            "meta": CATEGORY_META.get(category, CATEGORY_META["other"]),
            "category": category,
            "url": found["url"],
            "preview": details["preview"],
            "preview_fallback": details["preview"],
            "source": "behance",
        }

        if details["preview"]:
            local = download_preview(project, details["preview"])
            project["preview"] = local

        new_list.append(project)
        log(f"Added new project: {project['title']} [{category}]")

    PROJECTS_FILE.write_text(
        json.dumps(new_list, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8"
    )
    log(f"projects.json now contains {len(new_list)} public Behance projects")

    maybe_write_keepalive()
    return 0

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[behance-sync] ERROR: {exc}", file=sys.stderr, flush=True)
        raise SystemExit(1)
