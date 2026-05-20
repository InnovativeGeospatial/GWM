#!/usr/bin/env python3
"""
Global Witness Monitor -- Persecution Pipeline v4

Changes from v3:
- Token-delimited output. Claude now returns body sections as
  "PARA: <text>" and "PRAYER: <text>" and "HEADLINE: <text>" on their own
  lines. The post-processor splits on these tokens rather than on blank
  lines, which v3 couldn't reliably enforce. Bulletproof against Claude
  collapsing whitespace.
- "Prayer:" line treatment. The final paragraph is wrapped in
  <p class="gwm-prayer-line"><strong>Prayer:</strong> ...</p> so the
  WordPress site can style it distinctly via CSS.
- Fallback: if Claude ignores PARA tokens and returns one block, the
  pipeline sentence-splits into two paragraphs as a safety net.
"""

import os
import re
import sys
import time
import hashlib
import json
import html
import feedparser
import requests
from datetime import datetime, timezone, timedelta
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv('/opt/global-witness/.env')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import gwm_json_writer
    JSON_WRITER_AVAILABLE = True
except ImportError:
    JSON_WRITER_AVAILABLE = False

client = Anthropic()
WP_URL = os.getenv('WP_URL')
WP_USER = os.getenv('WP_USER')
WP_APP_PASSWORD = os.getenv('WP_APP_PASSWORD')
SEEN_FILE = '/opt/global-witness/seen_articles.json'
FEED_NAME = 'persecution'

RSS_FEEDS = [
    'https://morningstarnews.org/feed/',
    'https://www.persecution.org/feed/',
    'https://www.uscirf.gov/rss.xml',
    'https://www.opendoorsusa.org/feed/',
    'https://www.barnabasfund.org/feed/',
    'https://acninternational.org/feed/',
    'https://www.forum18.org/RSS.php',
    'https://www.ucanews.com/feed',
    'https://cruxnow.com/feed/',
    'https://chinaaid.org/feed/',
    'https://www.copticsolidarity.org/feed/',
    'https://news.google.com/rss/search?q=christian+killed+pastor+church&hl=en',
    'https://news.google.com/rss/search?q=christian+arrested+detained+faith&hl=en',
    'https://news.google.com/rss/search?q=church+burned+attacked+demolished&hl=en',
    'https://news.google.com/rss/search?q=christian+blasphemy+sentenced+prison&hl=en',
    'https://news.google.com/rss/search?q=christian+persecution+convert+killed&hl=en',
]

MAINSTREAM_SOURCES = [
    'bbc', 'reuters', 'aljazeera', 'hrw', 'amnesty', 'dw',
    'guardian', 'associated press', 'ap news',
]

PERSECUTION_SIGNALS = [
    'killed', 'kills', 'kill', 'murdered', 'murder', 'executed', 'execution',
    'beheaded', 'massacre', 'shot dead', 'slain', 'lynched',
    'arrested', 'detained', 'imprisoned', 'jailed', 'sentenced', 'convicted',
    'attacked', 'bombed', 'burned', 'demolished', 'destroyed', 'raided',
    'persecuted', 'persecution', 'martyred', 'martyr',
    'blasphemy', 'apostasy', 'forced conversion', 'forced to convert',
    'expelled', 'displaced', 'fled', 'refugee', 'evicted',
    'threatened', 'kidnapped', 'abducted', 'tortured', 'beaten',
    'banned', 'confiscated', 'closed down', 'shuttered',
    'discrimination', 'harassed', 'intimidated',
]

CHRISTIAN_IDENTIFIERS = [
    'christian', 'christians', 'church', 'churches', 'pastor', 'priest',
    'bishop', 'deacon', 'nun', 'monk',
    'missionary', 'missionaries', 'convert', 'converts', 'evangelical',
    'catholic', 'protestant', 'orthodox', 'pentecostal', 'baptist',
    'anglican', 'lutheran', 'methodist',
    'diocese', 'parish', 'chapel', 'cathedral', 'bible', 'bibles',
    'cross', 'crucifix', 'gospel', 'congregation', 'believer', 'believers',
    'worshipper', 'worshippers', 'house church', 'underground church',
]

EXCLUDE_TITLE_PATTERNS = [
    'mystery of suffering', 'book of job', 'bible study', 'devotional',
    'sermon series', 'prayer guide', 'reflection on', 'theological reflection',
    'policy analysis', 'policy perspective', 'op-ed', 'opinion:',
    'perspective:', 'analysis:', 'commentary:', 'podcast:', 'column:',
    'book review', 'film review', 'music review',
    'what the bible says', 'how to pray', 'study guide', 'sermon notes',
    'christian bale', 'christian mccaffrey', 'christian dior',
    'christian louboutin', 'christian siriano', 'christian pulisic',
    'church architecture', 'church music history',
    'christmas shopping', 'easter shopping', 'holiday shopping',
]

COUNTRY_CENTROIDS = {
    'afghanistan': [65.0, 33.9], 'albania': [20.2, 41.2], 'algeria': [2.6, 28.0],
    'angola': [17.9, -11.2], 'argentina': [-63.6, -38.4], 'armenia': [45.0, 40.1],
    'australia': [133.8, -25.3], 'austria': [14.6, 47.5], 'azerbaijan': [47.6, 40.1],
    'bahrain': [50.6, 26.0], 'bangladesh': [90.4, 23.7], 'belarus': [28.0, 53.7],
    'belgium': [4.5, 50.5], 'belize': [-88.5, 17.2], 'benin': [2.3, 9.3],
    'bolivia': [-64.7, -16.3], 'bosnia': [17.7, 43.9], 'botswana': [24.7, -22.3],
    'brazil': [-51.9, -14.2], 'brunei': [114.7, 4.5], 'bulgaria': [25.5, 42.7],
    'burkina faso': [-1.6, 12.4], 'burundi': [29.9, -3.4], 'cabo verde': [-24.0, 16.0],
    'cambodia': [104.9, 12.6], 'cameroon': [12.4, 3.9], 'canada': [-96.8, 60.0],
    'central african republic': [20.9, 6.6], 'chad': [18.7, 15.5],
    'chile': [-71.5, -35.7], 'china': [104.2, 35.9], 'colombia': [-74.3, 4.1],
    'comoros': [43.9, -11.9], 'congo': [15.8, -0.2], 'costa rica': [-83.8, 9.7],
    "cote d'ivoire": [-5.5, 7.5], 'croatia': [15.2, 45.1], 'cuba': [-79.5, 21.5],
    'cyprus': [33.4, 35.1], 'czech republic': [15.5, 49.8], 'denmark': [9.5, 56.3],
    'djibouti': [42.6, 11.8], 'dominica': [-61.4, 15.4],
    'dominican republic': [-70.5, 18.7],
    'dr congo': [24.0, -2.9], 'ecuador': [-78.1, -1.8], 'egypt': [30.8, 26.8],
    'el salvador': [-88.9, 13.8], 'equatorial guinea': [10.3, 1.7],
    'eritrea': [39.8, 15.2], 'estonia': [25.0, 58.6], 'eswatini': [31.5, -26.5],
    'ethiopia': [40.5, 9.1], 'fiji': [178.1, -17.7], 'finland': [26.0, 64.0],
    'france': [2.2, 46.2], 'gabon': [11.6, -0.8], 'gambia': [-15.3, 13.4],
    'georgia': [43.4, 42.3], 'germany': [10.5, 51.2], 'ghana': [-1.0, 7.9],
    'greece': [21.8, 39.1], 'guatemala': [-90.2, 15.8], 'guinea': [-11.3, 11.0],
    'guinea-bissau': [-15.2, 11.8], 'guyana': [-59.0, 5.0], 'haiti': [-72.3, 19.0],
    'honduras': [-86.2, 14.8], 'hungary': [19.5, 47.2], 'iceland': [-18.7, 64.9],
    'india': [78.7, 20.6], 'indonesia': [113.9, -0.8], 'iran': [53.7, 32.4],
    'iraq': [43.7, 33.2], 'ireland': [-8.2, 53.4], 'israel': [34.9, 31.0],
    'italy': [12.6, 42.5], 'jamaica': [-77.3, 18.1], 'japan': [138.3, 36.2],
    'jordan': [37.2, 30.6], 'kazakhstan': [66.9, 48.0], 'kenya': [37.9, 0.0],
    'kosovo': [20.9, 42.6], 'kuwait': [47.5, 29.3], 'kyrgyzstan': [74.8, 41.2],
    'laos': [103.0, 18.2], 'latvia': [24.6, 56.9], 'lebanon': [35.9, 33.9],
    'lesotho': [28.2, -29.6], 'liberia': [-9.4, 6.4], 'libya': [17.2, 26.3],
    'lithuania': [23.9, 55.2], 'luxembourg': [6.1, 49.8],
    'madagascar': [46.9, -18.8], 'malawi': [34.3, -13.2], 'malaysia': [109.7, 4.2],
    'maldives': [73.2, 3.2], 'mali': [-2.0, 17.6], 'malta': [14.4, 35.9],
    'mauritania': [-10.9, 20.3], 'mauritius': [57.6, -20.3],
    'mexico': [-102.6, 23.6], 'moldova': [28.4, 47.4], 'mongolia': [103.8, 46.9],
    'montenegro': [19.4, 42.7], 'morocco': [-7.1, 31.8], 'mozambique': [35.5, -18.7],
    'myanmar': [95.9, 17.1], 'namibia': [18.5, -22.0], 'nepal': [84.1, 28.4],
    'netherlands': [5.3, 52.1], 'new zealand': [172.0, -41.5],
    'nicaragua': [-85.2, 12.9], 'niger': [8.1, 17.6], 'nigeria': [8.7, 9.1],
    'north korea': [127.5, 40.3], 'north macedonia': [21.7, 41.6],
    'norway': [8.5, 60.5], 'oman': [57.5, 21.5], 'pakistan': [69.3, 30.4],
    'palestine': [35.2, 31.9], 'panama': [-80.8, 8.5],
    'papua new guinea': [143.9, -6.3], 'paraguay': [-58.4, -23.4],
    'peru': [-75.0, -9.2], 'philippines': [122.9, 12.9], 'poland': [19.1, 52.1],
    'portugal': [-8.2, 39.4], 'qatar': [51.2, 25.4], 'romania': [24.9, 45.9],
    'russia': [105.3, 61.5], 'rwanda': [29.9, -2.0], 'saudi arabia': [45.1, 24.0],
    'senegal': [-14.5, 14.5], 'serbia': [21.0, 44.0],
    'sierra leone': [-11.8, 8.5], 'singapore': [103.8, 1.4],
    'slovakia': [19.7, 48.7], 'slovenia': [14.8, 46.1],
    'solomon islands': [160.2, -9.6], 'somalia': [46.2, 6.1],
    'south africa': [25.1, -29.0], 'south korea': [127.8, 35.9],
    'south sudan': [31.3, 6.9], 'spain': [-3.7, 40.5], 'sri lanka': [80.7, 7.9],
    'sudan': [29.9, 12.9], 'suriname': [-56.0, 3.9], 'sweden': [18.6, 60.1],
    'switzerland': [8.2, 46.8], 'syria': [38.3, 34.8], 'taiwan': [120.9, 23.7],
    'tajikistan': [71.3, 38.9], 'tanzania': [34.9, -6.4], 'thailand': [101.0, 15.9],
    'timor-leste': [125.7, -8.9], 'togo': [0.8, 8.6], 'tonga': [-175.2, -21.2],
    'trinidad and tobago': [-61.2, 10.7], 'tunisia': [9.0, 33.9],
    'turkey': [35.2, 38.9], 'turkmenistan': [59.6, 39.0], 'uganda': [32.3, 1.4],
    'ukraine': [31.2, 48.4], 'united arab emirates': [53.8, 23.4],
    'united kingdom': [-3.4, 55.4], 'united states': [-95.7, 37.1],
    'uruguay': [-55.8, -32.5], 'uzbekistan': [63.9, 41.4], 'vanuatu': [166.9, -15.4],
    'vatican city': [12.5, 41.9], 'venezuela': [-66.6, 6.4],
    'vietnam': [108.3, 14.1], 'yemen': [47.6, 15.6], 'zambia': [27.8, -13.1],
    'zimbabwe': [30.0, -19.0],
}

_CANONICAL_COUNTRIES = set(COUNTRY_CENTROIDS.keys())

_COUNTRY_ALIASES = {
    'usa': 'united states', 'us': 'united states', 'u.s.': 'united states',
    'u.s.a.': 'united states', 'america': 'united states',
    'uk': 'united kingdom', 'u.k.': 'united kingdom',
    'britain': 'united kingdom', 'great britain': 'united kingdom',
    'england': 'united kingdom', 'scotland': 'united kingdom',
    'wales': 'united kingdom', 'uae': 'united arab emirates',
    'drc': 'dr congo',
    'democratic republic of congo': 'dr congo',
    'democratic republic of the congo': 'dr congo',
    'republic of congo': 'congo', 'congo-brazzaville': 'congo',
    'congo-kinshasa': 'dr congo',
    'burma': 'myanmar', 'czechia': 'czech republic',
    'ivory coast': "cote d'ivoire", 'cote d ivoire': "cote d'ivoire",
    'east timor': 'timor-leste', 'timor leste': 'timor-leste',
    'swaziland': 'eswatini', 'cape verde': 'cabo verde',
    'vatican': 'vatican city', 'holy see': 'vatican city',
    'palestinian territories': 'palestine', 'west bank': 'palestine',
    'gaza': 'palestine', 'gaza strip': 'palestine',
    's korea': 'south korea', 'n korea': 'north korea',
    'korea republic': 'south korea', 'dprk': 'north korea', 'rok': 'south korea',
    'bosnia and herzegovina': 'bosnia',
    'macedonia': 'north macedonia', 'turkiye': 'turkey',
    'russian federation': 'russia',
}


def validate_country(name):
    if not name:
        return None
    n = name.strip().lower().strip('.,;:')
    if n in _CANONICAL_COUNTRIES:
        return n
    if n in _COUNTRY_ALIASES:
        aliased = _COUNTRY_ALIASES[n]
        if aliased in _CANONICAL_COUNTRIES:
            return aliased
    return None


def parse_claude_response(text):
    """Parse the COUNTRY/--- header and return the rest verbatim."""
    out = {'status': 'malformed', 'countries': [], 'body': text, 'raw_country': ''}
    if not text:
        return out
    lines = text.split('\n')
    if len(lines) < 3:
        return out
    header = lines[0].strip()
    sep = lines[1].strip()
    if not header.upper().startswith('COUNTRY:'):
        return out
    if sep != '---':
        return out
    value = header.split(':', 1)[1].strip()
    out['raw_country'] = value
    out['body'] = '\n'.join(lines[2:]).strip()
    if not value or value.upper() == 'UNKNOWN':
        out['status'] = 'unknown'
        return out
    if value.upper().startswith('MULTIPLE:'):
        raw_list = value.split(':', 1)[1]
        candidates = [c.strip() for c in raw_list.split(',') if c.strip()]
    else:
        candidates = [value]
    validated = []
    for c in candidates:
        v = validate_country(c)
        if v and v not in validated:
            validated.append(v)
    if not validated:
        out['status'] = 'no_valid_country'
        return out
    out['countries'] = validated
    out['status'] = 'ok'
    return out


def load_seen():
    try:
        with open(SEEN_FILE, 'r') as f:
            return set(json.load(f))
    except Exception:
        return set()


def save_seen(seen):
    os.makedirs(os.path.dirname(SEEN_FILE), exist_ok=True)
    with open(SEEN_FILE, 'w') as f:
        json.dump(list(seen), f)

def purge_jsdelivr(filename):
    try:
        url = "https://purge.jsdelivr.net/gh/InnovativeGeospatial/GWM@main/" + filename
        r = requests.get(url, timeout=20)
        print("jsDelivr purge " + filename + " -> " + str(r.status_code))
    except Exception as e:
        print("jsDelivr purge failed for " + filename + ": " + str(e))

def article_hash(title):
    return hashlib.md5(title.lower().strip()[:100].encode()).hexdigest()


def is_mainstream(feed_url, feed_title):
    combined = (feed_url + ' ' + feed_title).lower()
    return any(s in combined for s in MAINSTREAM_SOURCES)


_COUNTRY_WORD_RE_CACHE = {}


def _country_word_re(country):
    if country not in _COUNTRY_WORD_RE_CACHE:
        _COUNTRY_WORD_RE_CACHE[country] = re.compile(
            r'\b' + re.escape(country) + r'\b', re.IGNORECASE
        )
    return _COUNTRY_WORD_RE_CACHE[country]


def has_country_mention(text):
    if not text:
        return False
    for c in _CANONICAL_COUNTRIES:
        if _country_word_re(c).search(text):
            return True
    for alias in _COUNTRY_ALIASES.keys():
        if _country_word_re(alias).search(text):
            return True
    return False


def is_news_incident(title, content):
    title_lower = title.lower()
    for pattern in EXCLUDE_TITLE_PATTERNS:
        if pattern in title_lower:
            return False
    text_check = title_lower + ' ' + content[:1500].lower()
    return has_country_mention(text_check)


def is_relevant(title, content, feed_url, feed_title):
    title_lower = title.lower()
    content_lower = content.lower()

    if not is_news_incident(title, content):
        return False

    combined = title_lower + ' ' + content_lower[:1500]
    has_ci = any(ci in combined for ci in CHRISTIAN_IDENTIFIERS)
    if not has_ci:
        return False

    if is_mainstream(feed_url, feed_title):
        check_text = title_lower + ' ' + content_lower[:500]
        has_ps = any(ps in check_text for ps in PERSECUTION_SIGNALS)
        if not has_ps:
            return False

    return True


def fetch_full_content(url):
    try:
        r = requests.get(
            url, timeout=8,
            headers={'User-Agent': 'Mozilla/5.0 (compatible; GlobalWitnessMonitor/1.0)'}
        )
        if r.status_code == 200:
            text = re.sub(r'<script[^>]*>.*?</script>', '', r.text, flags=re.DOTALL)
            text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
            text = re.sub(r'<[^>]+>', ' ', text)
            text = re.sub(r'\s+', ' ', text).strip()
            return text[:3000]
    except Exception:
        pass
    return None


def detect_country(title, content):
    text = (title + ' ' + (content or '')).lower()
    for country in sorted(_CANONICAL_COUNTRIES, key=len, reverse=True):
        if _country_word_re(country).search(text):
            return country
    for alias, canonical in _COUNTRY_ALIASES.items():
        if _country_word_re(alias).search(text):
            return canonical
    return None


def detect_type(title, content):
    text = (title + ' ' + content).lower()
    if any(k in text for k in ['kill', 'murder', 'execut', 'behead', 'massacre', 'shot dead', 'lynch']):
        return 'killing'
    if any(k in text for k in ['church burn', 'church attack', 'church demolish',
                                'church destroy', 'church raid', 'chapel burn']):
        return 'church'
    if any(k in text for k in ['displace', 'flee', 'fled', 'refugee', 'expel',
                                'evict', 'forced from home']):
        return 'displacement'
    return 'arrest'


def fetch_articles(seen):
    articles = []
    seen_titles = set()
    stats = {'fetched': 0, 'too_old': 0, 'already_seen': 0, 'thin': 0,
             'not_relevant': 0, 'kept': 0}

    for feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            feed_title = feed.feed.get('title', feed_url)
            for entry in feed.entries[:20]:
                stats['fetched'] += 1
                title = entry.get('title', '').strip()
                summary = entry.get('summary', '')
                link = entry.get('link', '')
                content = entry.get('content', [{}])[0].get('value', summary)
                if not title:
                    continue
                published = entry.get('published_parsed') or entry.get('updated_parsed')
                if published:
                    pub_dt = datetime(*published[:6], tzinfo=timezone.utc)
                    if datetime.now(timezone.utc) - pub_dt > timedelta(hours=72):
                        stats['too_old'] += 1
                        continue
                h = article_hash(title)
                if h in seen or title.lower() in seen_titles:
                    stats['already_seen'] += 1
                    continue
                clean = re.sub(r'<[^>]+>', ' ', content).strip()
                if len(clean) < 200:
                    fetched = fetch_full_content(link)
                    if fetched and len(fetched) > 200:
                        clean = fetched
                    else:
                        stats['thin'] += 1
                        print('Skipping thin: ' + title[:60])
                        continue
                if not is_relevant(title, clean, feed_url, feed_title):
                    stats['not_relevant'] += 1
                    continue
                seen_titles.add(title.lower())
                country = detect_country(title, clean)
                inc_type = detect_type(title, clean)
                coords = COUNTRY_CENTROIDS.get(country)
                if coords:
                    lat = coords[1]
                    lng = coords[0]
                else:
                    lat = None
                    lng = None
                articles.append({
                    'title': title,
                    'content': clean[:3000],
                    'link': link,
                    'source': feed_title,
                    'hash': h,
                    'country': country,
                    'incident_type': inc_type,
                    'lat': lat,
                    'lng': lng,
                })
                stats['kept'] += 1
            print('Fetched: ' + feed_url)
        except Exception as e:
            print('Error: ' + feed_url + ' - ' + str(e))

    print('Filter stats: ' + json.dumps(stats))
    print('Found ' + str(len(articles)) + ' candidate articles (pre-Claude-judge)')
    return articles


JUDGE_SYSTEM = (
    "You decide whether a news article describes an actual incident of "
    "Christian persecution suitable for Global Witness Monitor, a platform "
    "tracking persecution against Christians worldwide.\n\n"
    "An article QUALIFIES if it reports a specific event in which Christians, "
    "churches, clergy, missionaries, converts, or Christian institutions were "
    "harmed, threatened, restricted, arrested, attacked, killed, displaced, "
    "evicted, banned, or otherwise persecuted because of their faith or "
    "religious activity.\n\n"
    "An article DOES NOT QUALIFY if it is:\n"
    "- A policy/legislative debate (e.g. parliament debating a bill, even if "
    "Christian leaders weigh in for or against it)\n"
    "- An advocacy or opinion piece by Christians on social/political issues\n"
    "- Religious commentary, sermons, devotionals, theology, or worship news\n"
    "- General news where Christianity is incidental (e.g. a Christian was a "
    "victim of generic crime unrelated to their faith)\n"
    "- A roundup, anniversary piece, explainer, or background analysis\n"
    "- Coverage of Christian holidays, services, or events without an incident\n"
    "- News about Christian denominations' internal politics or appointments\n"
    "- Stories where the persecution happened to non-Christians\n\n"
    "Respond with EXACTLY one line in this format:\n"
    "VERDICT: YES | reason: <short reason>\n"
    "or\n"
    "VERDICT: NO | reason: <short reason>\n"
    "\n"
    "Be strict. When in doubt, answer NO. False positives hurt the platform "
    "more than missing a borderline story."
)


def judge_article(article):
    prompt = (
        "TITLE: " + article['title'] + "\n\n"
        "SOURCE: " + article['source'] + "\n\n"
        "CONTENT: " + article['content'][:2000] + "\n\n"
        "Is this an actual persecution incident as defined? Respond with the "
        "VERDICT line only."
    )
    try:
        msg = client.messages.create(
            model='claude-haiku-4-5-20251001',
            max_tokens=120,
            system=JUDGE_SYSTEM,
            messages=[{'role': 'user', 'content': prompt}],
        )
        raw = msg.content[0].text.strip()
        first = raw.split('\n', 1)[0].strip()
        verdict = 'NO'
        reason = ''
        m = re.match(r'VERDICT:\s*(YES|NO)\s*\|\s*reason:\s*(.*)', first, re.IGNORECASE)
        if m:
            verdict = m.group(1).upper()
            reason = m.group(2).strip()
        else:
            if re.search(r'\bYES\b', first, re.IGNORECASE):
                verdict = 'YES'
            elif re.search(r'\bNO\b', first, re.IGNORECASE):
                verdict = 'NO'
            reason = first[:120]
        return verdict, reason
    except Exception as e:
        print('Judge call failed: ' + str(e))
        return 'NO', 'judge_error: ' + str(e)[:80]


def fetch_full_article(url):
    try:
        r = requests.get(
            url, timeout=10,
            headers={'User-Agent': 'Mozilla/5.0 (compatible; GlobalWitnessMonitor/1.0)'}
        )
        if r.status_code == 200:
            text = re.sub(r'<script[^>]*>.*?</script>', '', r.text, flags=re.DOTALL)
            text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
            text = re.sub(r'<[^>]+>', ' ', text)
            text = re.sub(r'\s+', ' ', text).strip()
            return text[:4000]
    except Exception:
        pass
    return ''


def generate_article(article):
    body_text = fetch_full_article(article['link'])
    body_section = ''
    if body_text:
        print('Fetched ' + str(len(body_text)) + ' chars of full article')
        body_section = "FULL ARTICLE BODY:\n" + body_text + "\n\n"

    prompt = (
        'You are a journalist for Global Witness Monitor, a Christian persecution intelligence platform.\n\n'
        'STRUCTURED OUTPUT REQUIRED. Your response MUST follow this exact format:\n\n'
        'COUNTRY: <country_name | MULTIPLE: country1, country2 | UNKNOWN>\n'
        '---\n'
        'PARA: <first paragraph - what happened>\n'
        'PARA: <second paragraph - context, details, or pattern>\n'
        'PARA: <third paragraph - additional context, OPTIONAL>\n'
        'PRAYER: <one short prayer sentence; do NOT start with the word Pray; just write what should be prayed for>\n'
        'HEADLINE: <short descriptive headline, no personal names>\n\n'
        'Each section MUST start with its label (PARA: or PRAYER: or HEADLINE:) on its own line. Do not merge paragraphs. Do not skip the PRAYER: section.\n\n'
        'COUNTRY rules:\n'
        '- Use the country where the persecution event occurred, not the country of the outlet.\n'
        '- If multiple countries are substantively involved, use MULTIPLE: c1, c2.\n'
        '- Use UNKNOWN only if no country can be reasonably determined.\n'
        '- Use common country names: united states, united kingdom, dr congo, north korea, south korea, etc.\n\n'
        'Write a factual 100-250 word news report (total across all PARA sections) based ONLY on the source material below.\n\n'
        'STRICT RULES:\n'
        '- Only include facts present in the source material\n'
        '- Never invent names, statistics, dates, or locations\n'
        '- Never fabricate quotes\n'
        '- Redact identifying details to protect local communities:\n'
        "  - No personal names (replace with: man, woman, pastor, bishop, girl, boy, family, group, convert, believer)\n"
        "  - No specific church names (e.g. 'Linfen Covenant Home Church' -> 'a house church')\n"
        "  - No specific local ministry or denomination names within the country\n"
        "  - No towns, villages, counties, districts, or provinces (use the country only)\n"
        "  - You MAY name the external reporting watchdog (e.g. 'according to ChinaAid', 'according to Open Doors')\n"
        '- These redaction rules apply EVEN IF the source material includes the specific names. Redaction is required, not optional.\n'
        '- Mention the source naturally in the text\n'
        '- No source list at the end\n'
        '- No headers or sections inside paragraphs\n'
        '- Never repeat the same point twice\n'
        '- 2 or 3 PARA sections total. Do not combine all content into one PARA.\n'
        '- PRAYER: line should be a single specific prayer point related to this story\n\n'
        'SOURCE: ' + article['source'] + '\n'
        'TITLE: ' + article['title'] + '\n\n'
        + body_section +
        'SUMMARY: ' + article['content'] + '\n\nWrite now:'
    )
    response = client.messages.create(
        model='claude-sonnet-4-6',
        max_tokens=1000,
        messages=[{'role': 'user', 'content': prompt}],
    )
    raw = response.content[0].text
    parsed = parse_claude_response(raw)
    return raw, parsed


def is_refusal(text):
    signals = [
        'report unavailable', 'cannot write', 'i cannot', 'i am unable',
        'source material provided', 'only a headline', 'no article content',
        'insufficient information', 'unable to write',
    ]
    return any(s in text.lower() for s in signals)


def parse_tokenized_body(body_text):
    """Parse PARA: / PRAYER: / HEADLINE: tokenized response into clean fields."""
    out = {'paragraphs': [], 'prayer': '', 'headline': None}
    if not body_text:
        return out

    lines = body_text.split('\n')
    current_label = None
    current_buf = []

    def flush():
        if current_label is None or not current_buf:
            return
        text = ' '.join(s.strip() for s in current_buf if s.strip())
        text = re.sub(r'\s+', ' ', text).strip()
        if not text:
            return
        if current_label == 'PARA':
            out['paragraphs'].append(text)
        elif current_label == 'PRAY':
            text = re.sub(r'^pray[:\s]+(that\s+)?', '', text, flags=re.IGNORECASE)
            text = re.sub(r'^that\s+', '', text, flags=re.IGNORECASE)
            out['prayer'] = text
        elif current_label == 'HEADLINE':
            out['headline'] = text

    for line in lines:
        stripped = line.strip()
        m = re.match(r'^(PARA|PRAY|HEADLINE)\s*:\s*(.*)$', stripped, re.IGNORECASE)
        if m:
            flush()
            current_label = m.group(1).upper()
            current_buf = [m.group(2)]
        else:
            if current_label is not None:
                current_buf.append(stripped)
    flush()
    return out


def split_into_paragraphs_fallback(text, target_paragraphs=2):
    """Fallback when Claude returns one giant paragraph despite instructions."""
    if not text:
        return []
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    sentences = [s.strip() for s in sentences if s.strip()]
    if not sentences:
        return [text]
    if len(sentences) <= 2:
        return [' '.join(sentences)]
    chunk_size = max(2, len(sentences) // target_paragraphs)
    chunks = []
    for i in range(0, len(sentences), chunk_size):
        chunk = ' '.join(sentences[i:i + chunk_size])
        if chunk:
            chunks.append(chunk)
    return chunks


def format_body_for_wordpress(paragraphs, prayer):
    """Build the final WordPress HTML body from clean paragraph list + prayer."""
    parts = []
    for p in paragraphs:
        if not p:
            continue
        p_clean = html.unescape(p).strip()
        p_clean = re.sub(r'\s+', ' ', p_clean)
        parts.append('<p>' + p_clean + '</p>')
    if prayer:
        pr_clean = html.unescape(prayer).strip()
        pr_clean = re.sub(r'\s+', ' ', pr_clean)
        parts.append(
            '<p class="gwm-prayer-line"><strong>Prayer:</strong> ' + pr_clean + '</p>'
        )
    return '\n\n'.join(parts)


def get_or_create_category(name, slug):
    auth = (WP_USER, WP_APP_PASSWORD)
    r = requests.get(WP_URL + '/wp-json/wp/v2/categories?slug=' + slug, auth=auth)
    cats = r.json()
    if cats:
        return cats[0]['id']
    r = requests.post(
        WP_URL + '/wp-json/wp/v2/categories',
        auth=auth, json={'name': name, 'slug': slug},
    )
    return r.json().get('id')


def publish_to_wordpress(article, headline, formatted_body):
    auth = (WP_USER, WP_APP_PASSWORD)
    cat_id = get_or_create_category('Persecution Reports', 'persecution-reports')
    meta_html = (
        '<div class="gwm-meta" style="display:none;"' +
        ' data-country="' + (article['country'] or '') + '"' +
        ' data-type="' + article['incident_type'] + '"' +
        ' data-lat="' + str(article['lat'] or '') + '"' +
        ' data-lng="' + str(article['lng'] or '') + '"></div>'
    )
    title = headline or article['title']
    post_data = {
        'title': title,
        'content': formatted_body + meta_html,
        'status': 'publish',
        'categories': [cat_id],
        'excerpt': article['content'][:200],
    }
    r = requests.post(WP_URL + '/wp-json/wp/v2/posts', auth=auth, json=post_data)
    if r.status_code == 201:
        print('Published: ' + title[:60])
        return r.json()
    else:
        print('Failed: ' + str(r.status_code))
        return None


def run():
    print('=== Global Witness Monitor - Persecution Pipeline v4 ===')
    if not JSON_WRITER_AVAILABLE:
        print('WARNING: gwm_json_writer.py not found alongside this script - '
              'JSON feeds will NOT be updated. Dashboard will not show new events.')
    seen = load_seen()
    print('Previously seen: ' + str(len(seen)) + ' articles')
    articles = fetch_articles(seen)
    if not articles:
        print('No new articles found.')
        return
    published = 0
    skipped = 0
    judged_no = 0
    json_writes = 0
    for article in articles:
        try:
            verdict, reason = judge_article(article)
            print('JUDGE: ' + verdict + ' | ' + reason[:80] + ' | ' + article['title'][:60])
            if verdict != 'YES':
                judged_no += 1
                seen.add(article['hash'])
                continue

            print('Processing: ' + article['title'][:60])
            raw, parsed = generate_article(article)

            claude_country = ','.join(parsed['countries']) if parsed['countries'] else '-'
            detected_country = article.get('country') or '-'
            print(
                'CLAUDE_VS_DETECTED: claude_country=' + claude_country +
                ' detected_country=' + detected_country +
                ' status=' + parsed['status'] +
                " raw='" + parsed['raw_country'] + "'"
            )

            if parsed['status'] != 'ok':
                print('Skipping (' + parsed['status'] + '): ' + article['title'][:60])
                skipped += 1
                seen.add(article['hash'])
                continue

            primary = parsed['countries'][0]
            article['country'] = primary
            coords = COUNTRY_CENTROIDS.get(primary)
            if coords:
                article['lat'] = coords[1]
                article['lng'] = coords[0]
            else:
                article['lat'] = None
                article['lng'] = None

            generated = parsed['body']
            if is_refusal(generated):
                print('Skipping - refused')
                skipped += 1
                seen.add(article['hash'])
                continue

            tokens = parse_tokenized_body(generated)
            paragraphs = tokens['paragraphs']
            prayer = tokens['prayer']
            headline = tokens['headline']

            if not paragraphs:
                print('No PARA tokens found - using sentence-split fallback')
                paragraphs = split_into_paragraphs_fallback(generated, target_paragraphs=2)
            elif len(paragraphs) == 1 and len(paragraphs[0]) > 600:
                print('One large PARA found - splitting by sentences')
                paragraphs = split_into_paragraphs_fallback(paragraphs[0], target_paragraphs=2)

            total_len = sum(len(p) for p in paragraphs)
            if total_len < 50:
                print('Skipping - body too short')
                skipped += 1
                continue

            formatted_body = format_body_for_wordpress(paragraphs, prayer)

            print('FORMAT: paragraphs=' + str(len(paragraphs)) +
                  ' prayer=' + ('yes' if prayer else 'no') +
                  ' total_chars=' + str(total_len))

            result = publish_to_wordpress(article, headline, formatted_body)
            if result:
                published += 1
                seen.add(article['hash'])

                if JSON_WRITER_AVAILABLE:
                    try:
                        post_id = result.get('id')
                        post_link = result.get('link')
                        post_date = result.get('date_gmt') or result.get('date') or ''
                        event = {
                            'wp_id': post_id,
                            'wp_link': post_link,
                            'date': post_date or datetime.now(timezone.utc).isoformat(),
                            'title': headline or article['title'],
                            'body': formatted_body,
                            'country': primary,
                            'countries': parsed['countries'],
                            'type': article['incident_type'],
                            'lat': article['lat'],
                            'lng': article['lng'],
                            'source_title': article.get('source', ''),
                            'source_url': article.get('link', ''),
                            'prayer': prayer,
                        }
                        gwm_json_writer.write_event(FEED_NAME, event)
                        json_writes += 1
                    except Exception as e:
                        print('JSON write_event failed: ' + str(e))
            time.sleep(2)
        except Exception as e:
            print('Error: ' + str(e))
    save_seen(seen)

    if JSON_WRITER_AVAILABLE and json_writes > 0:
        try:
            print('Pushing ' + str(json_writes) + ' new events to GitHub JSON feeds...')
            written = gwm_json_writer.finalize(FEED_NAME)
            print('JSON feed updated: active=' + str(written.get('active')) +
                  ' archives=' + ','.join(written.get('archives', [])))
            purge_jsdelivr("persecution.json")
        except Exception as e:
            print('JSON finalize failed: ' + str(e))

    print('=== Done. Published: ' + str(published) +
          ' Judged-NO: ' + str(judged_no) +
          ' Skipped: ' + str(skipped) +
          ' JSON writes: ' + str(json_writes) + ' ===')


if __name__ == '__main__':
    run()
