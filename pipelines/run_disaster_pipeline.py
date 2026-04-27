#!/usr/bin/env python3
"""
Global Witness Monitor -- Natural Disaster Intelligence Pipeline v1
- Publishes disaster intelligence briefs to WordPress category 38
- Tags posts by country AND by disaster type
- RSS + GDELT coverage
- Stricter event-based filtering (actual disasters, not explainers)
- Dedup via hash + title similarity

Run examples:
  # Full global run (manual)
  cd /opt/disaster-pipeline && set -a && source .env && set +a && venv/bin/python run_disaster_pipeline.py

  # Filter by disaster type
  venv/bin/python run_disaster_pipeline.py --type earthquake
  venv/bin/python run_disaster_pipeline.py --type flood --type storm

  # Filter by region
  venv/bin/python run_disaster_pipeline.py --region asia

  # Filter by country
  venv/bin/python run_disaster_pipeline.py --country Japan --country Philippines
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

# -- LOGGING --
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
log = logging.getLogger(__name__)

# -- CONFIG --
load_dotenv()

WP_URL          = os.environ["WP_URL"].rstrip("/")
WP_USER         = os.environ["WP_USER"]
WP_APP_PASSWORD = os.environ["WP_APP_PASSWORD"]
ANTHROPIC_KEY   = os.environ["ANTHROPIC_API_KEY"]
WP_CATEGORY_ID  = int(os.environ.get("WP_CATEGORY_ID", 38))
MAPBOX_TOKEN    = os.environ.get("MAPBOX_TOKEN", "")

SEEN_FILE    = "/opt/disaster-pipeline/data/seen_articles.json"
MAX_ARTICLES = 50

# -- REGIONS (same as conflict pipeline for consistency) --
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

# -- RSS SOURCES (disaster-focused) --
RSS_FEEDS = [
    # USGS earthquake feeds (machine-readable, very clean)
    "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/significant_week.atom",
    "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_week.atom",
    # GDACS -- Global Disaster Alert and Coordination System
    "https://www.gdacs.org/xml/rss.xml",
    # ReliefWeb updates (broader humanitarian but catches major disasters)
    "https://reliefweb.int/updates/rss.xml",
    # Mainstream world news (catches major disasters)
    "https://feeds.reuters.com/reuters/worldNews",
    "https://feeds.apnews.com/rss/apf-worldnews",
    "https://feeds.bbci.co.uk/news/world/rss.xml",
    "https://www.aljazeera.com/xml/rss/all.xml",
    "https://rss.dw.com/rdf/rss-en-world",
    # UN news
    "https://news.un.org/feed/subscribe/en/news/all/rss.xml",
]

# -- DISASTER TERMS (must have at least one) --
DISASTER_TERMS = [
    # Earthquakes
    "earthquake", "quake", "seismic", "aftershock", "magnitude", "tremor",
    "richter", "tectonic", "fault line",
    # Tsunamis
    "tsunami", "tidal wave",
    # Floods
    "flood", "flooding", "inundation", "deluge", "monsoon flooding",
    "flash flood", "river overflow", "dam burst", "levee breach",
    # Storms / cyclones
    "hurricane", "typhoon", "cyclone", "tropical storm", "tropical depression",
    "tornado", "twister", "storm surge", "supercell", "derecho",
    "blizzard", "snowstorm", "ice storm", "hailstorm", "thunderstorm",
    "windstorm", "severe weather",
    # Wildfires
    "wildfire", "bushfire", "forest fire", "wildland fire", "brush fire",
    "blaze",
    # Volcanoes
    "volcano", "volcanic", "eruption", "lava flow", "lava", "ash plume",
    "pyroclastic", "magma", "caldera",
    # Landslides / mudflows
    "landslide", "mudslide", "mudflow", "rockslide", "rock fall",
    "avalanche", "debris flow",
    # Droughts / famine
    "drought", "famine", "water crisis", "crop failure",
    # Heat / cold
    "heatwave", "heat wave", "extreme heat", "cold snap", "freeze",
    # General
    "natural disaster", "catastrophe", "calamity", "disaster zone",
    "state of emergency", "emergency declared", "disaster declaration",
]

# -- EVENT SIGNALS (must have at least one to be an actual event) --
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

# -- EXCLUDE PATTERNS (opinion, explainers, non-events) --
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

# -- DISASTER TYPE DETECTION --
DISASTER_TYPE_KEYWORDS = {
    "Earthquake": [
        "earthquake", "quake", "seismic", "aftershock", "magnitude",
        "tremor", "richter", "tectonic",
    ],
    "Tsunami": [
        "tsunami", "tidal wave",
    ],
    "Flood": [
        "flood", "flooding", "inundation", "deluge", "monsoon flood",
        "flash flood", "river overflow", "dam burst", "levee",
    ],
    "Storm": [
        "hurricane", "typhoon", "cyclone", "tropical storm", "tropical depression",
        "tornado", "twister", "storm surge", "blizzard", "ice storm",
        "snowstorm", "hailstorm", "windstorm", "supercell", "derecho",
        "severe storm",
    ],
    "Wildfire": [
        "wildfire", "bushfire", "forest fire", "wildland fire", "brush fire",
    ],
    "Volcano": [
        "volcano", "volcanic", "eruption", "lava", "ash plume",
        "pyroclastic", "magma", "caldera",
    ],
    "Landslide": [
        "landslide", "mudslide", "mudflow", "rockslide", "avalanche",
        "debris flow",
    ],
    "Drought": [
        "drought", "famine", "water crisis", "crop failure",
    ],
    "Heatwave": [
        "heatwave", "heat wave", "extreme heat",
    ],
}

def detect_disaster_type(title, summary):
    """Return the best-matching disaster type label, or 'Other'."""
    text = (title + " " + summary).lower()
    # Check in priority order -- earthquake/tsunami/volcano are most specific
    priority = ["Tsunami", "Volcano", "Earthquake", "Wildfire",
                "Storm", "Flood", "Landslide", "Drought", "Heatwave"]
    for dtype in priority:
        keywords = DISASTER_TYPE_KEYWORDS[dtype]
        for kw in keywords:
            if kw in text:
                return dtype
    return "Other"

# Feeds whose items are inherently disaster events -- skip keyword/signal filters
TRUSTED_DISASTER_FEEDS = (
    "earthquake.usgs.gov",
    "gdacs.org",
)

def is_trusted_feed(feed_url):
    return any(domain in (feed_url or "") for domain in TRUSTED_DISASTER_FEEDS)

MAGNITUDE_PATTERN = re.compile(r"\bM\s?\d+\.\d+\b", re.IGNORECASE)

def is_relevant(title, summary):
    """Check if article is relevant AND is an actual event (not opinion/explainer)."""
    text = (title + " " + summary).lower()
    raw_text = title + " " + summary  # preserve case for regex

    # Magnitude pattern auto-qualifies (e.g. "M 5.2", "M7.4")
    has_magnitude = bool(MAGNITUDE_PATTERN.search(raw_text))

    has_disaster = has_magnitude or any(term in text for term in DISASTER_TERMS)
    if not has_disaster:
        return False

    has_event = has_magnitude or any(signal in text for signal in EVENT_SIGNALS)
    if not has_event:
        return False

    title_lower = title.lower()
    for pattern in EXCLUDE_PATTERNS:
        if pattern in title_lower:
            return False

    return True

# -- CANONICAL COUNTRY REGISTRY --
# Built lazily from ALL_COUNTRIES plus known aliases so we can validate
# Claude's returned country string against a single source of truth.
CANONICAL_COUNTRY_MAP = None  # populated on first use

# Manual aliases for common country-name variations Claude might produce
_COUNTRY_ALIASES = {
    "burma": "Myanmar",
    "burma (myanmar)": "Myanmar",
    "myanmar (burma)": "Myanmar",
    "timor-leste": "Timor Leste",
    "east timor": "Timor Leste",
    "dr congo": "Congo",
    "d.r. congo": "Congo",
    "drc": "Congo",
    "democratic republic of the congo": "Congo",
    "democratic republic of congo": "Congo",
    "republic of the congo": "Congo",
    "north korea": "North Korea",
    "south korea": "South Korea",
    "korea, north": "North Korea",
    "korea, south": "South Korea",
    "czech republic": "Czechia",
    "ivory coast": "Cote d'Ivoire",
    "cote divoire": "Cote d'Ivoire",
    "cabo verde": "Cape Verde",
    "uae": "United Arab Emirates",
    "uk": "United Kingdom",
    "britain": "United Kingdom",
    "great britain": "United Kingdom",
    "usa": "United States",
    "u.s.": "United States",
    "u.s.a.": "United States",
    "america": "United States",
    "vatican": "Vatican City",
    "holy see": "Vatican City",
    "palestinian territories": "Palestine",
    "gaza": "Palestine",
    "west bank": "Palestine",
    "state of palestine": "Palestine",
}


def _build_country_map():
    """Build lookup map from normalized name -> canonical name. Idempotent."""
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


def _normalize_country_key(s):
    """Lowercase, strip punctuation, collapse whitespace."""
    if not s:
        return ""
    s = s.lower().strip()
    # Remove common punctuation
    for ch in [".", ",", "(", ")", "-", "'", '"']:
        s = s.replace(ch, " ")
    # Collapse whitespace
    s = " ".join(s.split())
    return s


def validate_country(claude_country):
    """Validate Claude's country string against canonical registry.
    Returns canonical country name or None."""
    if not claude_country or not isinstance(claude_country, str):
        return None
    key = _normalize_country_key(claude_country)
    if not key:
        return None
    m = _build_country_map()
    return m.get(key)


VALID_DISASTER_TYPES = {
    "earthquake", "flood", "storm", "wildfire", "volcano",
    "tsunami", "landslide", "drought", "heatwave", "other",
}


def validate_disaster_type(claude_type):
    """Validate Claude's disaster type. Returns canonical Title-Case
    string or 'Other' if invalid."""
    if not claude_type or not isinstance(claude_type, str):
        return "Other"
    key = claude_type.strip().lower()
    if key in VALID_DISASTER_TYPES:
        return key.capitalize() if key != "other" else "Other"
    return "Other"


def parse_claude_response(raw_text):
    """Parse Claude's structured response.

    Expected format:
        COUNTRY: <country name | MULTIPLE: c1, c2 | UNKNOWN>
        DISASTER_TYPE: <type>
        ---
        <article body...>

    Returns dict with keys:
        countries: list of canonical country names (may be empty)
        disaster_type: canonical disaster type string
        body: article body text with header stripped
        raw_country_line: what Claude actually wrote (for logging)
        status: "ok" | "unknown" | "malformed" | "no_valid_country"
    """
    result = {
        "countries": [],
        "disaster_type": "Other",
        "location": "",
        "body": "",
        "raw_country_line": "",
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
    body_start_idx = 0

    # Scan first ~8 lines for header fields
    for i, line in enumerate(lines[:10]):
        stripped = line.strip()
        up = stripped.upper()
        if up.startswith("COUNTRY:"):
            country_line = stripped[len("COUNTRY:"):].strip()
            body_start_idx = max(body_start_idx, i + 1)
        elif up.startswith("DISASTER_TYPE:") or up.startswith("DISASTER TYPE:"):
            # accept either spelling
            if up.startswith("DISASTER_TYPE:"):
                type_line = stripped[len("DISASTER_TYPE:"):].strip()
            else:
                type_line = stripped[len("DISASTER TYPE:"):].strip()
            body_start_idx = max(body_start_idx, i + 1)
        elif up.startswith("LOCATION:"):
            location_line = stripped[len("LOCATION:"):].strip()
            body_start_idx = max(body_start_idx, i + 1)
        elif stripped == "---":
            body_start_idx = max(body_start_idx, i + 1)

    # Skip blank lines and separator after header
    while body_start_idx < len(lines) and (
        not lines[body_start_idx].strip() or lines[body_start_idx].strip() == "---"
    ):
        body_start_idx += 1

    result["body"] = "\n".join(lines[body_start_idx:]).strip()
    result["raw_country_line"] = country_line or ""

    # Parse disaster_type
    if type_line:
        result["disaster_type"] = validate_disaster_type(type_line)

    # Parse location (may be UNKNOWN; geocoding handles that)
    if location_line and location_line.upper() != "UNKNOWN":
        result["location"] = location_line

    # Parse country line
    if not country_line:
        result["status"] = "malformed"
        return result

    up = country_line.upper()
    if up == "UNKNOWN":
        result["status"] = "unknown"
        return result

    if up.startswith("MULTIPLE:") or up.startswith("MULTIPLE "):
        # Parse comma-separated list
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

    # Single country
    c = validate_country(country_line)
    if c:
        result["countries"] = [c]
        result["status"] = "ok"
    else:
        result["status"] = "no_valid_country"
    return result


# -- COUNTRY EXTRACTION --
def extract_country(title, summary):
    """Extract country from title/summary. Returns None if no country found."""
    text = (title + " " + summary).lower()

    # Longest-first to handle "South Sudan" vs "Sudan"
    sorted_countries = sorted(ALL_COUNTRIES, key=len, reverse=True)
    for country in sorted_countries:
        if country.lower() in text:
            return country

    # Demonyms
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

    # Major cities
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
        "reykjavik": "Iceland",
        "naples": "Italy", "sicily": "Italy",
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

# -- SIMILARITY CHECK --
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
    overlap = len(words1 & words2)
    return overlap / max(len(words1), len(words2))

def is_duplicate(title, existing_titles, threshold=0.75):
    for existing in existing_titles:
        if title_similarity(title, existing) >= threshold:
            return True
    return False

# -- SEEN ARTICLES --
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

def article_hash(url, title):
    return hashlib.md5((url + title).encode()).hexdigest()

# -- FETCH RSS FEEDS --
# GDACS uses color-coded severity prefixes (Green/Orange/Red) in titles.
# Replace with plain-English severity for readability.
def normalize_gdacs_severity(title):
    """Strip GDACS color-code severity prefixes (Green/Orange/Red) from titles.
    GDACS feeds prefix titles with severity color codes which aren't useful in the
    intelligence-brief context."""
    if not title:
        return title
    for color in ("Green ", "Orange ", "Red "):
        if title.startswith(color):
            return title[len(color):]
    return title


def extract_coords(entry):
    """Return (lat, lng) floats from a feedparser entry, or (None, None).

    Supports:
      - GeoRSS Simple: entry.where = {"type":"Point","coordinates":(lon,lat)} (USGS)
      - GeoRSS W3C: entry.geo_lat / entry.geo_long
      - GeoRSS plain: entry.georss_point = "lat lon"
    """
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
                title   = entry.get("title", "").strip()
                summary = entry.get("summary", entry.get("description", "")).strip()
                title = normalize_gdacs_severity(title)

                url     = entry.get("link", "")

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

                lat, lng = extract_coords(entry)
                candidates.append({
                    "title":        title,
                    "summary":      summary,
                    "url":          url,
                    "hash":         h,
                    "source":       feed.feed.get("title", feed_url),
                    "published":    entry.get("published", ""),
                    "country":      country,
                    "disaster_type": dtype,
                    "lat":          lat,
                    "lng":          lng,
                })
                seen_titles.append(title)

        except Exception as e:
            log.warning("RSS feed error (%s): %s", feed_url, e)

    log.info("RSS: found %d relevant unseen articles", len(candidates))
    return candidates

# -- FETCH GDELT --
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
                "&mode=artlist"
                "&maxrecords=10"
                "&timespan=24h"
                "&sort=DateDesc"
                "&format=json"
            )
            r = requests.get(url, timeout=15)
            if r.status_code == 429:
                log.warning("GDELT rate limited (429). Stopping GDELT for this run.")
                break
            if r.status_code != 200:
                log.warning("GDELT returned %s", r.status_code)
                time.sleep(5)
                continue

            data = r.json()
            articles = data.get("articles", [])

            for article in articles:
                title   = article.get("title", "").strip()
                url_art = article.get("url", "")
                source  = article.get("domain", "GDELT")

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
                    log.info("GDELT duplicate skip: %s", title[:60])
                    continue

                candidates.append({
                    "title":         title,
                    "summary":       title,
                    "url":           url_art,
                    "hash":          h,
                    "source":        source,
                    "published":     article.get("seendate", ""),
                    "country":       country,
                    "disaster_type": dtype,
                    "lat":           None,
                    "lng":           None,
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

# -- CLAUDE ARTICLE GENERATION --
SYSTEM_PROMPT = """You are an intelligence analyst for Global Witness Monitor, a platform serving
mission agencies, churches, and field workers who need accurate situational awareness for
deployment and safety decisions.

Your task is to write a factual natural disaster intelligence brief based strictly on the provided
source material.

REQUIRED OUTPUT FORMAT -- every response must begin with exactly this 3-line header:

COUNTRY: <primary country where the event physically occurred>
DISASTER_TYPE: <Earthquake|Flood|Storm|Wildfire|Volcano|Tsunami|Landslide|Drought|Heatwave|Other>
LOCATION: <most specific named place from the source: city, town, region, or "UNKNOWN" if no specific place is named>
---

Then the article body follows on the next line.

COUNTRY field rules:
- Return the country where the event PHYSICALLY OCCURRED, not where the news outlet is based.
- Ignore outlet names in the source material (e.g. "Pakistan Today", "Japan Times", "BBC").
- Ignore subject demonyms unrelated to event location (e.g. "Vietnamese in Japan earthquake" -- the
  event is in Japan, not Vietnam).
- For events affecting multiple countries: COUNTRY: MULTIPLE: Country1, Country2
- For events in international waters, Antarctica, or uncountryable regions: COUNTRY: UNKNOWN
- Use common country names: "Japan", "United States", "United Kingdom", "Myanmar", "Congo".
- Do NOT include state/province names (write "India" not "Manipur"; "United States" not "California").
- Do NOT include continents or regions (write "UNKNOWN" for "Southeast Asia floods" without a
  specific country, UNLESS one country is clearly the primary location).

LOCATION field rules:
- Return the most specific named place mentioned in the source material.
- Examples: "Petropavlovsk-Kamchatsky", "Kerala", "Mocoa, Putumayo", "Mount Etna".
- Do NOT include the country in the LOCATION value (the COUNTRY field captures that).
- For events spanning a wide region with no specific place, use the most specific
  region name (e.g. "Sichuan Province", "Eastern Java").
- If no specific place is named in the source, output LOCATION: UNKNOWN.

DISASTER_TYPE field rules:
- Return the PRIMARY event type, not secondary consequences.
- "Tsunami advisory lifted after Japan earthquake" -> DISASTER_TYPE: Earthquake (earthquake is
  the event; tsunami was a warning response).
- "Earthquake triggers tsunami" -> DISASTER_TYPE: Earthquake unless the tsunami itself caused
  the main damage reported.
- If truly unclassifiable, use DISASTER_TYPE: Other.

If you cannot identify a valid country with reasonable confidence from the source material, output
COUNTRY: UNKNOWN. Do not guess. Missing data is better than wrong data.

CRITICAL RULES:
- Base every claim strictly on the provided source material. Do not invent names, statistics,
  casualty figures, magnitudes, locations, or any other details not present in the source.
- Write in a factual, measured intelligence-briefing tone -- not sensational, not emotionally charged.
- The audience is mission professionals who need accurate, actionable information about regional
  safety, infrastructure status, and humanitarian conditions.
- Structure: lead with the key facts (what happened, where, scale), provide context,
  note implications for field operations, travel, and affected communities where relevant.
- Do NOT editorialize about climate policy, government response, or assign blame beyond what
  sources state.
- Length: 75-200 words.
- When names of people are mentioned in the source material, do not include them; refer to them
  as "a man", "a woman", "residents", "officials", "rescuers", etc.
- Do not include the source URL at the bottom of the article. You may attribute information
  inline using phrases like "according to local authorities" or "reports indicate".
- Do not include a title in your response -- only the article body.
- End with a one-sentence Mission Note: summarizing the operational significance for field workers
  (e.g., travel impact, infrastructure damage, humanitarian access concerns). Put this on it's own line apart from the paragraph. Do not put astriks next to it (no *).

IMPORTANT: Only respond with SKIP_NO_EVENT if the source is pure opinion, commentary, or an
explainer with no factual event reported. If the source mentions an actual disaster event -- even
with minimal detail like location, magnitude, or date -- write a concise brief using ONLY the
facts present. When details are sparse, use hedging attribution like "initial reports indicate"
or "according to the source" and keep the brief shorter (80-150 words is acceptable when source
material is thin). Do NOT invent details to hit a word count. A short, honest brief based on
limited confirmed facts is more valuable than no brief at all.

Only use SKIP_NO_EVENT for:
  - Pure opinion columns with no reported event
  - "What to know" / "Explainer" / "How X works" pieces
  - Pieces where the disaster is only mentioned in passing as context for a non-event story
  - Duplicates of news you've already covered (not your concern to detect -- pipeline handles it)"""

BAD_RESPONSE_PATTERNS = [
    "i cannot write",
    "i cannot provide",
    "i am unable to",
    "skip_no_event",
]

def is_valid_article(article_body):
    lower = article_body.lower()
    for pattern in BAD_RESPONSE_PATTERNS:
        if pattern in lower:
            return False
    word_count = len(article_body.split())
    if word_count < 60:
        return False
    return True


# -- ARTICLE BODY FETCHER --
def fetch_article_body(url, max_chars=4000):
    """Fetch article HTML and extract readable body text. Returns empty string on failure."""
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        log.warning("beautifulsoup4 not installed; skipping body fetch")
        return ""

    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (compatible; GlobalWitnessMonitor/1.0; "
                "+https://globalwitnessmonitor.com/)"
            )
        }
        r = requests.get(url, headers=headers, timeout=12)
        if r.status_code != 200:
            return ""

        ct = r.headers.get("content-type", "").lower()
        if "html" not in ct:
            return ""

        soup = BeautifulSoup(r.text, "html.parser")

        # Strip script, style, nav, header, footer, aside
        for tag in soup(["script", "style", "nav", "header", "footer", "aside", "form"]):
            tag.decompose()

        # Prefer <article> if present, otherwise <main>, otherwise body
        node = soup.find("article") or soup.find("main") or soup.body
        if not node:
            return ""

        # Collect paragraph text
        paragraphs = [p.get_text(" ", strip=True) for p in node.find_all("p")]
        text = " ".join(p for p in paragraphs if len(p) > 30)  # skip nav junk

        if not text:
            # fallback: all text
            text = node.get_text(" ", strip=True)

        # Normalize whitespace
        text = " ".join(text.split())
        return text[:max_chars]

    except Exception as e:
        log.info("body fetch failed for %s: %s", url[:60], e)
        return ""


def generate_article(item):
    client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)

    # Attempt to fetch full article body for richer context
    body_text = fetch_article_body(item["url"])
    body_section = ""
    if body_text:
        log.info("fetched %d chars of article body", len(body_text))
        body_section = "SOURCE BODY TEXT:\n" + body_text + "\n\n"

    user_prompt = (
        "Write a natural disaster intelligence brief based on this source material only.\n\n"
        "SOURCE TITLE: " + item["title"] + "\n\n"
        "SOURCE SUMMARY: " + item["summary"] + "\n\n"
        + body_section +
        "SOURCE URL: " + item["url"] + "\n\n"
        "SOURCE OUTLET: " + item["source"] + "\n\n"
        "DETECTED DISASTER TYPE: " + item.get("disaster_type", "Other") + "\n\n"
        "Use only facts present in the source material above. Prefer the SOURCE BODY TEXT when "
        "available for specific numbers, locations, and quotes. If the content is pure opinion "
        "or a non-event explainer with no reported disaster, respond with SKIP_NO_EVENT."
    )

    log.info("Generating article for: %s", item["title"][:70])

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=600,
        messages=[{"role": "user", "content": user_prompt}],
        system=SYSTEM_PROMPT,
    )

    raw_response = message.content[0].text.strip()
    parsed = parse_claude_response(raw_response)
    return raw_response, parsed

# -- GEOCODING --
def geocode_mapbox(location, country_hint=None):
    """Forward-geocode a place name via Mapbox.

    Args:
        location: a place name string (e.g. "Petropavlovsk-Kamchatsky").
        country_hint: canonical country name from Claude (e.g. "Russia").
            If provided, the returned feature MUST be in this country, or
            the result is rejected.

    Returns (lat, lng) floats, or (None, None) on failure / mismatch.
    """
    if not location or not MAPBOX_TOKEN:
        return None, None

    try:
        url = (
            "https://api.mapbox.com/geocoding/v5/mapbox.places/"
            + requests.utils.quote(location.strip())
            + ".json"
        )
        params = {
            "access_token": MAPBOX_TOKEN,
            "limit": 5,
            "types": "place,locality,region,district,country,neighborhood,address",
        }
        r = requests.get(url, params=params, timeout=10)
        if r.status_code != 200:
            log.warning("Mapbox returned %s for %r", r.status_code, location)
            return None, None

        features = (r.json() or {}).get("features", [])
        if not features:
            return None, None

        # Try each feature in relevance order; accept first whose country
        # context matches the hint. If no hint, accept the top result.
        hint_lower = (country_hint or "").strip().lower() if country_hint else None
        for feat in features:
            center = feat.get("center")
            if not center or len(center) < 2:
                continue
            lng, lat = float(center[0]), float(center[1])

            # Mapbox encodes country in place_type or context
            feat_country = ""
            if feat.get("place_type") == ["country"] or "country" in (feat.get("place_type") or []):
                feat_country = (feat.get("text") or "").lower()
            for ctx in (feat.get("context") or []):
                if isinstance(ctx, dict) and (ctx.get("id", "").startswith("country.")):
                    feat_country = (ctx.get("text") or "").lower()

            if hint_lower:
                # Accept country match OR partial overlap (e.g. "Russia" vs "Russian Federation")
                if feat_country and (
                    hint_lower == feat_country
                    or hint_lower in feat_country
                    or feat_country in hint_lower
                ):
                    return lat, lng
                # No country context at all -- skip rather than risk wrong placement
                continue
            else:
                return lat, lng

        log.info("Mapbox: no feature matched country hint %r for %r",
                 country_hint, location)
        return None, None

    except Exception as e:
        log.warning("Mapbox geocode error for %r: %s", location, e)
        return None, None


# -- WORDPRESS PUBLISH --
def get_or_create_tag(name, auth):
    """Return the tag ID for a given tag name, creating it if missing."""
    try:
        r = requests.get(
            WP_URL + "/wp-json/wp/v2/tags",
            params={"search": name, "per_page": 20},
            auth=auth,
            timeout=15,
        )
        existing = r.json() if r.status_code == 200 else []
        # Match must be exact (case-insensitive) -- search is fuzzy
        for tag in existing:
            if tag.get("name", "").strip().lower() == name.strip().lower():
                return tag["id"]

        # Create
        r2 = requests.post(
            WP_URL + "/wp-json/wp/v2/tags",
            json={"name": name},
            auth=auth,
            timeout=15,
        )
        if r2.status_code in (200, 201):
            return r2.json()["id"]
        else:
            log.warning("Tag create failed for %s (%s): %s",
                        name, r2.status_code, r2.text[:200])
            return None
    except Exception as e:
        log.warning("Tag lookup/create error for %s: %s", name, e)
        return None

def sanitize_title(title):
    """Decode HTML entities, replace en/em dashes with commas, ensure spacing
    after common labels like Depth: and Magnitude:."""
    if not title:
        return title
    t = html.unescape(title)
    t = t.replace("\u2013", ", ").replace("\u2014", ", ")
    # Add space after Depth:N or Magnitude:N if missing (USGS quirk)
    t = re.sub(r"(Depth|Magnitude|Mag):\s*(\d)", r"\1: \2", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t
  
def publish_to_wordpress(item, article_body, parsed=None):
    endpoint = WP_URL + "/wp-json/wp/v2/posts"
    auth     = (WP_USER, WP_APP_PASSWORD)

    # Use Claude-parsed country and disaster type as authoritative values.
    # Fall back to item-level detected values ONLY for the audit log comparison.
    detected_country = item.get("country")
    detected_dtype   = item.get("disaster_type", "Other")

    if parsed is None:
        # Old code path (should not occur after this patch)
        log.warning("publish_to_wordpress called without parsed structure; skipping")
        return False

    status = parsed.get("status", "malformed")

    # Audit log: show Claude vs title-scan divergence for every article
    log.info(
        "CLAUDE_VS_DETECTED: claude_country=%s claude_type=%s detected_country=%s detected_type=%s status=%s raw=%r",
        ",".join(parsed.get("countries", [])) or "-",
        parsed.get("disaster_type", "Other"),
        detected_country or "-",
        detected_dtype,
        status,
        parsed.get("raw_country_line", ""),
    )

    if status == "unknown":
        log.info("Skipping (Claude marked UNKNOWN): %s", item["title"][:60])
        return False
    if status == "malformed":
        log.warning("Skipping (Claude response malformed): %s", item["title"][:60])
        return False
    if status == "no_valid_country":
        log.warning(
            "Skipping (Claude country %r did not match registry): %s",
            parsed.get("raw_country_line", ""), item["title"][:60],
        )
        return False

    countries = parsed["countries"]
    dtype = parsed["disaster_type"]
    country = countries[0]  # primary country for logging

    tag_ids = []
    for c in countries:
        cid = get_or_create_tag(c, auth)
        if cid:
            tag_ids.append(cid)
    type_tag_id = get_or_create_tag(dtype, auth)
    if type_tag_id:
        tag_ids.append(type_tag_id)

    # Sanitize title (decode HTML entities, replace en/em dashes with commas)
    clean_title = sanitize_title(item["title"])

    # Build hidden meta div for dashboard type/country detection.
    # Coordinate priority: (1) Claude location -> Mapbox geocode,
    # (2) RSS feed-supplied coords (USGS/GDACS), (3) empty -> dashboard centroid.
    _final_lat = None
    _final_lng = None

    _claude_loc = parsed.get("location") if isinstance(parsed, dict) else None
    _country_hint = countries[0] if countries else None
    if _claude_loc:
        _glat, _glng = geocode_mapbox(_claude_loc, _country_hint)
        if _glat is not None and _glng is not None:
            _final_lat = _glat
            _final_lng = _glng
            log.info("Geocoded %r in %r -> %.4f, %.4f",
                     _claude_loc, _country_hint, _glat, _glng)
        else:
            log.info("Geocode failed for %r in %r", _claude_loc, _country_hint)

    if _final_lat is None or _final_lng is None:
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
    final_content = meta_div + article_body

    payload = {
        "title":      clean_title,
        "content":    final_content,
        "status":     "publish",
        "categories": [WP_CATEGORY_ID],
        "tags":       tag_ids,
    }

    r = requests.post(endpoint, json=payload, auth=auth, timeout=30)

    if r.status_code in (200, 201):
        post = r.json()
        log.info("Published: %s [%s / %s] (ID %s)",
                 item["title"][:50], country, dtype, post.get("id"))
        return True
    else:
        log.error("Publish failed (%s): %s", r.status_code, r.text[:300])
        return False

# -- ARGUMENT PARSING --
def parse_args():
    parser = argparse.ArgumentParser(
        description="GWM Natural Disaster Pipeline v1",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_disaster_pipeline.py                           # Global, all types
  python run_disaster_pipeline.py --type earthquake         # Earthquakes only
  python run_disaster_pipeline.py --region asia             # Asia only
  python run_disaster_pipeline.py --country Japan           # Japan only
  python run_disaster_pipeline.py --type flood --type storm # Floods + storms
        """
    )

    parser.add_argument(
        "--region", "-r",
        action="append",
        choices=list(REGIONS.keys()),
        help="Filter by region (can specify multiple)"
    )
    parser.add_argument(
        "--country", "-c",
        action="append",
        help="Filter by specific country (can specify multiple)"
    )
    parser.add_argument(
        "--type", "-t",
        action="append",
        help="Filter by disaster type: earthquake, flood, storm, wildfire, volcano, tsunami, landslide, drought, heatwave"
    )
    parser.add_argument(
        "--list-regions",
        action="store_true",
        help="List all regions and their countries"
    )

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

    filter_countries = list(set(filter_countries)) if filter_countries else None
    return filter_countries

# -- MAIN --
def main():
    args = parse_args()
    filter_countries = build_country_filter(args)
    filter_types = args.type if args.type else None

    label_parts = []
    if filter_countries:
        label_parts.append(str(len(filter_countries)) + " countries")
    if filter_types:
        label_parts.append("types: " + ",".join(filter_types))
    label = " | ".join(label_parts) if label_parts else "GLOBAL - all countries and types"

    log.info("=== Disaster Pipeline v1 starting (%s) ===", label)

    seen       = load_seen()
    candidates = fetch_all_feeds(seen, filter_countries, filter_types)

    if not candidates:
        log.info("No new relevant articles found. Done.")
        return

    published = 0
    skipped   = 0

    for item in candidates:
        try:
            _gen_result = generate_article(item)
            if isinstance(_gen_result, tuple):
                raw_response, parsed = _gen_result
            else:
                raw_response, parsed = _gen_result, None
            article_body = parsed["body"] if (parsed and parsed.get("body")) else raw_response


            if not is_valid_article(article_body):
                log.info("Skipping (invalid/refused): %s", item["title"][:60])
                seen.add(item["hash"])
                skipped += 1
                continue

            success = publish_to_wordpress(item, article_body, parsed=parsed)

            if success:
                seen.add(item["hash"])
                published += 1
                time.sleep(3)
            else:
                seen.add(item["hash"])
                skipped += 1

        except Exception as e:
            log.error("Error processing %s: %s", item["title"][:60], e)
            continue

    save_seen(seen)
    log.info("=== Done. Published %d, Skipped %d, Total %d ===",
             published, skipped, len(candidates))

if __name__ == "__main__":
    main()
