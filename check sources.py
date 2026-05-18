#!/usr/bin/env python3
"""
check_sources.py — audit country profile pages for missing Sources/References sections.

Finds the /country-profiles/ parent page, then audits all child pages.
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

    print(f"[audit] WP: {wp_url}")

    code, body = wp_get(
        f"{wp_url}/wp-json/wp/v2/pages?slug=country-profiles&_fields=id,slug,link",
        auth
    )
    if code != 200:
        print(f"[audit] ERROR finding parent: {code}\n{body[:500]}")
        sys.exit(1)
    parents = json.loads(body)
    if not parents:
        print("[audit] No page with slug 'country-profiles' found")
        sys.exit(1)
    parent_id = parents[0]['id']
    print(f"[audit] parent page id: {parent_id} ({parents[0]['link']})")
    print()

    with_sources    = []
    without_sources = []
    page_num = 1

    while True:
        url = (f"{wp_url}/wp-json/wp/v2/pages"
               f"?parent={parent_id}&per_page=100&page={page_num}"
               f"&_fields=id,slug,link,title,content")
        code, body = wp_get(url, auth)
        if code == 400:
            break
        if code != 200:
            print(f"[audit] ERROR listing children (page {page_num}): {code}")
            print(body[:500])
            sys.exit(1)
        items = json.loads(body)
        if not items:
            break

        for item in items:
            title   = item.get('title', {}).get('rendered', item.get('slug', ''))
            content = item.get('content', {}).get('rendered', '')
            if has_sources(content):
                with_sources.append(title)
            else:
                without_sources.append(title)

        if len(items) < 100:
            break
        page_num += 1

    with_sources.sort()
    without_sources.sort()

    print(f"=== HAS sources/references ({len(with_sources)}) ===")
    for n in with_sources:
        print(f"  has  {n}")
    print()
    print(f"=== MISSING sources/references ({len(without_sources)}) ===")
    for n in without_sources:
        print(f"  MISSING  {n}")
    print()
    print(f"Total: {len(with_sources) + len(without_sources)} country profile pages")


if __name__ == '__main__':
    main()
