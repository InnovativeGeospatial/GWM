#!/usr/bin/env python3
"""
strip_dividers.py — remove trailing '=====' divider lines from country profile pages

Reads WP_URL, WP_USER, WP_APP_PASSWORD from /opt/conflict-pipeline/.env
Iterates all posts under the country-profiles slug path, finds trailing lines
that are just '=' characters (with optional leading '#' and whitespace),
strips them, and updates the post.

DRY RUN: pass --dry to preview without changes.

Run:
    cd /opt/conflict-pipeline
    venv/bin/python strip_dividers.py --dry
    venv/bin/python strip_dividers.py
"""

import os
import re
import sys
import json
import base64
import urllib.request
import urllib.error
import urllib.parse

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

def wp_request(method, url, auth_header, payload=None):
    data = json.dumps(payload).encode("utf-8") if payload else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", auth_header)
    req.add_header("Accept", "application/json")
    if data:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, r.headers, r.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, e.headers, e.read().decode("utf-8", errors="replace")

# Match a line that is the divider: optional whitespace, optional '#', whitespace, then 10+ '=' signs
DIVIDER_LINE_RE = re.compile(r'^\s*#?\s*={10,}\s*$', re.MULTILINE)

def strip_trailing_dividers(content):
    """
    Remove trailing divider lines and their surrounding empty/whitespace blocks.
    Handles both plain divider lines and divider lines wrapped in <p> or <pre> tags.
    """
    original = content

    # Remove paragraph-wrapped dividers at the end: <p># ====...</p> or <p>====...</p>
    pattern_p = re.compile(
        r'(?:<!--\s*wp:paragraph\s*-->\s*)?<p>\s*#?\s*={10,}\s*</p>(?:\s*<!--\s*/wp:paragraph\s*-->)?\s*$',
        re.IGNORECASE
    )
    while True:
        new = pattern_p.sub('', content).rstrip()
        if new == content:
            break
        content = new

    # Remove preformatted-wrapped dividers at the end
    pattern_pre = re.compile(
        r'(?:<!--\s*wp:preformatted\s*-->\s*)?<pre[^>]*>\s*#?\s*={10,}\s*</pre>(?:\s*<!--\s*/wp:preformatted\s*-->)?\s*$',
        re.IGNORECASE
    )
    while True:
        new = pattern_pre.sub('', content).rstrip()
        if new == content:
            break
        content = new

    # Remove plain trailing divider lines (no wrapping tags)
    lines = content.split('\n')
    while lines and DIVIDER_LINE_RE.match(lines[-1].strip() or ''):
        lines.pop()
    while lines and not lines[-1].strip():
        lines.pop()
    content = '\n'.join(lines)

    return content, content != original


def main():
    dry = '--dry' in sys.argv

    env = load_env()
    wp_url  = env.get('WP_URL', 'https://globalwitnessmonitor.com').rstrip('/')
    wp_user = env['WP_USER']
    wp_pass = env['WP_APP_PASSWORD']

    auth = 'Basic ' + base64.b64encode(f'{wp_user}:{wp_pass}'.encode()).decode()

    print(f"[strip] WP: {wp_url}")
    print(f"[strip] mode: {'DRY RUN' if dry else 'LIVE'}")
    print()

    # Country profiles are WP "pages" (not posts) under /country-profiles/
    # Try pages endpoint with parent filter — but easier: list all pages and filter by slug pattern.
    # Fetch in batches of 100.
    page_num = 1
    updated = 0
    skipped = 0
    failed  = 0
    checked = 0

    while True:
        list_url = f"{wp_url}/wp-json/wp/v2/pages?per_page=100&page={page_num}&_fields=id,slug,link,title,content"
        code, headers, body = wp_request('GET', list_url, auth)
        if code == 400:
            # past the last page
            break
        if code != 200:
            print(f"[strip] ERROR listing pages (page {page_num}): {code}")
            print(body[:500])
            sys.exit(1)

        items = json.loads(body)
        if not items:
            break

        for item in items:
            slug = item.get('slug', '')
            link = item.get('link', '')
            # Only country profile pages
            if '/country-profiles/' not in link:
                continue

            checked += 1
            content = item.get('content', {}).get('rendered', '')
            # Use raw if available — but rendered is what /pages returns by default.
            # Need raw content for editing. Fetch with context=edit.
            edit_url = f"{wp_url}/wp-json/wp/v2/pages/{item['id']}?context=edit&_fields=id,content"
            ec, _, eb = wp_request('GET', edit_url, auth)
            if ec != 200:
                print(f"[strip]  ! {slug}: cannot fetch raw content ({ec})")
                failed += 1
                continue
            raw = json.loads(eb)['content']['raw']

            new_content, changed = strip_trailing_dividers(raw)

            if not changed:
                skipped += 1
                continue

            title = item.get('title', {}).get('rendered', slug)
            if dry:
                print(f"[strip]  ~ {slug}: would update (was {len(raw)} → {len(new_content)} chars)")
                updated += 1
                continue

            up_url = f"{wp_url}/wp-json/wp/v2/pages/{item['id']}"
            uc, _, ub = wp_request('POST', up_url, auth, {'content': new_content})
            if uc in (200, 201):
                print(f"[strip]  ✓ {slug}: updated")
                updated += 1
            else:
                print(f"[strip]  ! {slug}: update failed ({uc})")
                print(ub[:300])
                failed += 1

        page_num += 1

    print()
    print(f"[strip] checked: {checked}")
    print(f"[strip] {'would update' if dry else 'updated'}: {updated}")
    print(f"[strip] no divider found: {skipped}")
    print(f"[strip] failed: {failed}")
    if dry:
        print()
        print("Dry run complete. Re-run without --dry to apply.")


if __name__ == '__main__':
    main()
