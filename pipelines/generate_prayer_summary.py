#!/usr/bin/env python3
"""
GWM Prayer Summary Generator v2

Changes from v1:
- Reads feeds from raw GitHub (no dependency on local file paths)
- Uses Bearer auth matching gwm_json_writer.py
- Reads same GitHub env vars as the writer: GITHUB_TOKEN, GITHUB_OWNER,
  GITHUB_REPO, GITHUB_BRANCH

Runs after the three pipelines. Fetches the three live JSON feeds from
GitHub, filters to harm events where applicable, calls Claude once per
section to synthesize a bulleted prayer list, writes prayer_summary.json,
and pushes it to the active GitHub repo for the Pray page to fetch.

Filter rules:
- Persecution: all events (already judged by Claude in the pipeline)
- Conflict: exclude type "Other"; keep Armed Conflict, Civil Unrest,
  Coup or Crisis, Displacement
- Disaster: all events

Time window: events from the last 24 hours.

Cost: ~3 Claude calls per run, ~$0.005 total.
"""

import os
import sys
import json
import base64
import logging
import requests
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
import anthropic

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
log = logging.getLogger(__name__)

# Load env from conflict pipeline (has GitHub creds + Anthropic key)
load_dotenv('/opt/conflict-pipeline/.env')

ANTHROPIC_KEY = os.environ['ANTHROPIC_API_KEY']
GITHUB_TOKEN = os.environ['GITHUB_TOKEN']
GITHUB_OWNER = os.environ.get('GITHUB_OWNER', 'InnovativeGeospatial').strip()
GITHUB_REPO = os.environ.get('GITHUB_REPO', 'GWM').strip()
GITHUB_BRANCH = os.environ.get('GITHUB_BRANCH', 'main').strip()
GITHUB_PATH = os.environ.get('GITHUB_PATH', '').strip()

# Build the raw-content base URL for fetching feeds
RAW_BASE = (
    f"https://raw.githubusercontent.com/{GITHUB_OWNER}/{GITHUB_REPO}/"
    f"{GITHUB_BRANCH}/"
)
if GITHUB_PATH:
    RAW_BASE += GITHUB_PATH.rstrip('/') + '/'

FEED_URLS = {
    'persecution': RAW_BASE + 'persecution.json',
    'conflict':    RAW_BASE + 'conflict.json',
    'disaster':    RAW_BASE + 'disasters.json',
}

# Where to push the output in the repo (same path prefix as the feeds)
GITHUB_OUTPUT_PATH = (GITHUB_PATH.rstrip('/') + '/') if GITHUB_PATH else ''
GITHUB_OUTPUT_PATH += 'prayer_summary.json'

# Local copy (handy for debugging)
LOCAL_OUTPUT = '/opt/conflict-pipeline/data/prayer_summary.json'

# Filter rules
CONFLICT_KEEP_TYPES = {'Armed Conflict', 'Civil Unrest', 'Coup or Crisis', 'Displacement'}
WINDOW_HOURS = 24


def fetch_feed(url):
    """Fetch a JSON feed from raw GitHub. Returns event list or []."""
    try:
        nocache_url = url + '?nocache=' + str(int(datetime.now().timestamp()))
        r = requests.get(nocache_url, timeout=20)
        if r.status_code != 200:
            log.warning('Feed fetch failed (%s): %s', r.status_code, url)
            return []
        data = r.json()
        events = data.get('events', [])
        log.info('Fetched %d events from %s', len(events), url.split('/')[-1])
        return events
    except Exception as e:
        log.error('Error fetching %s: %s', url, e)
        return []


def filter_recent(events, hours=WINDOW_HOURS):
    """Keep only events from the last N hours."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    kept = []
    for ev in events:
        date_str = ev.get('date', '')
        if not date_str:
            continue
        try:
            if 'Z' in date_str:
                dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            elif '+' in date_str or date_str.count('-') > 2:
                dt = datetime.fromisoformat(date_str)
            else:
                dt = datetime.fromisoformat(date_str).replace(tzinfo=timezone.utc)
            if dt >= cutoff:
                kept.append(ev)
        except Exception as e:
            log.debug('Date parse error for %r: %s', date_str, e)
            continue
    return kept


def filter_conflict_types(events):
    """Drop events of type 'Other'. Keep the harm-category types."""
    return [e for e in events if e.get('type', 'Other') in CONFLICT_KEEP_TYPES]


def build_event_brief(ev):
    """Compact event representation for the Claude prompt."""
    import re as _re
    title = ev.get('title', '')[:120]
    country = ev.get('country', '')
    etype = ev.get('type', '')
    prayer = ev.get('prayer', '')
    body = ev.get('body', '')
    body_clean = _re.sub(r'<[^>]+>', ' ', body)
    body_clean = _re.sub(r'\s+', ' ', body_clean).strip()
    if len(body_clean) > 500:
        body_clean = body_clean[:500] + '...'
    parts = [
        'TITLE: ' + title,
        'COUNTRY: ' + country,
        'TYPE: ' + etype,
    ]
    if prayer:
        parts.append('EXISTING_PRAYER_NOTE: ' + prayer)
    parts.append('SUMMARY: ' + body_clean)
    return '\n'.join(parts)


SYSTEM_PROMPT = """You are writing a prayer guide for Christians around the world based on real news events from the last 24 hours.

Produce a JSON-formatted bulleted prayer list. Each bullet:
- Begins with a verb in imperative voice (Pray for..., Lift up..., Ask God for...)
- Is one sentence, 15-30 words
- Names the country and the concrete need (people affected, situation)
- Does NOT name individuals (names, churches, towns, villages, provinces)
- Does NOT assign political blame; focuses on people and outcomes to pray for
- Does NOT use the word "intercessor" or "intercession"

If multiple events from the same country exist, combine them into a single bullet that captures the shared need.

If no events qualify, return an empty bullets list.

REDACTION RULES (especially for persecution events):
- Never name a specific person
- Never name a specific church, ministry, or denomination
- Never name a town, village, district, or province; use the country only
- You may reference watchdog organizations if the source events did (Open Doors, ChinaAid, etc) but only if essential

Respond with ONLY valid JSON in this exact format, nothing before or after:
{"bullets": ["First prayer point.", "Second prayer point.", "Third prayer point."]}
"""


def call_claude_for_section(section_name, events, client):
    if not events:
        return []

    briefs = [build_event_brief(ev) for ev in events]
    joined = '\n\n---\n\n'.join(briefs)

    user_prompt = (
        'Section: ' + section_name.upper() + '\n'
        'Event count: ' + str(len(events)) + '\n\n'
        'Events from the last 24 hours:\n\n'
        + joined + '\n\n'
        'Generate the bulleted prayer list as JSON.'
    )

    try:
        msg = client.messages.create(
            model='claude-sonnet-4-6',
            max_tokens=1200,
            system=SYSTEM_PROMPT,
            messages=[{'role': 'user', 'content': user_prompt}],
        )
        raw = msg.content[0].text.strip()
        if raw.startswith('```'):
            raw = raw.split('```')[1]
            if raw.startswith('json'):
                raw = raw[4:]
            raw = raw.strip()
        parsed = json.loads(raw)
        bullets = parsed.get('bullets', [])
        log.info('%s: generated %d bullets from %d events',
                 section_name, len(bullets), len(events))
        return bullets
    except Exception as e:
        log.error('%s: Claude call failed: %s', section_name, e)
        return []


def gh_headers():
    return {
        'Authorization': 'Bearer ' + GITHUB_TOKEN,
        'Accept': 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28',
    }


def push_to_github(filepath, content_str):
    """Push the file to GITHUB_OWNER/GITHUB_REPO at filepath on GITHUB_BRANCH."""
    api_url = (
        'https://api.github.com/repos/' + GITHUB_OWNER + '/' + GITHUB_REPO +
        '/contents/' + filepath
    )
    log.info('Pushing to: %s (branch=%s)', api_url, GITHUB_BRANCH)

    # GET current SHA if file exists
    sha = None
    r = requests.get(api_url, headers=gh_headers(),
                     params={'ref': GITHUB_BRANCH}, timeout=15)
    if r.status_code == 200:
        sha = r.json().get('sha')
        log.info('Existing file SHA: %s', sha[:8] if sha else '(none)')
    elif r.status_code == 404:
        log.info('File does not exist yet, will create new')
    else:
        log.warning('GET returned %s: %s', r.status_code, r.text[:200])

    payload = {
        'message': 'Update prayer summary ' +
                   datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC'),
        'content': base64.b64encode(content_str.encode('utf-8')).decode('ascii'),
        'branch': GITHUB_BRANCH,
    }
    if sha:
        payload['sha'] = sha

    r = requests.put(api_url, headers=gh_headers(), json=payload, timeout=30)
    if r.status_code in (200, 201):
        log.info('Pushed %s to GitHub successfully', filepath)
        return True
    log.error('GitHub push failed (%s): %s', r.status_code, r.text[:300])
    return False


def main():
    log.info('=== Prayer Summary Generator v2 starting ===')
    log.info('GitHub target: %s/%s @ %s (path prefix: %r)',
             GITHUB_OWNER, GITHUB_REPO, GITHUB_BRANCH, GITHUB_PATH)
    log.info('Output path in repo: %s', GITHUB_OUTPUT_PATH)

    client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)

    # Fetch all three feeds from raw GitHub
    persecution_events = fetch_feed(FEED_URLS['persecution'])
    conflict_events = fetch_feed(FEED_URLS['conflict'])
    disaster_events = fetch_feed(FEED_URLS['disaster'])

    # Filter by time
    persecution_recent = filter_recent(persecution_events)
    conflict_recent = filter_recent(conflict_events)
    disaster_recent = filter_recent(disaster_events)

    # Apply conflict type filter
    conflict_filtered = filter_conflict_types(conflict_recent)

    log.info('After filtering: persecution=%d conflict=%d disaster=%d',
             len(persecution_recent), len(conflict_filtered),
             len(disaster_recent))

    # Generate bullets per section
    persecution_bullets = call_claude_for_section(
        'persecution', persecution_recent, client)
    conflict_bullets = call_claude_for_section(
        'conflict', conflict_filtered, client)
    disaster_bullets = call_claude_for_section(
        'disaster', disaster_recent, client)

    # Assemble output
    output = {
        'updated': datetime.now(timezone.utc).isoformat(),
        'window_hours': WINDOW_HOURS,
        'sections': {
            'persecution': {
                'event_count': len(persecution_recent),
                'bullets': persecution_bullets,
            },
            'conflict': {
                'event_count': len(conflict_filtered),
                'bullets': conflict_bullets,
            },
            'disaster': {
                'event_count': len(disaster_recent),
                'bullets': disaster_bullets,
            },
        },
    }

    content_str = json.dumps(output, indent=2)

    # Write local copy
    try:
        os.makedirs(os.path.dirname(LOCAL_OUTPUT), exist_ok=True)
        with open(LOCAL_OUTPUT, 'w') as f:
            f.write(content_str)
        log.info('Wrote local copy: %s', LOCAL_OUTPUT)
    except Exception as e:
        log.warning('Local write failed: %s', e)

    # Push to GitHub
    push_to_github(GITHUB_OUTPUT_PATH, content_str)

    log.info('=== Done. persecution=%d conflict=%d disaster=%d bullets ===',
             len(persecution_bullets), len(conflict_bullets),
             len(disaster_bullets))


if __name__ == '__main__':
    main()
