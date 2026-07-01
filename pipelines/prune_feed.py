#!/usr/bin/env python3
"""
Global Witness Monitor -- Feed Prune Tool   v3.0  (2026-06-30)

ONE tool. Replaces gwm_delete_persecution.py, gwm_points_sync.py, and the
earlier prune_feed.py. "Delete means delete":

INTERACTIVE PRUNE (default):
  cd /opt/conflict-pipeline; set -a; source .env; set +a
  venv/bin/python prune_feed.py --feed persecution
  -> numbered list, you pick rows, confirm. For each deleted event it:
       1. trashes the WordPress post           (recoverable in WP Trash)
       2. removes it from <feed>.json           (Latest Reports list)
       3. removes it from <feed>.points.json    (the GLOBE DOT)
       4. records it in suppressed_<feed>.json  (no re-publish for 2 days)

SWEEP ORPHAN DOTS (cleanup mode):
  venv/bin/python prune_feed.py --feed persecution --sync-dots
  -> removes every dot in <feed>.points.json whose report is no longer in
     <feed>.json. Use this to clear dots left behind by an older prune.

Settings:
  SUPPRESS_WINDOW_DAYS = 2     (was 21)
  PERMANENT_DELETE     = False (WP posts go to Trash, recoverable)
"""

import os
import sys
import json
import base64
import argparse
import requests
from datetime import datetime, timezone

VERSION = "3.0"
SUPPRESS_WINDOW_DAYS = 2
PERMANENT_DELETE = False   # True = delete WP posts forever instead of Trash

GITHUB_TOKEN  = os.environ['GITHUB_TOKEN']
GITHUB_OWNER  = os.environ.get('GITHUB_OWNER', 'InnovativeGeospatial')
GITHUB_REPO   = os.environ.get('GITHUB_REPO', 'GWM')
GITHUB_BRANCH = os.environ.get('GITHUB_BRANCH', 'main')

WP_URL          = os.environ.get('WP_URL', '').rstrip('/')
WP_USER         = os.environ.get('WP_USER', '')
WP_APP_PASSWORD = os.environ.get('WP_APP_PASSWORD', '')

API_BASE = ('https://api.github.com/repos/'
            + GITHUB_OWNER + '/' + GITHUB_REPO + '/contents/')
PURGE_BASE = ('https://purge.jsdelivr.net/gh/'
              + GITHUB_OWNER + '/' + GITHUB_REPO + '@' + GITHUB_BRANCH + '/')
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


# ---- GitHub helpers -----------------------------------------------------

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


# ---- WordPress: trash the underlying posts ------------------------------

def _trash_wp_posts(delete_ids):
    if not delete_ids:
        return
    if not (WP_URL and WP_USER and WP_APP_PASSWORD):
        print('WordPress: WP_URL/WP_USER/WP_APP_PASSWORD not in env -- skipping '
              'post deletion (feed/dots still pruned).')
        return
    auth = (WP_USER, WP_APP_PASSWORD)
    force = 'true' if PERMANENT_DELETE else 'false'
    verb = 'Deleted' if PERMANENT_DELETE else 'Trashed'
    for pid in sorted(delete_ids):
        try:
            r = requests.delete(WP_URL + '/wp-json/wp/v2/posts/' + str(pid),
                                auth=auth, params={'force': force}, timeout=30)
            if r.status_code in (200, 201):
                print('WordPress: ' + verb + ' post #' + str(pid))
            elif r.status_code in (404, 410):
                print('WordPress: post #' + str(pid) + ' already gone')
            else:
                print('WordPress: post #' + str(pid) + ' -> ' + str(r.status_code))
        except Exception as e:
            print('WordPress: post #' + str(pid) + ' error: ' + str(e)[:80])


# ---- dots: prune the slim points feed -----------------------------------

def _prune_points(feed_name, delete_ids, delete_keys):
    points_name = feed_name + '.points.json'
    try:
        meta = gh_get(points_name)
    except Exception as e:
        print('Points feed ' + points_name + ' not found, skipping dots ('
              + str(e)[:80] + ')')
        return
    sha = meta['sha']
    data = json.loads(base64.b64decode(meta['content']).decode('utf-8'))
    events = data.get('events', [])
    kept = []
    for e in events:
        if e.get('wp_id') is not None and e.get('wp_id') in delete_ids:
            continue
        if (e.get('wp_id') is None
                and (str(e.get('title', '')), str(e.get('date', ''))) in delete_keys):
            continue
        kept.append(e)
    removed = len(events) - len(kept)
    if removed == 0:
        print('Points feed: no matching dots found (already clear).')
        return
    kept.sort(key=lambda e: str(e.get('date', '')), reverse=True)
    data['events'] = kept
    data['count'] = len(kept)
    data['updated'] = datetime.now(timezone.utc).isoformat()
    gh_put(points_name, json.dumps(data, indent=2, ensure_ascii=False), sha,
           'Prune ' + str(removed) + ' point(s) from ' + points_name)
    purge_jsdelivr(points_name)
    print('Points feed: removed ' + str(removed) + ' dot(s). Now '
          + str(len(kept)) + '.')


def _event_key(e):
    if e.get('wp_id') is not None:
        return ('id', e.get('wp_id'))
    return ('td', str(e.get('title', '')), str(e.get('date', '')))


def sync_dots(feed_name):
    """Remove every dot whose report is no longer in <feed>.json."""
    print('=== GWM Dot Sweep v' + VERSION + ' -- ' + feed_name + ' ===')
    active = gh_get(feed_name + '.json')
    active_events = json.loads(base64.b64decode(active['content']).decode('utf-8')).get('events', [])
    live = {_event_key(e) for e in active_events}
    print(feed_name + '.json: ' + str(len(active_events)) + ' reports')

    pname = feed_name + '.points.json'
    pmeta = gh_get(pname)
    pdata = json.loads(base64.b64decode(pmeta['content']).decode('utf-8'))
    points = pdata.get('events', [])
    kept = [e for e in points if _event_key(e) in live]
    removed = len(points) - len(kept)
    print(pname + ': ' + str(len(points)) + ' dots -> ' + str(len(kept))
          + ' (removing ' + str(removed) + ' orphaned)')
    if removed == 0:
        print('Nothing to remove. Dots already match reports.')
        return
    kept.sort(key=lambda e: str(e.get('date', '')), reverse=True)
    pdata['events'] = kept
    pdata['count'] = len(kept)
    pdata['updated'] = datetime.now(timezone.utc).isoformat()
    gh_put(pname, json.dumps(pdata, indent=2, ensure_ascii=False), pmeta['sha'],
           'Sweep ' + str(removed) + ' orphaned dot(s) from ' + pname)
    purge_jsdelivr(pname)
    print('Done. Removed ' + str(removed) + ' orphaned dot(s). Globe clears in a few minutes.')


# ---- suppression --------------------------------------------------------

def _write_suppressions(feed_name, to_delete):
    path = os.path.join(SCRIPT_DIR, 'suppressed_' + feed_name + '.json')
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception:
        data = {}
    existing = data.get('suppressed', []) if isinstance(data, dict) else []
    today = datetime.now(timezone.utc).date().isoformat()

    def keyof(country, etype, title):
        return (str(country).strip().lower(), str(etype).strip().lower(),
                str(title).strip().lower())

    have = {keyof(s.get('country', ''), s.get('type', ''), s.get('title', ''))
            for s in existing}
    added = 0
    for e in to_delete:
        country = e.get('country', '')
        etype = e.get('type', '') or e.get('event_type', '')
        title = e.get('title', '')
        k = keyof(country, etype, title)
        if k in have:
            continue
        existing.append({
            'country': country, 'type': etype,
            'lat': e.get('lat'), 'lng': e.get('lng'),
            'title': title, 'date': today,
            'window_days': SUPPRESS_WINDOW_DAYS,
        })
        have.add(k)
        added += 1

    with open(path, 'w', encoding='utf-8') as f:
        json.dump({'updated': datetime.now(timezone.utc).isoformat(),
                   'suppressed': existing}, f, ensure_ascii=False, indent=2)
    print('Suppression list ' + os.path.basename(path) + ': +' + str(added)
          + ' new (total ' + str(len(existing)) + ', window '
          + str(SUPPRESS_WINDOW_DAYS) + 'd).')
    if feed_name != 'conflict':
        print('NOTE: only the conflict pipeline currently reads the suppression '
              'list. ' + feed_name + ' entries are recorded but not yet enforced.')


# ---- interactive prune --------------------------------------------------

def run(feed_name):
    filename = feed_name + '.json'
    print('=== GWM Feed Prune v' + VERSION + ' -- ' + filename + ' ===')

    print('Fetching ' + filename + ' from GitHub...')
    meta = gh_get(filename)
    sha = meta['sha']
    data = json.loads(base64.b64decode(meta['content']).decode('utf-8'))
    events = data.get('events', [])
    if not events:
        print('Feed has no events. Nothing to prune.')
        return

    events_sorted = sorted(events, key=lambda e: str(e.get('date', '')), reverse=False)
    print('\nCurrent events (' + str(len(events_sorted)) + ' total):\n')
    for i, e in enumerate(events_sorted, start=1):
        country = str(e.get('country', '')).title()
        date = str(e.get('date', ''))[:10]
        title = str(e.get('title', ''))[:80]
        print('  [' + str(i).rjust(3) + ']  ' + date + '  '
              + country.ljust(20) + '  ' + title)

    print('\nType numbers to DELETE (e.g. "3,7,12" or "3-7,12"). Enter to cancel.')
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
    print('\nWill DELETE these ' + str(len(to_delete)) + ' event(s) '
          + '(WP post + report + map dot):')
    for e in to_delete:
        print('   - ' + str(e.get('date', ''))[:10] + '  '
              + str(e.get('country', '')).title().ljust(20) + '  '
              + str(e.get('title', ''))[:80])
    print('Suppressed from re-publishing for ' + str(SUPPRESS_WINDOW_DAYS) + ' days.')
    if confirm_no(input('\nProceed? (yes/no): ')):
        print('Cancelled.')
        return

    delete_ids = {e.get('wp_id') for e in to_delete if e.get('wp_id') is not None}
    delete_keys = {(str(e.get('title', '')), str(e.get('date', '')))
                   for e in to_delete if e.get('wp_id') is None}

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
              + ' but matched ' + str(removed_count) + '. Aborting to avoid corruption.')
        return

    # 1. WordPress
    _trash_wp_posts(delete_ids)

    # 2. report feed
    kept.sort(key=lambda e: str(e.get('date', '')), reverse=True)
    data['events'] = kept
    data['count'] = len(kept)
    data['updated'] = datetime.now(timezone.utc).isoformat()
    print('Committing ' + filename + '...')
    gh_put(filename, json.dumps(data, indent=2, ensure_ascii=False), sha,
           'Prune ' + str(removed_count) + ' event(s) from ' + filename)
    purge_jsdelivr(filename)

    # 3. dots  4. suppression
    _prune_points(feed_name, delete_ids, delete_keys)
    _write_suppressions(feed_name, to_delete)

    print('\n=== Done. Removed ' + str(removed_count)
          + ' (WP post + report + dot). Feed now has ' + str(len(kept)) + ' events. ===')
    print('Note: jsDelivr can take a few minutes. Raw GitHub is instant.')


def confirm_no(ans):
    return ans.strip().lower() not in ('y', 'yes')


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--feed', default='conflict',
                   choices=['conflict', 'persecution', 'disasters'])
    p.add_argument('--sync-dots', action='store_true',
                   help='Only remove orphaned map dots (reports already deleted).')
    args = p.parse_args()
    if args.sync_dots:
        sync_dots(args.feed)
    else:
        run(args.feed)
