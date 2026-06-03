"""
travel_advisories.py
--------------------
Fetches US State Department Travel Advisories, normalizes them, and commits
travel_advisories.json to the GitHub repo for the dashboards to read.

Called from run_conflict_pipeline.py at the start of each run. Also standalone:

    cd /opt/conflict-pipeline && set -a && source .env && set +a && \
      venv/bin/python travel_advisories.py

LINK RESOLUTION (v4 — ISO-3 scheme):
    State retired the old /traveladvisories/traveladvisories/<slug>-travel-advisory.html
    base; those URLs now return soft-404s (HTTP 200 with a "Page Not Found" body),
    which fooled the old status-code check. State's live scheme is:
        https://travel.state.gov/en/international-travel/travel-advisories/destination.<iso3>.html
    (e.g. Afghanistan = destination.afg.html). This module builds every link
    deterministically from a name->ISO-3 map (no network verification, so the
    droplet is never throttled and no stale link-cache can resurface dead URLs).
    Names with no sovereign State page (territories, regional aggregates) fall
    back to the advisories index — never a 404.
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

GITHUB_OWNER  = os.environ.get('GITHUB_OWNER', 'InnovativeGeospatial')
GITHUB_REPO   = os.environ.get('GITHUB_REPO',  'GWM')
GITHUB_BRANCH = os.environ.get('GITHUB_BRANCH', 'main')
GITHUB_PATH   = os.environ.get('GITHUB_PATH',   'travel_advisories.json')
GITHUB_TOKEN  = os.environ.get('GITHUB_TOKEN',  '')

LOCAL_CACHE   = '/opt/conflict-pipeline/data/travel_advisories.json'


def _repo_slug():
    repo = (GITHUB_REPO or '').strip()
    if '/' in repo:
        return repo
    return (GITHUB_OWNER or '').strip() + '/' + repo


# ---------------------------------------------------------------------------
# State advisory link resolution (ISO-3 destination scheme)
# ---------------------------------------------------------------------------
_NEW_BASE = 'https://travel.state.gov/en/international-travel/travel-advisories/'
_ADVISORIES_INDEX = 'https://travel.state.gov/content/travel/en/traveladvisories/traveladvisories.html'

# Keyed by the EXACT name _parse_country() returns (i.e. the feed 'country').
# To add/fix one: find its destination.<iso3>.html on travel.state.gov and add
# the name -> ISO-3 pair here.
_ISO3 = {
    "Afghanistan": "AFG", "Albania": "ALB", "Algeria": "DZA", "Andorra": "AND",
    "Angola": "AGO", "Anguilla": "AIA", "Antigua and Barbuda": "ATG", "Argentina": "ARG",
    "Armenia": "ARM", "Aruba": "ABW", "Australia": "AUS", "Austria": "AUT",
    "Azerbaijan": "AZE", "Bahrain": "BHR", "Bangladesh": "BGD", "Barbados": "BRB",
    "Belarus": "BLR", "Belgium": "BEL", "Benin": "BEN", "Bermuda": "BMU",
    "Bhutan": "BTN", "Bolivia": "BOL", "Bosnia and Herzegovina": "BIH", "Botswana": "BWA",
    "Brazil": "BRA", "British Virgin Islands": "VGB", "Brunei": "BRN", "Bulgaria": "BGR",
    "Burkina Faso": "BFA", "Burma": "MMR", "Burundi": "BDI", "Cabo Verde": "CPV",
    "Cambodia": "KHM", "Cameroon": "CMR", "Canada": "CAN", "Cayman Islands": "CYM",
    "Central African Republic": "CAF", "Chad": "TCD", "Chile": "CHL", "Colombia": "COL",
    "Comoros": "COM", "Costa Rica": "CRI", "Cote d Ivoire": "CIV", "Croatia": "HRV",
    "Cuba": "CUB", "Curaçao": "CUW", "Cyprus": "CYP", "Czechia": "CZE",
    "Democratic Republic of the Congo": "COD", "Djibouti": "DJI", "Dominica": "DMA", "Dominican Republic": "DOM",
    "Ecuador": "ECU", "Egypt": "EGY", "El Salvador": "SLV", "Equatorial Guinea": "GNQ",
    "Eritrea": "ERI", "Estonia": "EST", "Eswatini": "SWZ", "Ethiopia": "ETH",
    "Federated States of Micronesia": "FSM", "Fiji": "FJI", "Finland": "FIN", "France": "FRA",
    "French Polynesia": "PYF", "Gabon": "GAB", "Georgia": "GEO", "Germany": "DEU",
    "Ghana": "GHA", "Greece": "GRC", "Greenland": "GRL", "Grenada": "GRD",
    "Guatemala": "GTM", "Guinea": "GIN", "Guinea-Bissau": "GNB", "Guyana": "GUY",
    "Haiti": "HTI", "Honduras": "HND", "Hong Kong": "HKG", "Hungary": "HUN",
    "Iceland": "ISL", "India": "IND", "Indonesia": "IDN", "Iran": "IRN",
    "Iraq": "IRQ", "Ireland": "IRL", "Italy": "ITA", "Jamaica": "JAM",
    "Japan": "JPN", "Jordan": "JOR", "Kazakhstan": "KAZ", "Kenya": "KEN",
    "Kingdom of Denmark": "DNK", "Kiribati": "KIR", "Kosovo": "XKS", "Kuwait": "KWT",
    "Laos": "LAO", "Latvia": "LVA", "Lebanon": "LBN", "Lesotho": "LSO",
    "Liberia": "LBR", "Libya": "LBY", "Liechtenstein": "LIE", "Lithuania": "LTU",
    "Luxembourg": "LUX", "Macau": "MAC", "Madagascar": "MDG", "Malawi": "MWI",
    "Malaysia": "MYS", "Maldives": "MDV", "Mali": "MLI", "Malta": "MLT",
    "Marshall Islands": "MHL", "Mauritania": "MRT", "Mauritius": "MUS", "Mexico": "MEX",
    "Moldova": "MDA", "Mongolia": "MNG", "Montenegro": "MNE", "Montserrat": "MSR",
    "Morocco": "MAR", "Mozambique": "MOZ", "Namibia": "NAM", "Nauru": "NRU",
    "Nepal": "NPL", "Netherlands": "NLD", "New Caledonia": "NCL", "New Zealand": "NZL",
    "Nicaragua": "NIC", "Niger": "NER", "Nigeria": "NGA", "North Korea": "PRK",
    "North Macedonia": "MKD", "Norway": "NOR", "Oman": "OMN", "Pakistan": "PAK",
    "Palau": "PLW", "Panama": "PAN", "Papua New Guinea": "PNG", "Paraguay": "PRY",
    "Peru": "PER", "Philippines": "PHL", "Poland": "POL", "Portugal": "PRT",
    "Qatar": "QAT", "Republic of the Congo": "COG", "Romania": "ROU", "Russia": "RUS",
    "Rwanda": "RWA", "Saint Kitts and Nevis": "KNA", "Saint Lucia": "LCA", "Saint Vincent and the Grenadines": "VCT",
    "Samoa": "WSM", "Sao Tome and Principe": "STP", "Saudi Arabia": "SAU", "Senegal": "SEN",
    "Serbia": "SRB", "Seychelles": "SYC", "Sierra Leone": "SLE", "Singapore": "SGP",
    "Sint Maarten": "SXM", "Slovakia": "SVK", "Slovenia": "SVN", "Solomon Islands": "SLB",
    "Somalia": "SOM", "South Africa": "ZAF", "South Korea": "KOR", "South Sudan": "SSD",
    "Spain": "ESP", "Sri Lanka": "LKA", "Sudan": "SDN", "Suriname": "SUR",
    "Sweden": "SWE", "Switzerland": "CHE", "Syria": "SYR", "Taiwan": "TWN",
    "Tajikistan": "TJK", "Tanzania": "TZA", "Thailand": "THA", "The Bahamas": "BHS",
    "The Gambia": "GMB", "The Kyrgyz Republic": "KGZ", "Timor-Leste": "TLS", "Togo": "TGO",
    "Tonga": "TON", "Trinidad and Tobago": "TTO", "Tunisia": "TUN", "Turkey": "TUR",
    "Turkmenistan": "TKM", "Turks and Caicos Islands": "TCA", "Tuvalu": "TUV", "Uganda": "UGA",
    "Ukraine": "UKR", "United Arab Emirates": "ARE", "United Kingdom": "GBR", "Uruguay": "URY",
    "Uzbekistan": "UZB", "Vanuatu": "VUT", "Venezuela": "VEN", "Vietnam": "VNM",
    "Yemen": "YEM", "Zambia": "ZMB", "Zimbabwe": "ZWE", "Mainland China, Hong Kong & Macau": "CHN",
}

def _advisory_link(name):
    iso = _ISO3.get(name)
    if iso:
        return _NEW_BASE + 'destination.' + iso.lower() + '.html'
    return _ADVISORIES_INDEX


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
    if not title:
        return ''
    parts = re.split(r'\s[\-\u2013\u2014]\s', title, maxsplit=1)
    country = parts[0].strip()
    country = re.sub(r'\s+Travel Advisory\s*$', '', country, flags=re.I)
    return country


# ---------------------------------------------------------------------------
# Fetch + normalize
# ---------------------------------------------------------------------------
def fetch_advisories():
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

        level   = _parse_level(title)
        country = _parse_country(title)

        if not country or not level:
            continue

        key = country.lower()
        if key in seen_countries:
            continue
        seen_countries.add(key)

        clean_summary = _strip_html(summary)
        if len(clean_summary) > 800:
            clean_summary = clean_summary[:797].rsplit(' ', 1)[0] + '...'

        advisories.append({
            'country':  country,
            'level':    level,
            'summary':  clean_summary,
            'link':     _advisory_link(country),
            'pub_date': pub,
        })

    advisories.sort(key=lambda a: (-a['level'], a['country'].lower()))
    log.info('  normalized to %d country advisories', len(advisories))
    return advisories


def build_payload(advisories):
    counts = {1: 0, 2: 0, 3: 0, 4: 0}
    for a in advisories:
        counts[a['level']] = counts.get(a['level'], 0) + 1
    return {
        'source':     'US Department of State',
        'source_url': _ADVISORIES_INDEX,
        'updated_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'total':      len(advisories),
        'counts':     counts,
        'advisories': advisories,
    }


# ---------------------------------------------------------------------------
# GitHub publish
# ---------------------------------------------------------------------------
def _github_get_sha(session):
    url = 'https://api.github.com/repos/' + _repo_slug() + '/contents/' + GITHUB_PATH
    r = session.get(url, params={'ref': GITHUB_BRANCH}, timeout=30)
    if r.status_code == 200:
        return r.json().get('sha')
    if r.status_code == 404:
        return None
    log.warning('GitHub GET returned %d: %s', r.status_code, r.text[:200])
    return None


def commit_to_github(payload):
    if not GITHUB_TOKEN:
        log.warning('GITHUB_TOKEN not set; skipping GitHub commit')
        return False

    body = json.dumps(payload, indent=2, ensure_ascii=False)
    encoded = base64.b64encode(body.encode('utf-8')).decode('ascii')

    session = requests.Session()
    session.headers.update({
        'Authorization': 'Bearer ' + GITHUB_TOKEN,
        'Accept':        'application/vnd.github+json',
        'User-Agent':    'GWM-ConflictPipeline/1.0',
    })

    sha = _github_get_sha(session)
    url = 'https://api.github.com/repos/' + _repo_slug() + '/contents/' + GITHUB_PATH
    commit_payload = {
        'message': 'Refresh travel advisories (' + str(payload['total']) +
                   ' countries, ' + payload['updated_at'] + ')',
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


def refresh():
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


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    )
    try:
        from dotenv import load_dotenv
        load_dotenv()
        GITHUB_OWNER  = os.environ.get('GITHUB_OWNER',  GITHUB_OWNER)
        GITHUB_REPO   = os.environ.get('GITHUB_REPO',   GITHUB_REPO)
        GITHUB_BRANCH = os.environ.get('GITHUB_BRANCH', GITHUB_BRANCH)
        GITHUB_PATH   = os.environ.get('GITHUB_PATH',   GITHUB_PATH)
        GITHUB_TOKEN  = os.environ.get('GITHUB_TOKEN',  GITHUB_TOKEN)
    except Exception:
        pass
    result = refresh()
    if result:
        print('OK  ' + str(result['total']) + ' advisories  '
              'L4=' + str(result['counts'].get(4,0)) + '  '
              'L3=' + str(result['counts'].get(3,0)) + '  '
              'L2=' + str(result['counts'].get(2,0)) + '  '
              'L1=' + str(result['counts'].get(1,0)))
    else:
        print('FAILED')
