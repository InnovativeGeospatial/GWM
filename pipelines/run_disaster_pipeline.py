#!/usr/bin/env python3
"""
Global Witness Monitor -- Natural Disaster Intelligence Pipeline v5
- Disease outbreak support via WHO Disease Outbreak News
- Cross-run WP dedup
- Structured titles, prayer field, EVENT_DATE, MAGNITUDE
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
    log.warning("gwm_json_writer.py not found in pipeline directory")

load_dotenv()

WP_URL          = os.environ["WP_URL"].rstrip("/")
WP_USER         = os.environ["WP_USER"]
WP_APP_PASSWORD = os.environ["WP_APP_PASSWORD"]
ANTHROPIC_KEY   = os.environ["ANTHROPIC_API_KEY"]
WP_CATEGORY_ID  = int(os.environ.get("WP_CATEGORY_ID", 38))
MAPBOX_TOKEN    = os.environ.get("MAPBOX_TOKEN", "")

SEEN_FILE    = "/opt/disaster-pipeline/data/seen_articles.json"
MAX_ARTICLES = 320          # final hard safety ceiling (sum of budgets below)
# Per-source budgets: guaranteed slots so no single feed crowds out the others.
# CAP gets the largest share (it's the global official-alert firehose); the rest
# keep a floor. Raise/lower these to trade coverage against run time + API cost.
USGS_BUDGET  = 60
CAP_BUDGET   = 150
RSS_BUDGET   = 60
GDELT_BUDGET = 40

# Earthquakes below this magnitude are dropped (editable). Raise to 5.5 or 6.0
# to thin seismic coverage further.
MIN_EARTHQUAKE_MAGNITUDE = 5.0

# USGS earthquakes are pulled as GeoJSON (stable event id + magnitude +
# coordinates) instead of the old .atom feeds -- this is what kills the
# title-based earthquake duplicates. See fetch_usgs().
USGS_GEOJSON_FEEDS = [
    "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/significant_week.geojson",
    "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_week.geojson",
]
FEED_NAME    = "disasters"

def _gwm_is_suppressed(event):
    """True if this event matches a suppression entry recorded by prune_feed.py.
    Same country+type, within the entry's day window, and (broad => country+type
    +window alone; else coords within 0.75deg OR title similarity >= 0.50).
    Fails open (returns False) on any error so it can never block all events."""
    import os, json
    from datetime import datetime, timezone
    from difflib import SequenceMatcher
    try:
        path = "/opt/conflict-pipeline/suppressed_" + FEED_NAME + ".json"
        if not os.path.exists(path):
            return False
        with open(path, encoding="utf-8") as _f:
            entries = json.load(_f)
        if not isinstance(entries, list) or not entries:
            return False
        ec = (event.get("country") or "").strip().lower()
        et = (event.get("type") or "").strip().lower()
        etitle = (event.get("title") or "").strip().lower()
        try:
            elat = float(event.get("lat")); elng = float(event.get("lng")); have = True
        except (TypeError, ValueError):
            elat = elng = 0.0; have = False
        now = datetime.now(timezone.utc)
        for s in entries:
            if (s.get("country") or "").strip().lower() != ec:
                continue
            if (s.get("type") or "").strip().lower() != et:
                continue
            added = s.get("added")
            if added:
                try:
                    a = datetime.fromisoformat(str(added).replace("Z", "+00:00"))
                    if a.tzinfo is None:
                        a = a.replace(tzinfo=timezone.utc)
                    if (now - a).days > int(s.get("window_days", 21)):
                        continue
                except Exception:
                    pass
            if s.get("broad"):
                return True
            try:
                if have and s.get("lat") is not None and s.get("lng") is not None:
                    if abs(float(s["lat"]) - elat) <= 0.75 and abs(float(s["lng"]) - elng) <= 0.75:
                        return True
            except (TypeError, ValueError):
                pass
            st = (s.get("title") or "").strip().lower()
            if st and etitle and SequenceMatcher(None, st, etitle).ratio() >= 0.50:
                return True
        return False
    except Exception:
        return False


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

def _gnews(query, freshness="when:3d"):
    """Google News RSS search-feed URL for a targeted query. Fills non-quake
    coverage gaps (floods, fires, storms, outbreaks) from regional outlets the
    curated feeds miss. Links are redirect shells -- fetch_article_body()
    resolves or falls back to the summary."""
    return ("https://news.google.com/rss/search?q="
            + requests.utils.quote(query + " " + freshness)
            + "&hl=en-US&gl=US&ceid=US:en")

GOOGLE_NEWS_QUERIES = [
    "flood OR flooding deaths OR displaced OR evacuated",
    "wildfire OR bushfire evacuation OR destroyed",
    "cyclone OR hurricane OR typhoon landfall OR damage",
    "landslide OR mudslide killed OR buried",
    "volcano eruption OR ashfall OR evacuate",
    "disease outbreak OR cholera OR ebola OR measles OR mpox",
    "drought OR famine emergency OR crisis",
    "tornado OR storm damage OR killed",
]

# Earthquakes now come from USGS_GEOJSON_FEEDS (fetch_usgs). These RSS feeds
# cover everything else. USGS .atom and the dead Reuters feed were removed.
RSS_FEEDS = [
    "https://www.gdacs.org/xml/rss.xml",
    "https://www.who.int/feeds/entity/csr/don/en/rss.xml",
    "https://reliefweb.int/updates/rss.xml",
    "https://feeds.apnews.com/rss/apf-worldnews",
    "https://feeds.bbci.co.uk/news/world/rss.xml",
    "https://www.aljazeera.com/xml/rss/all.xml",
    "https://rss.dw.com/rdf/rss-en-world",
    "https://news.un.org/feed/subscribe/en/news/all/rss.xml",
    # --- regional aggregators added 2026-06-28: widen small-country coverage ---
    "https://www.thenewhumanitarian.org/rss/all.xml",
    "https://allafrica.com/tools/headlines/rdf/africa/headlines.rdf",
    "https://globalvoices.org/feed/",
] + [_gnews(q) for q in GOOGLE_NEWS_QUERIES]

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
    "outbreak", "epidemic", "pandemic", "virus", "viral", "infection",
    "infectious disease", "disease outbreak", "cases of", "infected with",
    "cholera", "ebola", "marburg", "mpox", "monkeypox", "measles", "polio",
    "yellow fever", "dengue", "lassa fever", "diphtheria", "anthrax",
    "plague", "meningitis", "h5n1", "avian flu", "bird flu", "swine flu",
    "rift valley fever", "crimean-congo", "chikungunya", "zika",
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
    "infected", "sickened", "diagnosed", "confirmed cases", "cases reported",
    "spreading", "outbreak", "epidemic",
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
    "Disease":    ["outbreak", "epidemic", "pandemic", "disease outbreak",
                   "cholera", "ebola", "marburg", "mpox", "monkeypox",
                   "measles", "polio", "yellow fever", "dengue", "lassa",
                   "diphtheria", "anthrax", "plague", "meningitis", "h5n1",
                   "avian flu", "bird flu", "swine flu", "rift valley fever",
                   "crimean-congo", "chikungunya", "zika",
                   "infectious disease"],
}


def detect_disaster_type(title, summary):
    text = (title + " " + summary).lower()
    priority = ["Disease", "Tsunami", "Volcano", "Earthquake", "Wildfire",
                "Storm", "Flood", "Landslide", "Drought", "Heatwave"]
    for dtype in priority:
        for kw in DISASTER_TYPE_KEYWORDS[dtype]:
            if kw in text:
                return dtype
    return "Other"


TRUSTED_DISASTER_FEEDS = ("earthquake.usgs.gov", "gdacs.org", "who.int")


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
    "tsunami", "landslide", "drought", "heatwave", "disease", "other",
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
        "prayer": "", "alert_summary": "",
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
    alert_summary_line = None
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
    """Convert spelled-out numbers to digits so '31' and 'thirty-one' match."""
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


def is_duplicate_published_event(country, dtype, candidate_title):
    if not country or not dtype or dtype == "Other":
        return False
    recent = load_recent_wp_titles()
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
                log.info("WP event-sig dedup match: %r ~ %r (country=%s type=%s)",
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


_MAG_PATTERNS = [
    re.compile(r"magnitude\s*([0-9]+(?:\.[0-9]+)?)", re.IGNORECASE),
    re.compile(r"\bM\s?([0-9]+\.[0-9]+)", re.IGNORECASE),
    re.compile(r"\b([0-9]+\.[0-9]+)\s*M\b"),
]


def extract_magnitude(text):
    """Pull a numeric earthquake magnitude from free text, or None."""
    if not text:
        return None
    for pat in _MAG_PATTERNS:
        m = pat.search(text)
        if m:
            try:
                v = float(m.group(1))
                if 0.0 < v <= 10.0:
                    return v
            except ValueError:
                pass
    return None


def _eq_signatures(country, lat, lng, mag):
    """Identity keys for an earthquake so the same event from different sources
    and title formats collapses to one. Returns coordinate- and country-based
    signature strings to register/check."""
    sigs = []
    magpart = ("%.1f" % mag) if isinstance(mag, (int, float)) else "?"
    try:
        if lat is not None and lng is not None:
            sigs.append("EQ|%.1f|%.1f|%s" % (round(float(lat), 1),
                                             round(float(lng), 1), magpart))
    except (TypeError, ValueError):
        pass
    if country:
        sigs.append("EQ|%s|%s" % (str(country).lower(), magpart))
    return sigs


def fetch_usgs(seen, filter_countries, filter_types):
    """Earthquakes from USGS GeoJSON feeds: applies the magnitude floor and
    dedups by stable USGS event id (across the two feeds and across runs)."""
    candidates = []
    run_ids = set()
    if not matches_type_filter("Earthquake", filter_types):
        return candidates
    for feed_url in USGS_GEOJSON_FEEDS:
        log.info("Fetching USGS GeoJSON: %s", feed_url)
        try:
            r = requests.get(feed_url, timeout=20,
                             headers={"User-Agent": "GlobalWitnessMonitor/1.0"})
            if r.status_code != 200:
                log.warning("USGS feed %s -> %s", feed_url, r.status_code)
                continue
            features = (r.json() or {}).get("features", [])
            for feat in features:
                props = feat.get("properties") or {}
                geom = feat.get("geometry") or {}
                usgs_id = feat.get("id") or props.get("code") or ""
                if not usgs_id:
                    continue
                if ("USGS:" + usgs_id) in seen or usgs_id in run_ids:
                    continue
                mag = props.get("mag")
                try:
                    mag = float(mag) if mag is not None else None
                except (TypeError, ValueError):
                    mag = None
                if mag is None or mag < MIN_EARTHQUAKE_MAGNITUDE:
                    continue
                place = (props.get("place") or "").strip()
                coords = geom.get("coordinates") or []
                lat = lng = None
                if len(coords) >= 2:
                    try:
                        lng, lat = float(coords[0]), float(coords[1])
                    except (TypeError, ValueError):
                        lat = lng = None
                country = extract_country(place, "") if place else None
                if not matches_filter(country, filter_countries):
                    continue
                title = "M %.1f earthquake" % mag + ((" - " + place) if place else "")
                url = props.get("url") or (
                    "https://earthquake.usgs.gov/earthquakes/eventpage/" + usgs_id)
                summary = place + ((" (magnitude %.1f)" % mag) if mag else "")
                published = ""
                try:
                    t = props.get("time")
                    if t:
                        published = datetime.fromtimestamp(
                            t / 1000.0, timezone.utc).isoformat()
                except Exception:
                    published = ""
                run_ids.add(usgs_id)
                candidates.append({
                    "title": title, "summary": summary, "url": url,
                    "hash": article_hash(url, title),
                    "source": "USGS", "published": published,
                    "country": country, "disaster_type": "Earthquake",
                    "lat": lat, "lng": lng,
                    "usgs_id": usgs_id, "magnitude": mag,
                })
        except Exception as e:
            log.warning("USGS fetch error (%s): %s", feed_url, e)
    log.info("USGS: %d earthquakes >= M%.1f after id-dedup",
             len(candidates), MIN_EARTHQUAKE_MAGNITUDE)
    return candidates


def _dedup_earthquakes(candidates, seen):
    """Cross-source earthquake collapse + magnitude floor for non-USGS quakes.
    USGS items are processed first so their authoritative coords/magnitude
    define the signature; later news/GDACS reports of the same quake drop."""
    out = []
    run_sigs = set()
    ordered = sorted(candidates, key=lambda c: 0 if c.get("usgs_id") else 1)
    for c in ordered:
        if (c.get("disaster_type") or "") != "Earthquake":
            out.append(c)
            continue
        mag = c.get("magnitude")
        if mag is None:
            mag = extract_magnitude((c.get("title") or "") + " "
                                    + (c.get("summary") or ""))
        if mag is not None and mag < MIN_EARTHQUAKE_MAGNITUDE:
            log.info("Drop sub-floor quake (M%.1f): %s", mag,
                     (c.get("title") or "")[:60])
            continue
        sigs = _eq_signatures(c.get("country"), c.get("lat"),
                              c.get("lng"), mag)
        if any((sg in seen) or (sg in run_sigs) for sg in sigs):
            log.info("Drop duplicate quake: %s", (c.get("title") or "")[:60])
            continue
        for sg in sigs:
            run_sigs.add(sg)
        c["_eq_sigs"] = sigs
        out.append(c)
    return out


CAP_ENDPOINT   = "https://alerthub-api.ifrc.org/graphql/"
CAP_WINDOW_HOURS = 48           # only alerts sent within this window
CAP_PAGE_LIMIT   = 100          # alerts per GraphQL page
CAP_MAX_PAGES    = 5            # safety cap (=> up to 500 alerts/run)
CAP_SEVERITIES   = ["EXTREME", "SEVERE"]
CAP_URGENCIES    = ["IMMEDIATE", "EXPECTED"]
CAP_CATEGORIES   = ["GEO", "MET", "FIRE", "HEALTH", "ENV"]
# Source-URL substrings to drop from CAP. US NWS (api.weather.gov) issues
# thousands of routine county advisories; the US is well covered by the news
# feeds, so it's muted here. Add more substrings (e.g. "meteoalarm.org") to
# mute other noisy aggregators without touching code elsewhere.
CAP_BLOCK_SOURCES = ["api.weather.gov"]


def _cap_query(sent_iso, limit, offset):
    sev = ", ".join(CAP_SEVERITIES)
    urg = ", ".join(CAP_URGENCIES)
    cat = ", ".join(CAP_CATEGORIES)
    q = (
        "{ public { alerts("
        "filters: { sent: { gte: \"" + sent_iso + "\" }, "
        "infos: { severity: [" + sev + "], urgency: [" + urg + "], "
        "category: [" + cat + "] } }, "
        "order: { sent: DESC }, "
        "pagination: { offset: " + str(offset) + ", limit: " + str(limit) + " }"
        ") { items { identifier sent url country { name } "
        "infos { event headline description instruction severity "
        "areas { circles { value } polygons { value } } } } } } }"
    )
    return {"query": q}


def _cap_point(infos):
    """Best-effort lat/lng from CAP area circles (preferred) or polygon centroid.
    CAP coordinates are 'lat,lon' (latitude first)."""
    for info in infos or []:
        for area in info.get("areas") or []:
            for c in area.get("circles") or []:
                v = (c.get("value") or "").strip()
                if v:
                    head = v.split()[0]
                    if "," in head:
                        try:
                            la, lo = head.split(",")[:2]
                            return float(la), float(lo)
                        except ValueError:
                            pass
            for poly in area.get("polygons") or []:
                v = (poly.get("value") or "").strip()
                pts = []
                for pair in v.split():
                    if "," in pair:
                        try:
                            la, lo = pair.split(",")[:2]
                            pts.append((float(la), float(lo)))
                        except ValueError:
                            pass
                if pts:
                    return (sum(x[0] for x in pts) / len(pts),
                            sum(x[1] for x in pts) / len(pts))
    return None, None


def fetch_cap(seen, filter_countries, filter_types):
    """Pull official national alerts from the IFRC Alert Hub GraphQL API
    (CAP standard). Severity/urgency/category filtered at the query; deduped by
    the stable CAP identifier across runs. Returns candidates in the same shape
    as the other fetchers, so they go through Claude + the writer unchanged."""
    candidates = []
    run_ids = set()
    blocked = 0
    sent_iso = (datetime.now(timezone.utc)
                - timedelta(hours=CAP_WINDOW_HOURS)).isoformat()
    headers = {"Content-Type": "application/json",
               "User-Agent": "GlobalWitnessMonitor/1.0"}
    for page in range(CAP_MAX_PAGES):
        body = _cap_query(sent_iso, CAP_PAGE_LIMIT, page * CAP_PAGE_LIMIT)
        try:
            r = requests.post(CAP_ENDPOINT, json=body, headers=headers, timeout=30)
        except Exception as e:
            log.warning("CAP request error: %s", e)
            break
        if r.status_code != 200:
            log.warning("CAP endpoint -> %s: %s", r.status_code, r.text[:200])
            break
        try:
            payload = r.json()
            if payload.get("errors"):
                log.warning("CAP GraphQL errors: %s", str(payload["errors"])[:200])
                break
            alerts = (((payload.get("data") or {}).get("public") or {}).get("alerts") or {})
            items = alerts.get("items") or []
        except Exception as e:
            log.warning("CAP parse error: %s", e)
            break
        if not items:
            break
        for a in items:
            ident = a.get("identifier") or ""
            if not ident:
                continue
            if ("CAP:" + ident) in seen or ident in run_ids:
                continue
            infos = a.get("infos") or []
            info = infos[0] if infos else {}
            event = (info.get("event") or "").strip()
            headline = (info.get("headline") or event).strip()
            desc = (info.get("description") or "").strip()
            instr = (info.get("instruction") or "").strip()
            if not headline and not event:
                continue
            country = ((a.get("country") or {}).get("name") or "").strip() or None
            dtype = detect_disaster_type(event + " " + headline, desc) or "Other"
            if not matches_filter(country, filter_countries):
                continue
            if not matches_type_filter(dtype, filter_types):
                continue
            lat, lng = _cap_point(infos)
            url = a.get("url") or ""
            if any(b in url for b in CAP_BLOCK_SOURCES):
                blocked += 1
                continue
            title = headline or event
            summary = " ".join(x for x in [headline, desc, instr] if x)[:2500]
            run_ids.add(ident)
            candidates.append({
                "title": title, "summary": summary, "url": url,
                "hash": article_hash(url or ident, title),
                "source": "IFRC Alert Hub", "published": a.get("sent") or "",
                "country": country, "disaster_type": dtype,
                "lat": lat, "lng": lng, "cap_id": ident,
                "_cap_sev": (info.get("severity") or "").upper(),
            })
        if len(items) < CAP_PAGE_LIMIT:
            break
    candidates.sort(key=lambda c: 0 if c.get("_cap_sev") == "EXTREME" else 1)
    log.info("CAP: %d alerts after filter/dedup (%d blocked by source)", len(candidates), blocked)
    return candidates


def fetch_rss_feeds(seen, filter_countries, filter_types):
    candidates = []
    seen_titles = []
    for feed_url in RSS_FEEDS:
        log.info("Fetching RSS: %s", feed_url)
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:50]:
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
    usgs_candidates = fetch_usgs(seen, filter_countries, filter_types)
    cap_candidates = fetch_cap(seen, filter_countries, filter_types)
    rss_candidates = fetch_rss_feeds(seen, filter_countries, filter_types)
    rss_titles = [c["title"] for c in rss_candidates]
    gdelt_candidates = fetch_gdelt(seen, rss_titles, filter_countries, filter_types)
    usgs_candidates  = usgs_candidates[:USGS_BUDGET]
    cap_candidates   = cap_candidates[:CAP_BUDGET]
    rss_candidates   = rss_candidates[:RSS_BUDGET]
    gdelt_candidates = gdelt_candidates[:GDELT_BUDGET]
    log.info("Per-source budget applied: USGS=%d CAP=%d RSS=%d GDELT=%d",
             len(usgs_candidates), len(cap_candidates),
             len(rss_candidates), len(gdelt_candidates))
    all_candidates = usgs_candidates + cap_candidates + rss_candidates + gdelt_candidates
    all_candidates = _dedup_earthquakes(all_candidates, seen)
    log.info("Total candidates after EQ dedup: %d", len(all_candidates))
    return all_candidates[:MAX_ARTICLES]


SYSTEM_PROMPT = """You are writing brief, plain-language natural disaster reports for the general public on Global Witness Monitor. Mission agencies, churches, and field workers read these reports to stay aware of conditions where they serve.

REQUIRED OUTPUT FORMAT - every response must begin with exactly these header lines:

COUNTRY: <primary country where the event physically occurred>
DISASTER_TYPE: <Earthquake|Flood|Storm|Wildfire|Volcano|Tsunami|Landslide|Drought|Heatwave|Disease|Other>
LOCATION: <most specific named place from the source: city, town, region, or "UNKNOWN" if no specific place is named>
MAGNITUDE: <numeric magnitude rounded to nearest whole number for earthquakes (e.g. "6"); category number for hurricanes (e.g. "Cat 4"); "UNKNOWN" if not applicable or unknown>
EVENT_DATE: <event date in MM/DD/YYYY format, "UNKNOWN" if not stated in the source>
PRAYER: <a bare situation phrase naming what to pray for — NOT an instruction, NOT a sentence. No leading verb. Never begin with Pray, Lift up, Ask God, May, Let, or "for". Name the people and circumstance, 8-25 words, e.g. "Communities in central Indonesia recovering after a shallow earthquake" or "Residents across drought-stricken Somalia facing failed harvests">
ALERT_SUMMARY: <one factual sentence: what happened, where, and the single most important figure from the source (deaths, injured, displaced, homes destroyed, magnitude). Use ONLY quantitative descriptors. NEVER use vague intensifiers such as powerful, massive, severe, devastating, major, deadly, strong, huge, intense. If the source gives no figure, state the event plainly with no intensifier. 8-20 words. e.g. "Magnitude 6 earthquake displaced about 20,000 residents near Mindanao" or "Flooding submerged three districts of Sindh; no casualty figure reported">

---

Then the article body follows on the next line.

WRITING STYLE:
- Plain language for general public. NO technical jargon.
- DO NOT mention: MMI, intensity level, GDACS, USGS, "Mission Note", "Field teams should...", or any boilerplate operational language.
- Round depth to the nearest whole kilometer or describe qualitatively.
- DO NOT include exposure estimates like "30,000 in MMI VI".
- DO NOT include UTC times in the body.
- Length: only as long as the source supports. At most 100-180 words when the source is detailed; when the source is thin, write 2 to 4 factual sentences and then stop. Never pad to reach a length with background, history, or restatement (e.g. do NOT add filler such as 'the situation continues to develop', 'officials continue to monitor', or 'this is the Nth update').
- Lead with the concrete figures the source provides (deaths, injured, displaced, arrested, affected, magnitude, or similar). If the source provides no such figure, state that plainly in one sentence and do not imply a scale.
- NEVER name a city, town, village, district, or region that does not appear in the source material. If the source names no specific place, use the country or write UNKNOWN. Do not invent, guess, or infer a place name.
- Two or three short paragraphs separated by blank lines.
- Do not include personal names; use "a man", "a woman", "residents", "officials", "rescuers".
- Do not include the source URL in the body.
- Do not include a title. Body only.
- State when the event occurred in the body, using the event date from the source (e.g. "On June 14, 2026, ..."). If the source gives no date, do not invent one.
- End naturally - no Mission Note, no Field Teams advisory.
- DO NOT include the prayer line in the body.

DISASTER_TYPE field:
- Use Disease for disease outbreaks (cholera, ebola, mpox, measles, polio, etc.)
- Use Other if truly unclassifiable.

Respond with ONLY the token SKIP_NO_EVENT (nothing else) when the source is any of the following rather than an actual natural-hazard or disease event that has already occurred:
- A forecast, outlook, watch, warning, or "danger"/"red flag" advisory where the hazard is only predicted or possible and nothing has happened yet (e.g. "fire danger forecast", "thunderstorm warning issued", "flood watch in effect", "extreme fire danger expected").
- A personal or individual incident that is not a population-affecting natural hazard (e.g. one person killed or injured in an accident, a fall, or a stunt).
- Armed conflict, war, missile/drone strikes, shelling, bombing, terrorism, crime, or any human violence — these are not natural disasters and do not belong here.
- Pure opinion, an explainer, an anniversary or retrospective, or any item with no factual natural-disaster event reported.
Otherwise, write the report normally."""


REFUSAL_PATTERNS = [
    "i cannot write", "i cannot provide", "i am unable to",
    "i can't write", "i can not write", "i will not write",
]
SKIP_TOKEN = "skip_no_event"
MIN_WORDS = 30
SKIP_LOG = "/opt/disaster-pipeline/skips.log"


def log_skip(title, reason):
    """Append every dropped candidate to a skip log so drops stay inspectable
    without anyone having to watch the run."""
    try:
        with open(SKIP_LOG, "a") as f:
            f.write(datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
                    + "\t" + (reason or "?") + "\t" + (title or "")[:120] + "\n")
    except Exception as e:
        log.warning("skip-log write failed: %s", e)


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
        return False
    for pattern in REFUSAL_PATTERNS:
        if pattern in lower:
            return False
    return len(article_body.split()) >= MIN_WORDS


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
                    # figures are short; keep rows/items that are long
                    # OR carry a number (case/death/displaced counts)
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
        text = " ".join(text.split())
        return text[:max_chars]
    except Exception as e:
        log.info("body fetch failed for %s: %s", url[:60], e)
        return ""


def generate_article(item, firmer=False):
    client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
    body_text = fetch_article_body(item["url"])
    body_section = ""
    if body_text:
        log.info("fetched %d chars of article body", len(body_text))
        body_section = "SOURCE BODY TEXT:\n" + body_text + "\n\n"
    user_prompt = (
        "Write a plain-language natural disaster report based only on the source material below.\n\n"
        "SOURCE TITLE: " + item["title"] + "\n\n"
        "SOURCE SUMMARY: " + item["summary"] + "\n\n"
        + body_section +
        "SOURCE URL: " + item["url"] + "\n\n"
        "SOURCE OUTLET: " + item["source"] + "\n\n"
        "DETECTED DISASTER TYPE: " + item.get("disaster_type", "Other") + "\n\n"
        "Use only facts present in the source material above."
    )
    if firmer:
        user_prompt = (
            "The item below is a factual event already publicly reported by the "
            "outlet named. Summarize it as a plain-language natural-disaster report. "
            "Do not decline and do not refuse; if the source is thin, write only what "
            "it supports. If it genuinely describes no natural-hazard or disease event, "
            "reply with SKIP_NO_EVENT. Follow the header format exactly.\n\n"
        ) + user_prompt
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
    # US MM/DD/YYYY
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", s)
    if m:
        mm, dd, yyyy = m.groups()
        return "%02d/%02d/%s" % (int(mm), int(dd), yyyy)
    # ISO YYYY-MM-DD (optionally with time / offset)
    m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})", s)
    if m:
        yyyy, mm, dd = m.groups()
        return "%02d/%02d/%s" % (int(mm), int(dd), yyyy)
    # GDELT compact: YYYYMMDDTHHMMSSZ
    m = re.match(r"^(\d{4})(\d{2})(\d{2})T\d{6}Z$", s)
    if m:
        yyyy, mm, dd = m.groups()
        return "%02d/%02d/%s" % (int(mm), int(dd), yyyy)
    # RFC-822 (RSS feeds): "Sun, 14 Jun 2026 12:00:00 GMT"
    try:
        from email.utils import parsedate_to_datetime
        dt = parsedate_to_datetime(s)
        if dt:
            return "%02d/%02d/%04d" % (dt.month, dt.day, dt.year)
    except Exception:
        pass
    # Last resort: generic ISO parse
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return "%02d/%02d/%04d" % (dt.month, dt.day, dt.year)
    except Exception:
        pass
    return ""


def build_title(parsed, item):
    dtype = parsed.get("disaster_type", "Other") or "Other"
    countries = parsed.get("countries") or []
    country = countries[0] if countries else (item.get("country") or "")
    magnitude = (parsed.get("magnitude") or "").strip()
    event_date_us = _to_us_date(item.get("published"))
    if not event_date_us:
        event_date_us = _to_us_date(parsed.get("event_date"))

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
        "CLAUDE_VS_DETECTED: claude_country=%s claude_type=%s detected_country=%s detected_type=%s status=%s",
        ",".join(parsed.get("countries", [])) or "-",
        parsed.get("disaster_type", "Other"),
        detected_country or "-", detected_dtype, status,
    )

    if status == "unknown":
        log.info("Skipping (UNKNOWN): %s", item["title"][:60])
        return None, None, None, None, None
    if status == "malformed":
        log.warning("Skipping (malformed): %s", item["title"][:60])
        return None, None, None, None, None
    if status == "no_valid_country":
        log.warning("Skipping (no_valid_country): %s", item["title"][:60])
        return None, None, None, None, None

    if not parsed.get("location"):
        log.info("Skipping (no location): %s", item["title"][:60])
        return None, None, None, None, None

    countries = parsed["countries"]
    dtype = parsed["disaster_type"]
    prayer = parsed.get("prayer", "")

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
    if _final_lat is None and _country_hint:
        _clat, _clng = geocode_mapbox(_country_hint, _country_hint)
        if _clat is not None and _clng is not None:
            _final_lat = _clat
            _final_lng = _clng
            log.info("Country-centroid fallback %r -> %.4f, %.4f",
                     _country_hint, _clat, _clng)

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
        log.info("Published: %s [%s / %s] (ID %s)",
                 clean_title[:60], countries[0], dtype, post_id)
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
                        help="Skip JSON feed update")
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
                if is_refusal(article_body):
                    log.info("Refusal; retrying once (firmer): %s", item["title"][:60])
                    _gen = generate_article(item, firmer=True)
                    if isinstance(_gen, tuple):
                        raw_response, parsed = _gen
                    else:
                        raw_response, parsed = _gen, None
                    article_body = parsed["body"] if (parsed and parsed.get("body")) else raw_response
                if not is_valid_article(article_body):
                    log.info("Skipping (invalid): %s", item["title"][:60])
                    log_skip(item["title"], "invalid_or_refusal")
                    seen.add(item["hash"])
                    skipped += 1
                    continue

            _result = publish_to_wordpress(item, article_body, parsed=parsed)
            post_id, post_link, lat, lng, post_date = _result

            if post_id:
                seen.add(item["hash"])
                if item.get("usgs_id"):
                    seen.add("USGS:" + item["usgs_id"])
                for _s in (item.get("_eq_sigs") or []):
                    seen.add(_s)
                if item.get("cap_id"):
                    seen.add("CAP:" + item["cap_id"])
                published += 1

                if JSON_WRITER_AVAILABLE and not args.no_json:
                    countries = parsed.get("countries", []) if parsed else []
                    dtype = parsed.get("disaster_type", "Other") if parsed else "Other"
                    prayer = parsed.get("prayer", "") if parsed else ""
                    alert_summary = parsed.get("alert_summary", "") if parsed else ""
                    structured_title = build_title(parsed, item) if parsed else item["title"]
                    event = {
                        "wp_id": post_id,
                        "wp_link": post_link,
                        "date": post_date or datetime.now(timezone.utc).isoformat(),
                        "title": sanitize_title(structured_title),
                        "body": re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html.unescape(article_body or ""))).strip()[:220],
                        "country": countries[0] if countries else "",
                        "countries": countries,
                        "type": dtype,
                        "lat": lat,
                        "lng": lng,
                        "source_title": item.get("source", ""),
                        "source_url": item.get("url", ""),
                        "prayer": prayer,
                        "alert_summary": alert_summary,
                    }
                    try:
                        if _gwm_is_suppressed(event):
                            print("Suppressed (skipped feed write): " + str(event.get("title", "")))
                        else:
                            gwm_json_writer.write_event(FEED_NAME, event)
                        json_writes += 1
                    except Exception as e:
                        log.error("JSON write_event failed: %s", e)

                time.sleep(3)
            else:
                log_skip(item["title"], "publish_skip")
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
