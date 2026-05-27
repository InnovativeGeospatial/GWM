#!/usr/bin/env python3
"""
Global Witness Monitor -- Conflict Feed Prune Tool

Interactively delete events from conflict.json.

Workflow:
  1. Pulls the current feed from GitHub (so you're always editing the latest).
  2. Prints a numbered list of every event (newest first) with country, date, title.
  3. You type the numbers to delete (e.g. "3,7,12" or a range "3-7,12").
  4. Shows what will be deleted and asks for confirmation.
  5. Rewrites the feed without those events, fixes 'count' and 'updated',
     commits to GitHub (GET sha -> PUT), purges jsDelivr.

Run:
  cd /opt/conflict-pipeline && set -a && source .env && set +a && \
      venv/bin/python prune_feed.py

Optional flag:
  --feed persecution   prune persecution.json instead (works the same way)
  --feed disasters     prune disasters.json
  --feed conflict      default
"""

import os
import sys
import json
import base64
import argparse
import requests
from datetime import datetime, timezone

# ---- env / config -------------------------------------------------------

GITHUB_TOKEN  = os.environ['GITHUB_TOKEN']
GITHUB_OWNER  = os.environ.get('GITHUB_OWNER', 'InnovativeGeospatial')
GITHUB_REPO   = os.environ.get('GITHUB_REPO', 'GWM')
GITHUB_BRANCH = os.environ.get('GITHUB_BRANCH', 'main')

API_BASE = ('https://api.github.com/repos/'
            + GITHUB_OWNER + '/' + GITHUB_REPO + '/contents/')
PURGE_BASE = ('https://purge.jsdelivr.net/gh/'
              + GITHUB_OWNER + '/' + GITHUB_REPO + '@' + GITHUB_BRANCH + '/')


# ---- helpers ------------------------------------------------------------

def gh_get(path):
    url = API_BASE + path + '?ref=' + GITHUB_BRANCH
    r = requests.get(url, headers={
        'Authorization': 'token ' + GITHUB_TOKEN,
        'Accept': 'application/vnd.github+json',
    }, timeout=30)
    if r.status_code != 200:
        raise RuntimeError('GitHub GET ' + path + ' -> ' + str(r.status_code)
                           + ': ' + r.text[:300])
    return r.json()


def gh_put(path, content_str, sha, message):
    url = API_BASE + path
    payload = {
        'message':  message,
        'content':  base64.b64encode(content_str.encode('utf-8')).decode('ascii'),
        'sha':      sha,
        'branch':   GITHUB_BRANCH,
    }
    r = requests.put(url, headers={
        'Authorization': 'token ' + GITHUB_TOKEN,
        'Accept': 'application/vnd.github+json',
    }, json=payload, timeout=30)
    if r.status_code not in (200, 201):
        raise RuntimeError('GitHub PUT ' + path + ' -> ' + str(r.status_code)
                           + ': ' + r.text[:300])
    return r.json()


def purge_jsdelivr(filename):
    try:
        r = requests.get(PURGE_BASE + filename, timeout=20)
        print('jsDelivr purge ' + filename + ' -> ' + str(r.status_code))
    except Exception as e:
        print('jsDelivr purge failed: ' + str(e))


def parse_selection(text, max_n):
    """Accept '3,7,12' or '3-7,12,15-17'. Returns sorted list of unique
    1-based indices in range [1, max_n]."""
    out = set()
    text = text.strip()
    if not text:
        return []
    for part in text.split(','):
        part = part.strip()
        if not part:
            continue
        if '-' in part:
            a, b = part.split('-', 1)
            a, b = int(a.strip()), int(b.strip())
            if a > b:
                a, b = b, a
            for i in range(a, b + 1):
                if 1 <= i <= max_n:
                    out.add(i)
        else:
            i = int(part)
            if 1 <= i <= max_n:
                out.add(i)
    return sorted(out)


# ---- main ---------------------------------------------------------------

def run(feed_name):
    filename = feed_name + '.json'
    print('=== GWM Feed Prune -- ' + filename + ' ===')

    # 1. Pull latest from GitHub (with SHA for later PUT)
    print('Fetching ' + filename + ' from GitHub...')
    meta = gh_get(filename)
    sha = meta['sha']
    raw = base64.b64decode(meta['content']).decode('utf-8')
    data = json.loads(raw)
    events = data.get('events', [])
    if not events:
        print('Feed has no events. Nothing to prune.')
        return

    # 2. Sort by date desc and print numbered list
    events_sorted = sorted(
        events, key=lambda e: str(e.get('date', '')), reverse=True
    )
    print('\nCurrent events (' + str(len(events_sorted)) + ' total, newest first):\n')
    for i, e in enumerate(events_sorted, start=1):
        country = str(e.get('country', '')).title()
        date = str(e.get('date', ''))[:10]
        title = str(e.get('title', ''))[:80]
        print('  [' + str(i).rjust(3) + ']  ' + date + '  '
              + country.ljust(20) + '  ' + title)

    # 3. Prompt
    print('')
    print('Type numbers to DELETE (e.g. "3,7,12" or "3-7,12").')
    print('Press Enter with no input to cancel.')
    sel_text = input('Delete: ').strip()
    if not sel_text:
        print('Cancelled.')
        return

    try:
        indices = parse_selection(sel_text, len(events_sorted))
    except Exception as e:
        print('Could not parse selection: ' + str(e))
        return

    if not indices:
        print('No valid selections. Cancelled.')
        return

    to_delete = [events_sorted[i - 1] for i in indices]

    # 4. Confirm
    print('\nWill DELETE these ' + str(len(to_delete)) + ' event(s):')
    for e in to_delete:
        country = str(e.get('country', '')).title()
        date = str(e.get('date', ''))[:10]
        title = str(e.get('title', ''))[:80]
        print('   - ' + date + '  ' + country.ljust(20) + '  ' + title)
    confirm = input('\nProceed? (yes/no): ').strip().lower()
    if confirm not in ('y', 'yes'):
        print('Cancelled.')
        return

    # 5. Rewrite feed
    delete_ids = set()
    for e in to_delete:
        wp = e.get('wp_id')
        if wp is not None:
            delete_ids.add(wp)
    # Fallback identity for events with no wp_id: (title, date)
    delete_keys = set()
    for e in to_delete:
        if e.get('wp_id') is None:
            delete_keys.add((str(e.get('title', '')), str(e.get('date', ''))))

    kept = []
    for e in events:
        if e.get('wp_id') is not None and e.get('wp_id') in delete_ids:
            continue
        if (e.get('wp_id') is None
                and (str(e.get('title', '')), str(e.get('date', ''))) in delete_keys):
            continue
        kept.append(e)

    removed_count = len(events) - len(kept)
    if removed_count != len(to_delete):
        print('WARNING: planned to remove ' + str(len(to_delete))
              + ' but actually removed ' + str(removed_count)
              + '. Aborting to avoid corruption.')
        return

    data['events']  = kept
    data['count']   = len(kept)
    data['updated'] = datetime.now(timezone.utc).isoformat()

    new_content = json.dumps(data, indent=2, ensure_ascii=False)

    # 6. Commit
    print('Committing to GitHub...')
    msg = ('Prune ' + str(removed_count) + ' event(s) from ' + filename)
    gh_put(filename, new_content, sha, msg)
    print('Commit OK.')

    # 7. Purge jsDelivr
    purge_jsdelivr(filename)

    print('\n=== Done. Removed ' + str(removed_count)
          + ' event(s). Feed now has ' + str(len(kept)) + ' events. ===')
    print('Note: jsDelivr propagation can take a few minutes. Raw GitHub is '
          'instant.')


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--feed', default='conflict',
                   choices=['conflict', 'persecution', 'disasters'],
                   help='Which feed to prune (default: conflict)')
    args = p.parse_args()
    run(args.feed)
