#!/usr/bin/env python3
"""
check_sources.py — audit country profile pages for missing Sources/References.

Loads slugs from rankings.json (in same directory), then queries each WP page
by slug and checks for a Sources/References section.
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


def has_sources(html_content):
    if not html_content:
        return False
    text = re.sub(r'<[^>]+>', ' ', html_content)
    tail = text[int(len(text) * 0.5):]
    return bool(SOURCE_HEADING_RE.search(tail))


def main():
    env = load_env()
    wp_url  = env.get('WP_URL', 'https://globalwitnessmonitor.com').rstrip('/')
    wp_user = env['WP_USER']
    wp_pass = env['WP_APP_PASSWORD']
    auth = 'Basic ' + base64.b64encode(f'{wp_user}:{wp_pass}'.encode()).decode()

    if not os.path.exists(RANKINGS_FILE):
        print(f"[audit] ERROR: {RANKINGS_FILE} not found in current directory")
        sys.exit(1)

    with open(RANKINGS_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    countries = data.get('countries', [])
    print(f"[audit] WP: {wp_url}")
    print(f"[audit] loaded {len(countries)} countries from {RANKINGS_FILE}")
    print()

    with_sources    = []
    without_sources = []
    not_found       = []

    for c in countries:
        name = c.get('name', '')
        slug = c.get('slug', '')
        code, body = wp_get(
            f"{wp_url}/wp-json/wp/v2/pages?slug={slug}&_fields=id,slug,content",
            auth
        )
        if code != 200:
            not_found.append(f"{name} (slug:{slug}, HTTP {code})")
            continue
        items = json.loads(body)
        if not items:
            not_found.append(f"{name} (slug:{slug})")
            continue

        content = items[0].get('content', {}).get('rendered', '')
        if has_sources(content):
            with_sources.append(name)
        else:
            without_sources.append(name)

    with_sources.sort()
    without_sources.sort()
    not_found.sort()

    print(f"=== HAS sources/references ({len(with_sources)}) ===")
    for n in with_sources:
        print(f"  has  {n}")
    print()
    print(f"=== MISSING sources/references ({len(without_sources)}) ===")
    for n in without_sources:
        print(f"  MISSING  {n}")
    print()
    if not_found:
        print(f"=== PAGE NOT FOUND ({len(not_found)}) ===")
        for n in not_found:
            print(f"  notfound  {n}")
        print()
    total_checked = len(with_sources) + len(without_sources)
    print(f"Found pages: {total_checked} of {len(countries)} countries")
    print(f"  has sources: {len(with_sources)}")
    print(f"  missing sources: {len(without_sources)}")
    print(f"  page not found: {len(not_found)}")


if __name__ == '__main__':
    main()
