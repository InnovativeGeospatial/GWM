#!/usr/bin/env python3
"""
Global Witness Monitor -- Conflict & Unrest Pipeline v3
- Stricter event-based filtering (not opinion/explainers)
- Skip articles where AI can't generate proper brief
- Updated RSS sources
- GDELT free API integration
- Duplicate similarity check

Run: cd /opt/conflict-pipeline && set -a && source .env && set +a && venv/bin/python run_conflict_pipeline_v3.py
"""

import os
import json
import time
import hashlib
import logging
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
    'orders', 'ordered',  # e.g. "military orders investigation"
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
    
    # Must have conflict term
    has_conflict = any(term in text for term in CONFLICT_TERMS)
    if not has_conflict:
        return False
    
    # Must have event signal (something actually happened)
    has_event = any(signal in text for signal in EVENT_SIGNALS)
    if not has_event:
        return False
    
    # Must NOT match exclusion patterns
    title_lower = title.lower()
    for pattern in EXCLUDE_PATTERNS:
        if pattern in title_lower:
            return False
    
    return True

# -- SIMILARITY CHECK --
def title_similarity(title1, title2):
    """Simple word overlap similarity — returns 0.0 to 1.0."""
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
    """Returns True if title is too similar to any existing title."""
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
def fetch_rss_feeds(seen):
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
                })
                seen_titles.append(title)

        except Exception as e:
            log.warning('RSS feed error (%s): %s', feed_url, e)

    log.info('RSS: found %d relevant unseen articles', len(candidates))
    return candidates

# -- FETCH GDELT --
def fetch_gdelt(seen, existing_titles):
    """Fetch recent conflict events from GDELT free API."""
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
                })
                existing_titles.append(title)

            time.sleep(1)

        except Exception as e:
            log.warning('GDELT error: %s', e)

    log.info('GDELT: found %d additional articles', len(candidates))
    return candidates

# -- FETCH ALL FEEDS --
def fetch_all_feeds(seen):
    rss_candidates = fetch_rss_feeds(seen)
    rss_titles = [c['title'] for c in rss_candidates]

    gdelt_candidates = fetch_gdelt(seen, rss_titles)

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
    """Check if the generated article is valid (not a refusal or skip)."""
    lower = article_body.lower()
    for pattern in BAD_RESPONSE_PATTERNS:
        if pattern in lower:
            return False
    # Also check minimum length - valid briefs should be at least 100 words
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

# -- COUNTRY EXTRACTION --
COUNTRY_NAMES = [
    'Algeria', 'Angola', 'Benin', 'Botswana', 'Burkina Faso', 'Burundi',
    'Cameroon', 'Cape Verde', 'Central African Republic', 'Chad', 'Comoros',
    'Congo', 'Djibouti', 'Egypt', 'Equatorial Guinea', 'Eritrea', 'Eswatini',
    'Ethiopia', 'Gabon', 'Gambia', 'Ghana', 'Guinea', 'Guinea-Bissau',
    'Ivory Coast', 'Kenya', 'Lesotho', 'Liberia', 'Libya', 'Madagascar',
    'Malawi', 'Mali', 'Mauritania', 'Mauritius', 'Morocco', 'Mozambique',
    'Namibia', 'Niger', 'Nigeria', 'Rwanda', 'Senegal', 'Sierra Leone',
    'Somalia', 'South Africa', 'South Sudan', 'Sudan', 'Tanzania', 'Togo',
    'Tunisia', 'Uganda', 'Zambia', 'Zimbabwe',
    'Bahrain', 'Cyprus', 'Iran', 'Iraq', 'Israel', 'Jordan', 'Kuwait',
    'Lebanon', 'Oman', 'Palestine', 'Qatar', 'Saudi Arabia', 'Syria',
    'Turkey', 'United Arab Emirates', 'Yemen',
    'Afghanistan', 'Bangladesh', 'Bhutan', 'Brunei', 'Cambodia', 'China',
    'India', 'Indonesia', 'Japan', 'Kazakhstan', 'Kyrgyzstan', 'Laos',
    'Malaysia', 'Maldives', 'Mongolia', 'Myanmar', 'Nepal', 'North Korea',
    'Pakistan', 'Philippines', 'Singapore', 'South Korea', 'Sri Lanka',
    'Tajikistan', 'Thailand', 'Timor-Leste', 'Turkmenistan', 'Uzbekistan',
    'Vietnam',
    'Albania', 'Armenia', 'Azerbaijan', 'Belarus', 'Bosnia', 'Georgia',
    'Kosovo', 'Moldova', 'Montenegro', 'North Macedonia', 'Russia',
    'Serbia', 'Ukraine',
    'Bolivia', 'Brazil', 'Chile', 'Colombia', 'Cuba', 'Ecuador',
    'El Salvador', 'Guatemala', 'Guyana', 'Haiti', 'Honduras', 'Jamaica',
    'Mexico', 'Nicaragua', 'Panama', 'Paraguay', 'Peru', 'Trinidad',
    'Venezuela',
    'Fiji', 'Papua New Guinea', 'Solomon Islands', 'Vanuatu',
]

def extract_country(title, summary):
    text = title + ' ' + summary
    for country in COUNTRY_NAMES:
        if country.lower() in text.lower():
            return country
    return None

# -- WORDPRESS PUBLISH --
def publish_to_wordpress(item, article_body):
    endpoint = WP_URL + '/wp-json/wp/v2/posts'
    auth     = (WP_USER, WP_APP_PASSWORD)

    country = extract_country(item['title'], item['summary'])

    # Skip if no country detected (would be tagged "Global")
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
        log.info('Published: %s (ID %s)', item['title'], post.get('id'))
        return True
    else:
        log.error('Publish failed (%s): %s', r.status_code, r.text[:300])
        return False

# -- MAIN --
def main():
    log.info('=== Conflict Pipeline v3 starting ===')

    seen       = load_seen()
    candidates = fetch_all_feeds(seen)

    if not candidates:
        log.info('No new relevant articles found. Done.')
        return

    published = 0
    skipped   = 0
    
    for item in candidates:
        try:
            article_body = generate_article(item)
            
            # Check if article is valid
            if not is_valid_article(article_body):
                log.info('Skipping (invalid/refused): %s', item['title'][:60])
                seen.add(item['hash'])  # Mark as seen so we don't retry
                skipped += 1
                continue
            
            success = publish_to_wordpress(item, article_body)

            if success:
                seen.add(item['hash'])
                published += 1
                time.sleep(3)
            else:
                # If publish failed due to no country, still mark as seen
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
