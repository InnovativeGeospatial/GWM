import os
import re
import time
import hashlib
import json
import random
import feedparser
import requests
from datetime import datetime, timezone, timedelta
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv('/opt/global-witness/.env')

client = Anthropic()
WP_URL = os.getenv('WP_URL')
WP_USER = os.getenv('WP_USER')
WP_APP_PASSWORD = os.getenv('WP_APP_PASSWORD')
SEEN_FILE = '/opt/global-witness/seen_articles.json'

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
    'bbc','reuters','aljazeera','hrw','amnesty','dw','guardian','associated press'
]

PERSECUTION_SIGNALS = [
    'killed','murder','executed','beheaded','massacre','shot dead',
    'arrested','detained','imprisoned','jailed','sentenced',
    'attacked','bombed','burned','demolished','destroyed','raided',
    'persecuted','persecution','martyred','martyr',
    'blasphemy','apostasy','forced conversion',
    'expelled','displaced','fled','refugee',
    'threatened','kidnapped','abducted','tortured',
    'banned','confiscated','closed down',
]

CHRISTIAN_IDENTIFIERS = [
    'christian','church','pastor','priest','bishop','deacon',
    'missionary','convert','evangelical','catholic',
    'protestant','orthodox','pentecostal','baptist','anglican',
    'diocese','parish','chapel','cathedral','bible',
    'cross','gospel','congregation','believer',
]

# Hard exclude - false positives and non-news content
EXCLUDE_TITLE_PATTERNS = [
    'mystery of suffering','book of job','bible study','devotional',
    'sermon','prayer guide','reflection on','theological',
    'policy analysis','policy perspective','op-ed','opinion:',
    'perspective:','analysis:','commentary:','podcast:','column:',
    'review:','what the bible','how to pray','study guide',
    'book review','film review','music review','christmas',
    'easter','advent','lent','devotion','meditation',
    'christian bale','christian mccaffrey','christian dior',
    'christian louboutin','church of england climate',
    'church architecture','church music','christmas shopping',
]

COUNTRY_CENTROIDS = {
    'afghanistan':[65.0,33.9],'albania':[20.2,41.2],'algeria':[2.6,28.0],
    'angola':[17.9,-11.2],'argentina':[-63.6,-38.4],'armenia':[45.0,40.1],
    'australia':[133.8,-25.3],'austria':[14.6,47.5],'azerbaijan':[47.6,40.1],
    'bahrain':[50.6,26.0],'bangladesh':[90.4,23.7],'belarus':[28.0,53.7],
    'belgium':[4.5,50.5],'belize':[-88.5,17.2],'benin':[2.3,9.3],
    'bolivia':[-64.7,-16.3],'botswana':[24.7,-22.3],'brazil':[-51.9,-14.2],
    'bulgaria':[25.5,42.7],'burkina faso':[-1.6,12.4],'burundi':[29.9,-3.4],
    'cambodia':[104.9,12.6],'cameroon':[12.4,3.9],'canada':[-96.8,60.0],
    'central african republic':[20.9,6.6],'chad':[18.7,15.5],
    'chile':[-71.5,-35.7],'china':[104.2,35.9],'colombia':[-74.3,4.1],
    'comoros':[43.9,-11.9],'congo':[15.8,-0.2],'costa rica':[-83.8,9.7],
    'croatia':[15.2,45.1],'cuba':[-79.5,21.5],'cyprus':[33.4,35.1],
    'czech republic':[15.5,49.8],'denmark':[9.5,56.3],'djibouti':[42.6,11.8],
    'dr congo':[24.0,-2.9],'ecuador':[-78.1,-1.8],'egypt':[30.8,26.8],
    'el salvador':[-88.9,13.8],'eritrea':[39.8,15.2],'estonia':[25.0,58.6],
    'ethiopia':[40.5,9.1],'fiji':[178.1,-17.7],'finland':[26.0,64.0],
    'france':[2.2,46.2],'gabon':[11.6,-0.8],'gambia':[-15.3,13.4],
    'georgia':[43.4,42.3],'germany':[10.5,51.2],'ghana':[-1.0,7.9],
    'greece':[21.8,39.1],'guatemala':[-90.2,15.8],'guinea':[-11.3,11.0],
    'guyana':[-59.0,5.0],'haiti':[-72.3,19.0],'honduras':[-86.2,14.8],
    'hungary':[19.5,47.2],'iceland':[-18.7,64.9],'india':[78.7,20.6],
    'indonesia':[113.9,-0.8],'iran':[53.7,32.4],'iraq':[43.7,33.2],
    'ireland':[-8.2,53.4],'israel':[34.9,31.0],'italy':[12.6,42.5],
    'jamaica':[-77.3,18.1],'japan':[138.3,36.2],'jordan':[37.2,30.6],
    'kazakhstan':[66.9,48.0],'kenya':[37.9,0.0],'kuwait':[47.5,29.3],
    'kyrgyzstan':[74.8,41.2],'laos':[103.0,18.2],'latvia':[24.6,56.9],
    'lebanon':[35.9,33.9],'liberia':[-9.4,6.4],'libya':[17.2,26.3],
    'lithuania':[23.9,55.2],'luxembourg':[6.1,49.8],'madagascar':[46.9,-18.8],
    'malawi':[34.3,-13.2],'malaysia':[109.7,4.2],'maldives':[73.2,3.2],
    'mali':[-2.0,17.6],'malta':[14.4,35.9],'mauritania':[-10.9,20.3],
    'mauritius':[57.6,-20.3],'mexico':[-102.6,23.6],'moldova':[28.4,47.4],
    'mongolia':[103.8,46.9],'montenegro':[19.4,42.7],'morocco':[-7.1,31.8],
    'mozambique':[35.5,-18.7],'myanmar':[95.9,17.1],'namibia':[18.5,-22.0],
    'nepal':[84.1,28.4],'netherlands':[5.3,52.1],'new zealand':[172.0,-41.5],
    'nicaragua':[-85.2,12.9],'niger':[8.1,17.6],'nigeria':[8.7,9.1],
    'north korea':[127.5,40.3],'norway':[8.5,60.5],'oman':[57.5,21.5],
    'pakistan':[69.3,30.4],'panama':[-80.8,8.5],'papua new guinea':[143.9,-6.3],
    'paraguay':[-58.4,-23.4],'peru':[-75.0,-9.2],'philippines':[122.9,12.9],
    'poland':[19.1,52.1],'portugal':[-8.2,39.4],'qatar':[51.2,25.4],
    'romania':[24.9,45.9],'russia':[105.3,61.5],'rwanda':[29.9,-2.0],
    'saudi arabia':[45.1,24.0],'senegal':[-14.5,14.5],'serbia':[21.0,44.0],
    'sierra leone':[-11.8,8.5],'singapore':[103.8,1.4],'slovakia':[19.7,48.7],
    'slovenia':[14.8,46.1],'somalia':[46.2,6.1],'south africa':[25.1,-29.0],
    'south korea':[127.8,35.9],'south sudan':[31.3,6.9],'spain':[-3.7,40.5],
    'sri lanka':[80.7,7.9],'sudan':[29.9,12.9],'sweden':[18.6,60.1],
    'switzerland':[8.2,46.8],'syria':[38.3,34.8],'taiwan':[120.9,23.7],
    'tajikistan':[71.3,38.9],'tanzania':[34.9,-6.4],'thailand':[101.0,15.9],
    'togo':[0.8,8.6],'trinidad and tobago':[-61.2,10.7],'tunisia':[9.0,33.9],
    'turkey':[35.2,38.9],'turkmenistan':[59.6,39.0],'uganda':[32.3,1.4],
    'ukraine':[31.2,48.4],'united arab emirates':[53.8,23.4],
    'united kingdom':[-3.4,55.4],'united states':[-95.7,37.1],
    'uruguay':[-55.8,-32.5],'uzbekistan':[63.9,41.4],'venezuela':[-66.6,6.4],
    'vietnam':[108.3,14.1],'yemen':[47.6,15.6],'zambia':[27.8,-13.1],
    'zimbabwe':[30.0,-19.0],
}


# -- CANONICAL COUNTRY REGISTRY (derived from COUNTRY_CENTROIDS) --
_CANONICAL_COUNTRIES = set(COUNTRY_CENTROIDS.keys())

# Common aliases -> canonical name (all lowercase)
_COUNTRY_ALIASES = {
    "usa": "united states",
    "us": "united states",
    "u.s.": "united states",
    "u.s.a.": "united states",
    "america": "united states",
    "uk": "united kingdom",
    "u.k.": "united kingdom",
    "britain": "united kingdom",
    "great britain": "united kingdom",
    "england": "united kingdom",
    "scotland": "united kingdom",
    "wales": "united kingdom",
    "uae": "united arab emirates",
    "drc": "dr congo",
    "democratic republic of congo": "dr congo",
    "democratic republic of the congo": "dr congo",
    "republic of congo": "congo",
    "congo-brazzaville": "congo",
    "congo-kinshasa": "dr congo",
    "burma": "myanmar",
    "czechia": "czech republic",
    "ivory coast": "cote d'ivoire",
    "cote d ivoire": "cote d'ivoire",
    "east timor": "timor-leste",
    "timor leste": "timor-leste",
    "swaziland": "eswatini",
    "cape verde": "cabo verde",
    "vatican": "vatican city",
    "holy see": "vatican city",
    "palestinian territories": "palestine",
    "west bank": "palestine",
    "gaza": "palestine",
    "gaza strip": "palestine",
    "s korea": "south korea",
    "n korea": "north korea",
    "korea republic": "south korea",
    "dprk": "north korea",
    "rok": "south korea",
}

def validate_country(name):
    """Return canonical country name (lowercase) or None."""
    if not name:
        return None
    n = name.strip().lower().strip(".,;:")
    if n in _CANONICAL_COUNTRIES:
        return n
    if n in _COUNTRY_ALIASES:
        aliased = _COUNTRY_ALIASES[n]
        if aliased in _CANONICAL_COUNTRIES:
            return aliased
    return None

def parse_claude_response(text):
    """
    Parse Claude's structured output. Expected format:
        COUNTRY: <canonical | MULTIPLE: c1, c2 | UNKNOWN>
        ---
        <article body>
        HEADLINE: ...

    Returns dict:
        {
          "status": "ok" | "unknown" | "malformed" | "no_valid_country",
          "countries": [canonical_country, ...],
          "body": str,              # body without header
          "raw_country": str,       # original header value for audit
        }
    """
    out = {"status": "malformed", "countries": [], "body": text, "raw_country": ""}
    if not text:
        return out

    lines = text.split("\n", 3)
    if len(lines) < 3:
        return out

    header = lines[0].strip()
    sep = lines[1].strip()

    if not header.upper().startswith("COUNTRY:"):
        return out
    if sep != "---":
        return out

    value = header.split(":", 1)[1].strip()
    out["raw_country"] = value
    body = lines[2] if len(lines) == 3 else (lines[2] + "\n" + lines[3])
    out["body"] = body.strip()

    if not value or value.upper() == "UNKNOWN":
        out["status"] = "unknown"
        return out

    if value.upper().startswith("MULTIPLE:"):
        raw_list = value.split(":", 1)[1]
        candidates = [c.strip() for c in raw_list.split(",") if c.strip()]
    else:
        candidates = [value]

    validated = []
    for c in candidates:
        v = validate_country(c)
        if v and v not in validated:
            validated.append(v)

    if not validated:
        out["status"] = "no_valid_country"
        return out

    out["countries"] = validated
    out["status"] = "ok"
    return out

def load_seen():
    try:
        with open(SEEN_FILE, "r") as f:
            return set(json.load(f))
    except:
        return set()

def save_seen(seen):
    with open(SEEN_FILE, "w") as f:
        json.dump(list(seen), f)

def article_hash(title):
    return hashlib.md5(title.lower().strip()[:100].encode()).hexdigest()

def is_mainstream(feed_url, feed_title):
    combined = (feed_url + " " + feed_title).lower()
    return any(s in combined for s in MAINSTREAM_SOURCES)

def is_news_incident(title, content):
    """Require article to describe a specific real-world incident, not opinion/devotional."""
    title_lower = title.lower()
    content_lower = content.lower()

    # Hard exclude non-news content types
    for pattern in EXCLUDE_TITLE_PATTERNS:
        if pattern in title_lower:
            return False

    # Require at least one concrete incident word in title or first 500 chars
    incident_words = [
        "killed","kills","kill","murdered","murder","executed","execution",
        "arrested","arrested","detained","detention","imprisoned","sentenced",
        "attacked","attack","bombed","burned","demolished","destroyed","raided",
        "kidnapped","abducted","tortured","expelled","displaced","fled",
        "closed","banned","confiscated","threatened",
    ]
    text_check = title_lower + " " + content_lower[:500]
    has_incident = any(w in text_check for w in incident_words)

    # Require a country or place name in the content
    has_location = any(c in content_lower for c in COUNTRY_CENTROIDS.keys())

    return has_incident and has_location

def is_relevant(title, content, feed_url, feed_title):
    title_lower = title.lower()

    # For mainstream sources title must have Christian + persecution signal
    if is_mainstream(feed_url, feed_title):
        has_ci = any(ci in title_lower for ci in CHRISTIAN_IDENTIFIERS)
        has_ps = any(ps in title_lower for ps in PERSECUTION_SIGNALS)
        if not (has_ci and has_ps):
            return False

    # Must be a specific news incident not opinion/devotional
    if not is_news_incident(title, content):
        return False

    # Proximity check - Christian identifier and persecution signal in same sentence
    sentences = re.split(r"[.!?]", (title + " " + content).lower())
    for sentence in sentences:
        has_ci = any(ci in sentence for ci in CHRISTIAN_IDENTIFIERS)
        has_ps = any(ps in sentence for ps in PERSECUTION_SIGNALS)
        if has_ci and has_ps:
            return True

    return False

def fetch_full_content(url):
    try:
        r = requests.get(url, timeout=8,
            headers={"User-Agent": "Mozilla/5.0 (compatible; GlobalWitnessMonitor/1.0)"})
        if r.status_code == 200:
            text = re.sub(r"<script[^>]*>.*?</script>", "", r.text, flags=re.DOTALL)
            text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL)
            text = re.sub(r"<[^>]+>", " ", text)
            text = re.sub(r"\s+", " ", text).strip()
            return text[:3000]
    except:
        pass
    return None

def detect_country(title, content):
    title_lower = title.lower()
    for country in sorted(COUNTRY_CENTROIDS.keys(), key=len, reverse=True):
        if country in title_lower:
            return country
    dateline = re.match(r"^([A-Z][A-Za-z\s,]+?)\s*[\(\-]", content or "")
    if dateline:
        dl = dateline.group(1).strip().lower()
        for country in COUNTRY_CENTROIDS.keys():
            if country in dl:
                return country
    content_lower = (content or "").lower()
    best = None
    best_pos = len(content_lower)
    for country in COUNTRY_CENTROIDS.keys():
        pos = content_lower.find(country)
        if pos != -1 and pos < best_pos:
            best_pos = pos
            best = country
    return best

def detect_type(title, content):
    text = (title + " " + content).lower()
    if any(k in text for k in ["kill","murder","execut","behead","massacre","shot dead","lynch"]):
        return "killing"
    if any(k in text for k in ["church burn","church attack","church demolish","church destroy","church raid","chapel burn"]):
        return "church"
    if any(k in text for k in ["displace","flee","fled","refugee","expel","evict","forced from home"]):
        return "displacement"
    return "arrest"

def fetch_articles(seen):
    articles = []
    seen_titles = set()
    for feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            feed_title = feed.feed.get("title", feed_url)
            for entry in feed.entries[:20]:
                title = entry.get("title", "").strip()
                summary = entry.get("summary", "")
                link = entry.get("link", "")
                content = entry.get("content", [{}])[0].get("value", summary)
                if not title:
                    continue
                published = entry.get("published_parsed") or entry.get("updated_parsed")
                if published:
                    pub_dt = datetime(*published[:6], tzinfo=timezone.utc)
                    if datetime.now(timezone.utc) - pub_dt > timedelta(hours=48):
                        continue
                h = article_hash(title)
                if h in seen or title.lower() in seen_titles:
                    continue
                clean = re.sub(r"<[^>]+>", " ", content).strip()
                if len(clean) < 200:
                    fetched = fetch_full_content(link)
                    if fetched and len(fetched) > 200:
                        clean = fetched
                    else:
                        print("Skipping thin: " + title[:60])
                        continue
                if not is_relevant(title, clean, feed_url, feed_title):
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
                    "title": title,
                    "content": clean[:3000],
                    "link": link,
                    "source": feed_title,
                    "hash": h,
                    "country": country,
                    "incident_type": inc_type,
                    "lat": lat,
                    "lng": lng,
                })
            print("Fetched: " + feed_url)
        except Exception as e:
            print("Error: " + feed_url + " - " + str(e))
    print("Found " + str(len(articles)) + " relevant articles")
    return articles

def generate_article(article):
    prompt = (
        "You are a journalist for Global Witness Monitor, a Christian persecution intelligence platform.\n\n"
        "STRUCTURED OUTPUT REQUIRED. Your response must begin with exactly these two header lines:\n"
        "COUNTRY: <country_name | MULTIPLE: country1, country2 | UNKNOWN>\n"
        "---\n"
        "Then the article body.\n\n"
        "COUNTRY rules:\n"
        "- Use the country where the persecution event occurred, not the country of the outlet.\n"
        "- If multiple countries are substantively involved (e.g. cross-border refugees, diaspora incident with country of origin), use MULTIPLE: c1, c2.\n"
        "- Use UNKNOWN only if no country can be reasonably determined.\n"
        "- Use common country names: united states, united kingdom, dr congo, north korea, south korea, etc.\n\n"
        "Write a factual 100-250 word news report based ONLY on the source material below.\n\n"
        "STRICT RULES:\n"
        "- Only include facts present in the source material\n"
        "- Never invent names, statistics, dates, or locations\n"
        "- Never fabricate quotes\n"
        "- Redact identifying details to protect local communities:\n"
        "  - No personal names (replace with: man, woman, pastor, bishop, girl, boy, family, group, convert, believer)\n"
        "  - No specific church names (e.g. 'Linfen Covenant Home Church' -> 'a house church')\n"
        "  - No specific local ministry or denomination names within the country (e.g. 'Three-Self Patriotic Movement' -> 'a state-sanctioned church body')\n"
        "  - No towns, villages, counties, districts, or provinces (use the country only, or generic phrasing like 'a rural area' or 'a northern province')\n"
        "  - You MAY name the external reporting watchdog (e.g. 'according to ChinaAid', 'according to Open Doors') since those are not local community identifiers\n"
        "- These redaction rules apply EVEN IF the source material includes the specific names. Redaction is required, not optional.\n"
        "- Mention the source naturally in the text\n"
        "- No source list at the end\n"
        "- No headers or sections\n"
        "- Never repeat the same point twice\n"
        "- End with one short prayer prompt sentence\n"
        "- 100-250 words maximum\n\n"
        "After the article write on a new line: HEADLINE: [short descriptive headline, no personal names]\n\n"
        "SOURCE: " + article["source"] + "\n"
        "TITLE: " + article["title"] + "\n"
        "CONTENT: " + article["content"] + "\n\nWrite now:"
    )
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=900,
        messages=[{"role": "user", "content": prompt}]
    )
    raw = response.content[0].text
    parsed = parse_claude_response(raw)
    return raw, parsed

def is_refusal(text):
    signals = [
        "report unavailable","cannot write","i cannot","i am unable",
        "source material provided","only a headline","no article content",
        "insufficient information","unable to write"
    ]
    return any(s in text.lower() for s in signals)

def parse_generated(text):
    if "HEADLINE:" in text:
        parts = text.split("HEADLINE:")
        body = parts[0].strip()
        headline = parts[1].strip().split("\n")[0].strip()
    else:
        body = text.strip()
        headline = None
    return headline, body

def get_or_create_category(name, slug):
    auth = (WP_USER, WP_APP_PASSWORD)
    r = requests.get(WP_URL + "/wp-json/wp/v2/categories?slug=" + slug, auth=auth)
    cats = r.json()
    if cats:
        return cats[0]["id"]
    r = requests.post(WP_URL + "/wp-json/wp/v2/categories",
                      auth=auth, json={"name": name, "slug": slug})
    return r.json().get("id")

def publish_to_wordpress(article, headline, body):
    auth = (WP_USER, WP_APP_PASSWORD)
    cat_id = get_or_create_category("Persecution Reports", "persecution-reports")
    meta_html = (
        "<div class=\"gwm-meta\" style=\"display:none;\"" +
        " data-country=\"" + (article["country"] or "") + "\"" +
        " data-type=\"" + article["incident_type"] + "\"" +
        " data-lat=\"" + str(article["lat"] or "") + "\"" +
        " data-lng=\"" + str(article["lng"] or "") + "\"></div>"
    )
    title = headline or article["title"]
    post_data = {
        "title": title,
        "content": body + meta_html,
        "status": "publish",
        "categories": [cat_id],
        "excerpt": article["content"][:200],
    }
    r = requests.post(WP_URL + "/wp-json/wp/v2/posts", auth=auth, json=post_data)
    if r.status_code == 201:
        print("Published: " + title[:60])
        return r.json()
    else:
        print("Failed: " + str(r.status_code))
        return None

def run():
    print("=== Global Witness Monitor - Persecution Pipeline ===")
    seen = load_seen()
    print("Previously seen: " + str(len(seen)) + " articles")
    articles = fetch_articles(seen)
    if not articles:
        print("No new articles found.")
        return
    published = 0
    skipped = 0
    for article in articles:
        try:
            print("Processing: " + article["title"][:60])
            raw, parsed = generate_article(article)

            # Audit line: Claude's country vs pre-detected country
            claude_country = ",".join(parsed["countries"]) if parsed["countries"] else "-"
            detected_country = article.get("country") or "-"
            print(
                "CLAUDE_VS_DETECTED: claude_country=" + claude_country +
                " detected_country=" + detected_country +
                " status=" + parsed["status"] +
                " raw='" + parsed["raw_country"] + "'"
            )

            if parsed["status"] != "ok":
                print("Skipping (" + parsed["status"] + "): " + article["title"][:60])
                skipped += 1
                seen.add(article["hash"])
                continue

            # Override: Claude is source of truth
            primary = parsed["countries"][0]
            article["country"] = primary
            coords = COUNTRY_CENTROIDS.get(primary)
            if coords:
                article["lat"] = coords[1]
                article["lng"] = coords[0]
            else:
                article["lat"] = None
                article["lng"] = None

            # Use parsed body (header stripped) for downstream processing
            generated = parsed["body"] if parsed["body"] else raw
            if is_refusal(generated):
                print("Skipping - refused")
                skipped += 1
                seen.add(article["hash"])
                continue
            headline, body = parse_generated(generated)
            if not body or len(body) < 50:
                print("Skipping - too short")
                skipped += 1
                continue
            result = publish_to_wordpress(article, headline, body)
            if result:
                published += 1
                seen.add(article["hash"])
            time.sleep(2)
        except Exception as e:
            print("Error: " + str(e))
    save_seen(seen)
    print("=== Done. Published: " + str(published) + " Skipped: " + str(skipped) + " ===")

if __name__ == "__main__":
    run()
