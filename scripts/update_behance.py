#!/usr/bin/env python3
"""
Behance -> projects.json sync for Kseniia Smirnova's portfolio.

Why this version exists:
GitHub-hosted runners can receive HTTP 403 from behance.net directly.
This script therefore asks Jina Reader to render/read the public Behance pages
and parses the returned Markdown. No Behance login, API token, or secret is
required.

Sync policy:
- Existing projects are NEVER removed automatically.
- Existing hand-edited titles/categories/previews are preserved.
- New public projects found on the first Behance profile page are prepended.
  (New Behance projects appear on the first profile page, which is exactly what
  the daily sync needs.)
- For a new project, the script tries to use the first Behance project-module
  image and save a local high-quality copy. If downloading that image fails,
  the remote high-quality CDN URL is kept instead.
- A tiny keepalive state file is refreshed at most once every 30 days.
"""

from __future__ import annotations

import json
import re
import sys
import time
from datetime import datetime, timezone, timedelta
from html import unescape
from pathlib import Path
from urllib.parse import urlparse

import requests

PROFILE_URL = "https://www.behance.net/oskuhallaART"
READER_PREFIX = "https://r.jina.ai/"
PROJECTS_FILE = Path("projects.json")
PREVIEW_DIR = Path("assets/project-previews")
STATE_FILE = Path(".behance-sync-state.json")

REQUEST_TIMEOUT = 60

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "KseniiaPortfolioSync/2.0 (+GitHub Actions)",
    "Accept": "text/plain,text/markdown;q=0.9,*/*;q=0.8",
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

def request(url: str, *, headers: dict | None = None) -> requests.Response:
    last_error = None
    for attempt in range(1, 4):
        try:
            response = SESSION.get(
                url,
                timeout=REQUEST_TIMEOUT,
                allow_redirects=True,
                headers=headers or {},
            )
            if response.status_code == 200:
                return response
            last_error = RuntimeError(f"HTTP {response.status_code} for {url}")
        except requests.RequestException as exc:
            last_error = exc

        if attempt < 3:
            time.sleep(attempt * 2)

    raise RuntimeError(f"Failed to fetch {url}: {last_error}")

def reader_url(target_url: str) -> str:
    return READER_PREFIX + target_url

def read_with_jina(target_url: str) -> str:
    url = reader_url(target_url)
    log(f"Reader fetch: {target_url}")
    response = request(
        url,
        headers={
            "Accept": "text/plain",
            # These headers are understood by Jina Reader and keep the output
            # suitable for link/image extraction.
            "X-Return-Format": "markdown",
        },
    )
    text = response.text
    if len(text.strip()) < 100:
        raise RuntimeError(f"Reader returned unexpectedly little content for {target_url}")
    return text

def load_existing() -> list[dict]:
    if not PROJECTS_FILE.exists():
        return []
    data = json.loads(PROJECTS_FILE.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise RuntimeError("projects.json must contain a JSON array")
    return data

def project_id(url: str) -> str:
    match = re.search(r"/gallery/(\d+)/", url)
    if not match:
        raise ValueError(f"Not a Behance project URL: {url}")
    return match.group(1)

def clean_url(url: str) -> str:
    url = unescape(url).replace("\\/", "/").strip()
    url = url.rstrip(".,;")
    # Markdown links can leave a trailing quote or bracket in loose regex matches.
    return url.rstrip("'\"<>]")

def extract_project_links(markdown: str) -> list[dict]:
    """
    Jina Reader converts page links to Markdown. We collect all Behance gallery
    URLs in appearance order, which matches the profile's newest-first ordering.
    """
    pattern = re.compile(
        r"https?://(?:www\.)?behance\.net/gallery/(\d+)/[^\s\])<>\"']+",
        re.I,
    )
    seen = set()
    result = []

    for match in pattern.finditer(markdown):
        pid = match.group(1)
        url = clean_url(match.group(0))
        if pid in seen:
            continue
        seen.add(pid)
        result.append({"id": pid, "url": url})

    if not result:
        raise RuntimeError(
            "Jina Reader returned the Behance page, but no /gallery/ project "
            "links were found. Existing projects.json was NOT changed."
        )

    return result

def extract_reader_title(markdown: str, fallback_url: str) -> str:
    # Jina Reader normally begins with a metadata line: "Title: ..."
    match = re.search(r"(?mi)^Title:\s*(.+?)\s*$", markdown)
    if match:
        title = match.group(1).strip()
    else:
        # Try first Markdown H1.
        match = re.search(r"(?m)^#\s+(.+?)\s*$", markdown)
        title = match.group(1).strip() if match else ""

    title = re.sub(r"\s*::\s*Behance\s*$", "", title, flags=re.I)
    title = re.sub(r"\s+on Behance\s*$", "", title, flags=re.I)

    if not title:
        title = fallback_url.rstrip("/").split("/")[-1].replace("-", " ")

    return title.strip()

def extract_first_project_image(markdown: str) -> str:
    """
    Prefer a project_modules image because those are the actual project content.
    If none is present, fall back to a Behance project thumbnail.
    """
    markdown = unescape(markdown).replace("\\/", "/")

    patterns = [
        r"https://mir-s3-cdn-cf\.behance\.net/project_modules/[^\s\])<>\"']+",
        r"https://mir-s3-cdn-cf\.behance\.net/projects/[^\s\])<>\"']+",
    ]

    for pattern in patterns:
        match = re.search(pattern, markdown, flags=re.I)
        if match:
            return clean_url(match.group(0))
    return ""

def to_high_quality_behance_url(url: str) -> str:
    """
    Behance CDN image URLs contain a size directory. For project images, request
    max_1200, which is enough for the site's two-column 16:10 cards without
    stretching a tiny thumbnail.
    """
    if not url:
        return url

    url = clean_url(url).split("?")[0]
    match = re.match(
        r"(https://mir-s3-cdn-cf\.behance\.net/(?:project_modules|projects)/)"
        r"([^/]+)(/.*)",
        url,
        flags=re.I,
    )
    if not match:
        return url

    prefix, _size, suffix = match.groups()
    return prefix + "max_1200" + suffix

def infer_category(title: str, body: str) -> str:
    text = f"{title} {body[:7000]}".lower()

    groups = [
        ("packaging", (
            "packaging", "package", "label", "bottle", "perfume", "parfum",
            "cosmetic", "cider", "nuts", "box", "tube", "jar",
            "упаков", "парфюм", "этикет",
        )),
        ("branding", (
            "branding", "brand identity", "identity", "logo", "brandbook",
            "brand book", "бренд", "логотип", "айдентик",
        )),
        ("digital", (
            "ux", "ui", "app", "application", "website", "web design",
            "landing", "interface", "digital", "presentation", "mobile",
        )),
        ("editorial", (
            "editorial", "postcard", "postcards", "artbook", "art book",
            "book", "brochure", "magazine", "catalog", "print series",
            "открытк", "книга", "журнал",
        )),
        ("illustration", (
            "illustration", "character", "tattoo", "sticker", "drawing",
            "figure", "game", "animal", "illustrat",
            "иллюстрац", "тату", "персонаж", "игра",
        )),
    ]

    for category, keywords in groups:
        if any(keyword in text for keyword in keywords):
            return category
    return "other"

def extension_from_response(response: requests.Response, url: str) -> str:
    ctype = (response.headers.get("Content-Type") or "").split(";")[0].lower().strip()
    mapping = {
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "image/gif": ".gif",
    }
    if ctype in mapping:
        return mapping[ctype]

    suffix = Path(urlparse(url).path).suffix.lower()
    if suffix in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
        return ".jpg" if suffix == ".jpeg" else suffix
    return ".jpg"

def save_preview_locally(pid: str, remote_url: str) -> tuple[str, str]:
    """
    Returns (preview, fallback). If the CDN download succeeds, preview is a local
    repository path and fallback is the remote URL. Otherwise both use remote.
    """
    if not remote_url:
        return "", ""

    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    high_quality = to_high_quality_behance_url(remote_url)

    # Reuse an already-downloaded preview.
    existing = sorted(PREVIEW_DIR.glob(f"{pid}.*"))
    if existing:
        return existing[0].as_posix(), high_quality

    try:
        response = request(
            high_quality,
            headers={
                "Accept": "image/avif,image/webp,image/png,image/jpeg,*/*",
                "Referer": "https://www.behance.net/",
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 Chrome/151 Safari/537.36"
                ),
            },
        )
        ctype = (response.headers.get("Content-Type") or "").lower()
        if "image/" in ctype and len(response.content) >= 8_000:
            ext = extension_from_response(response, high_quality)
            target = PREVIEW_DIR / f"{pid}{ext}"
            target.write_bytes(response.content)
            log(f"Saved local preview: {target} ({len(response.content)/1024:.0f} KB)")
            return target.as_posix(), high_quality
    except Exception as exc:
        log(f"Could not download preview locally: {exc}")

    log("Using remote high-quality preview URL")
    return high_quality, high_quality

def build_new_project(found: dict) -> dict:
    markdown = read_with_jina(found["url"])
    title = extract_reader_title(markdown, found["url"])
    category = infer_category(title, markdown)
    image = extract_first_project_image(markdown)
    preview, fallback = save_preview_locally(found["id"], image)

    return {
        "id": found["id"],
        "title": title,
        "meta": CATEGORY_META.get(category, CATEGORY_META["other"]),
        "category": category,
        "url": found["url"],
        "preview": preview,
        "preview_fallback": fallback,
        "source": "behance",
    }

def maybe_write_keepalive() -> None:
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
                indent=2,
            ) + "\n",
            encoding="utf-8",
        )
        log("Updated monthly workflow keepalive state")

def main() -> int:
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

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[behance-sync] ERROR: {exc}", file=sys.stderr, flush=True)
        raise SystemExit(1)
