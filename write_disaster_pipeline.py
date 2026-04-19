#!/usr/bin/env python3
"""
write_disaster_pipeline.py

Python-writes-Python deployer for the GWM Natural Disaster Pipeline.

Usage on the server:
    curl -sL <raw-gist-url> -o /tmp/write_disaster_pipeline.py
    python3 /tmp/write_disaster_pipeline.py

This creates /opt/disaster-pipeline/run_disaster_pipeline.py with zero
quote corruption risk. After running this, you still need to:
    1. cp /opt/conflict-pipeline/.env /opt/disaster-pipeline/.env
    2. Edit /opt/disaster-pipeline/.env and change WP_CATEGORY_ID to 38
    3. Create venv and install deps (see setup commands)
    4. Run the pipeline
"""

import os

TARGET_DIR  = "/opt/disaster-pipeline"
TARGET_FILE = os.path.join(TARGET_DIR, "run_disaster_pipeline.py")

PIPELINE_CODE = r'''#!/usr/bin/env python3
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

def is_relevant(title, summary):
    """Check if article is relevant AND is an actual event (not opinion/explainer)."""
    text = (title + " " + summary).lower()

    has_disaster = any(term in text for term in DISASTER_TERMS)
    if not has_disaster:
        return False

    has_event = any(signal in text for signal in EVENT_SIGNALS)
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

                if not is_relevant(title, summary):
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

                candidates.append({
                    "title":        title,
                    "summary":      summary,
                    "url":          url,
                    "hash":         h,
                    "source":       feed.feed.get("title", feed_url),
                    "published":    entry.get("published", ""),
                    "country":      country,
                    "disaster_type": dtype,
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
            if r.status_code != 200:
                log.warning("GDELT returned %s", r.status_code)
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
                })
                existing_titles.append(title)

            time.sleep(1)

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
- Length: 150-250 words.
- When names of people are mentioned in the source material, do not include them; refer to them
  as "a man", "a woman", "residents", "officials", "rescuers", etc.
- Do not include the source URL at the bottom of the article. You may attribute information
  inline using phrases like "according to local authorities" or "reports indicate".
- Do not include a title in your response -- only the article body.
- End with a one-sentence Mission Note: summarizing the operational significance for field workers
  (e.g., travel impact, infrastructure damage, humanitarian access concerns).

IMPORTANT: If the source material does not describe an actual disaster event (something that
happened), or if there is insufficient factual information to write a proper intelligence brief,
respond with exactly: SKIP_NO_EVENT"""

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
    if word_count < 80:
        return False
    return True

def generate_article(item):
    client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)

    user_prompt = (
        "Write a natural disaster intelligence brief based on this source material only.\n\n"
        "SOURCE TITLE: " + item["title"] + "\n\n"
        "SOURCE SUMMARY: " + item["summary"] + "\n\n"
        "SOURCE URL: " + item["url"] + "\n\n"
        "SOURCE OUTLET: " + item["source"] + "\n\n"
        "DETECTED DISASTER TYPE: " + item.get("disaster_type", "Other") + "\n\n"
        "Remember: only use facts present in the source material above. "
        "If this is not an actual disaster event or lacks sufficient detail, "
        "respond with SKIP_NO_EVENT."
    )

    log.info("Generating article for: %s", item["title"][:70])

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=600,
        messages=[{"role": "user", "content": user_prompt}],
        system=SYSTEM_PROMPT,
    )

    return message.content[0].text.strip()

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

def publish_to_wordpress(item, article_body):
    endpoint = WP_URL + "/wp-json/wp/v2/posts"
    auth     = (WP_USER, WP_APP_PASSWORD)

    country = item.get("country")
    dtype   = item.get("disaster_type", "Other")

    if not country:
        log.info("Skipping (no country detected): %s", item["title"][:60])
        return False

    tag_ids = []
    country_tag_id = get_or_create_tag(country, auth)
    if country_tag_id:
        tag_ids.append(country_tag_id)
    type_tag_id = get_or_create_tag(dtype, auth)
    if type_tag_id:
        tag_ids.append(type_tag_id)

    payload = {
        "title":      item["title"],
        "content":    article_body,
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
            article_body = generate_article(item)

            if not is_valid_article(article_body):
                log.info("Skipping (invalid/refused): %s", item["title"][:60])
                seen.add(item["hash"])
                skipped += 1
                continue

            success = publish_to_wordpress(item, article_body)

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
'''


def main():
    # Make sure target dir exists
    os.makedirs(TARGET_DIR, exist_ok=True)
    os.makedirs(os.path.join(TARGET_DIR, "data"), exist_ok=True)

    # Write the pipeline file
    with open(TARGET_FILE, "w") as f:
        f.write(PIPELINE_CODE)

    # Make executable
    os.chmod(TARGET_FILE, 0o755)

    # Report
    size = os.path.getsize(TARGET_FILE)
    lines = PIPELINE_CODE.count("\n")
    print("=" * 60)
    print("SUCCESS")
    print("=" * 60)
    print("Wrote: " + TARGET_FILE)
    print("Size:  " + str(size) + " bytes")
    print("Lines: " + str(lines))
    print()
    print("NEXT STEPS:")
    print("  1. cp /opt/conflict-pipeline/.env /opt/disaster-pipeline/.env")
    print("  2. Edit /opt/disaster-pipeline/.env")
    print("     Change WP_CATEGORY_ID from 8 to 38")
    print("  3. cd /opt/disaster-pipeline")
    print("  4. python3 -m venv venv")
    print("  5. venv/bin/pip install anthropic feedparser python-dotenv requests")
    print("  6. set -a && source .env && set +a && venv/bin/python run_disaster_pipeline.py")
    print("=" * 60)


if __name__ == "__main__":
    main()
