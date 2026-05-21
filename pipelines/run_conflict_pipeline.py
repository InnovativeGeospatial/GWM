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
from datetime import datetime, timezone
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
MAX_ARTICLES = 50
FEED_NAME    = "conflict"

REGIONS = {
    'middle-east': [
        'Iran', 'Iraq', 'Syria', 'Yemen', 'Israel', 'Palestine', 'Lebanon',
        'Jordan', 'Saudi Arabia', 'United Arab Emirates', 'Qatar', 'Kuwait',
        'Bahrain', 'Oman', 'Turkey', 'Cyprus',
    ],
    'africa': [
        'Algeria', 'Angola', 'Benin', 'Botswana', 'Burkina Faso', 'Burundi',
        'Cameroon', 'Cape Verde', 'Central African Republic', 'Chad', 'Comoros',
        'Congo', 'Djibouti', 'Egypt', 'Equatorial Guinea', 'Eritrea', 'Eswatini',
        'Ethiopia', 'Gabon', 'Gambia', 'Ghana', 'Guinea', 'Guinea-Bissau',
        'Ivory Coast', 'Kenya', 'Lesotho', 'Liberia', 'Libya', 'Madagascar',
        'Malawi', 'Mali', 'Mauritania', 'Mauritius', 'Morocco', 'Mozambique',
        'Namibia', 'Niger', 'Nigeria', 'Rwanda', 'Senegal', 'Sierra Leone',
        'Somalia', 'South Africa', 'South Sudan', 'Sudan', 'Tanzania', 'Togo',
        'Tunisia', 'Uganda', 'Zambia', 'Zimbabwe',
    ],
    'asia': [
        'Afghanistan', 'Bangladesh', 'Bhutan', 'Brunei', 'Cambodia', 'China',
        'India', 'Indonesia', 'Japan', 'Kazakhstan', 'Kyrgyzstan', 'Laos',
        'Malaysia', 'Maldives', 'Mongolia', 'Myanmar', 'Nepal', 'North Korea',
        'Pakistan', 'Philippines', 'Singapore', 'South Korea', 'Sri Lanka',
        'Tajikistan', 'Thailand', 'Timor-Leste', 'Turkmenistan', 'Uzbekistan',
        'Vietnam',
    ],
    'europe': [
        'Albania', 'Armenia', 'Azerbaijan', 'Belarus', 'Bosnia', 'Georgia',
        'Kosovo', 'Moldova', 'Montenegro', 'North Macedonia', 'Russia',
        'Serbia', 'Ukraine',
    ],
    'americas': [
        'Argentina', 'Bolivia', 'Brazil', 'Canada', 'Chile', 'Colombia',
        'Costa Rica', 'Cuba', 'Dominican Republic', 'Ecuador',
        'El Salvador', 'Guatemala', 'Guyana', 'Haiti', 'Honduras', 'Jamaica',
        'Mexico', 'Nicaragua', 'Panama', 'Paraguay', 'Peru', 'Trinidad',
        'United States', 'Uruguay', 'Venezuela',
    ],
    'pacific': [
        'Fiji', 'Papua New Guinea', 'Solomon Islands', 'Vanuatu',
    ],
}

ALL_COUNTRIES = []
for region_countries in REGIONS.values():
    ALL_COUNTRIES.extend(region_countries)
ALL_COUNTRIES = list(set(ALL_COUNTRIES))

RSS_FEEDS = [
    'https://reliefweb.int/updates/rss.xml',
    'https://www.crisisgroup.org/rss.xml',
    'https://www.aljazeera.com/xml/rss/all.xml',
    'https://feeds.reuters.com/reuters/worldNews',
    'https://www.hrw.org/rss/world/all',
    'https://news.un.org/feed/subscribe/en/news/all/rss.xml',
    'https://feeds.apnews.com/rss/apf-worldnews',
    'https://rss.dw.com/rdf/rss-en-world',
    'https://feeds.bbci.co.uk/news/world/rss.xml',
]

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


def is_relevant(title, summary):
    text = (title + ' ' + summary).lower()
    has_conflict = any(term in text for term in CONFLICT_TERMS)
    if not has_conflict:
        return False
    has_event = any(signal in text for signal in EVENT_SIGNALS)
    if not has_event:
        return False
    title_lower = title.lower()
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


def title_similarity(title1, title2):
    words1 = set(title1.lower().split())
    words2 = set(title2.lower().split())
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
        from datetime import timedelta
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
            for entry in feed.entries[:30]:
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
PRAYER: <one short prayer prompt sentence related to this event; do NOT begin with the word "Pray"; just write what to pray for, e.g. "the families of those killed and for an end to the cycle of violence" or "civilians caught between rival armed groups">
---

Then the article body follows on the next line.

WRITING STYLE - VERY IMPORTANT:
- Plain language for general public. NO technical jargon, NO intelligence-briefing tone.
- DO NOT include "Mission Note:", "Field teams should...", "Operational significance...", or any boilerplate operational language at the end.
- DO NOT editorialize about geopolitics or assign blame beyond what sources state.
- Length: 100-180 words.
- Two or three short paragraphs. Use blank lines between paragraphs (the WordPress editor will turn those into proper paragraph spacing).
- Do not include personal names; use "a man", "a woman", "residents", "officials", "soldiers", "protesters", etc.
- Do not include the source URL in the body.
- Do not include a title in your response - only the article body.
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

PRAY field:
- One sentence, specific to this event.
- Focus on civilians affected, families of victims, restraint by armed parties, leaders pursuing peace, displaced people, or similar concrete needs.
- Do not assign blame or make political statements.

Only respond with SKIP_NO_EVENT if the source is pure opinion, commentary, or an explainer with no factual event reported."""


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
        "prayer": "",
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


BAD_RESPONSE_PATTERNS = [
    'i cannot write', 'i cannot provide',
    'i am unable to', 'skip_no_event',
]


def is_valid_article(article_body):
    lower = article_body.lower()
    for pattern in BAD_RESPONSE_PATTERNS:
        if pattern in lower:
            log.info("INVALID_REASON: matched bad pattern '%s'", pattern)
            return False
    word_count = len(article_body.split())
    if word_count < 60:
        log.info("INVALID_REASON: word_count=%d", word_count)
        return False
    return True


def fetch_article_body(url, max_chars=4000):
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return ""
    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; GlobalWitnessMonitor/1.0)"}
        r = requests.get(url, headers=headers, timeout=12)
        if r.status_code != 200:
            return ""
        if "html" not in r.headers.get("content-type", "").lower():
            return ""
        soup = BeautifulSoup(r.text, "html.parser")
        for tag in soup(["script", "style", "nav", "header", "footer", "aside", "form"]):
            tag.decompose()
        node = soup.find("article") or soup.find("main") or soup.body
        if not node:
            return ""
        paragraphs = [p.get_text(" ", strip=True) for p in node.find_all("p")]
        text = " ".join(p for p in paragraphs if len(p) > 30)
        if not text:
            text = node.get_text(" ", strip=True)
        return " ".join(text.split())[:max_chars]
    except Exception as e:
        log.info("body fetch failed for %s: %s", url[:60], e)
        return ""


def generate_article(item):
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
        url = ("https://api.mapbox.com/geocoding/v5/mapbox.places/"
               + requests.utils.quote(location.strip()) + ".json")
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
    t = text.strip()
    low = t.lower()
    if low.startswith("for "):
        return t
    if low.startswith("that "):
        return t
    return "for " + t[0].lower() + t[1:]


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
    if prayer:
        pr = html.unescape(prayer).strip()
        pr = re.sub(r"\s+", " ", pr)
        pr = _prayer_with_for(pr)
        cleaned.append(
            '<p class="gwm-prayer-line"><em>Prayer:</em> ' + pr + '</p>'
        )
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


def publish_to_wordpress(item, article_body, parsed=None):
    endpoint = WP_URL + '/wp-json/wp/v2/posts'
    auth = (WP_USER, WP_APP_PASSWORD)

    if parsed is None:
        log.warning("publish_to_wordpress called without parsed structure; skipping")
        return None, None, None, None, None

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
        return None, None, None, None, None
    if status == "malformed":
        log.warning("Skipping (Claude response malformed): %s", item['title'][:60])
        return None, None, None, None, None
    if status == "no_valid_country":
        log.warning("Skipping (Claude country %r not in registry): %s",
                    parsed.get("raw_country_line", ""), item['title'][:60])
        return None, None, None, None, None

    countries = parsed["countries"]
    etype = parsed.get("event_type", "Other")
    prayer = parsed.get("prayer", "")

    tag_ids = []
    for c in countries:
        cid = get_or_create_tag(c, auth)
        if cid:
            tag_ids.append(cid)
    type_tag_id = get_or_create_tag(etype, auth)
    if type_tag_id:
        tag_ids.append(type_tag_id)

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
        return post_id, post_link, _final_lat, _final_lng, post_date
    else:
        log.error('Publish failed (%s): %s', r.status_code, r.text[:300])
        return None, None, None, None, None


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
                log.info('Skipping (invalid): %s', item['title'][:60])
                seen.add(item['hash'])
                skipped += 1
                continue

            _result = publish_to_wordpress(item, article_body, parsed=parsed)
            post_id, post_link, lat, lng, post_date = _result

            if post_id:
                seen.add(item['hash'])
                published += 1

                if JSON_WRITER_AVAILABLE and not args.no_json:
                    countries = parsed.get("countries", []) if parsed else []
                    etype = parsed.get("event_type", "Other") if parsed else "Other"
                    prayer = parsed.get("prayer", "") if parsed else ""
                    structured_title = build_title(parsed, item) if parsed else item['title']
                    feed_body = html.unescape(article_body or "")
                    feed_prayer = _prayer_with_for(html.unescape(prayer or "").strip()) if prayer else ""
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
                    }
                    try:
                        gwm_json_writer.write_event(FEED_NAME, event)
                        json_writes += 1
                    except Exception as e:
                        log.error("JSON write_event failed for %s: %s",
                                  item['title'][:60], e)

                time.sleep(3)
            else:
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

    log.info('=== Done. Published %d, Skipped %d, JSON writes %d, Total %d ===',
             published, skipped, json_writes, len(candidates))


if __name__ == '__main__':
    main()
