#!/usr/bin/env python3
"""
Global Witness Monitor -- Conflict & Unrest Pipeline v4
- Region and country filtering via command line
- Stricter event-based filtering (not opinion/explainers)
- Skip articles where AI can't generate proper brief
- GDELT free API integration
- Duplicate similarity check

Run examples:
  # Full global run (manual)
  cd /opt/conflict-pipeline && set -a && source .env && set +a && venv/bin/python run_conflict_pipeline_v4.py

  # Middle East only (can schedule frequently)
  venv/bin/python run_conflict_pipeline_v4.py --region middle-east

  # Specific country
  venv/bin/python run_conflict_pipeline_v4.py --country Iran

  # Multiple countries
  venv/bin/python run_conflict_pipeline_v4.py --country Iran --country Syria --country Yemen

  # Multiple regions
  venv/bin/python run_conflict_pipeline_v4.py --region middle-east --region africa
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
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
log = logging.getLogger(__name__)

# -- CONFIG --
load_dotenv()

WP_URL          = os.environ['WP_URL'].rstrip('/')
WP_USER         = os.environ['WP_USER']
WP_APP_PASSWORD = os.environ['WP_APP_PASSWORD']
ANTHROPIC_KEY   = os.environ['ANTHROPIC_API_KEY']
WP_CATEGORY_ID  = int(os.environ.get('WP_CATEGORY_ID', 8))

SEEN_FILE    = '/opt/conflict-pipeline/data/seen_articles.json'
MAX_ARTICLES = 50

# -- REGIONS --
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
        'Bolivia', 'Brazil', 'Chile', 'Colombia', 'Cuba', 'Ecuador',
        'El Salvador', 'Guatemala', 'Guyana', 'Haiti', 'Honduras', 'Jamaica',
        'Mexico', 'Nicaragua', 'Panama', 'Paraguay', 'Peru', 'Trinidad',
        'Venezuela',
    ],
    'pacific': [
        'Fiji', 'Papua New Guinea', 'Solomon Islands', 'Vanuatu',
    ],
}

# Build flat list of all countries
ALL_COUNTRIES = []
for region_countries in REGIONS.values():
    ALL_COUNTRIES.extend(region_countries)
ALL_COUNTRIES = list(set(ALL_COUNTRIES))

# -- RSS SOURCES --
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

# -- CONFLICT KEYWORDS (must have at least one) --
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

# -- EVENT VERBS (must have at least one to be an actual event) --
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

# -- EXCLUDE PATTERNS (opinion, explainers, non-events) --
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
    """Check if article is relevant AND is an actual event (not opinion/explainer)."""
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

# -- COUNTRY EXTRACTION --
def extract_country(title, summary):
    """Extract country from title/summary. Returns None if no country found."""
    text = (title + ' ' + summary).lower()
    
    # Check for country names (longest match first to handle "South Sudan" vs "Sudan")
    sorted_countries = sorted(ALL_COUNTRIES, key=len, reverse=True)
    for country in sorted_countries:
        if country.lower() in text:
            return country
    
    # Check for demonyms and alternates
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
    
    # Check for major cities
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
    """Check if country matches the filter list."""
    if not filter_countries:
        return True  # No filter = all countries
    if not country:
        return False  # No country detected = skip
    return country in filter_countries

# -- SIMILARITY CHECK --
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

# -- SEEN ARTICLES --
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

def article_hash(url, title):
    return hashlib.md5((url + title).encode()).hexdigest()

# -- FETCH RSS FEEDS --
def fetch_rss_feeds(seen, filter_countries):
    candidates = []
    seen_titles = []

    for feed_url in RSS_FEEDS:
        log.info('Fetching RSS: %s', feed_url)
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:30]:
                title   = entry.get('title', '').strip()
                summary = entry.get('summary', entry.get('description', '')).strip()
                url     = entry.get('link', '')

                if not title or not url:
                    continue

                h = article_hash(url, title)
                if h in seen:
                    continue

                if not is_relevant(title, summary):
                    continue

                # Extract country and check filter
                country = extract_country(title, summary)
                if not matches_filter(country, filter_countries):
                    continue

                if is_duplicate(title, seen_titles):
                    log.info('Skipping duplicate: %s', title[:60])
                    continue

                candidates.append({
                    'title':     title,
                    'summary':   summary,
                    'url':       url,
                    'hash':      h,
                    'source':    feed.feed.get('title', feed_url),
                    'published': entry.get('published', ''),
                    'country':   country,
                })
                seen_titles.append(title)

        except Exception as e:
            log.warning('RSS feed error (%s): %s', feed_url, e)

    log.info('RSS: found %d relevant unseen articles', len(candidates))
    return candidates

# -- FETCH GDELT --
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
                '&mode=artlist'
                '&maxrecords=10'
                '&timespan=24h'
                '&sort=DateDesc'
                '&format=json'
            )
            r = requests.get(url, timeout=15)
            if r.status_code != 200:
                log.warning('GDELT returned %s', r.status_code)
                continue

            data = r.json()
            articles = data.get('articles', [])

            for article in articles:
                title   = article.get('title', '').strip()
                url_art = article.get('url', '')
                source  = article.get('domain', 'GDELT')

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

                candidates.append({
                    'title':     title,
                    'summary':   title,
                    'url':       url_art,
                    'hash':      h,
                    'source':    source,
                    'published': article.get('seendate', ''),
                    'country':   country,
                })
                existing_titles.append(title)

            time.sleep(1)

        except Exception as e:
            log.warning('GDELT error: %s', e)

    log.info('GDELT: found %d additional articles', len(candidates))
    return candidates

# -- FETCH ALL FEEDS --
def fetch_all_feeds(seen, filter_countries):
    rss_candidates = fetch_rss_feeds(seen, filter_countries)
    rss_titles = [c['title'] for c in rss_candidates]

    gdelt_candidates = fetch_gdelt(seen, rss_titles, filter_countries)

    all_candidates = rss_candidates + gdelt_candidates
    log.info('Total candidates: %d', len(all_candidates))
    return all_candidates[:MAX_ARTICLES]

# -- CLAUDE ARTICLE GENERATION --
SYSTEM_PROMPT = """You are an intelligence analyst for Global Witness Monitor, a platform serving
mission agencies, churches, and field workers who need accurate situational awareness in dangerous regions.

Your task is to write a factual conflict and unrest intelligence brief based strictly on the provided
source material.

CRITICAL RULES:
- Base every claim strictly on the provided source material. Do not invent names, statistics,
  casualty figures, locations, or any other details not present in the source.
- Write in a factual, measured intelligence-briefing tone -- not sensational, not emotionally charged.
- The audience is mission professionals who need accurate, actionable information about regional safety.
- Structure: lead with the key development, provide context, note implications for civilian/missionary safety where relevant.
- Do NOT editorialize about geopolitics or assign blame beyond what sources state.
- Length: 150-250 words.
- When names of people are mentioned in the source material, do not include them, refer to them as man, woman, people, etc.
- Do not include the source at the bottom of the article, just add the name somewhere in the article as according to... or something like that.
- Do not include a title in your response -- only the article body.
- End with a one-sentence Mission Note: summarizing the operational significance for field workers.

IMPORTANT: If the source material does not describe an actual event (something that happened), 
or if there is insufficient factual information to write a proper intelligence brief, 
respond with exactly: SKIP_NO_EVENT"""

# -- BAD RESPONSE PATTERNS --
BAD_RESPONSE_PATTERNS = [
    'i cannot write',
    'i cannot provide',
    'i am unable to',
    'cannot accurately',
    'cannot be accurately',
    'limited source material',
    'insufficient information',
    'not enough information',
    'based on the limited',
    'based on the extremely limited',
    'cannot generate',
    'unable to generate',
    'skip_no_event',
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
        "Write a conflict intelligence brief based on this source material only.\n\n"
        "SOURCE TITLE: " + item['title'] + "\n\n"
        "SOURCE SUMMARY: " + item['summary'] + "\n\n"
        "SOURCE URL: " + item['url'] + "\n\n"
        "SOURCE OUTLET: " + item['source'] + "\n\n"
        "Remember: only use facts present in the source material above. "
        "If this is not an actual event or lacks sufficient detail, respond with SKIP_NO_EVENT."
    )

    log.info('Generating article for: %s', item['title'])

    message = client.messages.create(
        model='claude-sonnet-4-20250514',
        max_tokens=600,
        messages=[{'role': 'user', 'content': user_prompt}],
        system=SYSTEM_PROMPT,
    )

    return message.content[0].text.strip()

# -- WORDPRESS PUBLISH --
def publish_to_wordpress(item, article_body):
    endpoint = WP_URL + '/wp-json/wp/v2/posts'
    auth     = (WP_USER, WP_APP_PASSWORD)

    country = item.get('country')

    if not country:
        log.info('Skipping (no country detected): %s', item['title'][:60])
        return False

    tag_ids = []
    try:
        r = requests.get(
            WP_URL + '/wp-json/wp/v2/tags',
            params={'search': country},
            auth=auth
        )
        existing = r.json()
        if existing:
            tag_ids.append(existing[0]['id'])
        else:
            r2 = requests.post(
                WP_URL + '/wp-json/wp/v2/tags',
                json={'name': country},
                auth=auth
            )
            if r2.status_code in (200, 201):
                tag_ids.append(r2.json()['id'])
    except Exception as e:
        log.warning('Tag error for %s: %s', country, e)

    payload = {
        'title':      item['title'],
        'content':    article_body,
        'status':     'publish',
        'categories': [WP_CATEGORY_ID],
        'tags':       tag_ids,
    }

    r = requests.post(endpoint, json=payload, auth=auth)

    if r.status_code in (200, 201):
        post = r.json()
        log.info('Published: %s [%s] (ID %s)', item['title'][:50], country, post.get('id'))
        return True
    else:
        log.error('Publish failed (%s): %s', r.status_code, r.text[:300])
        return False

# -- ARGUMENT PARSING --
def parse_args():
    parser = argparse.ArgumentParser(
        description='GWM Conflict Pipeline v4 - with region/country filtering',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run full global scan
  python run_conflict_pipeline_v4.py

  # Run only Middle East
  python run_conflict_pipeline_v4.py --region middle-east

  # Run only Africa
  python run_conflict_pipeline_v4.py --region africa

  # Run specific country
  python run_conflict_pipeline_v4.py --country Iran

  # Run multiple countries
  python run_conflict_pipeline_v4.py --country Iran --country Syria

  # Run multiple regions
  python run_conflict_pipeline_v4.py --region middle-east --region africa

Available regions: middle-east, africa, asia, europe, americas, pacific
        """
    )
    
    parser.add_argument(
        '--region', '-r',
        action='append',
        choices=list(REGIONS.keys()),
        help='Filter by region (can specify multiple)'
    )
    
    parser.add_argument(
        '--country', '-c',
        action='append',
        help='Filter by specific country (can specify multiple)'
    )
    
    parser.add_argument(
        '--list-regions',
        action='store_true',
        help='List all regions and their countries'
    )
    
    return parser.parse_args()

def build_country_filter(args):
    """Build list of countries to filter by based on args."""
    if args.list_regions:
        print("\nAvailable regions:\n")
        for region, countries in REGIONS.items():
            print(f"  {region}:")
            print(f"    {', '.join(countries)}\n")
        sys.exit(0)
    
    filter_countries = []
    
    # Add countries from specified regions
    if args.region:
        for region in args.region:
            filter_countries.extend(REGIONS[region])
    
    # Add individually specified countries
    if args.country:
        for country in args.country:
            # Normalize country name (capitalize each word)
            normalized = ' '.join(word.capitalize() for word in country.split())
            filter_countries.append(normalized)
    
    # Remove duplicates
    filter_countries = list(set(filter_countries)) if filter_countries else None
    
    return filter_countries

# -- MAIN --
def main():
    args = parse_args()
    filter_countries = build_country_filter(args)
    
    if filter_countries:
        log.info('=== Conflict Pipeline v4 starting (filtered: %d countries) ===', len(filter_countries))
        log.info('Countries: %s', ', '.join(sorted(filter_countries)[:10]) + ('...' if len(filter_countries) > 10 else ''))
    else:
        log.info('=== Conflict Pipeline v4 starting (GLOBAL - all countries) ===')

    seen       = load_seen()
    candidates = fetch_all_feeds(seen, filter_countries)

    if not candidates:
        log.info('No new relevant articles found. Done.')
        return

    published = 0
    skipped   = 0
    
    for item in candidates:
        try:
            article_body = generate_article(item)
            
            if not is_valid_article(article_body):
                log.info('Skipping (invalid/refused): %s', item['title'][:60])
                seen.add(item['hash'])
                skipped += 1
                continue
            
            success = publish_to_wordpress(item, article_body)

            if success:
                seen.add(item['hash'])
                published += 1
                time.sleep(3)
            else:
                seen.add(item['hash'])
                skipped += 1

        except Exception as e:
            log.error('Error processing "%s": %s', item['title'], e)
            continue

    save_seen(seen)
    log.info('=== Done. Published %d, Skipped %d, Total %d ===', 
             published, skipped, len(candidates))

if __name__ == '__main__':
    main()
