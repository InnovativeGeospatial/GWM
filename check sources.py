#!/usr/bin/env python3
"""
check_sources.py — audit country profile pages for missing Sources/References sections.

Lists every country profile page and reports whether it contains a
"Sources" or "References" heading. Outputs grouped results.

Run:
    cd /opt/conflict-pipeline
    venv/bin/python check_sources.py
"""

import os
import re
import sys
import json
import base64
import urllib.request
import urllib.error

ENV_PATH = "/opt/conflict-pipeline/.env"

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

def wp_request(method, url, auth_header):
    req = urllib.request.Request(url, method=method)
    req.add_header("Authorization", auth_header)
    req.add_header("Accept", "application/json")
    req.add_header("User-Agent", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, r.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")


SOURCE_HEADING_RE = re.compile(
    r'(sources?\s*&?\s*references?|references|sources|works\s+cited|bibliography)',
    re.IGNORECASE
)

def has_sources(content):
    """Return True if content contains a sources/references heading."""
    if not content:
        return False
    # Look only at the last ~40% of content (sources are at the bottom)
    tail = content[int(len(content) * 0.5):]
    return bool(SOURCE_HEADING_RE.search(tail))


def main():
    env = load_env()
    wp_url  = env.get('WP_URL', 'https://globalwitnessmonitor.com').rstrip('/')
    wp_user = env['WP_USER']
    wp_pass = env['WP_APP_PASSWORD']
    auth = 'Basic ' + base64.b64encode(f'{wp_user}:{wp_pass}'.encode()).decode()

    print(f"[audit] WP: {wp_url}")
    print()

    with_sources    = []
    without_sources = []

    page_num = 1
    while True:
        url = f"{wp_url}/wp-json/wp/v2/pages?per_page=100&page={page_num}&_fields=id,slug,link,title,content"
        code, body = wp_request('GET', url, auth)
        if code == 400:
            break
        if code != 200:
            print(f"[audit] ERROR listing (page {page_num}): {code}")
            print(body[:500])
            sys.exit(1)
        items = json.loads(body)
        if not items:
            break

        for item in items:
            link = item.get('link', '')
            if '/country-profiles/' not in link:
                continue
            slug    = item.get('slug', '')
            title   = item.get('title', {}).get('rendered', slug)
            content = item.get('content', {}).get('rendered', '')
            # strip HTML tags for easier matching
            stripped = re.sub(r'<[^>]+>', ' ', content)
            if has_sources(stripped):
                with_sources.append(title)
            else:
                without_sources.append(title)

        page_num += 1

    with_sources.sort()
    without_sources.sort()

    print(f"=== HAS sources/references ({len(with_sources)}) ===")
    for n in with_sources:
        print(f"  ✓ {n}")
    print()
    print(f"=== MISSING sources/references ({len(without_sources)}) ===")
    for n in without_sources:
        print(f"  ✗ {n}")
    print()
    print(f"Total: {len(with_sources) + len(without_sources)} country profile pages")


if __name__ == '__main__':
    main()
