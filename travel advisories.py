"""
travel_advisories.py
--------------------
Fetches US State Department Travel Advisories, normalizes them,
and commits travel_advisories.json to the GitHub repo so the
dashboard JS can load it cleanly via jsDelivr (no CORS issues).

Called from run_conflict_pipeline.py at the start of each run.
Also runnable standalone for testing:

    cd /opt/conflict-pipeline && set -a && source .env && set +a && \
      venv/bin/python travel_advisories.py
"""
import os
import re
import json
import base64
import logging
import requests
from datetime import datetime, timezone

log = logging.getLogger(__name__)

STATE_DEPT_URL = 'https://cadataapi.state.gov/api/TravelAdvisories'

# --- GitHub target (set via .env) --------------------------------------------
# Uses the SAME OWNER + REPO split as gwm_json_writer so one .env convention
# works everywhere. Tolerant of either form:
#   GITHUB_OWNER=InnovativeGeospatial  GITHUB_REPO=GWM      (current .env)
#   GITHUB_REPO=InnovativeGeospatial/GWM                     (full slug)
GITHUB_OWNER  = os.environ.get('GITHUB_OWNER', 'InnovativeGeospatial')
GITHUB_REPO   = os.environ.get('GITHUB_REPO',  'GWM')
GITHUB_BRANCH = os.environ.get('GITHUB_BRANCH', 'main')
GITHUB_PATH   = os.environ.get('GITHUB_PATH',   'travel_advisories.json')
GITHUB_TOKEN  = os.environ.get('GITHUB_TOKEN',  '')


def _repo_slug():
    """Return 'owner/repo'. If GITHUB_REPO already contains a slash, trust it;
    otherwise join GITHUB_OWNER + GITHUB_REPO."""
    repo = (GITHUB_REPO or '').strip()
    if '/' in repo:
        return repo
    return (GITHUB_OWNER or '').strip() + '/' + repo


LOCAL_CACHE   = '/opt/conflict-pipeline/data/travel_advisories.json'


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _strip_html(s):
    if not s:
        return ''
    s = re.sub(r'<[^>]+>', ' ', s)
    s = re.sub(r'&nbsp;', ' ', s)
    s = re.sub(r'&amp;',  '&', s)
    s = re.sub(r'&quot;', '"', s)
    s = re.sub(r'&#\d+;', '',  s)
    s = re.sub(r'\s+', ' ', s)
    return s.strip()

def _parse_level(title):
    """Extract 1-4 from strings like 'Bangladesh - Level 3: Reconsider Travel'."""
    if not title:
        return None
    m = re.search(r'Level\s+(\d)', title)
    if m:
        try:
            n = int(m.group(1))
            if 1 <= n <= 4:
                return n
        except ValueError:
            pass
    return None

def _parse_country(title):
    """Return the country name portion before ' - Level N...'."""
    if not title:
        return ''
    # Split on " - " or " – " (em dash safety), take the first chunk
    parts = re.split(r'\s[\-\u2013\u2014]\s', title, maxsplit=1)
    country = parts[0].strip()
    # Some titles end with "Travel Advisory" or similar suffix on the name
    country = re.sub(r'\s+Travel Advisory\s*$', '', country, flags=re.I)
    return country


# ---------------------------------------------------------------------------
# State Dept advisory link resolution
# ---------------------------------------------------------------------------
# State's advisory page URLs are irregular and CANNOT be reliably constructed
# from the country name — e.g. afghanistan-advisory.html, burma-travel-advisory.html,
# and bosinia-and-herzegovina-travel-advisory.html (State's own misspelling).
# So we use the link the feed itself provides (correct for the large majority),
# pin the verified-broken ones in the override map, and fall back to the
# advisories index page (never a 404) only when the feed gives us nothing.
#
# To add an override: open the country's advisory on travel.state.gov, copy the
# full URL from the address bar, and key it by the EXACT name the dashboard shows
# (i.e. what _parse_country returns for that country).
_ADVISORIES_INDEX = 'https://travel.state.gov/content/travel/en/traveladvisories/traveladvisories.html'

_ADVISORY_URL_OVERRIDES = {
    'Afghanistan': 'https://travel.state.gov/content/travel/en/traveladvisories/traveladvisories/afghanistan-advisory.html',
    'Burma (Myanmar)': 'https://travel.state.gov/content/travel/en/traveladvisories/traveladvisories/burma-travel-advisory.html',
    'Burma': 'https://travel.state.gov/content/travel/en/traveladvisories/traveladvisories/burma-travel-advisory.html',
    'Bosnia and Herzegovina': 'https://travel.state.gov/content/travel/en/traveladvisories/traveladvisories/bosinia-and-herzegovina-travel-advisory.html',
}

def _advisory_link(name, feed_link):
    ov = _ADVISORY_URL_OVERRIDES.get(name)
    if ov:
        return ov
    if feed_link:
        return feed_link
    return _ADVISORIES_INDEX


# ---------------------------------------------------------------------------
# Fetch + normalize
# ---------------------------------------------------------------------------
def fetch_advisories():
    """Pull the live feed and return a normalized list of dicts."""
    log.info('Fetching State Dept travel advisories')
    r = requests.get(
        STATE_DEPT_URL,
        headers={'User-Agent': 'GWM-ConflictPipeline/1.0'},
        timeout=45,
    )
    r.raise_for_status()
    raw = r.json()
    log.info('  received %d raw entries', len(raw))

    advisories = []
    seen_countries = set()

    for entry in raw:
        title   = entry.get('Title') or ''
        summary = entry.get('Summary') or entry.get('Description') or ''
        pub     = entry.get('PubDate') or entry.get('Published') or entry.get('Updated') or ''
        feed_link = entry.get('Link') or entry.get('Url') or ''

        level   = _parse_level(title)
        country = _parse_country(title)

        if not country or not level:
            continue

        key = country.lower()
        if key in seen_countries:
            # State Dept occasionally has duplicate rows; keep first
            continue
        seen_countries.add(key)

        clean_summary = _strip_html(summary)
        # Trim extremely long summaries to something the dashboard can show
        if len(clean_summary) > 800:
            clean_summary = clean_summary[:797].rsplit(' ', 1)[0] + '...'

        advisories.append({
            'country':  country,
            'level':    level,
            'summary':  clean_summary,
            'link':     _advisory_link(country, feed_link),
            'pub_date': pub,
        })

    # Stable sort: level desc, then country asc
    advisories.sort(key=lambda a: (-a['level'], a['country'].lower()))
    log.info('  normalized to %d country advisories', len(advisories))
    return advisories


def build_payload(advisories):
    """Wrap the advisory list with metadata."""
    counts = {1: 0, 2: 0, 3: 0, 4: 0}
    for a in advisories:
        counts[a['level']] = counts.get(a['level'], 0) + 1
    return {
        'source':     'US Department of State',
        'source_url': 'https://travel.state.gov/content/travel/en/traveladvisories/traveladvisories.html',
        'updated_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'total':      len(advisories),
        'counts':     counts,
        'advisories': advisories,
    }


# ---------------------------------------------------------------------------
# GitHub publish
# ---------------------------------------------------------------------------
def _github_get_sha(session):
    """Return the current file SHA on GitHub, or None if it doesn't exist yet."""
    url = f'https://api.github.com/repos/{_repo_slug()}/contents/{GITHUB_PATH}'
    r = session.get(url, params={'ref': GITHUB_BRANCH}, timeout=30)
    if r.status_code == 200:
        return r.json().get('sha')
    if r.status_code == 404:
        return None
    log.warning('GitHub GET returned %d: %s', r.status_code, r.text[:200])
    return None


def commit_to_github(payload):
    """Commit the JSON file to the configured GitHub repo. Returns True on success."""
    if not GITHUB_TOKEN:
        log.warning('GITHUB_TOKEN not set; skipping GitHub commit')
        return False

    body = json.dumps(payload, indent=2, ensure_ascii=False)
    encoded = base64.b64encode(body.encode('utf-8')).decode('ascii')

    session = requests.Session()
    session.headers.update({
        'Authorization': f'Bearer {GITHUB_TOKEN}',
        'Accept':        'application/vnd.github+json',
        'User-Agent':    'GWM-ConflictPipeline/1.0',
    })

    sha = _github_get_sha(session)

    url = f'https://api.github.com/repos/{_repo_slug()}/contents/{GITHUB_PATH}'
    commit_payload = {
        'message': f'Refresh travel advisories ({payload["total"]} countries, {payload["updated_at"]})',
        'content': encoded,
        'branch':  GITHUB_BRANCH,
    }
    if sha:
        commit_payload['sha'] = sha

    r = session.put(url, json=commit_payload, timeout=45)
    if r.status_code in (200, 201):
        log.info('Committed %s to %s@%s', GITHUB_PATH, _repo_slug(), GITHUB_BRANCH)
        return True
    log.error('GitHub commit failed %d: %s', r.status_code, r.text[:300])
    return False


def save_local_cache(payload):
    try:
        os.makedirs(os.path.dirname(LOCAL_CACHE), exist_ok=True)
        with open(LOCAL_CACHE, 'w', encoding='utf-8') as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        log.info('Wrote local cache: %s', LOCAL_CACHE)
    except Exception as e:
        log.warning('Local cache write failed: %s', e)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------
def refresh():
    """Fetch -> normalize -> commit. Returns payload dict (or None on failure)."""
    try:
        advisories = fetch_advisories()
    except Exception as e:
        log.error('Travel advisory fetch failed: %s', e)
        return None

    if not advisories:
        log.warning('No advisories parsed; skipping commit')
        return None

    payload = build_payload(advisories)
    save_local_cache(payload)
    commit_to_github(payload)
    return payload


# ---------------------------------------------------------------------------
# Standalone runner
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    )
    try:
        from dotenv import load_dotenv
        load_dotenv()
        # re-read module-level vars from env after load_dotenv
        GITHUB_OWNER  = os.environ.get('GITHUB_OWNER',  GITHUB_OWNER)
        GITHUB_REPO   = os.environ.get('GITHUB_REPO',   GITHUB_REPO)
        GITHUB_BRANCH = os.environ.get('GITHUB_BRANCH', GITHUB_BRANCH)
        GITHUB_PATH   = os.environ.get('GITHUB_PATH',   GITHUB_PATH)
        GITHUB_TOKEN  = os.environ.get('GITHUB_TOKEN',  GITHUB_TOKEN)
    except Exception:
        pass
    result = refresh()
    if result:
        print(f'OK  {result["total"]} advisories  '
              f'L4={result["counts"].get(4,0)}  '
              f'L3={result["counts"].get(3,0)}  '
              f'L2={result["counts"].get(2,0)}  '
              f'L1={result["counts"].get(1,0)}')
    else:
        print('FAILED')
