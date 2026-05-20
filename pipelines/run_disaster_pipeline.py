#!/usr/bin/env python3
"""
Global Witness Monitor -- Natural Disaster Intelligence Pipeline v5

Changes from v4:
- Cross-run WP dedup. Before adding an article to the candidate list,
  check the last 30 days of WP posts in the disaster category and skip
  if title similarity >= 0.65 to an existing post. This prevents the
  same earthquake/hurricane/etc from being published 3-5 times when
  multiple outlets cover the same event.
- Matches the dedup pattern from conflict pipeline v6.
"""

import os
import re
import sys
import json
import time
import hashlib
import logging
import argparse
import requests
import feedparser
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
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
log = logging.getLogger(__name__)

if not JSON_WRITER_AVAILABLE:
    log.warning("gwm_json_writer.py not found in pipeline directory — "
                "JSON feeds will not be updated this run")

load_dotenv()

WP_URL          = os.environ["WP_URL"].rstrip("/")
WP_USER         = os.environ["WP_USER"]
WP_APP_PASSWORD = os.environ["WP_APP_PASSWORD"]
ANTHROPIC_KEY   = os.environ["ANTHROPIC_API_KEY"]
WP_CATEGORY_ID  = int(os.environ.get("WP_CATEGORY_ID", 38))
MAPBOX_TOKEN    = os.environ.get("MAPBOX_TOKEN", "")

SEEN_FILE    = "/opt/disaster-pipeline/data/seen_articles.json"
MAX_ARTICLES = 50
FEED_NAME    = "disasters"

REGIONS = {
    "middle-east": [
        "Iran", "Iraq", "Syria", "Yemen", "Israel", "Palestine", "Lebanon",
        "Jordan", "Saudi Arabia", "United Arab Emirates", "Qatar", "Kuwait",
        "Bahrain", "Oman", "Turkey", "Cyprus",
    ],
    "africa": [
        "Algeria", "Angola", "Benin", "Botswana", "Burkina Faso", "Burundi",
        "Cameroon", "Cape Verde", "Central African Republic", "Chad", "Comoros",
        "Congo", "Djibouti", "Egypt", "Equatorial Guinea", "Eritrea", "Eswatini",
        "Ethiopia", "Gabon", "Gambia", "Ghana", "Guinea", "Guinea-Bissau",
        "Ivory Coast", "Kenya", "Lesotho", "Liberia", "Libya", "Madagascar",
        "Malawi", "Mali", "Mauritania", "Mauritius", "Morocco", "Mozambique",
        "Namibia", "Niger", "Nigeria", "Rwanda", "Senegal", "Sierra Leone",
        "Somalia", "South Africa", "South Sudan", "Sudan", "Tanzania", "Togo",
        "Tunisia", "Uganda", "Zambia", "Zimbabwe",
    ],
    "asia": [
        "Afghanistan", "Bangladesh", "Bhutan", "Brunei", "Cambodia", "China",
        "India", "Indonesia", "Japan", "Kazakhstan", "Kyrgyzstan", "Laos",
        "Malaysia", "Maldives", "Mongolia", "Myanmar", "Nepal", "North Korea",
        "Pakistan", "Philippines", "Singapore", "South Korea", "Sri Lanka",
        "Taiwan", "Tajikistan", "Thailand", "Timor-Leste", "Turkmenistan",
        "Uzbekistan", "Vietnam",
    ],
    "europe": [
        "Albania", "Armenia", "Austria", "Azerbaijan", "Belarus", "Belgium",
        "Bosnia", "Bulgaria", "Croatia", "Czech Republic", "Denmark", "Estonia",
        "Finland", "France", "Georgia", "Germany", "Greece", "Hungary",
        "Iceland", "Ireland", "Italy", "Kosovo", "Latvia", "Lithuania",
        "Luxembourg", "Malta", "Moldova", "Montenegro", "Netherlands",
        "North Macedonia", "Norway", "Poland", "Portugal", "Romania", "Russia",
        "Serbia", "Slovakia", "Slovenia", "Spain", "Sweden", "Switzerland",
        "Ukraine", "United Kingdom",
    ],
    "americas": [
        "Argentina", "Bolivia", "Brazil", "Canada", "Chile", "Colombia",
        "Costa Rica", "Cuba", "Dominican Republic", "Ecuador", "El Salvador",
        "Guatemala", "Guyana", "Haiti", "Honduras", "Jamaica", "Mexico",
        "Nicaragua", "Panama", "Paraguay", "Peru", "Trinidad", "United States",
        "Uruguay", "Venezuela",
    ],
    "pacific": [
        "Australia", "Fiji", "New Zealand", "Papua New Guinea",
        "Solomon Islands", "Vanuatu", "Samoa", "Tonga",
    ],
}

ALL_COUNTRIES = []
for region_countries in REGIONS.values():
    ALL_COUNTRIES.extend(region_countries)
ALL_COUNTRIES = list(set(ALL_COUNTRIES))

RSS_FEEDS = [
    "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/significant_week.atom",
    "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_week.atom",
    "https://www.gdacs.org/xml/rss.xml",
    "https://reliefweb.int/updates/rss.xml",
    "https://feeds.reuters.com/reuters/worldNews",
    "https://feeds.apnews.com/rss/apf-worldnews",
    "https://feeds.bbci.co.uk/news/world/rss.xml",
    "https://www.aljazeera.com/xml/rss/all.xml",
    "https://rss.dw.com/rdf/rss-en-world",
    "https://news.un.org/feed/subscribe/en/news/all/rss.xml",
]

DISASTER_TERMS = [
    "earthquake", "quake", "seismic", "aftershock", "magnitude", "tremor",
    "richter", "tectonic", "fault line",
    "tsunami", "tidal wave",
    "flood", "flooding", "inundation", "deluge", "monsoon flooding",
    "flash flood", "river overflow", "dam burst", "levee breach",
    "hurricane", "typhoon", "cyclone", "tropical storm", "tropical depression",
    "tornado", "twister", "storm surge", "supercell", "derecho",
    "blizzard", "snowstorm", "ice storm", "hailstorm", "thunderstorm",
    "windstorm", "severe weather",
    "wildfire", "bushfire", "forest fire", "wildland fire", "brush fire",
    "blaze",
    "volcano", "volcanic", "eruption", "lava flow", "lava", "ash plume",
    "pyroclastic", "magma", "caldera",
    "landslide", "mudslide", "mudflow", "rockslide", "rock fall",
    "avalanche", "debris flow",
    "drought", "famine", "water crisis", "crop failure",
    "heatwave", "heat wave", "extreme heat", "cold snap", "freeze",
    "natural disaster", "catastrophe", "calamity", "disaster zone",
    "state of emergency", "emergency declared", "disaster declaration",
]

EVENT_SIGNALS = [
    "struck", "hit", "hits", "hitting",
    "killed", "kills", "dead", "death", "deaths", "dies", "died",
    "injured", "injuries", "wounded",
    "erupted", "erupting", "erupts",
    "flooded", "flooding", "floods", "submerged",
    "destroyed", "destroying", "destroys",
    "damaged", "damages",
    "swept", "sweeping", "sweeps",
    "evacuated", "evacuating", "evacuation", "evacuations", "evacuate",
    "displaced", "displaces", "displacement",
    "collapsed", "collapses", "collapsing",
    "buried", "burying",
    "toppled", "toppling",
    "burning", "burned", "burns", "scorched",
    "triggered", "triggers", "triggering",
    "recorded", "registered", "measured",
    "warn", "warns", "warning", "warned",
    "declared", "declares",
    "hospitalized", "hospitalised",
    "missing", "rescued", "rescue",
    "trapped", "stranded",
    "washed away", "submerged",
    "toll", "casualties", "fatalities",
    "leveled", "levelled", "flattened",
    "issued",
]

EXCLUDE_PATTERNS = [
    "what is a", "what are", "how does", "how would", "how to",
    "explained", "explainer", "analysis", "opinion",
    "what comes next", "what to expect", "what to know",
    "five things", "three things", "things to know",
    "in pictures", "in photos", "photo gallery",
    "quiz", "poll", "survey",
    "tributes to", "pays tribute", "pay tributes",
    "climate change explained", "understanding climate",
    "how to prepare", "how to survive", "preparedness guide",
    "live updates", "live blog", "live:",
    "could cause", "could trigger", "could lead to",
    "what if",
    "anniversary of",
]

DISASTER_TYPE_KEYWORDS = {
    "Earthquake": ["earthquake", "quake", "seismic", "aftershock", "magnitude",
                   "tremor", "richter", "tectonic"],
    "Tsunami":    ["tsunami", "tidal wave"],
    "Flood":      ["flood", "flooding", "inundation", "deluge", "monsoon flood",
                   "flash flood", "river overflow", "dam burst", "levee"],
    "Storm":      ["hurricane", "typhoon", "cyclone", "tropical storm",
                   "tropical depression", "tornado", "twister", "storm surge",
                   "blizzard", "ice storm", "snowstorm", "hailstorm",
                   "windstorm", "supercell", "derecho", "severe storm"],
    "Wildfire":   ["wildfire", "bushfire", "forest fire", "wildland fire",
                   "brush fire"],
    "Volcano":    ["volcano", "volcanic", "eruption", "lava", "ash plume",
                   "pyroclastic", "magma", "caldera"],
    "Landslide":  ["landslide", "mudslide", "mudflow", "rockslide",
                   "avalanche", "debris flow"],
    "Drought":    ["drought", "famine", "water crisis", "crop failure"],
    "Heatwave":   ["heatwave", "heat wave", "extreme heat"],
}


def detect_disaster_type(title, summary):
    text = (title + " " + summary).lower()
    priority = ["Tsunami", "Volcano", "Earthquake", "Wildfire",
                "Storm", "Flood", "Landslide", "Drought", "Heatwave"]
    for dtype in priority:
        for kw in DISASTER_TYPE_KEYWORDS[dtype]:
            if kw in text:
                return dtype
    return "Other"


TRUSTED_DISASTER_FEEDS = ("earthquake.usgs.gov", "gdacs.org")


def is_trusted_feed(feed_url):
    return any(domain in (feed_url or "") for domain in TRUSTED_DISASTER_FEEDS)


MAGNITUDE_PATTERN = re.compile(r"\bM\s?\d+\.\d+\b", re.IGNORECASE)


def is_relevant(title, summary):
    text = (title + " " + summary).lower()
    raw_text = title + " " + summary
    has_magnitude = bool(MAGNITUDE_PATTERN.search(raw_text))
    has_disaster = has_magnitude or any(t in text for t in DISASTER_TERMS)
    if not has_disaster:
        return False
    has_event = has_magnitude or any(s in text for s in EVENT_SIGNALS)
    if not has_event:
        return False
    title_lower = title.lower()
    for pattern in EXCLUDE_PATTERNS:
        if pattern in title_lower:
            return False
    return True


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
    "ivory coast": "Cote d'Ivoire", "cote divoire": "Cote d'Ivoire",
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


VALID_DISASTER_TYPES = {
    "earthquake", "flood", "storm", "wildfire", "volcano",
    "tsunami", "landslide", "drought", "heatwave", "other",
}


def validate_disaster_type(claude_type):
    if not claude_type or not isinstance(claude_type, str):
        return "Other"
    key = claude_type.strip().lower()
    if key in VALID_DISASTER_TYPES:
        return key.capitalize() if key != "other" else "Other"
    return "Other"


def parse_claude_response(raw_text):
    result = {
        "countries": [], "disaster_type": "Other",
        "location": "", "magnitude": "", "event_date": "",
        "prayer": "",
        "body": "", "raw_country_line": "", "status": "malformed",
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
    magnitude_line = None
    event_date_line = None
    pray_line = None
    body_start_idx = 0

    for i, line in enumerate(lines[:15]):
        stripped = line.strip()
        up = stripped.upper()
        if up.startswith("COUNTRY:"):
            country_line = stripped[len("COUNTRY:"):].strip()
            body_start_idx = max(body_start_idx, i + 1)
        elif up.startswith("DISASTER_TYPE:") or up.startswith("DISASTER TYPE:"):
            if up.startswith("DISASTER_TYPE:"):
                type_line = stripped[len("DISASTER_TYPE:"):].strip()
            else:
                type_line = stripped[len("DISASTER TYPE:"):].strip()
            body_start_idx = max(body_start_idx, i + 1)
        elif up.startswith("LOCATION:"):
            location_line = stripped[len("LOCATION:"):].strip()
            body_start_idx = max(body_start_idx, i + 1)
        elif up.startswith("MAGNITUDE:"):
            magnitude_line = stripped[len("MAGNITUDE:"):].strip()
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
        result["disaster_type"] = validate_disaster_type(type_line)
    if location_line and location_line.upper() != "UNKNOWN":
        result["location"] = location_line
    if magnitude_line and magnitude_line.upper() != "UNKNOWN":
        result["magnitude"] = magnitude_line
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


def extract_country(title, summary):
    text = (title + " " + summary).lower()
    sorted_countries = sorted(ALL_COUNTRIES, key=len, reverse=True)
    for country in sorted_countries:
        if country.lower() in text:
            return country
    demonyms = {
        "iranian": "Iran", "iraqi": "Iraq", "syrian": "Syria", "yemeni": "Yemen",
        "israeli": "Israel", "palestinian": "Palestine", "lebanese": "Lebanon",
        "afghan": "Afghanistan", "pakistani": "Pakistan", "indian": "India",
        "chinese": "China", "russian": "Russia", "ukrainian": "Ukraine",
        "sudanese": "Sudan", "ethiopian": "Ethiopia", "somali": "Somalia",
        "nigerian": "Nigeria", "kenyan": "Kenya", "congolese": "Congo",
        "malian": "Mali", "haitian": "Haiti", "venezuelan": "Venezuela",
        "colombian": "Colombia", "mexican": "Mexico", "brazilian": "Brazil",
        "burmese": "Myanmar", "filipino": "Philippines", "thai": "Thailand",
        "turkish": "Turkey", "egyptian": "Egypt", "libyan": "Libya",
        "tunisian": "Tunisia", "algerian": "Algeria", "moroccan": "Morocco",
        "japanese": "Japan", "indonesian": "Indonesia", "australian": "Australia",
        "american": "United States", "british": "United Kingdom",
        "french": "France", "german": "Germany", "spanish": "Spain",
        "italian": "Italy", "greek": "Greece", "portuguese": "Portugal",
        "canadian": "Canada", "taiwanese": "Taiwan",
    }
    for demonym, country in demonyms.items():
        if demonym in text:
            return country
    cities = {
        "tehran": "Iran", "baghdad": "Iraq", "damascus": "Syria",
        "gaza": "Palestine", "beirut": "Lebanon",
        "kabul": "Afghanistan", "islamabad": "Pakistan", "karachi": "Pakistan",
        "moscow": "Russia", "kyiv": "Ukraine",
        "khartoum": "Sudan", "addis ababa": "Ethiopia", "mogadishu": "Somalia",
        "lagos": "Nigeria", "nairobi": "Kenya",
        "port-au-prince": "Haiti", "caracas": "Venezuela",
        "tokyo": "Japan", "osaka": "Japan", "fukushima": "Japan",
        "manila": "Philippines", "bangkok": "Thailand",
        "istanbul": "Turkey", "cairo": "Egypt",
        "jakarta": "Indonesia", "sumatra": "Indonesia", "java": "Indonesia",
        "bali": "Indonesia", "sulawesi": "Indonesia",
        "los angeles": "United States", "california": "United States",
        "new york": "United States", "florida": "United States",
        "texas": "United States", "louisiana": "United States",
        "sydney": "Australia", "melbourne": "Australia",
        "queensland": "Australia", "new south wales": "Australia",
        "reykjavik": "Iceland", "naples": "Italy", "sicily": "Italy",
        "iceland": "Iceland",
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


def matches_type_filter(dtype, filter_types):
    if not filter_types:
        return True
    return dtype.lower() in [t.lower() for t in filter_types]


def title_similarity(title1, title2):
    words1 = set(title1.lower().split())
    words2 = set(title2.lower().split())
    stopwords = {"the", "a", "an", "in", "on", "at", "to", "for",
                 "of", "and", "or", "is", "are", "was", "were",
                 "with", "by", "from", "as", "it", "its", "be"}
    words1 = words1 - stopwords
    words2 = words2 - stopwords
    if not words1 or not words2:
        return 0.0
    return len(words1 & words2) / max(len(words1), len(words2))


def is_duplicate(title, existing_titles, threshold=0.75):
    for existing in existing_titles:
        if title_similarity(title, existing) >= threshold:
            return True
    return False


# ─── Cross-run WP dedup ──────────────────────────────────────────────
_RECENT_WP_TITLES_CACHE = None


def load_recent_wp_titles(days=30):
    """Fetch the last N days of WP post titles in the disaster category.
    Cached in-process so we only hit the WP REST API once per pipeline run."""
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
    """Check if a candidate title closely matches any title already in WP.
    Used to prevent the same disaster being republished across runs when
    multiple outlets cover it.

    Note: candidate titles from RSS feeds look like:
      'M 5.2 - 12 km W of Liuzhou, China'
      'M 6.0 - Strong earthquake hits Indonesia'

    But published WP titles look like:
      'Earthquake in China 05/18/2026 — Magnitude 5'

    Title-level similarity won't catch these directly. So we ALSO extract
    detected_country from the candidate item and do a country+type+date
    check by comparing tokenized titles after normalization."""
    recent = load_recent_wp_titles()
    for existing in recent:
        if title_similarity(candidate_title, existing) >= threshold:
            log.info("WP dedup match: %r ~ %r",
                     candidate_title[:60], existing[:60])
            return True
    return False


def is_duplicate_published_event(country, dtype, candidate_title):
    """Stronger dedup: build a normalized 'event signature' from country+type
    and check against recent WP titles. Most published WP titles start with
    '<DisasterType> in <Country>' so this catches the common case where
    multiple outlets cover the same earthquake/flood/etc.

    Returns True if a recent WP title matches the same country+type AND
    has reasonable token overlap with the candidate."""
    if not country or not dtype or dtype == "Other":
        return False
    recent = load_recent_wp_titles()
    # Build a search prefix: "<dtype> in <country>"
    expected_prefix = (dtype + " in " + country).lower()
    candidate_tokens = set(candidate_title.lower().split())
    stopwords = {"the", "a", "an", "in", "on", "at", "to", "for",
                 "of", "and", "or", "is", "are", "was", "were",
                 "with", "by", "from", "as", "it", "its", "be",
                 "magnitude", "earthquake", "quake", "flood", "storm",
                 "wildfire", "volcano", "tsunami", "landslide", "drought"}
    candidate_tokens -= stopwords
    for existing in recent:
        existing_lower = existing.lower()
        if existing_lower.startswith(expected_prefix):
            existing_tokens = set(existing_lower.split()) - stopwords
            if not candidate_tokens or not existing_tokens:
                continue
            overlap = len(candidate_tokens & existing_tokens)
            if overlap >= 1:
                log.info("WP event-sig dedup match: %r matches existing %r (country=%s type=%s)",
                         candidate_title[:60], existing[:60], country, dtype)
                return True
    return False


def load_seen():
    if os.path.exists(SEEN_FILE):
        try:
            with open(SEEN_FILE, "r") as f:
                return set(json.load(f))
        except Exception:
            return set()
    return set()


def save_seen(seen):
    os.makedirs(os.path.dirname(SEEN_FILE), exist_ok=True)
    seen_list = list(seen)[-2000:]
    with open(SEEN_FILE, "w") as f:
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


def normalize_gdacs_severity(title):
    if not title:
        return title
    for color in ("Green ", "Orange ", "Red "):
        if title.startswith(color):
            return title[len(color):]
    return title


def extract_coords(entry):
    try:
        where = entry.get("where") if hasattr(entry, "get") else None
        if isinstance(where, dict):
            coords = where.get("coordinates")
            if coords and len(coords) >= 2:
                lon, lat = float(coords[0]), float(coords[1])
                return lat, lon
    except Exception:
        pass
    try:
        lat = entry.get("geo_lat") if hasattr(entry, "get") else None
        lng = entry.get("geo_long") if hasattr(entry, "get") else None
        if lat and lng:
            return float(lat), float(lng)
    except Exception:
        pass
    try:
        pt = entry.get("georss_point") if hasattr(entry, "get") else None
        if pt and isinstance(pt, str):
            parts = pt.strip().split()
            if len(parts) >= 2:
                return float(parts[0]), float(parts[1])
    except Exception:
        pass
    return None, None


def fetch_rss_feeds(seen, filter_countries, filter_types):
    candidates = []
    seen_titles = []
    for feed_url in RSS_FEEDS:
        log.info("Fetching RSS: %s", feed_url)
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:30]:
                title = entry.get("title", "").strip()
                summary = entry.get("summary", entry.get("description", "")).strip()
                title = normalize_gdacs_severity(title)
                url = entry.get("link", "")
                if not title or not url:
                    continue
                h = article_hash(url, title)
                if h in seen:
                    continue
                if not is_trusted_feed(feed_url) and not is_relevant(title, summary):
                    continue
                country = extract_country(title, summary)
                if not matches_filter(country, filter_countries):
                    continue
                dtype = detect_disaster_type(title, summary)
                if not matches_type_filter(dtype, filter_types):
                    continue
                if is_duplicate(title, seen_titles):
                    log.info("Skipping duplicate: %s", title[:60])
                    continue
                # Cross-run WP dedup
                if is_duplicate_of_existing_wp(title):
                    log.info("Skipping (already in WP recently): %s", title[:60])
                    continue
                if country and is_duplicate_published_event(country, dtype, title):
                    log.info("Skipping (matches recent WP event signature): %s",
                             title[:60])
                    continue
                lat, lng = extract_coords(entry)
                candidates.append({
                    "title": title, "summary": summary, "url": url,
                    "hash": h,
                    "source": feed.feed.get("title", feed_url),
                    "published": entry.get("published", ""),
                    "country": country, "disaster_type": dtype,
                    "lat": lat, "lng": lng,
                })
                seen_titles.append(title)
        except Exception as e:
            log.warning("RSS feed error (%s): %s", feed_url, e)
    log.info("RSS: found %d relevant unseen articles", len(candidates))
    return candidates


def fetch_gdelt(seen, existing_titles, filter_countries, filter_types):
    log.info("Fetching GDELT...")
    candidates = []
    query_terms = [
        "earthquake magnitude killed",
        "flood flooding evacuated displaced",
        "hurricane typhoon cyclone landfall",
        "wildfire bushfire destroyed evacuated",
        "volcano eruption ash evacuated",
        "tsunami warning struck",
        "landslide mudslide buried killed",
    ]
    for query in query_terms:
        try:
            url = (
                "https://api.gdeltproject.org/api/v2/doc/doc"
                "?query=" + requests.utils.quote(query) +
                "&mode=artlist&maxrecords=10&timespan=24h"
                "&sort=DateDesc&format=json"
            )
            r = requests.get(url, timeout=15)
            if r.status_code == 429:
                log.warning("GDELT rate limited (429). Stopping.")
                break
            if r.status_code != 200:
                log.warning("GDELT returned %s", r.status_code)
                time.sleep(5)
                continue
            data = r.json()
            for article in data.get("articles", []):
                title = article.get("title", "").strip()
                url_art = article.get("url", "")
                source = article.get("domain", "GDELT")
                if not title or not url_art:
                    continue
                h = article_hash(url_art, title)
                if h in seen:
                    continue
                if not is_relevant(title, ""):
                    continue
                country = extract_country(title, "")
                if not matches_filter(country, filter_countries):
                    continue
                dtype = detect_disaster_type(title, "")
                if not matches_type_filter(dtype, filter_types):
                    continue
                if is_duplicate(title, existing_titles):
                    continue
                # Cross-run WP dedup
                if is_duplicate_of_existing_wp(title):
                    log.info("GDELT skip (already in WP recently): %s", title[:60])
                    continue
                if country and is_duplicate_published_event(country, dtype, title):
                    log.info("GDELT skip (matches recent WP event signature): %s",
                             title[:60])
                    continue
                candidates.append({
                    "title": title, "summary": title, "url": url_art,
                    "hash": h, "source": source,
                    "published": article.get("seendate", ""),
                    "country": country, "disaster_type": dtype,
                    "lat": None, "lng": None,
                })
                existing_titles.append(title)
            time.sleep(5)
        except Exception as e:
            log.warning("GDELT error: %s", e)
    log.info("GDELT: found %d additional articles", len(candidates))
    return candidates


def fetch_all_feeds(seen, filter_countries, filter_types):
    rss_candidates = fetch_rss_feeds(seen, filter_countries, filter_types)
    rss_titles = [c["title"] for c in rss_candidates]
    gdelt_candidates = fetch_gdelt(seen, rss_titles, filter_countries, filter_types)
    all_candidates = rss_candidates + gdelt_candidates
    log.info("Total candidates: %d", len(all_candidates))
    return all_candidates[:MAX_ARTICLES]


SYSTEM_PROMPT = """You are writing brief, plain-language natural disaster reports for the general public on Global Witness Monitor. Mission agencies, churches, and field workers read these reports to stay aware of conditions where they serve.

REQUIRED OUTPUT FORMAT — every response must begin with exactly these header lines:

COUNTRY: <primary country where the event physically occurred>
DISASTER_TYPE: <Earthquake|Flood|Storm|Wildfire|Volcano|Tsunami|Landslide|Drought|Heatwave|Other>
LOCATION: <most specific named place from the source: city, town, region, or "UNKNOWN" if no specific place is named>
MAGNITUDE: <numeric magnitude rounded to nearest whole number for earthquakes (e.g. "6"); category number for hurricanes (e.g. "Cat 4"); "UNKNOWN" if not applicable or unknown>
EVENT_DATE: <event date in MM/DD/YYYY format, "UNKNOWN" if not stated in the source>
PRAYER: <one short prayer prompt sentence related to this event; do NOT begin with the word "Pray"; just write what to pray for, e.g. "those who lost homes and the rescuers searching the rubble" or "displaced families and aid teams reaching cut-off areas">
---

Then the article body follows on the next line.

WRITING STYLE — VERY IMPORTANT:
- Plain language for general public. NO technical jargon.
- DO NOT mention: Modified Mercalli Intensity, MMI, MMI scale, intensity level, GDACS, Global Disaster Alert and Coordination System, USGS, "Mission Note", "Field teams should...", or any boilerplate operational language.
- DO NOT round depths to three decimal places. Round depth to the nearest whole kilometer ("about 73 kilometers deep") or describe it qualitatively ("shallow", "deep").
- DO NOT include exposure estimates like "30,000 in MMI VI" or "740 thousand in MMI IV". If the source mentions how many people felt strong shaking, just say it plainly: "tens of thousands of people felt strong shaking".
- DO NOT include UTC times in the body. Use plain dates and approximate times only if essential.
- Length: 100-180 words.
- Two or three short paragraphs. Use blank lines between paragraphs (the WordPress editor will turn those into proper paragraph spacing).
- Do not include personal names; use "a man", "a woman", "residents", "officials", "rescuers".
- Do not include the source URL in the body.
- Do not include a title. Body only.
- End naturally — no Mission Note, no Field Teams advisory, no boilerplate.
- DO NOT include the prayer line in the body. The PRAYER: field at the top of the header is the only place the prayer appears.

COUNTRY field rules:
- Country where the event physically occurred, NOT the news outlet's country.
- For events affecting multiple countries: COUNTRY: MULTIPLE: Country1, Country2
- For events in international waters or unknown: COUNTRY: UNKNOWN
- Use common country names: "Japan", "United States", "United Kingdom", "Myanmar", "Congo".
- Do NOT include state/province names.

LOCATION field rules:
- Most specific named place mentioned in the source.
- Do NOT include the country.
- If no specific place is named, output LOCATION: UNKNOWN.

DISASTER_TYPE field:
- Primary event type only.
- Use Other if truly unclassifiable.

MAGNITUDE field:
- For earthquakes: integer like "6" (round 6.0, 5.8, 6.2 all to "6"). If decimal is meaningful (e.g. 5.0 vs 5.5), keep one decimal: "5.5".
- For hurricanes: "Cat 4".
- For other disaster types or when unknown: UNKNOWN.

EVENT_DATE field:
- MM/DD/YYYY format. Use the date the event occurred, not when it was reported.
- UNKNOWN if not in source.

PRAY field:
- One sentence, specific to this event.
- Focus on victims, displaced families, rescue and aid workers, those in damage paths, or similar concrete needs.
- Do not assign blame or make political statements.

Only respond with SKIP_NO_EVENT if the source is pure opinion, commentary, or an explainer with no factual event reported."""


BAD_RESPONSE_PATTERNS = [
    "i cannot write", "i cannot provide",
    "i am unable to", "skip_no_event",
]


def is_valid_article(article_body):
    lower = article_body.lower()
    for pattern in BAD_RESPONSE_PATTERNS:
        if pattern in lower:
            return False
    return len(article_body.split()) >= 60


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
        text = " ".join(text.split())
        return text[:max_chars]
    except Exception as e:
        log.info("body fetch failed for %s: %s", url[:60], e)
        return ""


def generate_article(item):
    client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
    body_text = fetch_article_body(item["url"])
    body_section = ""
    if body_text:
        log.info("fetched %d chars of article body", len(body_text))
        body_section = "SOURCE BODY TEXT:\n" + body_text + "\n\n"
    user_prompt = (
        "Write a plain-language natural disaster report based only on the source material below. "
        "Follow the header format and writing style rules from the system prompt exactly.\n\n"
        "SOURCE TITLE: " + item["title"] + "\n\n"
        "SOURCE SUMMARY: " + item["summary"] + "\n\n"
        + body_section +
        "SOURCE URL: " + item["url"] + "\n\n"
        "SOURCE OUTLET: " + item["source"] + "\n\n"
        "DETECTED DISASTER TYPE: " + item.get("disaster_type", "Other") + "\n\n"
        "Use only facts present in the source material above."
    )
    log.info("Generating article for: %s", item["title"][:70])
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=800,
        messages=[{"role": "user", "content": user_prompt}],
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
                if feat_country and (
                    hint_lower == feat_country
                    or hint_lower in feat_country
                    or feat_country in hint_lower
                ):
                    return lat, lng
                continue
            else:
                return lat, lng
        return None, None
    except Exception as e:
        log.warning("Mapbox geocode error for %r: %s", location, e)
        return None, None


def get_or_create_tag(name, auth):
    try:
        r = requests.get(WP_URL + "/wp-json/wp/v2/tags",
                         params={"search": name, "per_page": 20},
                         auth=auth, timeout=15)
        existing = r.json() if r.status_code == 200 else []
        for tag in existing:
            if tag.get("name", "").strip().lower() == name.strip().lower():
                return tag["id"]
        r2 = requests.post(WP_URL + "/wp-json/wp/v2/tags",
                           json={"name": name}, auth=auth, timeout=15)
        if r2.status_code in (200, 201):
            return r2.json()["id"]
    except Exception as e:
        log.warning("Tag error for %s: %s", name, e)
    return None


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
    dtype = parsed.get("disaster_type", "Other") or "Other"
    countries = parsed.get("countries") or []
    country = countries[0] if countries else (item.get("country") or "")
    magnitude = (parsed.get("magnitude") or "").strip()
    event_date_us = _to_us_date(parsed.get("event_date"))
    if not event_date_us:
        event_date_us = _to_us_date(item.get("published"))

    parts = [dtype]
    if country:
        parts.append("in " + country)
    if event_date_us:
        parts.append(event_date_us)
    base = " ".join(parts)
    if magnitude and magnitude.upper() != "UNKNOWN":
        if dtype == "Earthquake":
            base += " \u2014 Magnitude " + magnitude
        else:
            base += " \u2014 " + magnitude
    return base


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


def format_body_for_wordpress(body_text, prayer=""):
    """Wrap paragraphs in <p> tags. Optionally append styled Prayer line."""
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
        cleaned.append(
            '<p class="gwm-prayer-line"><strong>Prayer:</strong> ' + pr + '</p>'
        )
    return "\n\n".join(cleaned)


def publish_to_wordpress(item, article_body, parsed=None):
    endpoint = WP_URL + "/wp-json/wp/v2/posts"
    auth = (WP_USER, WP_APP_PASSWORD)

    detected_country = item.get("country")
    detected_dtype = item.get("disaster_type", "Other")

    if parsed is None:
        log.warning("publish_to_wordpress called without parsed structure; skipping")
        return None, None, None, None, None

    status = parsed.get("status", "malformed")
    log.info(
        "CLAUDE_VS_DETECTED: claude_country=%s claude_type=%s detected_country=%s detected_type=%s status=%s raw=%r",
        ",".join(parsed.get("countries", [])) or "-",
        parsed.get("disaster_type", "Other"),
        detected_country or "-", detected_dtype, status,
        parsed.get("raw_country_line", ""),
    )

    if status == "unknown":
        log.info("Skipping (UNKNOWN): %s", item["title"][:60])
        return None, None, None, None, None
    if status == "malformed":
        log.warning("Skipping (malformed): %s", item["title"][:60])
        return None, None, None, None, None
    if status == "no_valid_country":
        log.warning("Skipping (no_valid_country %r): %s",
                    parsed.get("raw_country_line", ""), item["title"][:60])
        return None, None, None, None, None

    if not parsed.get("location"):
        log.info("Skipping (no location): %s", item["title"][:60])
        return None, None, None, None, None

    countries = parsed["countries"]
    dtype = parsed["disaster_type"]
    prayer = parsed.get("prayer", "")

    # Second-stage WP dedup after Claude classifies — now we have the
    # canonical structured title to compare. This catches cases where
    # the source title was vague but the published title resolved to
    # something already in WP.
    candidate_published_title = build_title(parsed, item)
    if is_duplicate_of_existing_wp(candidate_published_title):
        log.info("Skipping (post-Claude WP dedup match): %s",
                 candidate_published_title[:60])
        return None, None, None, None, None

    tag_ids = []
    for c in countries:
        cid = get_or_create_tag(c, auth)
        if cid:
            tag_ids.append(cid)
    type_tag_id = get_or_create_tag(dtype, auth)
    if type_tag_id:
        tag_ids.append(type_tag_id)

    structured_title = build_title(parsed, item)
    clean_title = sanitize_title(structured_title)

    _final_lat = None
    _final_lng = None
    _claude_loc = parsed.get("location")
    _country_hint = countries[0] if countries else None
    if _claude_loc:
        _glat, _glng = geocode_mapbox(_claude_loc, _country_hint)
        if _glat is not None and _glng is not None:
            _final_lat = _glat
            _final_lng = _glng
            log.info("Geocoded %r in %r -> %.4f, %.4f",
                     _claude_loc, _country_hint, _glat, _glng)
    if _final_lat is None:
        _ilat = item.get("lat")
        _ilng = item.get("lng")
        if isinstance(_ilat, (int, float)) and isinstance(_ilng, (int, float)):
            _final_lat = _ilat
            _final_lng = _ilng

    _lat_str = ("%.4f" % _final_lat) if isinstance(_final_lat, (int, float)) else ""
    _lng_str = ("%.4f" % _final_lng) if isinstance(_final_lng, (int, float)) else ""
    meta_div = (
        '<div class="gwm-disaster-meta"'
        ' data-country="' + (countries[0] if countries else "") + '"'
        ' data-type="' + dtype + '"'
        ' data-lat="' + _lat_str + '"'
        ' data-lng="' + _lng_str + '"'
        ' style="display:none;"></div>\n'
    )

    formatted_body = format_body_for_wordpress(article_body, prayer)
    final_content = meta_div + formatted_body

    payload = {
        "title": clean_title,
        "content": final_content,
        "status": "publish",
        "categories": [WP_CATEGORY_ID],
        "tags": tag_ids,
    }

    r = requests.post(endpoint, json=payload, auth=auth, timeout=30)
    if r.status_code in (200, 201):
        post = r.json()
        post_id = post.get("id")
        post_link = post.get("link")
        post_date = post.get("date_gmt") or post.get("date") or ""
        log.info("Published: %s [%s / %s] (ID %s) prayer=%s",
                 clean_title[:60], countries[0], dtype, post_id,
                 "yes" if prayer else "no")
        # Add the just-published title to the cache so subsequent items
        # in this run can see it.
        if _RECENT_WP_TITLES_CACHE is not None:
            _RECENT_WP_TITLES_CACHE.append(clean_title)
        return post_id, post_link, _final_lat, _final_lng, post_date
    else:
        log.error("Publish failed (%s): %s", r.status_code, r.text[:300])
        return None, None, None, None, None


def parse_args():
    parser = argparse.ArgumentParser(description="GWM Disaster Pipeline v5")
    parser.add_argument("--region", "-r", action="append",
                        choices=list(REGIONS.keys()),
                        help="Filter by region")
    parser.add_argument("--country", "-c", action="append",
                        help="Filter by specific country")
    parser.add_argument("--type", "-t", action="append",
                        help="Filter by disaster type")
    parser.add_argument("--list-regions", action="store_true",
                        help="List all regions")
    parser.add_argument("--no-json", action="store_true",
                        help="Skip JSON feed update (publish to WP only)")
    return parser.parse_args()


def build_country_filter(args):
    if args.list_regions:
        print("\nAvailable regions:\n")
        for region, countries in REGIONS.items():
            print("  " + region + ":")
            print("    " + ", ".join(countries) + "\n")
        sys.exit(0)
    filter_countries = []
    if args.region:
        for region in args.region:
            filter_countries.extend(REGIONS[region])
    if args.country:
        for country in args.country:
            normalized = " ".join(w.capitalize() for w in country.split())
            filter_countries.append(normalized)
    return list(set(filter_countries)) if filter_countries else None


def main():
    args = parse_args()
    filter_countries = build_country_filter(args)
    filter_types = args.type if args.type else None

    label_parts = []
    if filter_countries:
        label_parts.append(str(len(filter_countries)) + " countries")
    if filter_types:
        label_parts.append("types: " + ",".join(filter_types))
    label = " | ".join(label_parts) if label_parts else "GLOBAL"

    log.info("=== Disaster Pipeline v5 starting (%s) ===", label)

    seen = load_seen()
    candidates = fetch_all_feeds(seen, filter_countries, filter_types)
    if not candidates:
        log.info("No new relevant articles found. Done.")
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
                log.info("Skipping (invalid): %s", item["title"][:60])
                seen.add(item["hash"])
                skipped += 1
                continue

            _result = publish_to_wordpress(item, article_body, parsed=parsed)
            post_id, post_link, lat, lng, post_date = _result

            if post_id:
                seen.add(item["hash"])
                published += 1

                if JSON_WRITER_AVAILABLE and not args.no_json:
                    countries = parsed.get("countries", []) if parsed else []
                    dtype = parsed.get("disaster_type", "Other") if parsed else "Other"
                    prayer = parsed.get("prayer", "") if parsed else ""
                    structured_title = build_title(parsed, item) if parsed else item["title"]
                    event = {
                        "wp_id": post_id,
                        "wp_link": post_link,
                        "date": post_date or datetime.now(timezone.utc).isoformat(),
                        "title": sanitize_title(structured_title),
                        "body": article_body,
                        "country": countries[0] if countries else "",
                        "countries": countries,
                        "type": dtype,
                        "lat": lat,
                        "lng": lng,
                        "source_title": item.get("source", ""),
                        "source_url": item.get("url", ""),
                        "prayer": prayer,
                    }
                    try:
                   
                      gwm_json_writer.write_event(FEED_NAME, event)
                      
                      json_writes += 1
                    except Exception as e:
                        log.error("JSON write_event failed for %s: %s",
                                  item["title"][:60], e)

                time.sleep(3)
            else:
                seen.add(item["hash"])
                skipped += 1

        except Exception as e:
            log.error("Error processing %s: %s", item["title"][:60], e)
            continue

    save_seen(seen)
if JSON_WRITER_AVAILABLE and not args.no_json and json_writes > 0:
    try:
        log.info("Pushing %d new events to GitHub JSON feeds...", json_writes)
        written = gwm_json_writer.finalize(FEED_NAME)
        log.info("JSON feed updated: active=%s archives=%s",
                 written.get("active"),
                 ",".join(written.get("archives", [])))
        purge_jsdelivr("disasters.json")
    except Exception as e:
        log.error("JSON finalize failed: %s", e)

    log.info("=== Done. Published %d, Skipped %d, JSON writes %d, Total %d ===",
                 published, skipped, json_writes, len(candidates))




if __name__ == "__main__":
    main()
