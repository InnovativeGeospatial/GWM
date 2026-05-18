#!/usr/bin/env python3
"""
check_sources.py — audit country profile pages.

Classifies each into one of three buckets:
  1. Has profile content AND sources
  2. Has profile content but MISSING sources
  3. Empty/placeholder page (no real content)

Threshold: a "real" profile is >2000 chars of plain text after stripping HTML.
"""

import os
import re
import sys
import json
import base64
import urllib.request
import urllib.error

ENV_PATH = "/opt/conflict-pipeline/.env"
RANKINGS_FILE = "rankings.json"
MIN_REAL_CONTENT_CHARS = 2000


def load_env():
    env = {}
    with open(ENV_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def wp_get(url, auth_header):
    req = urllib.request.Request(url, method='GET')
    req.add_header("Authorization", auth_header)
    req.add_header("Accept", "application/json")
    req.add_header("User-Agent", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, r.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")


SOURCE_HEADING_RE = re.compile(
    r'(sources?\s*&?(?:amp;)?\s*references?|references|sources|works\s+cited|bibliography)',
    re.IGNORECASE
)


def analyze_content(html_content):
    """Return (text_length, has_sources)."""
    if not html_content:
        return 0, False
    text = re.sub(r'<[^>]+>', ' ', html_content)
    text = re.sub(r'\s+', ' ', text).strip()
    has = bool(SOURCE_HEADING_RE.search(text[int(len(text) * 0.5):]))
    return len(text), has


def main():
    env = load_env()
    wp_url  = env.get('WP_URL', 'https://globalwitnessmonitor.com').rstrip('/')
    wp_user = env['WP_USER']
    wp_pass = env['WP_APP_PASSWORD']
    auth = 'Basic ' + base64.b64encode(f'{wp_user}:{wp_pass}'.encode()).decode()

    if not os.path.exists(RANKINGS_FILE):
        print(f"[audit] ERROR: {RANKINGS_FILE} not found in cwd")
        sys.exit(1)

    with open(RANKINGS_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    countries = data.get('countries', [])
    print(f"[audit] WP: {wp_url}")
    print(f"[audit] {len(countries)} countries from {RANKINGS_FILE}")
    print(f"[audit] threshold: >{MIN_REAL_CONTENT_CHARS} text chars = real profile")
    print()

    complete       = []  # has content + sources
    missing_src    = []  # has content, no sources
    placeholder    = []  # no real content
    not_found      = []  # WP page doesn't exist

    for c in countries:
        name = c.get('name', '')
        slug = c.get('slug', '')
        code, body = wp_get(
            f"{wp_url}/wp-json/wp/v2/pages?slug={slug}&_fields=id,slug,content",
            auth
        )
        if code != 200:
            not_found.append(f"{name} (HTTP {code})")
            continue
        items = json.loads(body)
        if not items:
            not_found.append(f"{name} (no page with slug:{slug})")
            continue

        content = items[0].get('content', {}).get('rendered', '')
        length, has_src = analyze_content(content)

        if length < MIN_REAL_CONTENT_CHARS:
            placeholder.append(f"{name} ({length} chars)")
        elif has_src:
            complete.append(name)
        else:
            missing_src.append(name)

    complete.sort()
    missing_src.sort()
    placeholder.sort()
    not_found.sort()

    print(f"=== COMPLETE: profile + sources ({len(complete)}) ===")
    for n in complete:
        print(f"  ok  {n}")
    print()
    print(f"=== HAS PROFILE BUT MISSING SOURCES ({len(missing_src)}) ===")
    for n in missing_src:
        print(f"  add-sources  {n}")
    print()
    print(f"=== PLACEHOLDER / EMPTY ({len(placeholder)}) ===")
    for n in placeholder:
        print(f"  needs-profile  {n}")
    print()
    if not_found:
        print(f"=== PAGE DOES NOT EXIST IN WP ({len(not_found)}) ===")
        for n in not_found:
            print(f"  create-page  {n}")
        print()

    total = len(complete) + len(missing_src) + len(placeholder) + len(not_found)
    print(f"Total: {total} of {len(countries)} countries")
    print(f"  complete: {len(complete)}")
    print(f"  needs sources: {len(missing_src)}")
    print(f"  needs profile written: {len(placeholder)}")
    print(f"  needs page created: {len(not_found)}")


if __name__ == '__main__':
    main()
