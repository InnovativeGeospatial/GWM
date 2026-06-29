#!/usr/bin/env python3
"""
Global Witness Monitor -- Conflict & Unrest Pipeline v6

Changes from v5:
- PRAY: header field. Claude now returns a one-line prayer prompt in the
  header block. The pipeline appends it as a styled paragraph at the end
  of the article body: <p class="gwm-prayer-line"><strong>Pray:</strong>...</p>
- format_body_for_wordpress() now accepts an optional prayer arg.
- JSON feed includes 'prayer' field per event.
- jsDelivr purge after JSON finalize.
- Everything else (dedup, geocoding, title format, GDELT) unchanged.

v6.1 (same-location rollup):
- If a new event geocodes to the SAME place as a conflict post published in
  the last MERGE_WINDOW_HOURS (coords rounded to COORD_MATCH_PRECISION
  decimals, ~1.1 km), the new event is MERGED into that existing post
  instead of creating a separate post. Posts immediately; nothing delayed.
  "Same place" = same coordinates, so Gaza-with-Gaza merges but a different
  city in the same country stays separate.
- The merge updates BOTH layers with the SAME wp_id: the WordPress post body
  (a dated "Update --" section is appended) AND the JSON feed event (the
  writer overwrites by wp_id). So WordPress, conflict.json, and the archive
  all hold ONE record per location instead of several.
- Events with LOCATION: UNKNOWN never geocode, so they never merge -- they
  post individually, as before.

v6.2 (quality fixes - 2026-06):
- RELEVANCE GATE: events Claude classifies as EVENT_TYPE "Other" are no longer
  published to the conflict feed (Other = not a conflict category). Obvious
  natural-disaster / accident items are also dropped before generation so they
  do not burn API calls (they belong to the disaster pipeline).
- IDENTITY DEDUP: merge is keyed on (primary country + event_type) within the
  window instead of exact coordinates. This collapses the same escalation that
  arrives under different place labels ("Iran" / "Tehran" / "Beirut") and the
  null-coordinate duplicates that the coord-only merge used to miss entirely.
- GEOCODE GUARD: the geocoder now queries "<location>, <country>" so an
  ambiguous place name no longer resolves to a same-named US town. Mismatches
  are rejected and the event posts without a map pin rather than a wrong one.
"""

import re
import os
import sys
import json
import time
import hashlib
import logging
import argparse
import requests
import feedparser
import travel_advisories
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
import anthropic
import html

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import gwm_json_writer
    JSON_WRITER_AVAILABLE = True
except ImportError:
    JSON_WRITER_AVAILABLE = False

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
log = logging.getLogger(__name__)

if not JSON_WRITER_AVAILABLE:
    log.warning("gwm_json_writer.py not found in pipeline directory - "
                "JSON feeds will not be updated this run")

load_dotenv()

WP_URL          = os.environ['WP_URL'].rstrip('/')
WP_USER         = os.environ['WP_USER']
WP_APP_PASSWORD = os.environ['WP_APP_PASSWORD']
ANTHROPIC_KEY   = os.environ['ANTHROPIC_API_KEY']
WP_CATEGORY_ID  = int(os.environ.get('WP_CATEGORY_ID', 8))
MAPBOX_TOKEN    = os.environ.get('MAPBOX_TOKEN', '')

SEEN_FILE    = '/opt/conflict-pipeline/data/seen_articles.json'
MAX_ARTICLES = 120
FEED_NAME    = "conflict"

# -- SAME-LOCATION ROLLUP --
# Merge events that geocode to the same place within this many hours into one
# post. "Same place" = coords rounded to COORD_MATCH_PRECISION decimals.
COORD_MATCH_PRECISION = 2   # ~1.1 km
MERGE_WINDOW_HOURS    = 24

# -- v6.2 IDENTITY DEDUP / RELEVANCE --
# A post is treated as the same event as a recent one when it shares the same
# primary country AND event_type within MERGE_WINDOW_HOURS and either side is
# missing coords, the coords are within MERGE_COORD_DEG, or the titles overlap
# at least MERGE_TITLE_SIM.
MERGE_COORD_DEG = 0.75      # ~80 km (sum of abs lat/lng deltas)
MERGE_TITLE_SIM = 0.50
# Per-event suppression list (written by prune_feed.py). Blocks a SPECIFIC
# deleted event from re-publishing for a bounded window -- not a permanent
# place/topic block. Lives beside this script on the droplet.
SUPPRESS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "suppressed_conflict.json")
SUPPRESS_DEFAULT_WINDOW_DAYS = 21
# Only these event types belong in the conflict feed. "Other" is dropped.
ALLOWED_EVENT_TYPES = {
    "Armed Conflict", "Civil Unrest", "Coup or Crisis", "Displacement",
}

REGIONS = {
    'middle-east': [
        'Bahrain', 'Cyprus', 'Iran', 'Iraq', 'Israel', 'Jordan',
        'Kuwait', 'Lebanon', 'Oman', 'Palestine', 'Qatar', 'Saudi Arabia',
        'Syria', 'Turkey', 'United Arab Emirates', 'Yemen',
    ],
    'africa': [
        'Algeria', 'Angola', 'Benin', 'Botswana', 'Burkina Faso', 'Burundi',
        'Cameroon', 'Cape Verde', 'Central African Republic', 'Chad', 'Comoros', 'Congo',
        'DR Congo', 'Djibouti', 'Egypt', 'Equatorial Guinea', 'Eritrea', 'Eswatini',
        'Ethiopia', 'Gabon', 'Gambia', 'Ghana', 'Guinea', 'Guinea-Bissau',
        'Ivory Coast', 'Kenya', 'Lesotho', 'Liberia', 'Libya', 'Madagascar',
        'Malawi', 'Mali', 'Mauritania', 'Mauritius', 'Morocco', 'Mozambique',
        'Namibia', 'Niger', 'Nigeria', 'Rwanda', 'Sao Tome and Principe', 'Senegal',
        'Sierra Leone', 'Somalia', 'South Africa', 'South Sudan', 'Sudan', 'Tanzania',
        'Togo', 'Tunisia', 'Uganda', 'Zambia', 'Zimbabwe',
    ],
    'asia': [
        'Afghanistan', 'Bangladesh', 'Bhutan', 'Brunei', 'Cambodia', 'China',
        'India', 'Indonesia', 'Japan', 'Kazakhstan', 'Kyrgyzstan', 'Laos',
        'Malaysia', 'Maldives', 'Mongolia', 'Myanmar', 'Nepal', 'North Korea',
        'Pakistan', 'Philippines', 'Singapore', 'South Korea', 'Sri Lanka', 'Taiwan',
        'Tajikistan', 'Thailand', 'Timor-Leste', 'Turkmenistan', 'Uzbekistan', 'Vietnam',
    ],
    'europe': [
        'Albania', 'Andorra', 'Armenia', 'Austria', 'Azerbaijan', 'Belarus',
        'Belgium', 'Bosnia', 'Bulgaria', 'Croatia', 'Czech Republic', 'Denmark',
        'Estonia', 'Finland', 'France', 'Georgia', 'Germany', 'Greece',
        'Hungary', 'Iceland', 'Ireland', 'Italy', 'Kosovo', 'Latvia',
        'Liechtenstein', 'Lithuania', 'Luxembourg', 'Malta', 'Moldova', 'Monaco',
        'Montenegro', 'Netherlands', 'North Macedonia', 'Norway', 'Poland', 'Portugal',
        'Romania', 'Russia', 'San Marino', 'Serbia', 'Slovakia', 'Slovenia',
        'Spain', 'Sweden', 'Switzerland', 'Ukraine', 'United Kingdom', 'Vatican City',
    ],
    'americas': [
        'Antigua and Barbuda', 'Argentina', 'Barbados', 'Belize', 'Bolivia', 'Brazil',
        'Canada', 'Chile', 'Colombia', 'Costa Rica', 'Cuba', 'Dominica',
        'Dominican Republic', 'Ecuador', 'El Salvador', 'Grenada', 'Guatemala', 'Guyana',
        'Haiti', 'Honduras', 'Jamaica', 'Mexico', 'Nicaragua', 'Panama',
        'Paraguay', 'Peru', 'Saint Kitts and Nevis', 'Saint Lucia', 'Saint Vincent and the Grenadines', 'Suriname',
        'Trinidad and Tobago', 'United States', 'Uruguay', 'Venezuela',
    ],
    'pacific': [
        'Australia', 'Fiji', 'Kiribati', 'Marshall Islands', 'Micronesia', 'Nauru',
        'New Zealand', 'Palau', 'Papua New Guinea', 'Samoa', 'Solomon Islands', 'Tonga',
        'Tuvalu', 'Vanuatu',
    ],
}

ALL_COUNTRIES = []
for region_countries in REGIONS.values():
    ALL_COUNTRIES.extend(region_countries)
ALL_COUNTRIES = list(set(ALL_COUNTRIES))

def _gnews(query, freshness="when:3d"):
    """Build a Google News RSS search-feed URL for a targeted query.
    Google News aggregates thousands of outlets (incl. regional/local ones)
    that the curated feeds below miss -- this is what fills geographic gaps
    like Mexico/cartel coverage. Links are news.google.com redirect shells;
    fetch_article_body() handles resolving or falling back to the summary."""
    return ("https://news.google.com/rss/search?q="
            + requests.utils.quote(query + " " + freshness)
            + "&hl=en-US&gl=US&ceid=US:en")

# Targeted Google News queries that fill coverage gaps (organized crime +
# regional conflict). Edit/extend freely -- one line per query.
GOOGLE_NEWS_QUERIES = [
    "Mexico cartel violence OR kidnapping OR gunmen",
    "Haiti gang violence OR kidnapping",
    "Colombia OR Ecuador armed group OR massacre OR violence",
    "Nigeria attack OR kidnapping OR bandits OR Boko Haram",
    "Sahel OR Burkina Faso OR Mali OR Niger attack OR militants",
    "DR Congo M23 OR rebels OR massacre OR clashes",
    "Sudan RSF OR fighting OR airstrike OR El Fasher",
    "Ethiopia OR Somalia al-Shabaab OR clashes OR drone",
    "Myanmar military OR airstrike OR clashes",
    "Syria OR Iraq airstrike OR clashes OR militants",
    "massacre OR coup OR airstrike OR ambush",
    "cartel OR gang massacre OR kidnapping OR shootout",
]

RSS_FEEDS = [
    'https://reliefweb.int/updates/rss.xml',
    'https://www.crisisgroup.org/rss.xml',
    'https://www.aljazeera.com/xml/rss/all.xml',
    'https://www.hrw.org/rss/world/all',
    'https://news.un.org/feed/subscribe/en/news/all/rss.xml',
    'https://feeds.apnews.com/rss/apf-worldnews',
    'https://rss.dw.com/rdf/rss-en-world',
    'https://feeds.bbci.co.uk/news/world/rss.xml',
    'https://www.france24.com/en/rss',
] + [_gnews(q) for q in GOOGLE_NEWS_QUERIES]

CONFLICT_TERMS = [
    'armed conflict', 'civil war', 'war', 'combat', 'fighting',
    'airstrike', 'air strike', 'bombing', 'shelling', 'militia',
    'insurgency', 'insurgent', 'rebel', 'offensive', 'casualties',
    'coup', 'overthrow', 'junta', 'crackdown', 'detention',
    'protest', 'unrest', 'uprising', 'riot', 'demonstration',
    'displaced', 'displacement', 'refugee', 'flee', 'evacuation',
    'humanitarian crisis', 'ceasefire', 'siege', 'blockade',
    'political prisoner', 'opposition leader',
    'attack', 'killed', 'deaths', 'massacre', 'violence',
    'terrorist', 'extremist', 'jihadist', 'al-shabaab', 'isis',
    'houthi', 'rsf', 'm23', 'boko haram', 'iswap',
    'explosion', 'bomb', 'strikes', 'troops', 'military operation',
    'cartel', 'cartels', 'gang', 'gangs', 'gang violence', 'narco',
    'organized crime', 'drug war', 'kidnapping', 'kidnap', 'abduction',
    'gunmen', 'gunman', 'shootout', 'gunfight', 'extortion', 'ambush',
    'armed group', 'armed groups', 'paramilitary', 'vigilante', 'bandit',
    'bandits', 'militant', 'militants', 'assassination', 'hostage',
    'disappearance', 'mass grave', 'raid', 'lynching',
]

EVENT_SIGNALS = [
    'killed', 'dies', 'died', 'dead', 'death', 'deaths',
    'attack', 'attacked', 'attacks',
    'strike', 'strikes', 'struck',
    'bomb', 'bombed', 'bombing',
    'shoot', 'shot', 'shooting',
    'explode', 'exploded', 'explosion',
    'clash', 'clashed', 'clashes',
    'flee', 'fled', 'fleeing',
    'arrest', 'arrested', 'arrests', 'detained', 'detention',
    'protest', 'protested', 'protesters', 'protests',
    'riot', 'riots', 'rioting',
    'seize', 'seized', 'capture', 'captured',
    'invade', 'invaded', 'invasion',
    'launch', 'launched', 'launches',
    'deploy', 'deployed', 'deployment',
    'evacuate', 'evacuated', 'evacuation',
    'displace', 'displaced', 'displacement',
    'coup', 'overthrow', 'topple', 'toppled',
    'ceasefire', 'truce',
    'collapse', 'collapsed',
    'orders', 'ordered',
    'convict', 'convicted', 'sentence', 'sentenced',
    'execute', 'executed', 'execution',
    'kidnap', 'kidnapped', 'kidnapping', 'abduct', 'abducted',
    'ambush', 'ambushed', 'raid', 'raided', 'storm', 'stormed',
    'assassinate', 'assassinated', 'behead', 'beheaded',
    'massacre', 'massacred', 'gunned', 'hostage',
    'disappear', 'disappeared', 'wounded', 'injured', 'torched',
]

EXCLUDE_PATTERNS = [
    'what is a', 'what are', 'how does', 'how would', 'how to',
    'explained', 'explainer', 'analysis', 'opinion',
    'would pick up if', 'would call', 'would talk',
    'could come', 'could happen', 'could lead',
    'what comes next', 'what to expect', 'what to know',
    'five things', 'three things', 'things to know',
    'in pictures', 'in photos', 'photo gallery',
    'quiz', 'poll', 'survey',
    'tributes to', 'pays tribute', 'pay tributes',
    'celebrity', 'celebrities', 'fans pay',
    'i am not afraid', 'not afraid of',
    'will it work', 'is it working',
    'live updates', 'live blog', 'live:',
]

# v6.2: natural-disaster / accident items belong to the disaster pipeline,
# never the conflict feed. Reject these at the title before generation so
# they do not consume an API call. Kept deliberately narrow (clear physical
# disasters/accidents only) to avoid dropping real conflict reports.
NATURAL_NONCONFLICT_TERMS = [
    'earthquake', 'quake', 'magnitude', 'aftershock', 'tsunami',
    'volcano', 'volcanic', 'eruption', 'wildfire', 'bushfire',
    'landslide', 'mudslide', 'avalanche',
    'cyclone', 'hurricane', 'typhoon', 'tornado',
    'shark attack', 'plane crash', 'helicopter crash', 'air crash',
    'bus crash', 'car crash', 'train crash', 'derailment', 'derailed',
    'capsized', 'capsize', 'ferry sank',
]


def is_relevant(title, summary):
    text = (title + ' ' + summary).lower()
    title_lower = title.lower()
    # v6.2: drop obvious natural-disaster / accident items (disaster pipeline
    # owns these). Title-only check to avoid catching conflict pieces that
    # merely mention a disaster word in passing.
    for term in NATURAL_NONCONFLICT_TERMS:
        if term in title_lower:
            return False
    has_conflict = any(term in text for term in CONFLICT_TERMS)
    if not has_conflict:
        return False
    has_event = any(signal in text for signal in EVENT_SIGNALS)
    if not has_event:
        return False
    for pattern in EXCLUDE_PATTERNS:
        if pattern in title_lower:
            return False
    return True


def extract_country(title, summary):
    text = (title + ' ' + summary).lower()
    sorted_countries = sorted(ALL_COUNTRIES, key=len, reverse=True)
    for country in sorted_countries:
        if country.lower() in text:
            return country
    demonyms = {
        'iranian': 'Iran', 'iraqi': 'Iraq', 'syrian': 'Syria', 'yemeni': 'Yemen',
        'israeli': 'Israel', 'palestinian': 'Palestine', 'lebanese': 'Lebanon',
        'afghan': 'Afghanistan', 'pakistani': 'Pakistan', 'indian': 'India',
        'chinese': 'China', 'russian': 'Russia', 'ukrainian': 'Ukraine',
        'sudanese': 'Sudan', 'ethiopian': 'Ethiopia', 'somali': 'Somalia',
        'nigerian': 'Nigeria', 'kenyan': 'Kenya', 'congolese': 'Congo',
        'malian': 'Mali', 'haitian': 'Haiti', 'venezuelan': 'Venezuela',
        'colombian': 'Colombia', 'mexican': 'Mexico', 'brazilian': 'Brazil',
        'burmese': 'Myanmar', 'filipino': 'Philippines', 'thai': 'Thailand',
        'turkish': 'Turkey', 'egyptian': 'Egypt', 'libyan': 'Libya',
        'tunisian': 'Tunisia', 'algerian': 'Algeria', 'moroccan': 'Morocco',
        'nigerien': 'Niger', 'burkinabe': 'Burkina Faso', 'salvadoran': 'El Salvador',
        'honduran': 'Honduras', 'guatemalan': 'Guatemala', 'ecuadorian': 'Ecuador',
    }
    for demonym, country in demonyms.items():
        if demonym in text:
            return country
    cities = {
        'tehran': 'Iran', 'baghdad': 'Iraq', 'damascus': 'Syria', 'sanaa': 'Yemen',
        'gaza': 'Palestine', 'west bank': 'Palestine', 'beirut': 'Lebanon',
        'kabul': 'Afghanistan', 'islamabad': 'Pakistan', 'karachi': 'Pakistan',
        'moscow': 'Russia', 'kyiv': 'Ukraine', 'kiev': 'Ukraine', 'kharkiv': 'Ukraine',
        'khartoum': 'Sudan', 'addis ababa': 'Ethiopia', 'mogadishu': 'Somalia',
        'lagos': 'Nigeria', 'abuja': 'Nigeria', 'nairobi': 'Kenya', 'kinshasa': 'Congo',
        'bamako': 'Mali', 'port-au-prince': 'Haiti', 'caracas': 'Venezuela',
        'yangon': 'Myanmar', 'manila': 'Philippines', 'bangkok': 'Thailand',
        'ankara': 'Turkey', 'istanbul': 'Turkey', 'cairo': 'Egypt', 'tripoli': 'Libya',
        'beijing': 'China', 'hong kong': 'China', 'taipei': 'China',
        'strait of hormuz': 'Iran', 'hormuz': 'Iran',
        'culiacan': 'Mexico', 'culiacán': 'Mexico', 'sinaloa': 'Mexico',
        'michoacan': 'Mexico', 'michoacán': 'Mexico', 'guerrero': 'Mexico',
        'acapulco': 'Mexico', 'tamaulipas': 'Mexico', 'juarez': 'Mexico',
        'juárez': 'Mexico', 'tijuana': 'Mexico', 'jalisco': 'Mexico',
        'chiapas': 'Mexico', 'zacatecas': 'Mexico', 'guanajuato': 'Mexico',
        'medellin': 'Colombia', 'medellín': 'Colombia', 'bogota': 'Colombia',
        'bogotá': 'Colombia', 'guayaquil': 'Ecuador',
        'san salvador': 'El Salvador', 'tegucigalpa': 'Honduras',
        'goma': 'Congo', 'ituri': 'Congo', 'maiduguri': 'Nigeria',
        'ouagadougou': 'Burkina Faso', 'niamey': 'Niger', 'juba': 'South Sudan',
        'el fasher': 'Sudan', 'port sudan': 'Sudan', 'tigray': 'Ethiopia',
        'amhara': 'Ethiopia', 'aleppo': 'Syria', 'idlib': 'Syria',
        'mosul': 'Iraq', 'basra': 'Iraq', 'rafah': 'Palestine',
        'khan younis': 'Palestine', 'hebron': 'Palestine', 'jenin': 'Palestine',
        'rakhine': 'Myanmar', 'sagaing': 'Myanmar', 'mandalay': 'Myanmar',
        'kandahar': 'Afghanistan', 'peshawar': 'Pakistan', 'quetta': 'Pakistan',
        'manipur': 'India', 'srinagar': 'India',
    }
    for city, country in cities.items():
        if city in text:
            return country
    return None


def matches_filter(country, filter_countries):
    if not filter_countries:
        return True
    if not country:
        return False
    return country in filter_countries


_NUM_WORDS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11,
    "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
    "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19,
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60,
    "seventy": 70, "eighty": 80, "ninety": 90, "hundred": 100,
    "thousand": 1000,
}


def _normalize_numbers(text):
    if not text:
        return ""
    t = text.lower().replace("-", " ")
    tokens = t.split()
    out = []
    i = 0
    while i < len(tokens):
        w = tokens[i]
        if w in _NUM_WORDS:
            val = _NUM_WORDS[w]
            j = i + 1
            while j < len(tokens) and tokens[j] in _NUM_WORDS:
                nxt = _NUM_WORDS[tokens[j]]
                if nxt in (100, 1000):
                    val = (val or 1) * nxt
                elif val and val % 10 == 0 and 0 < nxt < 10:
                    val += nxt
                elif val >= 100 and nxt < 100:
                    val += nxt
                else:
                    break
                j += 1
            out.append(str(val))
            i = j
        else:
            out.append(w)
            i += 1
    return " ".join(out)


def title_similarity(title1, title2):
    words1 = set(_normalize_numbers(title1).split())
    words2 = set(_normalize_numbers(title2).split())
    stopwords = {'the', 'a', 'an', 'in', 'on', 'at', 'to', 'for',
                 'of', 'and', 'or', 'is', 'are', 'was', 'were',
                 'with', 'by', 'from', 'as', 'it', 'its', 'be'}
    words1 = words1 - stopwords
    words2 = words2 - stopwords
    if not words1 or not words2:
        return 0.0
    overlap = len(words1 & words2)
    return overlap / max(len(words1), len(words2))


def is_duplicate(title, existing_titles, threshold=0.75):
    for existing in existing_titles:
        if title_similarity(title, existing) >= threshold:
            return True
    return False


_RECENT_WP_TITLES_CACHE = None


def load_recent_wp_titles(days=30):
    global _RECENT_WP_TITLES_CACHE
    if _RECENT_WP_TITLES_CACHE is not None:
        return _RECENT_WP_TITLES_CACHE
    titles = []
    try:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        page = 1
        while page <= 5:
            url = (WP_URL + "/wp-json/wp/v2/posts"
                   "?categories=" + str(WP_CATEGORY_ID) +
                   "&per_page=100&page=" + str(page) +
                   "&_fields=id,title,date_gmt" +
                   "&after=" + cutoff +
                   "&orderby=date&order=desc")
            r = requests.get(url, timeout=15)
            if r.status_code != 200:
                break
            posts = r.json()
            if not posts:
                break
            for p in posts:
                t = p.get("title", {}).get("rendered", "")
                t = html.unescape(t)
                t = re.sub(r"<[^>]+>", "", t).strip()
                if t:
                    titles.append(t)
            page += 1
        log.info("WP dedup cache: loaded %d recent titles (last %d days)",
                 len(titles), days)
    except Exception as e:
        log.warning("WP dedup cache load failed: %s", e)
    _RECENT_WP_TITLES_CACHE = titles
    return titles


def is_duplicate_of_existing_wp(candidate_title, threshold=0.65):
    recent = load_recent_wp_titles()
    for existing in recent:
        if title_similarity(candidate_title, existing) >= threshold:
            log.info("WP dedup match: %r ~ %r",
                     candidate_title[:60], existing[:60])
            return True
    return False


def load_seen():
    if os.path.exists(SEEN_FILE):
        try:
            with open(SEEN_FILE, 'r') as f:
                return set(json.load(f))
        except Exception:
            return set()
    return set()


def save_seen(seen):
    os.makedirs(os.path.dirname(SEEN_FILE), exist_ok=True)
    seen_list = list(seen)[-2000:]
    with open(SEEN_FILE, 'w') as f:
        json.dump(seen_list, f)


def purge_jsdelivr(filename):
    try:
        url = "https://purge.jsdelivr.net/gh/InnovativeGeospatial/GWM@main/" + filename
        r = requests.get(url, timeout=20)
        log.info("jsDelivr purge %s -> %s", filename, r.status_code)
    except Exception as e:
        log.warning("jsDelivr purge failed for %s: %s", filename, e)


def article_hash(url, title):
    return hashlib.md5((url + title).encode()).hexdigest()


def fetch_rss_feeds(seen, filter_countries):
    candidates = []
    seen_titles = []
    for feed_url in RSS_FEEDS:
        log.info('Fetching RSS: %s', feed_url)
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:60]:
                title = entry.get('title', '').strip()
                summary = entry.get('summary', entry.get('description', '')).strip()
                url = entry.get('link', '')
                if not title or not url:
                    continue
                h = article_hash(url, title)
                if h in seen:
                    continue
                if not is_relevant(title, summary):
                    continue
                country = extract_country(title, summary)
                if not matches_filter(country, filter_countries):
                    continue
                if is_duplicate(title, seen_titles):
                    log.info('Skipping duplicate: %s', title[:60])
                    continue
                if is_duplicate_of_existing_wp(title):
                    log.info('Skipping (already in WP recently): %s', title[:60])
                    continue
                candidates.append({
                    'title': title, 'summary': summary, 'url': url,
                    'hash': h, 'source': feed.feed.get('title', feed_url),
                    'published': entry.get('published', ''),
                    'country': country,
                })
                seen_titles.append(title)
        except Exception as e:
            log.warning('RSS feed error (%s): %s', feed_url, e)
    log.info('RSS: found %d relevant unseen articles', len(candidates))
    return candidates


def fetch_gdelt(seen, existing_titles, filter_countries):
    log.info('Fetching GDELT...')
    candidates = []
    query_terms = [
        'armed conflict massacre killed attack',
        'coup military junta crackdown',
        'civil war insurgency rebel offensive',
        'humanitarian crisis displaced siege',
    ]
    for query in query_terms:
        try:
            url = (
                'https://api.gdeltproject.org/api/v2/doc/doc'
                '?query=' + requests.utils.quote(query) +
                '&mode=artlist&maxrecords=10&timespan=24h'
                '&sort=DateDesc&format=json'
            )
            r = requests.get(url, timeout=15)
            if r.status_code != 200:
                log.warning('GDELT returned %s', r.status_code)
                continue
            data = r.json()
            articles = data.get('articles', [])
            for article in articles:
                title = article.get('title', '').strip()
                url_art = article.get('url', '')
                source = article.get('domain', 'GDELT')
                if not title or not url_art:
                    continue
                h = article_hash(url_art, title)
                if h in seen:
                    continue
                if not is_relevant(title, ''):
                    continue
                country = extract_country(title, '')
                if not matches_filter(country, filter_countries):
                    continue
                if is_duplicate(title, existing_titles):
                    log.info('GDELT duplicate skip: %s', title[:60])
                    continue
                if is_duplicate_of_existing_wp(title):
                    log.info('GDELT skip (already in WP recently): %s', title[:60])
                    continue
                candidates.append({
                    'title': title, 'summary': title, 'url': url_art,
                    'hash': h, 'source': source,
                    'published': article.get('seendate', ''),
                    'country': country,
                })
                existing_titles.append(title)
            time.sleep(1)
        except Exception as e:
            log.warning('GDELT error: %s', e)
    log.info('GDELT: found %d additional articles', len(candidates))
    return candidates


def fetch_all_feeds(seen, filter_countries):
    rss_candidates = fetch_rss_feeds(seen, filter_countries)
    rss_titles = [c['title'] for c in rss_candidates]
    gdelt_candidates = fetch_gdelt(seen, rss_titles, filter_countries)
    all_candidates = rss_candidates + gdelt_candidates
    log.info('Total candidates: %d', len(all_candidates))
    return all_candidates[:MAX_ARTICLES]


SYSTEM_PROMPT = """You are writing brief, plain-language conflict and unrest reports for the general public on Global Witness Monitor. Mission agencies, churches, and field workers read these reports to stay aware of conditions where they serve.

REQUIRED OUTPUT FORMAT - every response must begin with exactly these header lines:

COUNTRY: <primary country where the event physically occurred>
EVENT_TYPE: <Armed Conflict|Civil Unrest|Coup or Crisis|Displacement|Other>
LOCATION: <most specific named place from the source: city, town, district, or named region. UNKNOWN only if no place is named anywhere in the source>
EVENT_DATE: <event date in MM/DD/YYYY format, "UNKNOWN" if not stated in the source>
PRAYER: <a bare situation phrase naming what to pray for — NOT an instruction, NOT a sentence. No leading verb. Never begin with Pray, Lift up, Ask God, May, Let, or "for". Name the people and circumstance, 8-25 words, e.g. "Two million civilians in Gaza facing ongoing airstrikes" or "Families displaced by cross-border shelling in southern Lebanon">
ALERT_SUMMARY: <one factual sentence: what happened, where, and the single most important figure from the source (killed, wounded, displaced, detained, arrested). Use ONLY quantitative descriptors. NEVER use vague intensifiers such as powerful, massive, severe, devastating, major, deadly, intense, heavy. If the source gives no figure, state the event plainly with no intensifier. 8-20 words. e.g. "Shelling killed 12 and displaced about 4,000 in southern Lebanon" or "Security forces detained 30 protesters in Herat; no casualties reported">

---

Then the article body follows on the next line.

WRITING STYLE - VERY IMPORTANT:
- Plain language for general public. NO technical jargon, NO intelligence-briefing tone.
- DO NOT include "Mission Note:", "Field teams should...", "Operational significance...", or any boilerplate operational language at the end.
- DO NOT editorialize about geopolitics or assign blame beyond what sources state.
- Length: only as long as the source supports. At most 100-180 words when the source is detailed; when the source is thin, write 2 to 4 factual sentences and then stop. Never pad to reach a length with background, history, or restatement (e.g. do NOT add filler such as 'the situation continues to develop', 'officials continue to monitor', or 'this is the Nth update').
- Lead with the concrete figures the source provides (deaths, injured, displaced, arrested, affected, magnitude, or similar). If the source provides no such figure, state that plainly in one sentence and do not imply a scale.
- NEVER name a city, town, village, district, or region that does not appear in the source material. If the source names no specific place, use the country or write UNKNOWN. Do not invent, guess, or infer a place name.
- Two or three short paragraphs. Use blank lines between paragraphs (the WordPress editor will turn those into proper paragraph spacing).
- Do not include personal names; use "a man", "a woman", "residents", "officials", "soldiers", "protesters", etc.
- Do not include the source URL in the body.
- Do not include a title in your response - only the article body.
- State when the event happened in the body, using the event date in plain language (for example, "On June 18, 2026, ..."). If the source does not give a date, do not invent one.
- End naturally with the last fact or implication for civilians - no boilerplate.
- DO NOT include the prayer line in the body. The PRAYER: field at the top of the header is the only place the prayer appears.

COUNTRY field rules:
- Country where the event physically occurred, NOT the news outlet's country.
- For events affecting multiple countries: COUNTRY: MULTIPLE: Country1, Country2
- For events in international waters or unknown: COUNTRY: UNKNOWN
- Use common country names: "Iran", "United States", "United Kingdom", "Myanmar", "Congo".
- Do NOT include state/province names.

LOCATION field rules:
- Most specific named place mentioned in the source.
- Examples: "Hebron", "Cauca", "Gaziantep", "Aleppo", "northern Mali".
- Do NOT include the country.
- UNKNOWN only when truly no place name appears in the source.

EVENT_TYPE field:
- Use one of: Armed Conflict, Civil Unrest, Coup or Crisis, Displacement, Other.

EVENT_DATE field:
- MM/DD/YYYY format. Use the date the event occurred, not when it was reported.
- UNKNOWN if not in source.

PRAYER field:
- A bare situation phrase, not an instruction or sentence. Name who is affected and what is happening.
- No leading verb. Never start with Pray, Lift up, Ask God, May, Let, Grant, or "for".
- Focus on civilians affected, families of victims, or displaced people.
- Do not assign blame or make political statements.

Respond with SKIP_NO_EVENT (and nothing else) if ANY of these apply:
- The source is pure opinion, commentary, or an explainer with no factual event reported.
- The piece is about an anniversary, commemoration, memorial, or remembrance of a past event.
- The piece recounts a historical event rather than reporting something happening now (for example "years ago", "decades ago", "in 19XX", "on this day", "this week in history").
- The only news hook is a planned or delivered speech, ceremony, statement, hearing, or announcement ABOUT a past event, rather than a new event on the ground.
- The piece is about espionage, surveillance, intelligence, policy, diplomacy, or institutions, with no specific on-the-ground location where something physically happened.
- The piece is primarily about a court verdict, trial, sentencing, conviction, indictment, or legal ruling concerning events that already happened, rather than a new violent event occurring now on the ground.
- The event is a natural disaster or accident (earthquake, flood, storm, wildfire, landslide, plane/vehicle crash, shark attack, building fire) with no armed-conflict, unrest, or political-violence dimension."""


CANONICAL_COUNTRY_MAP = None

_COUNTRY_ALIASES = {
    "burma": "Myanmar", "burma (myanmar)": "Myanmar", "myanmar (burma)": "Myanmar",
    "timor-leste": "Timor Leste", "east timor": "Timor Leste",
    "dr congo": "Congo", "d.r. congo": "Congo", "drc": "Congo",
    "democratic republic of the congo": "Congo",
    "democratic republic of congo": "Congo",
    "republic of the congo": "Congo",
    "north korea": "North Korea", "south korea": "South Korea",
    "korea, north": "North Korea", "korea, south": "South Korea",
    "czech republic": "Czechia",
    "cote d'ivoire": "Ivory Coast", "cote divoire": "Ivory Coast",
    "cabo verde": "Cape Verde",
    "uae": "United Arab Emirates",
    "uk": "United Kingdom", "britain": "United Kingdom",
    "great britain": "United Kingdom",
    "usa": "United States", "u.s.": "United States",
    "u.s.a.": "United States", "america": "United States",
    "vatican": "Vatican City", "holy see": "Vatican City",
    "palestinian territories": "Palestine",
    "gaza": "Palestine", "west bank": "Palestine",
    "state of palestine": "Palestine",
}


def _normalize_country_key(s):
    if not s:
        return ""
    s = s.lower().strip()
    for ch in [".", ",", "(", ")", "-", "'", '"']:
        s = s.replace(ch, " ")
    return " ".join(s.split())


def _build_country_map():
    global CANONICAL_COUNTRY_MAP
    if CANONICAL_COUNTRY_MAP is not None:
        return CANONICAL_COUNTRY_MAP
    m = {}
    for c in ALL_COUNTRIES:
        m[_normalize_country_key(c)] = c
    for alias, canonical in _COUNTRY_ALIASES.items():
        m[_normalize_country_key(alias)] = canonical
    CANONICAL_COUNTRY_MAP = m
    return m


def validate_country(claude_country):
    if not claude_country or not isinstance(claude_country, str):
        return None
    key = _normalize_country_key(claude_country)
    if not key:
        return None
    return _build_country_map().get(key)


def parse_claude_response(raw_text):
    result = {
        "countries": [], "event_type": "Other",
        "location": "", "event_date": "",
        "prayer": "", "alert_summary": "",
        "body": "", "raw_country_line": "",
        "status": "malformed",
    }
    if not raw_text:
        return result

    lines = raw_text.strip().splitlines()
    if len(lines) < 2:
        result["body"] = raw_text.strip()
        return result

    country_line = None
    type_line = None
    location_line = None
    event_date_line = None
    pray_line = None
    alert_summary_line = None
    body_start_idx = 0

    for i, line in enumerate(lines[:15]):
        stripped = line.strip()
        up = stripped.upper()
        if up.startswith("COUNTRY:"):
            country_line = stripped[len("COUNTRY:"):].strip()
            body_start_idx = max(body_start_idx, i + 1)
        elif up.startswith("EVENT_TYPE:") or up.startswith("EVENT TYPE:"):
            if up.startswith("EVENT_TYPE:"):
                type_line = stripped[len("EVENT_TYPE:"):].strip()
            else:
                type_line = stripped[len("EVENT TYPE:"):].strip()
            body_start_idx = max(body_start_idx, i + 1)
        elif up.startswith("LOCATION:"):
            location_line = stripped[len("LOCATION:"):].strip()
            body_start_idx = max(body_start_idx, i + 1)
        elif up.startswith("EVENT_DATE:") or up.startswith("EVENT DATE:"):
            if up.startswith("EVENT_DATE:"):
                event_date_line = stripped[len("EVENT_DATE:"):].strip()
            else:
                event_date_line = stripped[len("EVENT DATE:"):].strip()
            body_start_idx = max(body_start_idx, i + 1)
        elif up.startswith("PRAYER:"):
            pray_line = stripped[len("PRAYER:"):].strip()
            body_start_idx = max(body_start_idx, i + 1)
        elif up.startswith("ALERT_SUMMARY:") or up.startswith("ALERT SUMMARY:"):
            if up.startswith("ALERT_SUMMARY:"):
                alert_summary_line = stripped[len("ALERT_SUMMARY:"):].strip()
            else:
                alert_summary_line = stripped[len("ALERT SUMMARY:"):].strip()
            body_start_idx = max(body_start_idx, i + 1)
        elif stripped == "---":
            body_start_idx = max(body_start_idx, i + 1)

    while body_start_idx < len(lines) and (
        not lines[body_start_idx].strip() or lines[body_start_idx].strip() == "---"
    ):
        body_start_idx += 1

    result["body"] = "\n".join(lines[body_start_idx:]).strip()
    result["raw_country_line"] = country_line or ""

    if type_line:
        _t_norm = type_line.strip().lower()
        _valid = {
            "armed conflict": "Armed Conflict",
            "civil unrest": "Civil Unrest",
            "coup or crisis": "Coup or Crisis",
            "coup": "Coup or Crisis",
            "crisis": "Coup or Crisis",
            "displacement": "Displacement",
            "other": "Other",
        }
        result["event_type"] = _valid.get(_t_norm, "Other")

    if location_line and location_line.upper() != "UNKNOWN":
        result["location"] = location_line
    if event_date_line and event_date_line.upper() != "UNKNOWN":
        result["event_date"] = event_date_line

    if pray_line:
        pl = re.sub(r'^pray[:\s]+(that\s+)?', '', pray_line, flags=re.IGNORECASE)
        pl = re.sub(r'^that\s+', '', pl, flags=re.IGNORECASE)
        result["prayer"] = pl.strip()

    if alert_summary_line and alert_summary_line.upper() != "UNKNOWN":
        result["alert_summary"] = alert_summary_line.strip()

    if not country_line:
        return result

    up = country_line.upper()
    if up == "UNKNOWN":
        result["status"] = "unknown"
        return result

    if up.startswith("MULTIPLE:") or up.startswith("MULTIPLE "):
        raw_list = country_line.split(":", 1)[-1] if ":" in country_line else country_line[8:]
        parts = [p.strip() for p in raw_list.split(",") if p.strip()]
        validated = []
        for p in parts:
            c = validate_country(p)
            if c and c not in validated:
                validated.append(c)
        if validated:
            result["countries"] = validated
            result["status"] = "ok"
        else:
            result["status"] = "no_valid_country"
        return result

    c = validate_country(country_line)
    if c:
        result["countries"] = [c]
        result["status"] = "ok"
    else:
        result["status"] = "no_valid_country"
    return result


REFUSAL_PATTERNS = [
    'i cannot write', 'i cannot provide', 'i am unable to',
    "i can't write", 'i can not write', 'i will not write',
]
SKIP_TOKEN = 'skip_no_event'
MIN_WORDS = 30
SKIP_LOG = '/opt/conflict-pipeline/skips.log'


def log_skip(title, reason):
    """Append every dropped candidate to a skip log so drops stay inspectable
    without anyone having to watch the run."""
    try:
        with open(SKIP_LOG, 'a') as f:
            f.write(datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
                    + '\t' + (reason or '?') + '\t' + (title or '')[:120] + '\n')
    except Exception as e:
        log.warning('skip-log write failed: %s', e)


def is_refusal(article_body):
    """True only for an actual model refusal -- NOT the deliberate
    SKIP_NO_EVENT signal, which is a correct rejection."""
    lower = article_body.lower()
    if SKIP_TOKEN in lower:
        return False
    return any(p in lower for p in REFUSAL_PATTERNS)


def is_valid_article(article_body):
    lower = article_body.lower()
    if SKIP_TOKEN in lower:
        log.info("INVALID_REASON: skip_no_event")
        return False
    for pattern in REFUSAL_PATTERNS:
        if pattern in lower:
            log.info("INVALID_REASON: matched refusal '%s'", pattern)
            return False
    word_count = len(article_body.split())
    if word_count < MIN_WORDS:
        log.info("INVALID_REASON: word_count=%d", word_count)
        return False
    return True


def fetch_article_body(url, max_chars=6000):
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return ""
    try:
        headers = {"User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                                  "AppleWebKit/605.1.15 (KHTML, like Gecko) "
                                  "Version/17.0 Safari/605.1.15")}
        r = requests.get(url, headers=headers, timeout=20, allow_redirects=True)
        if r.status_code != 200:
            return ""
        # Google News RSS links are redirect shells. If we never escaped to a
        # real publisher, skip extraction and let the RSS summary carry it.
        if "news.google.com" in (r.url or url):
            return ""
        if "html" not in r.headers.get("content-type", "").lower():
            return ""
        soup = BeautifulSoup(r.text, "html.parser")
        for tag in soup(["script", "style", "nav", "header", "footer", "aside", "form", "figure", "figcaption"]):
            tag.decompose()
        def _extract(scope):
            if not scope:
                return ""
            blocks = []
            for el in scope.find_all(["p", "li", "tr", "h2", "h3"]):
                t = el.get_text(" ", strip=True)
                if not t:
                    continue
                if el.name in ("li", "tr"):
                    if len(t) > 25 or any(c.isdigit() for c in t):
                        blocks.append(t)
                elif len(t) > 25:
                    blocks.append(t)
            return " ".join(blocks)

        node = soup.find("article") or soup.find("main") or soup.body
        text = _extract(node)
        if len(text) < 400:
            full = _extract(soup.body or soup)
            if len(full) > len(text):
                text = full
        if not text:
            text = (node or soup).get_text(" ", strip=True)
        return " ".join(text.split())[:max_chars]
    except Exception as e:
        log.info("body fetch failed for %s: %s", url[:60], e)
        return ""


def generate_article(item, firmer=False):
    client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
    body_text = fetch_article_body(item['url'])
    body_section = ""
    if body_text:
        log.info("fetched %d chars of article body", len(body_text))
        body_section = "SOURCE BODY TEXT:\n" + body_text + "\n\n"
    user_prompt = (
        "Write a plain-language conflict report based only on the source material below. "
        "Follow the header format and writing style rules from the system prompt exactly.\n\n"
        "SOURCE TITLE: " + item['title'] + "\n\n"
        "SOURCE SUMMARY: " + item['summary'] + "\n\n"
        + body_section +
        "SOURCE URL: " + item['url'] + "\n\n"
        "SOURCE OUTLET: " + item['source'] + "\n\n"
        "Use only facts present in the source material above."
    )
    if firmer:
        user_prompt = (
            "The item below is a factual news event already publicly reported "
            "by the outlet named. Summarize it for a conflict-monitoring service "
            "read by missionaries and churches. Do not decline and do not refuse; "
            "if the source is thin, write only what it supports. If it genuinely "
            "describes no real-world event, reply with SKIP_NO_EVENT. Follow the "
            "header format exactly.\n\n"
        ) + user_prompt
    log.info('Generating article for: %s', item['title'][:70])
    message = client.messages.create(
        model='claude-sonnet-4-6',
        max_tokens=800,
        messages=[{'role': 'user', 'content': user_prompt}],
        system=SYSTEM_PROMPT,
    )
    raw_response = message.content[0].text.strip()
    parsed = parse_claude_response(raw_response)
    return raw_response, parsed


def geocode_mapbox(location, country_hint=None):
    if not location or not MAPBOX_TOKEN:
        return None, None
    try:
        # v6.2: bias the geocoder to the event's own country by appending it to
        # the query. Stops ambiguous place names ("Sinai Peninsula", "Sea of
        # Oman", "Pentagon") from resolving to same-named US towns.
        query = location.strip()
        if country_hint and country_hint.strip():
            query = query + ", " + country_hint.strip()
        url = ("https://api.mapbox.com/geocoding/v5/mapbox.places/"
               + requests.utils.quote(query) + ".json")
        params = {
            "access_token": MAPBOX_TOKEN, "limit": 5,
            "types": "place,locality,region,district,country,neighborhood,address",
        }
        r = requests.get(url, params=params, timeout=10)
        if r.status_code != 200:
            return None, None
        features = (r.json() or {}).get("features", [])
        if not features:
            return None, None
        hint_lower = (country_hint or "").strip().lower() if country_hint else None
        for feat in features:
            center = feat.get("center")
            if not center or len(center) < 2:
                continue
            lng, lat = float(center[0]), float(center[1])
            feat_country = ""
            if "country" in (feat.get("place_type") or []):
                feat_country = (feat.get("text") or "").lower()
            for ctx in (feat.get("context") or []):
                if isinstance(ctx, dict) and ctx.get("id", "").startswith("country."):
                    feat_country = (ctx.get("text") or "").lower()
            if hint_lower:
                _disputed = {
                    "israel": "il_ps", "palestine": "il_ps",
                    "palestinian territories": "il_ps",
                    "west bank": "il_ps", "gaza": "il_ps",
                }
                hint_disputed = _disputed.get(hint_lower)
                feat_disputed = _disputed.get(feat_country) if feat_country else None
                if feat_country and (
                    hint_lower == feat_country
                    or hint_lower in feat_country
                    or feat_country in hint_lower
                    or (hint_disputed and hint_disputed == feat_disputed)
                ):
                    return lat, lng
                continue
            else:
                return lat, lng
        return None, None
    except Exception as e:
        log.warning("Mapbox geocode error for %r: %s", location, e)
        return None, None


_BANNED_TITLE_PREFIXES = (
    "minor ", "major ", "severe ", "massive ", "deadly ",
    "devastating ", "catastrophic ", "small ", "large ",
    "moderate ", "strong ",
)


def _strip_qualifier(label):
    if not label:
        return label
    low = label.lower()
    for p in _BANNED_TITLE_PREFIXES:
        if low.startswith(p):
            label = label[len(p):]
            break
    return label


def _to_us_date(any_date_str):
    if not any_date_str:
        return ""
    s = str(any_date_str).strip()
    if not s or s.upper() == "UNKNOWN":
        return ""
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", s)
    if m:
        mm, dd, yyyy = m.groups()
        return f"{int(mm):02d}/{int(dd):02d}/{yyyy}"
    m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})", s)
    if m:
        yyyy, mm, dd = m.groups()
        return f"{int(mm):02d}/{int(dd):02d}/{yyyy}"
    return ""


def build_title(parsed, item):
    etype_raw = parsed.get("event_type", "Other") or "Other"
    etype_norm = etype_raw.strip().lower()
    if etype_norm == "other":
        etype_display = ""
    elif etype_norm == "coup or crisis":
        etype_display = "Coup/Crisis"
    else:
        etype_display = etype_raw

    countries = parsed.get("countries") or []
    country = countries[0] if countries else (item.get("country") or "")
    location = (parsed.get("location") or "").strip()
    has_location = bool(location) and location.upper() != "UNKNOWN"

    # Title format: "<EventType> in <Location>". No date.
    # Falls back to country when no specific location is named.
    place = location if has_location else country
    if etype_display and place:
        return etype_display + " in " + place
    if etype_display:
        return etype_display
    if place:
        return place
    return "Conflict Report"


def sanitize_title(title):
    if not title:
        return title
    t = html.unescape(title)
    t = t.strip().strip('"\'')
    t = _strip_qualifier(t)
    t = re.sub(r"\s+", " ", t).strip()
    if t:
        t = t[0].upper() + t[1:]
    return t


def _prayer_with_for(text):
    """Ensure the prayer phrase begins with 'for ' so it reads naturally
    after the 'Prayer:' label, e.g. 'Prayer: for the families ...'."""
    if not text:
        return text
    return text.strip()



def format_body_for_wordpress(body_text, prayer=""):
    """Wrap paragraphs in <p> tags. Optionally append styled Pray line."""
    if not body_text:
        return ""
    decoded = html.unescape(body_text).strip()
    paras = re.split(r"\n\s*\n", decoded)
    cleaned = []
    for p in paras:
        p = p.strip()
        if not p:
            continue
        p = re.sub(r"\s*\n\s*", " ", p)
        p = re.sub(r"\s+", " ", p).strip()
        cleaned.append("<p>" + p + "</p>")
    return "\n\n".join(cleaned)


def get_or_create_tag(name, auth):
    try:
        r = requests.get(WP_URL + '/wp-json/wp/v2/tags',
                         params={'search': name, 'per_page': 20},
                         auth=auth, timeout=15)
        existing = r.json() if r.status_code == 200 else []
        for tag in existing:
            if tag.get("name", "").strip().lower() == name.strip().lower():
                return tag["id"]
        r2 = requests.post(WP_URL + '/wp-json/wp/v2/tags',
                           json={"name": name}, auth=auth, timeout=15)
        if r2.status_code in (200, 201):
            return r2.json()["id"]
    except Exception as e:
        log.warning('Tag error for %s: %s', name, e)
    return None


# -- SAME-LOCATION ROLLUP HELPERS --
_META_COORD_RE = re.compile(r'data-lat="([^"]*)"[^>]*data-lng="([^"]*)"')


def _coord_key(lat, lng):
    """Round coords to a match key. Same city -> same key."""
    try:
        if lat in (None, "") or lng in (None, ""):
            return None
        return (round(float(lat), COORD_MATCH_PRECISION),
                round(float(lng), COORD_MATCH_PRECISION))
    except (TypeError, ValueError):
        return None


def _extract_meta_coords(content):
    """Pull data-lat/data-lng out of a post's hidden meta div."""
    if not content:
        return None
    m = _META_COORD_RE.search(content)
    if not m:
        return None
    return _coord_key(m.group(1).strip(), m.group(2).strip())


def _meta_field(content, field):
    """Pull a single data-<field> value out of a post's hidden meta div."""
    if not content:
        return ""
    m = re.search(r'data-' + field + r'="([^"]*)"', content)
    return m.group(1).strip() if m else ""


def _strip_meta_div(body):
    """Remove the hidden gwm-conflict-meta div from a body fragment."""
    if not body:
        return ""
    return re.sub(r'<div class="gwm-conflict-meta".*?</div>\s*', "", body,
                  flags=re.DOTALL)


def find_recent_conflict_post(lat, lng, auth):
    """Legacy coord-only lookup. Retained for reference; superseded by
    find_recent_conflict_post_v2, which keys on event identity."""
    key = _coord_key(lat, lng)
    if key is None:
        return None
    after = (datetime.now(timezone.utc)
             - timedelta(hours=MERGE_WINDOW_HOURS)).isoformat()
    try:
        r = requests.get(
            WP_URL + '/wp-json/wp/v2/posts',
            params={
                'categories': WP_CATEGORY_ID,
                'after': after,
                'per_page': 50,
                'orderby': 'date',
                'order': 'desc',
                'context': 'edit',          # returns content.raw (unprocessed)
                '_fields': 'id,content,date,date_gmt,title',
            },
            auth=auth, timeout=20,
        )
        if r.status_code != 200:
            log.warning('Rollup lookup failed (%s)', r.status_code)
            return None
        for post in r.json():
            c = post.get('content') or {}
            raw = c.get('raw') or c.get('rendered', '')
            if _extract_meta_coords(raw) == key:
                t = (post.get('title') or {})
                return {
                    'id': post.get('id'),
                    'content': raw,
                    'date': post.get('date_gmt') or post.get('date') or '',
                    'title': t.get('raw') or t.get('rendered') or '',
                }
    except Exception as e:
        log.warning('Rollup lookup error: %s', e)
    return None


def find_recent_conflict_post_v2(primary_country, event_type, clean_title,
                                 lat, lng, auth):
    """Identity-based merge lookup. Finds a recent category-8 post that is the
    SAME event as the incoming one and returns it for merging.

    Same event = published within MERGE_WINDOW_HOURS AND same primary country
    (data-country) AND same event_type (data-type) AND any of:
      - either side has no coordinates  (collapses the null-coord duplicates
        that the old coord-only merge missed -- this is what spammed the feed
        with one post per place label for a single escalation), OR
      - both have coords within MERGE_COORD_DEG, OR
      - the cleaned titles overlap at least MERGE_TITLE_SIM.
    """
    if not primary_country or not event_type:
        return None
    after = (datetime.now(timezone.utc)
             - timedelta(hours=MERGE_WINDOW_HOURS)).isoformat()
    have_new = isinstance(lat, (int, float)) and isinstance(lng, (int, float))
    try:
        r = requests.get(
            WP_URL + '/wp-json/wp/v2/posts',
            params={
                'categories': WP_CATEGORY_ID,
                'after': after,
                'per_page': 50,
                'orderby': 'date',
                'order': 'desc',
                'context': 'edit',
                '_fields': 'id,content,date,date_gmt,title',
            },
            auth=auth, timeout=20,
        )
        if r.status_code != 200:
            log.warning('Rollup lookup failed (%s)', r.status_code)
            return None
        for post in r.json():
            c = post.get('content') or {}
            raw = c.get('raw') or c.get('rendered', '')
            if _meta_field(raw, 'country') != primary_country:
                continue
            if _meta_field(raw, 'type') != event_type:
                continue
            t = (post.get('title') or {})
            existing_title = t.get('raw') or t.get('rendered') or ''
            old_lat = _meta_field(raw, 'lat')
            old_lng = _meta_field(raw, 'lng')
            have_old = bool(old_lat) and bool(old_lng)

            merge = False
            if not (have_new and have_old):
                merge = True
            else:
                try:
                    dist = abs(float(old_lat) - lat) + abs(float(old_lng) - lng)
                    if dist <= MERGE_COORD_DEG:
                        merge = True
                except ValueError:
                    merge = True
            if not merge:
                etitle_plain = re.sub(r"<[^>]+>", "", html.unescape(existing_title))
                if title_similarity(clean_title, etitle_plain) >= MERGE_TITLE_SIM:
                    merge = True

            if merge:
                log.info("Identity merge: %r/%s -> existing post %s (%r)",
                         primary_country, event_type, post.get('id'),
                         existing_title[:50])
                return {
                    'id': post.get('id'),
                    'content': raw,
                    'date': post.get('date_gmt') or post.get('date') or '',
                    'title': existing_title,
                }
    except Exception as e:
        log.warning('Rollup lookup error: %s', e)
    return None


def _build_merged_content(existing_content, new_body_html):
    """Append a new incident to an existing post. Keeps the existing post's
    hidden meta div (and its map coordinates) so the map point is unchanged;
    strips any meta div from the incoming body so there is only one.
    new_body_html is already WordPress-formatted (<p> wrapped)."""
    new_inner = _strip_meta_div(new_body_html).strip()
    today = datetime.now(timezone.utc).strftime('%B %d, %Y')
    sep = ('\n<hr class="gwm-incident-sep">\n'
           '<p class="gwm-incident-label"><strong>Update \u2014 ' + today
           + '</strong></p>\n')
    return existing_content.rstrip() + sep + new_inner


def _rollup_title(existing_title, location, country, total):
    """Title for a merged post: '<Location>, <Country> — N Conflict Reports'."""
    loc = (location or "").strip()
    base = (loc + ", " if loc else "") + (country or "")
    base = base.strip().strip(",").strip()
    if not base:
        base = (existing_title or "Conflict").strip()
    return base + " \u2014 " + str(total) + " Conflict Reports"


def _load_suppressions():
    """Local, per-event suppression list written by prune_feed.py. Each entry
    blocks re-publication of one specific deleted event (matched on
    country + type + location) for a bounded number of days."""
    try:
        with open(SUPPRESS_FILE, "r", encoding="utf-8") as f:
            return json.load(f).get("suppressed", [])
    except Exception:
        return []


_SUPPRESSIONS = _load_suppressions()


def _is_suppressed(country, event_type, lat, lng, clean_title):
    """Return the matching suppression entry, or None. Matches when an active
    (non-expired) entry shares country+type AND either coords within
    MERGE_COORD_DEG or title overlap >= MERGE_TITLE_SIM."""
    if not _SUPPRESSIONS:
        return None
    today = datetime.now(timezone.utc).date()
    c = (country or "").strip().lower()
    t = (event_type or "").strip().lower()
    for s in _SUPPRESSIONS:
        if str(s.get("country", "")).strip().lower() != c:
            continue
        if str(s.get("type", "")).strip().lower() != t:
            continue
        wd = s.get("window_days", SUPPRESS_DEFAULT_WINDOW_DAYS)
        try:
            sdate = datetime.fromisoformat(str(s.get("date", ""))[:10]).date()
            if (today - sdate).days > int(wd):
                continue   # expired -- a genuinely new event here is allowed
        except Exception:
            pass           # unparseable date -> treat as still active
        if s.get("broad"):
            return s
        slat, slng = s.get("lat"), s.get("lng")
        if (isinstance(lat, (int, float)) and isinstance(lng, (int, float))
                and isinstance(slat, (int, float))
                and isinstance(slng, (int, float))):
            if abs(lat - slat) + abs(lng - slng) <= MERGE_COORD_DEG:
                return s
        st = str(s.get("title", ""))
        if st and clean_title and title_similarity(clean_title, st) >= MERGE_TITLE_SIM:
            return s
    return None


def publish_to_wordpress(item, article_body, parsed=None):
    """Publish a new post OR merge into a recent same-event post.

    Returns (post_id, post_link, lat, lng, post_date, merged) where merged is
    True when the event was rolled into an existing post."""
    endpoint = WP_URL + '/wp-json/wp/v2/posts'
    auth = (WP_USER, WP_APP_PASSWORD)

    if parsed is None:
        log.warning("publish_to_wordpress called without parsed structure; skipping")
        return None, None, None, None, None, False

    status = parsed.get("status", "malformed")
    log.info(
        "CLAUDE_VS_DETECTED: claude_country=%s event_type=%s detected_country=%s status=%s raw=%r",
        ",".join(parsed.get("countries", [])) or "-",
        parsed.get("event_type", "Other"),
        item.get("country") or "-", status,
        parsed.get("raw_country_line", ""),
    )

    if status == "unknown":
        log.info("Skipping (Claude marked UNKNOWN): %s", item['title'][:60])
        return None, None, None, None, None, False
    if status == "malformed":
        log.warning("Skipping (Claude response malformed): %s", item['title'][:60])
        return None, None, None, None, None, False
    if status == "no_valid_country":
        log.warning("Skipping (Claude country %r not in registry): %s",
                    parsed.get("raw_country_line", ""), item['title'][:60])
        return None, None, None, None, None, False

    etype = parsed.get("event_type", "Other")
    # v6.2 relevance backstop: only the four conflict categories belong in this
    # feed. "Other" (and anything unexpected) is dropped here as well as in
    # main(), so it can never reach the feed even if called directly.
    if etype not in ALLOWED_EVENT_TYPES:
        log.info("Skipping (event_type %r not a conflict category): %s",
                 etype, item['title'][:60])
        return None, None, None, None, None, False

    if not (parsed.get("location") or "").strip():
        log.info("Skipping (no specific location named): %s", item['title'][:60])
        return None, None, None, None, None, False

    countries = parsed["countries"]
    prayer = parsed.get("prayer", "")

    structured_title = build_title(parsed, item)
    clean_title = sanitize_title(structured_title)

    _final_lat = None
    _final_lng = None
    _claude_loc = parsed.get("location")
    _country_hint = countries[0] if countries else None
    if _claude_loc:
        try:
            _glat, _glng = geocode_mapbox(_claude_loc, _country_hint)
            if _glat is not None and _glng is not None:
                _final_lat = _glat
                _final_lng = _glng
                log.info("Geocoded %r in %r -> %.4f, %.4f",
                         _claude_loc, _country_hint, _glat, _glng)
        except Exception as _ge:
            log.warning("Geocode exception: %s", _ge)

    _lat_str = ("%.4f" % _final_lat) if isinstance(_final_lat, (int, float)) else ""
    _lng_str = ("%.4f" % _final_lng) if isinstance(_final_lng, (int, float)) else ""
    _meta_div = (
        '<div class="gwm-conflict-meta"'
        ' data-country="' + (countries[0] if countries else "") + '"'
        ' data-type="' + etype + '"'
        ' data-lat="' + _lat_str + '"'
        ' data-lng="' + _lng_str + '"'
        ' style="display:none;"></div>\n'
    )

    formatted_body = format_body_for_wordpress(article_body, prayer)
    final_content = _meta_div + formatted_body

    # --- Per-event suppression: a specific event the operator deleted must not
    # resurrect (including via merge into a lingering WP post). Checked BEFORE
    # the merge logic so a matched event writes nothing to WordPress or feed.
    _sup = _is_suppressed(countries[0] if countries else "", etype,
                          _final_lat, _final_lng, clean_title)
    if _sup:
        log.info("Skipping (suppressed event): %s", item['title'][:60])
        log_skip(item['title'], 'suppressed')
        return None, None, None, None, None, False

    # --- Identity rollup: merge into a recent SAME-EVENT post (country+type) ---
    # Attempted even when coords are missing, which is exactly the case the old
    # coord-only merge skipped and that flooded the feed with duplicates.
    _primary_country = countries[0] if countries else ""
    _match = find_recent_conflict_post_v2(
        _primary_country, etype, clean_title, _final_lat, _final_lng, auth)
    if _match and _match.get('id'):
        # Replace the existing post with the freshly written article, marked as
        # an update -- do NOT stack another copy underneath. Keep the existing
        # post's meta div (and its map coordinates) so the map point is stable.
        _today_lbl = datetime.now(timezone.utc).strftime('%B %d, %Y')
        _meta_m = re.search(r'<div class="gwm-conflict-meta".*?</div>',
                            _match['content'], flags=re.DOTALL)
        _keep_meta = (_meta_m.group(0) + '\n') if _meta_m else _meta_div
        _updated_label = ('<p class="gwm-update-label"><strong>Updated:</strong> '
                          + _today_lbl + '</p>\n')
        _new_inner = _strip_meta_div(formatted_body).strip()
        merged_content = _keep_meta + _updated_label + _new_inner
        _now_iso = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S')
        # Reuse the existing post's coords for the returned lat/lng so the JSON
        # feed entry keeps the original map point.
        _ex_lat = _meta_field(_match['content'], 'lat')
        _ex_lng = _meta_field(_match['content'], 'lng')
        try:
            _ret_lat = float(_ex_lat) if _ex_lat else _final_lat
            _ret_lng = float(_ex_lng) if _ex_lng else _final_lng
        except ValueError:
            _ret_lat, _ret_lng = _final_lat, _final_lng
        ur = requests.post(
            endpoint + '/' + str(_match['id']),
            json={'title': clean_title, 'content': merged_content,
                  'date_gmt': _now_iso},
            auth=auth, timeout=30,
        )
        if ur.status_code in (200, 201):
            post = ur.json()
            post_date = post.get('date_gmt') or post.get('date') or _now_iso
            log.info("Updated post ID %s [%s / %s]: %s",
                     _match['id'], _primary_country, etype, clean_title[:50])
            return (_match['id'], post.get('link'),
                    _ret_lat, _ret_lng, post_date, True)
        log.error("Update failed (%s); creating a new post instead: %s",
                  ur.status_code, ur.text[:200])
        # fall through to normal create

    tag_ids = []
    for c in countries:
        cid = get_or_create_tag(c, auth)
        if cid:
            tag_ids.append(cid)
    type_tag_id = get_or_create_tag(etype, auth)
    if type_tag_id:
        tag_ids.append(type_tag_id)

    payload = {
        'title': clean_title,
        'content': final_content,
        'status': 'publish',
        'categories': [WP_CATEGORY_ID],
        'tags': tag_ids,
    }

    r = requests.post(endpoint, json=payload, auth=auth, timeout=30)
    if r.status_code in (200, 201):
        post = r.json()
        post_id = post.get('id')
        post_link = post.get('link')
        post_date = post.get('date_gmt') or post.get('date') or ''
        log.info('Published: %s [%s / %s] (ID %s) prayer=%s',
                 clean_title[:60], countries[0], etype, post_id,
                 'yes' if prayer else 'no')
        return post_id, post_link, _final_lat, _final_lng, post_date, False
    else:
        log.error('Publish failed (%s): %s', r.status_code, r.text[:300])
        return None, None, None, None, None, False


def parse_args():
    parser = argparse.ArgumentParser(description='GWM Conflict Pipeline v6')
    parser.add_argument('--region', '-r', action='append',
                        choices=list(REGIONS.keys()),
                        help='Filter by region')
    parser.add_argument('--country', '-c', action='append',
                        help='Filter by specific country')
    parser.add_argument('--list-regions', action='store_true',
                        help='List all regions')
    parser.add_argument('--no-json', action='store_true',
                        help='Skip JSON feed update')
    return parser.parse_args()


def build_country_filter(args):
    if args.list_regions:
        print("\nAvailable regions:\n")
        for region, countries in REGIONS.items():
            print(f"  {region}:")
            print(f"    {', '.join(countries)}\n")
        sys.exit(0)
    filter_countries = []
    if args.region:
        for region in args.region:
            filter_countries.extend(REGIONS[region])
    if args.country:
        for country in args.country:
            normalized = ' '.join(word.capitalize() for word in country.split())
            filter_countries.append(normalized)
    return list(set(filter_countries)) if filter_countries else None


def main():
    args = parse_args()
    try:
        travel_advisories.refresh()
    except Exception as e:
        log.warning('Travel advisory refresh failed (non-fatal): %s', e)

    filter_countries = build_country_filter(args)
    if filter_countries:
        log.info('=== Conflict Pipeline v6 starting (filtered: %d countries) ===',
                 len(filter_countries))
    else:
        log.info('=== Conflict Pipeline v6 starting (GLOBAL) ===')

    seen = load_seen()
    candidates = fetch_all_feeds(seen, filter_countries)
    if not candidates:
        log.info('No new relevant articles found. Done.')
        return

    published = 0
    merged = 0
    skipped = 0
    json_writes = 0

    for item in candidates:
        try:
            _gen = generate_article(item)
            if isinstance(_gen, tuple):
                raw_response, parsed = _gen
            else:
                raw_response, parsed = _gen, None
            article_body = parsed["body"] if (parsed and parsed.get("body")) else raw_response

            if not is_valid_article(article_body):
                if is_refusal(article_body):
                    log.info('Refusal; retrying once (firmer): %s', item['title'][:60])
                    _gen = generate_article(item, firmer=True)
                    if isinstance(_gen, tuple):
                        raw_response, parsed = _gen
                    else:
                        raw_response, parsed = _gen, None
                    article_body = parsed["body"] if (parsed and parsed.get("body")) else raw_response
                if not is_valid_article(article_body):
                    log.info('Skipping (invalid): %s', item['title'][:60])
                    log_skip(item['title'], 'invalid_or_refusal')
                    seen.add(item['hash'])
                    skipped += 1
                    continue

            # v6.2 relevance gate: only the four conflict categories are
            # published. "Other" (shark attacks, fires, anniversaries,
            # explainers, espionage/policy pieces) is dropped here before any
            # geocoding or WP work.
            _etype = (parsed.get("event_type") if parsed else "Other") or "Other"
            if _etype not in ALLOWED_EVENT_TYPES:
                log.info('Skipping (event_type %r not a conflict category): %s',
                         _etype, item['title'][:60])
                log_skip(item['title'], 'event_type_other')
                seen.add(item['hash'])
                skipped += 1
                continue

            _result = publish_to_wordpress(item, article_body, parsed=parsed)
            post_id, post_link, lat, lng, post_date, was_merged = _result

            if post_id:
                seen.add(item['hash'])
                if was_merged:
                    merged += 1
                else:
                    published += 1

                if JSON_WRITER_AVAILABLE and not args.no_json:
                    countries = parsed.get("countries", []) if parsed else []
                    etype = parsed.get("event_type", "Other") if parsed else "Other"
                    prayer = parsed.get("prayer", "") if parsed else ""
                    alert_summary = parsed.get("alert_summary", "") if parsed else ""
                    structured_title = build_title(parsed, item) if parsed else item['title']
                    # Feed carries only a short excerpt, not the full article.
                    # The full text lives on the WordPress post (wp_link). This
                    # keeps conflict.json small; the dashboard truncates to ~140
                    # chars anyway. Strip HTML, collapse whitespace, cap length.
                    _ftxt = re.sub(r'<[^>]+>', ' ', html.unescape(article_body or ""))
                    _ftxt = re.sub(r'\s+', ' ', _ftxt).strip()
                    feed_body = _ftxt[:220]
                    feed_prayer = _prayer_with_for(html.unescape(prayer or "").strip()) if prayer else ""
                    # On a merge, reuse the existing post's wp_id and date so the
                    # writer overwrites the SAME feed entry (one record per place).
                    event = {
                        "wp_id": post_id,
                        "wp_link": post_link,
                        "date": post_date or datetime.now(timezone.utc).isoformat(),
                        "title": sanitize_title(structured_title),
                        "body": feed_body,
                        "country": countries[0] if countries else "",
                        "countries": countries,
                        "type": etype,
                        "lat": lat,
                        "lng": lng,
                        "source_title": item.get("source", ""),
                        "source_url": item.get("url", ""),
                        "prayer": feed_prayer,
                        "alert_summary": alert_summary,
                    }
                    try:
                        gwm_json_writer.write_event(FEED_NAME, event)
                        json_writes += 1
                    except Exception as e:
                        log.error("JSON write_event failed for %s: %s",
                                  item['title'][:60], e)

                time.sleep(3)
            else:
                log_skip(item['title'], 'publish_skip')
                seen.add(item['hash'])
                skipped += 1

        except Exception as e:
            log.error('Error processing "%s": %s', item['title'], e)
            continue

    save_seen(seen)

    if JSON_WRITER_AVAILABLE and not args.no_json and json_writes > 0:
        try:
            log.info("Pushing %d new events to GitHub JSON feeds...", json_writes)
            written = gwm_json_writer.finalize(FEED_NAME)
            log.info("JSON feed updated: active=%s archives=%s",
                     written.get("active"),
                     ",".join(written.get("archives", [])))
            purge_jsdelivr("conflict.json")
        except Exception as e:
            log.error("JSON finalize failed: %s", e)

    log.info('=== Done. Published %d, Merged %d, Skipped %d, JSON writes %d, Total %d ===',
             published, merged, skipped, json_writes, len(candidates))


if __name__ == '__main__':
    main()
