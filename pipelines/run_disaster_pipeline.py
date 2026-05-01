#!/usr/bin/env python3
"""
Global Witness Monitor -- Natural Disaster Intelligence Pipeline v2
Canonical source. Mirrors conflict pipeline patterns:
  - Country-scoped article generation (drops unrelated content from sources)
  - Lead-with-the-event voice (bans "According to" openers)
  - Claude-rewritten TITLE field for clean, country-focused headlines
  - Roundup / multi-country headline rejection
  - Mapbox geocoding via LOCATION field
  - Hidden gwm-disaster-meta div for the dashboard
  - Title sanitization + first-letter capitalization
  - Structured parse_claude_response with status codes

Run examples:
  cd /opt/disaster-pipeline && set -a && source .env && set +a && venv/bin/python run_disaster_pipeline.py
  venv/bin/python run_disaster_pipeline.py --type earthquake
  venv/bin/python run_disaster_pipeline.py --region asia
  venv/bin/python run_disaster_pipeline.py --country Japan --country Philippines
  venv/bin/python run_disaster_pipeline.py --type flood --type storm
"""

import os
import sys
import json
import time
import html
import hashlib
import logging
import argparse
import re
import requests
import feedparser
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
import anthropic

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

# -- DISASTER TERMS (must have at least one) --
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
    "washed away",
    "toll", "casualties", "fatalities",
    "leveled", "levelled", "flattened",
    "issued",
]

# -- EXCLUDE PATTERNS (opinion, explainers, roundups, non-events) --
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
    "video:", "video shows", "watch:", "footage:", "footage shows",
    "photos:", "pictures of",
    # Roundup / briefing format -- multi-country aggregator headlines
    "world news in brief", "news in brief", "briefing:",
    "daily briefing", "morning briefing", "evening briefing",
    "news roundup", "weekly roundup", "roundup:",
    "world news roundup", "news digest",
    "today's headlines", "headlines:", "in brief:",
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

VALID_DISASTER_TYPES = [
    "Earthquake", "Flood", "Storm", "Wildfire", "Volcano",
    "Tsunami", "Landslide", "Drought", "Heatwave", "Other",
]


def detect_disaster_type(title, summary):
    """Return the best-matching disaster type label, or 'Other'."""
    text = (title + " " + summary).lower()
    priority = ["Tsunami", "Volcano", "Earthquake", "Wildfire",
                "Storm", "Flood", "Landslide", "Drought", "Heatwave"]
    for dtype in priority:
        for kw in DISASTER_TYPE_KEYWORDS[dtype]:
            if kw in text:
                return dtype
    return "Other"


def validate_disaster_type(claude_value):
    if not claude_value:
        return "Other"
    v = claude_value.strip().lower()
    valid_map = {t.lower(): t for t in VALID_DISASTER_TYPES}
    return valid_map.get(v, "Other")


# Feeds whose items are inherently disaster events -- skip keyword/signal filters
TRUSTED_DISASTER_FEEDS = (
    "earthquake.usgs.gov",
    "gdacs.org",
)

def is_trusted_feed(feed_url):
    return any(domain in (feed_url or "") for domain in TRUSTED_DISASTER_FEEDS)


MAGNITUDE_PATTERN = re.compile(r"\bM\s?\d+\.\d+\b", re.IGNORECASE)


def is_relevant(title, summary):
    """Check if article is relevant AND is an actual event (not opinion/explainer/roundup)."""
    text = (title + " " + summary).lower()
    raw_text = title + " " + summary

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


# -- COUNTRY EXTRACTION --
def extract_country(title, summary):
    """Extract country from title/summary. Returns None if no country found."""
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


# -- USGS / GDACS COORDINATE EXTRACTION --
USGS_GEORSS_PATTERN = re.compile(
    r"<georss:point>\s*([\-\d\.]+)\s+([\-\d\.]+)\s*</georss:point>",
    re.IGNORECASE,
)


def extract_feed_coords(entry):
    """Extract lat/lng from RSS entry if present (USGS, GDACS supply these)."""
    # USGS / GDACS use georss
    geo_lat = entry.get("geo_lat") or entry.get("georss_point")
    if entry.get("where"):
        # feedparser may parse georss into 'where'
        try:
            coords = entry["where"].get("coordinates")
            if coords and len(coords) >= 2:
                return float(coords[1]), float(coords[0])
        except Exception:
            pass
    if isinstance(geo_lat, str):
        m = USGS_GEORSS_PATTERN.search(geo_lat)
        if m:
            try:
                return float(m.group(1)), float(m.group(2))
            except ValueError:
                pass
    # feedparser sometimes exposes 'geo_lat' / 'geo_long' as strings
    try:
        lat = entry.get("geo_lat")
        lng = entry.get("geo_long")
        if lat and lng:
            return float(lat), float(lng)
    except Exception:
        pass
    return None, None


# -- FETCH RSS FEEDS --
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

                lat, lng = extract_feed_coords(entry)

                candidates.append({
                    "title":         title,
                    "summary":       summary,
                    "url":           url,
                    "hash":          h,
                    "source":        feed.feed.get("title", feed_url),
                    "published":     entry.get("published", ""),
                    "country":       country,
                    "disaster_type": dtype,
                    "lat":           lat,
                    "lng":           lng,
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

REQUIRED OUTPUT FORMAT -- every response must begin with exactly this 4-line header:

COUNTRY: <primary country where the event physically occurred>
DISASTER_TYPE: <Earthquake|Flood|Storm|Wildfire|Volcano|Tsunami|Landslide|Drought|Heatwave|Other>
LOCATION: <most specific named place from the source -- city, town, district, or named region. Use UNKNOWN ONLY if no place is named anywhere in the source>
TITLE: <a fresh 6-12 word headline focused ONLY on the event in COUNTRY -- never a roundup, never multi-country, never the source's original headline>
---

Then the article body follows on the next line.

LOCATION field rules:
- Return the most specific named place mentioned ANYWHERE in the source material.
- Examples: "Petropavlovsk-Kamchatsky", "Kerala", "Mocoa, Putumayo", "Mount Etna", "Sichuan Province".
- Do NOT include the country in the LOCATION value (the COUNTRY field captures that).
- Prefer the smallest geographic unit named (city > district > province > region).
- For events spanning a wide region with no named place, use the most specific
  region name (e.g. "Eastern Java", "Sichuan Province").
- Output LOCATION: UNKNOWN ONLY when truly no place name appears in the source.

COUNTRY field rules:
- Return the country where the event PHYSICALLY OCCURRED, not where the news outlet is based.
- Ignore outlet names in the source material.
- For events spanning multiple countries, pick the most affected one.
- Use common country names: "Iran", "United States", "United Kingdom", "Myanmar", "Congo".
- Do NOT include state/province names.
- If you cannot identify a valid country with reasonable confidence, output COUNTRY: UNKNOWN.

CRITICAL RULES:
- Base every claim strictly on the provided source material. Do not invent names, statistics,
  casualty figures, magnitudes, locations, or any other details not present in the source.
- COUNTRY-SCOPED CONTENT: The article must focus EXCLUSIVELY on the event in the COUNTRY field.
  If the source mentions other countries, other disasters, or unrelated stories, IGNORE them
  entirely. Do not reference, summarize, or list them in the article body. The brief is about
  ONE country and ONE event line. Drop everything else even if it appears in the source.
- DO NOT begin the article with "According to <outlet>", "Per <outlet>", "<Outlet> reports",
  "<Outlet> says", or any equivalent attribution-first opener. Lead with what happened, where,
  and the scale -- the news itself, not the news outlet.
- Source attribution should appear ONCE, naturally, in the middle or near the end of the
  article (e.g. "...as reported by <outlet>" or "...the <outlet> report indicates..."), and
  only when attribution adds analytical value. Never name the outlet at the start. Never
  name it more than once.
- Write in a factual, measured intelligence-briefing tone -- not sensational, not emotionally charged.
- The audience is mission professionals who need accurate, actionable information about regional
  safety, infrastructure status, and humanitarian conditions.
- Structure: lead with the key facts (what happened, where, scale), provide context,
  note implications for field operations, travel, and affected communities where relevant.
- Do NOT editorialize about climate policy, government response, or assign blame beyond what
  sources state.
- Length: 80-200 words. Shorter is fine when source detail is thin -- never invent to hit a count.
- When names of people are mentioned in the source material, do not include them; refer to them
  as "a man", "a woman", "residents", "officials", "rescuers", etc.
- Do not include the source URL in the article body.
- Do not include a title in the article body -- only the body. (The TITLE field captures the headline.)
- End with a one-sentence Mission Note: summarizing the operational significance for field workers
  (e.g., travel impact, infrastructure damage, humanitarian access concerns). Put it on its own
  line apart from the paragraph. Do not put asterisks next to it (no *).

ROUNDUP / MULTI-COUNTRY RULE:
- If the source title or summary clearly aggregates events across MULTIPLE unrelated
  countries (e.g. "World News in Brief", "News Roundup", or a headline naming three
  or more countries with separate events), respond with SKIP_NO_EVENT.
- Roundup briefings dilute country-scoped intelligence. The pipeline will pick up
  individual wire-story coverage of each event separately on later passes.

MEDIA-ANNOUNCEMENT RULE:
- If the source material is primarily an announcement of a video, photo gallery, livestream,
  or audio segment ("Video:", "Footage:", "Photos:", "Watch this", "New footage shows..."),
  respond with SKIP_NO_EVENT. The pipeline will pick up wire-story coverage on a later pass.

ANNIVERSARY / COMMEMORATION RULE:
- If the source is about a memorial, anniversary, ceremony, tribute, or remembrance for a past
  disaster, respond with SKIP_NO_EVENT. The pipeline surfaces ACTIONABLE current events.

Only respond with SKIP_NO_EVENT for the cases above OR when the source is pure opinion/commentary
with no reported event. If the source mentions an actual disaster -- even with minimal detail
like location, magnitude, or date -- write a concise brief using ONLY the facts present. When
details are sparse, hedge ("initial reports indicate", "the source notes") and keep the brief
shorter (80-150 words is acceptable). A short, honest brief based on limited confirmed facts
is more valuable than no brief at all."""


BAD_RESPONSE_PATTERNS = [
    "i cannot write",
    "i cannot provide",
    "i am unable to",
    "skip_no_event",
]


def is_valid_article(article_body):
    if not article_body:
        return False
    lower = article_body.lower()
    for pattern in BAD_RESPONSE_PATTERNS:
        if pattern in lower:
            log.info("INVALID_REASON: matched bad pattern %r", pattern)
            return False
    word_count = len(article_body.split())
    if word_count < 60:
        log.info("INVALID_REASON: word_count=%d", word_count)
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
        "Write a natural disaster intelligence brief based on this source material only.\n\n"
        "SOURCE TITLE: " + item["title"] + "\n\n"
        "SOURCE SUMMARY: " + item["summary"] + "\n\n"
        + body_section +
        "SOURCE URL: " + item["url"] + "\n\n"
        "SOURCE OUTLET: " + item["source"] + "\n\n"
        "DETECTED DISASTER TYPE: " + item.get("disaster_type", "Other") + "\n\n"
        "Use only facts present in the source material above. Prefer the SOURCE BODY TEXT when "
        "available for specific numbers, locations, and quotes. If the content is pure opinion, "
        "a non-event explainer, a roundup of multiple countries, or a commemoration of past "
        "events, respond with SKIP_NO_EVENT."
    )

    log.info("Generating article for: %s", item["title"][:70])

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=700,
        messages=[{"role": "user", "content": user_prompt}],
        system=SYSTEM_PROMPT,
    )

    raw_response = message.content[0].text.strip()
    parsed = parse_claude_response(raw_response)
    return raw_response, parsed


# -- PARSE CLAUDE RESPONSE --
def parse_claude_response(raw_text):
    """Parse Claude's structured response.

    Expected header (4 lines + ---):
        COUNTRY: <country | UNKNOWN>
        DISASTER_TYPE: <type>
        LOCATION: <place | UNKNOWN>
        TITLE: <rewritten headline>
        ---
        <article body>
    """
    result = {
        "country": "",
        "disaster_type": "Other",
        "location": "",
        "title": "",
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
    title_line = None
    body_start_idx = 0

    for i, line in enumerate(lines[:10]):
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
        elif up.startswith("TITLE:"):
            title_line = stripped[len("TITLE:"):].strip()
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

    if title_line:
        tl = title_line.strip().strip('"').strip("'").strip()
        if tl:
            result["title"] = tl

    if not country_line:
        result["status"] = "malformed"
        return result

    up = country_line.upper()
    if up == "UNKNOWN":
        result["status"] = "unknown"
        return result

    # Validate country against ALL_COUNTRIES (case-insensitive, alias-tolerant)
    canon = canonicalize_country(country_line)
    if canon:
        result["country"] = canon
        result["status"] = "ok"
    else:
        result["status"] = "no_valid_country"
    return result


COUNTRY_ALIASES = {
    "burma": "Myanmar",
    "drc": "Congo",
    "democratic republic of the congo": "Congo",
    "democratic republic of congo": "Congo",
    "republic of the congo": "Congo",
    "north korea": "North Korea",
    "south korea": "South Korea",
    "uae": "United Arab Emirates",
    "uk": "United Kingdom",
    "britain": "United Kingdom",
    "great britain": "United Kingdom",
    "usa": "United States",
    "u.s.": "United States",
    "u.s.a.": "United States",
    "america": "United States",
    "ivory coast": "Ivory Coast",
    "cote d'ivoire": "Ivory Coast",
}


def canonicalize_country(name):
    if not name:
        return None
    key = name.strip().lower()
    if not key:
        return None
    # Direct alias
    if key in COUNTRY_ALIASES:
        return COUNTRY_ALIASES[key]
    # Match against ALL_COUNTRIES
    for c in ALL_COUNTRIES:
        if c.lower() == key:
            return c
    return None


# -- TITLE SANITIZATION --
def sanitize_title(title):
    """Decode HTML entities, strip trailing source attributions, normalize
    en/em dashes, and capitalize the first letter."""
    if not title:
        return title
    t = html.unescape(title)
    # Strip trailing " - Source" / " | Source"
    t = re.sub(
        r"\s*[-\u2013\u2014|]\s*[A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,4}(?:\s+(?:News|Network|Times|Post|Today|Tribune|Herald))?\s*$",
        "",
        t,
    )
    t = t.replace("\u2013", ", ").replace("\u2014", ", ")
    t = re.sub(r"\s+", " ", t).strip()
    if t:
        t = t[0].upper() + t[1:]
    return t


# -- GEOCODING --
def geocode_mapbox(location, country_hint=None):
    """Forward-geocode a place name via Mapbox. Returns (lat, lng) or (None, None)."""
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

        log.info("Mapbox: no feature matched country hint %r for %r",
                 country_hint, location)
        return None, None

    except Exception as e:
        log.warning("Mapbox geocode error for %r: %s", location, e)
        return None, None


# -- WORDPRESS PUBLISH --
def get_or_create_tag(name, auth):
    try:
        r = requests.get(
            WP_URL + "/wp-json/wp/v2/tags",
            params={"search": name, "per_page": 20},
            auth=auth,
            timeout=15,
        )
        existing = r.json() if r.status_code == 200 else []
        for tag in existing:
            if tag.get("name", "").strip().lower() == name.strip().lower():
                return tag["id"]
        r2 = requests.post(
            WP_URL + "/wp-json/wp/v2/tags",
            json={"name": name},
            auth=auth,
            timeout=15,
        )
        if r2.status_code in (200, 201):
            return r2.json()["id"]
        log.warning("Tag create failed for %s (%s): %s",
                    name, r2.status_code, r2.text[:200])
        return None
    except Exception as e:
        log.warning("Tag lookup/create error for %s: %s", name, e)
        return None


def publish_to_wordpress(item, article_body, parsed=None):
    endpoint = WP_URL + "/wp-json/wp/v2/posts"
    auth     = (WP_USER, WP_APP_PASSWORD)

    if parsed is None:
        log.warning("publish_to_wordpress called without parsed structure; skipping")
        return False

    status = parsed.get("status", "malformed")
    detected_country = item.get("country")

    log.info(
        "CLAUDE_VS_DETECTED: claude_country=%s detected_country=%s status=%s raw=%r",
        parsed.get("country") or "-",
        detected_country or "-",
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
            "Skipping (Claude country %r not in registry): %s",
            parsed.get("raw_country_line", ""), item["title"][:60],
        )
        return False

    country = parsed["country"]
    dtype   = parsed.get("disaster_type", item.get("disaster_type", "Other"))

    # Title: prefer Claude-rewritten, fall back to sanitized source title
    claude_title = parsed.get("title", "")
    if claude_title:
        final_title = sanitize_title(claude_title)
    else:
        final_title = sanitize_title(item["title"])

    # Coordinates: (1) Claude location -> Mapbox, (2) feed-supplied (USGS/GDACS), (3) empty
    final_lat = None
    final_lng = None
    claude_loc = parsed.get("location") or ""
    if claude_loc:
        glat, glng = geocode_mapbox(claude_loc, country)
        if glat is not None and glng is not None:
            final_lat, final_lng = glat, glng
            log.info("Geocoded %r in %r -> %.4f, %.4f", claude_loc, country, glat, glng)
        else:
            log.info("Geocode failed for %r in %r", claude_loc, country)

    if final_lat is None or final_lng is None:
        ilat = item.get("lat")
        ilng = item.get("lng")
        if isinstance(ilat, (int, float)) and isinstance(ilng, (int, float)):
            final_lat, final_lng = ilat, ilng

    lat_str = ("%.4f" % final_lat) if isinstance(final_lat, (int, float)) else ""
    lng_str = ("%.4f" % final_lng) if isinstance(final_lng, (int, float)) else ""

    meta_div = (
        '<div class="gwm-disaster-meta"'
        ' data-country="' + country + '"'
        ' data-type="' + dtype + '"'
        ' data-lat="' + lat_str + '"'
        ' data-lng="' + lng_str + '"'
        ' style="display:none;"></div>\n'
    )

    # Convert plain-text paragraph breaks to <p> tags
    body = article_body
    if isinstance(body, str) and "<p>" not in body:
        paragraphs = [p.strip() for p in body.split("\n\n") if p.strip()]
        body = "\n".join("<p>" + p.replace("\n", " ") + "</p>" for p in paragraphs)

    final_content = meta_div + body

    # Tags: country + disaster type
    tag_ids = []
    country_tag_id = get_or_create_tag(country, auth)
    if country_tag_id:
        tag_ids.append(country_tag_id)
    type_tag_id = get_or_create_tag(dtype, auth)
    if type_tag_id:
        tag_ids.append(type_tag_id)

    payload = {
        "title":      final_title,
        "content":    final_content,
        "status":     "publish",
        "categories": [WP_CATEGORY_ID],
        "tags":       tag_ids,
    }

    r = requests.post(endpoint, json=payload, auth=auth, timeout=30)

    if r.status_code in (200, 201):
        post = r.json()
        log.info("Published: %s [%s / %s] (ID %s)",
                 final_title[:50], country, dtype, post.get("id"))
        return True
    else:
        log.error("Publish failed (%s): %s", r.status_code, r.text[:300])
        return False


# -- ARGUMENT PARSING --
def parse_args():
    parser = argparse.ArgumentParser(
        description="GWM Natural Disaster Pipeline v2",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_disaster_pipeline.py
  python run_disaster_pipeline.py --type earthquake
  python run_disaster_pipeline.py --region asia
  python run_disaster_pipeline.py --country Japan
  python run_disaster_pipeline.py --type flood --type storm
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
        help="Filter by disaster type"
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

    return list(set(filter_countries)) if filter_countries else None


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

    log.info("=== Disaster Pipeline v2 starting (%s) ===", label)

    seen       = load_seen()
    candidates = fetch_all_feeds(seen, filter_countries, filter_types)

    if not candidates:
        log.info("No new relevant articles found. Done.")
        return

    published = 0
    skipped   = 0

    for item in candidates:
        try:
            raw_response, parsed = generate_article(item)
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
