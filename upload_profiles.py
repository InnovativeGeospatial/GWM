#!/usr/bin/env python3
"""
GWM Country Profile Uploader v3
Reads combined profiles.txt, finds each WordPress page by slug,
and OVERWRITES content completely via the WP REST API.

Deploy: commit to GitHub, then on droplet:
  curl -o /opt/conflict-pipeline/upload_profiles.py \
    https://raw.githubusercontent.com/InnovativeGeospatial/GWM-archive/main/scripts/upload_profiles.py

Run:
  cd /opt/conflict-pipeline && set -a && source .env && set +a && venv/bin/python upload_profiles.py
"""

import os
import re
import sys
import time
import requests
from dotenv import load_dotenv
load_dotenv('/opt/conflict-pipeline/.env')

# ── CONFIG ────────────────────────────────────────────────────

WP_URL          = os.environ.get('WP_URL', '').rstrip('/')
WP_USER         = os.environ.get('WP_USER', '')
WP_APP_PASSWORD = os.environ.get('WP_APP_PASSWORD', '')
PROFILES_FILE   = '/opt/conflict-pipeline/profiles.txt'
DELAY_SECONDS   = 0.4   # pause between API calls to avoid hammering WP

# ── MARKDOWN TO HTML ─────────────────────────────────────────

def md_to_html(text):
    lines = text.split('\n')
    html_lines = []
    in_list = False
    in_para = False
    para_buf = []

    def flush_para():
        nonlocal in_para, para_buf
        if para_buf:
            content = ' '.join(para_buf).strip()
            if content:
                html_lines.append('<p>' + content + '</p>')
        in_para = False
        para_buf = []

    def flush_list():
        nonlocal in_list
        if in_list:
            html_lines.append('</ul>')
            in_list = False

    def inline(s):
        # Bold
        s = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', s)
        # Italic
        s = re.sub(r'\*(.+?)\*', r'<em>\1</em>', s)
        # Links
        s = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', s)
        return s

    for line in lines:
        stripped = line.strip()

        # Skip separator lines and empty metadata markers
        if re.match(r'^={10,}$', stripped) or re.match(r'^-{3,}$', stripped):
            flush_para()
            flush_list()
            continue

        # Skip metadata header lines (COUNTRY:, TITLE:, SLUG:, etc.)
        if re.match(r'^[A-Z_]+:\s', stripped) and not stripped.startswith('##'):
            continue

        # H2
        if stripped.startswith('## '):
            flush_para()
            flush_list()
            heading = inline(stripped[3:].strip())
            html_lines.append('<h2>' + heading + '</h2>')
            continue

        # H3
        if stripped.startswith('### '):
            flush_para()
            flush_list()
            heading = inline(stripped[4:].strip())
            html_lines.append('<h3>' + heading + '</h3>')
            continue

        # Bullet list item
        if stripped.startswith('- '):
            flush_para()
            if not in_list:
                html_lines.append('<ul>')
                in_list = True
            item = inline(stripped[2:].strip())
            html_lines.append('<li>' + item + '</li>')
            continue

        # Blank line — end paragraph and list
        if not stripped:
            flush_para()
            flush_list()
            continue

        # Regular text — accumulate into paragraph
        flush_list()
        in_para = True
        para_buf.append(inline(stripped))

    flush_para()
    flush_list()
    return '\n'.join(html_lines)

# ── PROFILE PARSER ────────────────────────────────────────────

def parse_profiles(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        raw = f.read()

    # Split on the separator lines that precede each COUNTRY: block
    # Each profile block starts with a line of ===...
    # We split on COUNTRY: markers reliably
    blocks = re.split(r'(?:^|\n)COUNTRY:\s*', raw)

    profiles = []
    for block in blocks:
        if not block.strip():
            continue

        lines = block.strip().split('\n')
        country_name = lines[0].strip()
        if not country_name:
            continue

        # Extract metadata fields
        def get_field(field):
            m = re.search(r'^' + field + r':\s*(.+)$', block, re.MULTILINE)
            return m.group(1).strip() if m else ''

        title = get_field('TITLE') or country_name
        slug  = get_field('SLUG')   # e.g. "country-profiles/afghanistan"

        # Extract content — everything from first ## heading onward
        content_match = re.search(r'^##\s+', block, re.MULTILINE)
        if not content_match:
            print('  WARNING: No ## heading found for ' + country_name + ' — skipping')
            continue

        content_md = block[content_match.start():]
        content_html = md_to_html(content_md)

        profiles.append({
            'country':  country_name,
            'title':    title,
            'slug':     slug,
            'content':  content_html,
        })

    return profiles

# ── WORDPRESS API ─────────────────────────────────────────────

def find_page_by_slug(slug):
    """
    Find a WordPress page by its full slug, e.g. 'country-profiles/afghanistan'.
    Tries the slug leaf first (just 'afghanistan'), then filters by full path.
    """
    if not slug:
        return None

    leaf = slug.split('/')[-1]  # 'afghanistan'

    # Search by slug
    url = WP_URL + '/wp-json/wp/v2/pages'
    params = {'slug': leaf, 'per_page': 10, '_fields': 'id,slug,link,parent,title'}
    r = requests.get(url, params=params, auth=(WP_USER, WP_APP_PASSWORD), timeout=15)

    if r.status_code != 200:
        return None

    pages = r.json()
    if not pages:
        return None

    # If only one result, use it
    if len(pages) == 1:
        return pages[0]

    # Multiple results — prefer the one whose link contains the full slug path
    slug_lower = slug.lower()
    for page in pages:
        link = page.get('link', '').lower()
        if slug_lower in link:
            return page

    # Fall back to first result
    return pages[0]


def update_page(page_id, title, content):
    """Overwrite a WordPress page's title and content completely."""
    url = WP_URL + '/wp-json/wp/v2/pages/' + str(page_id)
    payload = {
        'title':   title,
        'content': content,
        'status':  'publish',
    }
    r = requests.post(
        url,
        json=payload,
        auth=(WP_USER, WP_APP_PASSWORD),
        timeout=30,
    )
    return r.status_code in (200, 201)

# ── MAIN ──────────────────────────────────────────────────────

def main():
    # Validate config
    if not WP_URL or not WP_USER or not WP_APP_PASSWORD:
        print('ERROR: WP_URL, WP_USER, and WP_APP_PASSWORD must be set in environment.')
        sys.exit(1)

    print('=== GWM Profile Uploader v3 ===')
    print('Source file: ' + PROFILES_FILE)
    print('Target:      ' + WP_URL)
    print('')

    if not os.path.exists(PROFILES_FILE):
        print('ERROR: profiles.txt not found at ' + PROFILES_FILE)
        sys.exit(1)

    profiles = parse_profiles(PROFILES_FILE)
    print('Profiles parsed: ' + str(len(profiles)))
    print('')

    success   = 0
    not_found = []
    failed    = []

    for p in profiles:
        country = p['country']
        slug    = p['slug']
        label   = country + ' (' + slug + ')' if slug else country
        print('  ' + label + ' ...', end=' ', flush=True)

        page = find_page_by_slug(slug)
        if not page:
            print('NOT FOUND')
            not_found.append(country)
            time.sleep(DELAY_SECONDS)
            continue

        page_id = page['id']
        ok = update_page(page_id, p['title'], p['content'])

        if ok:
            print('OK  [ID ' + str(page_id) + ']')
            success += 1
        else:
            print('FAILED')
            failed.append(country)

        time.sleep(DELAY_SECONDS)

    print('')
    print('=== Results ===')
    print('Updated:   ' + str(success))
    print('Not found: ' + str(len(not_found)))
    if not_found:
        for c in not_found:
            print('  - ' + c)
    print('Failed:    ' + str(len(failed)))
    if failed:
        for c in failed:
            print('  - ' + c)

if __name__ == '__main__':
    main()
