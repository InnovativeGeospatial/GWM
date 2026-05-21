#!/usr/bin/env python3
"""
Global Witness Monitor -- Alert Digest Script v1

Sends daily / weekly digest emails to subscribers based on the alert
preferences they set at PMPro checkout (region, specific countries,
alert types, frequency).

How it runs
-----------
1. Pulls subscribers from the WordPress REST endpoint
   /wp-json/gwm/v1/alert-subscribers (the companion Code Snippet).
2. Reads the three JSON feeds (persecution / conflict / disasters) from
   raw GitHub.
3. Filters each feed to events NEWER than this script's last successful
   run (timestamp stored in LAST_RUN_FILE).
4. For each subscriber, matches new events against their region +
   country + alert-type preferences.
5. Sends one digest email per matched subscriber via Gmail SMTP.

Frequency
---------
This script handles 'daily' and 'weekly'. Pass the mode as argv[1]:
    python gwm_alert_digest.py daily
    python gwm_alert_digest.py weekly
'instant' subscribers are treated as 'daily' for now (instant delivery
would fire from the pipelines themselves -- a later phase).

Two separate last-run files are kept so daily and weekly windows do not
interfere with each other.

Env (.env alongside this script)
--------------------------------
    GWM_API_SECRET        shared secret matching the WP endpoint
    WP_BASE_URL           e.g. https://globalwitnessmonitor.com
    SMTP_HOST             smtp.gmail.com
    SMTP_PORT             587
    SMTP_USER             info@globalwitnessmonitor.com
    SMTP_PASS             Gmail App Password
    SMTP_FROM             info@globalwitnessmonitor.com
    DIGEST_TEST_EMAIL     optional: if set, ALL mail goes here instead
                          of real subscribers (for safe testing)
"""

import os
import sys
import json
import html
import smtplib
import requests
from email.mime.text import MIMEText
from email.utils import formataddr
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))

GWM_API_SECRET    = os.getenv('GWM_API_SECRET', '')
WP_BASE_URL       = os.getenv('WP_BASE_URL', 'https://globalwitnessmonitor.com').rstrip('/')
SMTP_HOST         = os.getenv('SMTP_HOST', 'smtp.gmail.com')
SMTP_PORT         = int(os.getenv('SMTP_PORT', '587'))
SMTP_USER         = os.getenv('SMTP_USER', '')
SMTP_PASS         = os.getenv('SMTP_PASS', '')
SMTP_FROM         = os.getenv('SMTP_FROM', SMTP_USER)
DIGEST_TEST_EMAIL = os.getenv('DIGEST_TEST_EMAIL', '').strip()

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

FEEDS = {
    'persecution': 'https://raw.githubusercontent.com/InnovativeGeospatial/GWM/main/persecution.json',
    'conflict':    'https://raw.githubusercontent.com/InnovativeGeospatial/GWM/main/conflict.json',
    'disaster':    'https://raw.githubusercontent.com/InnovativeGeospatial/GWM/main/disasters.json',
}

# Public-facing label for each alert type (the checkout value -> display).
TYPE_LABEL = {
    'persecution': 'Persecution',
    'conflict':    'Conflict & Unrest',
    'disaster':    'Natural Hazards',
}

# The PMPro "Regions" field stores 7 values. They do NOT line up 1:1 with
# the conflict pipeline's REGIONS dict (which has africa, middle-east, asia,
# europe, americas, pacific). This alias map translates each PMPro region
# value into the set of conflict-pipeline region keys it covers.
#
#   asia-pacific   -> asia + pacific      (pipeline splits them)
#   north-america  -> americas            (pipeline does not split the
#   latin-america  -> americas             Americas, so both map to americas)
#   all            -> handled separately (matches every country)
PMPRO_REGION_ALIASES = {
    'africa':        ['africa'],
    'middle-east':   ['middle-east'],
    'asia-pacific':  ['asia', 'pacific'],
    'europe':        ['europe'],
    'north-america': ['americas'],
    'latin-america': ['americas'],
}

# Region -> set of country values. Filled by load_region_map(); the
# fallback below is used only if the conflict pipeline file is not found.
REGION_MAP_FALLBACK = {}


def log(msg):
    print('[' + datetime.now(timezone.utc).strftime('%H:%M:%S') + '] ' + msg)


# ---------------------------------------------------------------------------
# Last-run timestamp handling
# ---------------------------------------------------------------------------

def last_run_file(mode):
    return os.path.join(SCRIPT_DIR, 'last_digest_run_' + mode + '.txt')


def read_last_run(mode):
    """Return the datetime of the last successful run for this mode.

    If no marker exists, default to (now - 1 day) for daily, (now - 7 days)
    for weekly, so the first run sends a sensible recent window rather than
    the entire feed history."""
    path = last_run_file(mode)
    try:
        with open(path, 'r') as f:
            return datetime.fromisoformat(f.read().strip())
    except Exception:
        days = 7 if mode == 'weekly' else 1
        return datetime.now(timezone.utc) - timedelta(days=days)


def write_last_run(mode, when):
    with open(last_run_file(mode), 'w') as f:
        f.write(when.isoformat())


# ---------------------------------------------------------------------------
# Region map -- reuse the conflict pipeline's REGIONS dict as source of truth
# ---------------------------------------------------------------------------

def load_region_map():
    """Build {region_value: set(country_values)} from the conflict pipeline.

    The conflict pipeline's REGIONS dict is the canonical region->country
    grouping. Country names are lowercased to match feed 'country' values."""
    import ast
    candidates = [
        '/opt/conflict-pipeline/run_conflict_pipeline.py',
        os.path.join(SCRIPT_DIR, 'run_conflict_pipeline.py'),
    ]
    for path in candidates:
        if not os.path.exists(path):
            continue
        try:
            src = open(path).read()
            for n in ast.parse(src).body:
                if (isinstance(n, ast.Assign)
                        and getattr(n.targets[0], 'id', '') == 'REGIONS'):
                    raw = ast.literal_eval(n.value)
                    return {
                        region.lower(): set(c.lower() for c in countries)
                        for region, countries in raw.items()
                    }
        except Exception as e:
            log('Could not parse REGIONS from ' + path + ': ' + str(e))
    log('WARNING: conflict pipeline REGIONS not found - region matching '
        'will use the fallback map (may be empty).')
    return dict(REGION_MAP_FALLBACK)


# ---------------------------------------------------------------------------
# Subscribers + feeds
# ---------------------------------------------------------------------------

def fetch_subscribers():
    url = WP_BASE_URL + '/wp-json/gwm/v1/alert-subscribers'
    r = requests.get(url, params={'key': GWM_API_SECRET}, timeout=30)
    if r.status_code != 200:
        raise RuntimeError('subscriber endpoint HTTP ' + str(r.status_code)
                            + ': ' + r.text[:200])
    data = r.json()
    return data.get('subscribers', [])


def fetch_feed(name):
    url = FEEDS[name]
    try:
        r = requests.get(url, timeout=30, headers={'Cache-Control': 'no-cache'})
        if r.status_code != 200:
            log('feed ' + name + ' HTTP ' + str(r.status_code))
            return []
        data = r.json()
        events = data.get('events', [])
        for e in events:
            e['_feed'] = name
        return events
    except Exception as e:
        log('feed ' + name + ' error: ' + str(e))
        return []


def parse_event_date(event):
    s = str(event.get('date', '')).strip()
    if not s:
        return None
    if not s.endswith('Z') and '+' not in s[10:]:
        s = s + '+00:00'
    s = s.replace('Z', '+00:00')
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------

def subscriber_country_set(sub, region_map):
    """All country values this subscriber should be alerted for:
    their explicit countries plus everything in their chosen regions.

    A PMPro region value 'all' => everything (returns None).
    Other PMPro region values are translated through PMPRO_REGION_ALIASES
    into conflict-pipeline region keys, then resolved to countries."""
    countries = set(sub.get('countries', []))
    regions = sub.get('regions', [])
    for region in regions:
        if region == 'all' or 'all' in region:
            return None  # None == match every country
        pipeline_regions = PMPRO_REGION_ALIASES.get(region, [region])
        for pr in pipeline_regions:
            if pr in region_map:
                countries |= region_map[pr]
    return countries


def match_events(sub, events_by_type, region_map):
    """Return the list of events this subscriber should receive."""
    wanted_types = set(sub.get('types', []))
    if not wanted_types:
        return []
    country_set = subscriber_country_set(sub, region_map)
    matched = []
    for etype, events in events_by_type.items():
        if etype not in wanted_types:
            continue
        for e in events:
            ec = str(e.get('country', '')).lower().strip()
            if country_set is None or ec in country_set:
                matched.append(e)
    matched.sort(key=lambda e: str(e.get('date', '')), reverse=True)
    return matched


# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------

def build_email_html(sub, matched, mode):
    name = sub.get('name') or 'Friend'
    period = 'this week' if mode == 'weekly' else 'today'
    by_type = {}
    for e in matched:
        by_type.setdefault(e.get('_feed', 'persecution'), []).append(e)

    parts = []
    parts.append(
        '<div style="font-family:Georgia,serif;max-width:600px;margin:0 auto;'
        'color:#1a1a1a;">'
    )
    parts.append(
        '<h2 style="color:#7a1f1f;border-bottom:2px solid #7a1f1f;'
        'padding-bottom:6px;">Global Witness Monitor &mdash; Alert Digest</h2>'
    )
    parts.append(
        '<p>Dear ' + html.escape(name) + ',</p>'
        '<p>Here are the developments ' + period + ' from the regions and '
        'countries you follow.</p>'
    )

    for etype in ('persecution', 'conflict', 'disaster'):
        evs = by_type.get(etype)
        if not evs:
            continue
        parts.append(
            '<h3 style="color:#7a1f1f;margin-top:24px;">'
            + TYPE_LABEL.get(etype, etype) + '</h3>'
        )
        for e in evs:
            title = html.escape(str(e.get('title', 'Untitled')))
            country = html.escape(str(e.get('country', '')).title())
            link = html.escape(str(e.get('wp_link', '#')))
            body = str(e.get('body', ''))
            # plain-text snippet from the HTML body
            import re
            snippet = re.sub(r'<[^>]+>', ' ', body)
            snippet = re.sub(r'\s+', ' ', snippet).strip()
            if len(snippet) > 220:
                snippet = snippet[:220] + '...'
            parts.append(
                '<div style="margin:14px 0;padding:12px;'
                'background:#f6f3ee;border-left:3px solid #7a1f1f;">'
                '<div style="font-size:11px;text-transform:uppercase;'
                'letter-spacing:0.08em;color:#888;">' + country + '</div>'
                '<div style="font-weight:bold;font-size:15px;margin:4px 0;">'
                + title + '</div>'
                '<div style="font-size:13px;color:#444;">'
                + html.escape(snippet) + '</div>'
                '<a href="' + link + '" style="font-size:12px;color:#7a1f1f;">'
                'Read full report &rarr;</a>'
                '</div>'
            )

    parts.append(
        '<p style="font-size:12px;color:#888;margin-top:28px;'
        'border-top:1px solid #ddd;padding-top:12px;">'
        'You receive these alerts because you subscribed at '
        'globalwitnessmonitor.com. To change your regions, countries, alert '
        'types, or frequency, update your account preferences.'
        '</p>'
    )
    parts.append('</div>')
    return ''.join(parts)


def send_email(to_email, subject, html_body):
    msg = MIMEText(html_body, 'html', 'utf-8')
    msg['Subject'] = subject
    msg['From'] = formataddr(('Global Witness Monitor', SMTP_FROM))
    msg['To'] = to_email
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.sendmail(SMTP_FROM, [to_email], msg.as_string())


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run(mode):
    log('=== GWM Alert Digest -- mode=' + mode + ' ===')
    if mode not in ('daily', 'weekly'):
        log('Unknown mode. Use: daily | weekly')
        return

    started_at = datetime.now(timezone.utc)
    since = read_last_run(mode)
    log('Sending events newer than ' + since.isoformat())

    region_map = load_region_map()
    log('Region map loaded: ' + str(len(region_map)) + ' regions')

    # Pull and window the feeds
    events_by_type = {}
    total_new = 0
    for name in FEEDS:
        events = fetch_feed(name)
        fresh = []
        for e in events:
            d = parse_event_date(e)
            if d and d > since:
                fresh.append(e)
        events_by_type[name] = fresh
        total_new += len(fresh)
        log('feed ' + name + ': ' + str(len(fresh)) + ' new of '
            + str(len(events)))

    if total_new == 0:
        log('No new events since last run. Nothing to send.')
        write_last_run(mode, started_at)
        log('=== Done (no mail) ===')
        return

    subscribers = fetch_subscribers()
    log('Subscribers fetched: ' + str(len(subscribers)))

    # 'instant' subscribers fold into the daily run for now
    eligible_freqs = {'daily', 'instant'} if mode == 'daily' else {'weekly'}

    sent = 0
    skipped_no_match = 0
    skipped_freq = 0
    errors = 0

    for sub in subscribers:
        freq = sub.get('frequency', 'daily')
        if freq not in eligible_freqs:
            skipped_freq += 1
            continue
        matched = match_events(sub, events_by_type, region_map)
        if not matched:
            skipped_no_match += 1
            continue

        to_email = DIGEST_TEST_EMAIL if DIGEST_TEST_EMAIL else sub.get('email')
        if not to_email:
            continue

        n = len(matched)
        subject = ('Global Witness Monitor: ' + str(n) + ' new '
                   + ('alert' if n == 1 else 'alerts'))
        body = build_email_html(sub, matched, mode)
        try:
            send_email(to_email, subject, body)
            sent += 1
            log('sent -> ' + to_email + ' (' + str(n) + ' events)'
                + (' [TEST REDIRECT]' if DIGEST_TEST_EMAIL else ''))
        except Exception as e:
            errors += 1
            log('SEND FAILED -> ' + to_email + ': ' + str(e))

    # Only advance the marker if we did not error out wholesale
    write_last_run(mode, started_at)

    log('=== Done. sent=' + str(sent)
        + ' no_match=' + str(skipped_no_match)
        + ' wrong_freq=' + str(skipped_freq)
        + ' errors=' + str(errors) + ' ===')


if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else 'daily'
    run(mode)
