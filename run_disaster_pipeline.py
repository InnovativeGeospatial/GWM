#!/usr/bin/env python3
"""
Global Witness Monitor - Natural Disaster Intelligence Pipeline
Fetches RSS feeds, filters for actual disaster events, generates articles via Claude,
publishes to WordPress under the Disaster Reports category.
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
from datetime import datetime, timezone
from dotenv import load_dotenv
import anthropic

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------
load_dotenv()
WP_URL = os.environ['WP_URL'].rstrip('/')
WP_USER = os.environ['WP_USER']
WP_APP_PASSWORD = os.environ['WP_APP_PASSWORD']
ANTHROPIC_KEY = os.environ['ANTHROPIC_API_KEY']
WP_CATEGORY_ID = int(os.environ.get('WP_CATEGORY_ID', 9))

PIPELINE_DIR = '/opt/disaster-pipeline'
DATA_DIR = os.path.join(PIPELINE_DIR, 'data')
SEEN_FILE = os.path.join(DATA_DIR, 'seen_articles.json')
ARTICLES_PER_RUN = int(os.environ.get('ARTICLES_PER_RUN', 5))

os.makedirs(DATA_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# RSS feeds
# ---------------------------------------------------------------------------
RSS_FEEDS = [
    ('GDACS',         'https://www.gdacs.org/xml/rss.xml'),
    ('ReliefWeb',     'https://reliefweb.int/updates/rss.xml'),
    ('USGS',          'https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/significant_week.atom'),
    ('NOAA',          'https://www.weather.gov/rss_page.php'),
    ('UN News',       'https://news.un.org/feed/subscribe/en/news/all/rss.xml'),
]

# ---------------------------------------------------------------------------
# Filtering vocabulary
# ---------------------------------------------------------------------------
DISASTER_TERMS = [
    'earthquake', 'quake', 'seismic', 'tremor', 'aftershock', 'magnitude',
    'flood', 'flooding', 'flash flood', 'inundation', 'deluge',
    'hurricane', 'typhoon', 'cyclone', 'tropical storm',
    'wildfire', 'bushfire', 'forest fire', 'blaze',
    'volcano', 'eruption', 'volcanic', 'lava', 'ash',
    'tsunami', 'tidal wave',
    'landslide', 'mudslide', 'avalanche',
    'drought', 'famine', 'water shortage',
    'tornado', 'twister',
    'storm surge', 'extreme weather',
]

EVENT_SIGNALS = [
    'hit', 'hits', 'struck', 'strikes',
    'killed', 'deaths', 'dead', 'casualties', 'victims',
    'destroyed', 'damaged', 'devastated',
    'evacuated', 'evacuation', 'displaced', 'fled',
    'collapsed', 'swept away', 'buried',
    'triggered', 'caused', 'unleashed',
    'ravaged', 'ravages', 'engulfed',
    'magnitude',
]

EXCLUDE_PATTERNS = [
    'what is a', 'how to prepare', 'explained', 'explainer',
    'could hit', 'may strike', 'threatens',
    'anniversary', 'remembering', 'years ago',
    'preparedness guide', 'climate explained',
]

# ---------------------------------------------------------------------------
# Region definitions for --region filtering
# ---------------------------------------------------------------------------
REGIONS = {
    'middle-east': [
        'Iran', 'Iraq', 'Syria', 'Lebanon', 'Israel', 'Palestine', 'Gaza',
        'Jordan', 'Saudi Arabia', 'Yemen', 'Oman', 'Kuwait', 'Qatar',
        'Bahrain', 'UAE', 'United Arab Emirates', 'Turkey', 'Egypt'
    ],
    'africa': [
        'Nigeria', 'Kenya', 'Ethiopia', 'Somalia', 'Sudan', 'South Sudan',
        'DRC', 'Congo', 'Uganda', 'Tanzania', 'Rwanda', 'Burundi',
        'Mali', 'Burkina Faso', 'Niger', 'Chad', 'Cameroon',
        'Mozambique', 'Madagascar', 'Malawi', 'Zambia', 'Zimbabwe',
        'South Africa', 'Angola', 'Namibia', 'Botswana', 'Lesotho',
        'Ghana', 'Ivory Coast', 'Senegal', 'Liberia', 'Sierra Leone',
        'Morocco', 'Algeria', 'Tunisia', 'Libya', 'Eritrea', 'Djibouti',
        'Central African Republic', 'Gabon', 'Equatorial Guinea',
    ],
    'asia': [
        'China', 'India', 'Pakistan', 'Bangladesh', 'Nepal', 'Bhutan',
        'Sri Lanka', 'Myanmar', 'Thailand', 'Vietnam', 'Cambodia', 'Laos',
        'Malaysia', 'Indonesia', 'Philippines', 'Singapore', 'Brunei',
        'Japan', 'South Korea', 'North Korea', 'Mongolia', 'Taiwan',
        'Afghanistan', 'Kazakhstan', 'Uzbekistan', 'Turkmenistan',
        'Kyrgyzstan', 'Tajikistan', 'Maldives', 'Timor-Leste',
    ],
    'europe': [
        'United Kingdom', 'UK', 'Britain', 'England', 'Scotland', 'Wales',
        'Ireland', 'France', 'Germany', 'Spain', 'Portugal', 'Italy',
        'Greece', 'Netherlands', 'Belgium', 'Luxembourg', 'Switzerland',
        'Austria', 'Poland', 'Czech Republic', 'Slovakia', 'Hungary',
        'Romania', 'Bulgaria', 'Serbia', 'Croatia', 'Slovenia', 'Bosnia',
        'Albania', 'Kosovo', 'Macedonia', 'Montenegro', 'Moldova',
        'Ukraine', 'Belarus', 'Russia', 'Norway', 'Sweden', 'Finland',
        'Denmark', 'Iceland', 'Estonia', 'Latvia', 'Lithuania',
    ],
    'americas': [
        'United States', 'USA', 'US', 'America', 'Canada', 'Mexico',
        'Guatemala', 'Honduras', 'El Salvador', 'Nicaragua', 'Costa Rica',
        'Panama', 'Belize', 'Cuba', 'Haiti', 'Dominican Republic',
        'Jamaica', 'Bahamas', 'Puerto Rico', 'Trinidad',
        'Colombia', 'Venezuela', 'Ecuador', 'Peru', 'Bolivia', 'Brazil',
        'Argentina', 'Chile', 'Paraguay', 'Uruguay', 'Guyana', 'Suriname',
    ],
    'pacific': [
        'Australia', 'New Zealand', 'Papua New Guinea', 'Fiji', 'Samoa',
        'Tonga', 'Vanuatu', 'Solomon Islands', 'Kiribati', 'Tuvalu',
        'Micronesia', 'Marshall Islands', 'Palau', 'Nauru',
    ],
}

# ---------------------------------------------------------------------------
# Country detection (names, demonyms, major cities)
# ---------------------------------------------------------------------------
COUNTRY_LOOKUP = {
    # Africa
    'nigeria': 'Nigeria', 'nigerian': 'Nigeria', 'lagos': 'Nigeria', 'abuja': 'Nigeria',
    'kenya': 'Kenya', 'kenyan': 'Kenya', 'nairobi': 'Kenya', 'mombasa': 'Kenya',
    'ethiopia': 'Ethiopia', 'ethiopian': 'Ethiopia', 'addis ababa': 'Ethiopia',
    'somalia': 'Somalia', 'somali': 'Somalia', 'mogadishu': 'Somalia',
    'sudan': 'Sudan', 'sudanese': 'Sudan', 'khartoum': 'Sudan',
    'south sudan': 'South Sudan', 'juba': 'South Sudan',
    'drc': 'DRC', 'congo': 'DRC', 'kinshasa': 'DRC', 'goma': 'DRC',
    'uganda': 'Uganda', 'ugandan': 'Uganda', 'kampala': 'Uganda',
    'tanzania': 'Tanzania', 'tanzanian': 'Tanzania', 'dar es salaam': 'Tanzania', 'dodoma': 'Tanzania',
    'rwanda': 'Rwanda', 'rwandan': 'Rwanda', 'kigali': 'Rwanda',
    'burundi': 'Burundi', 'bujumbura': 'Burundi',
    'mali': 'Mali', 'malian': 'Mali', 'bamako': 'Mali',
    'burkina faso': 'Burkina Faso', 'ouagadougou': 'Burkina Faso',
    'niger': 'Niger', 'niamey': 'Niger',
    'chad': 'Chad', 'chadian': 'Chad', "n'djamena": 'Chad',
    'cameroon': 'Cameroon', 'cameroonian': 'Cameroon', 'yaounde': 'Cameroon',
    'mozambique': 'Mozambique', 'mozambican': 'Mozambique', 'maputo': 'Mozambique',
    'madagascar': 'Madagascar', 'malagasy': 'Madagascar', 'antananarivo': 'Madagascar',
    'malawi': 'Malawi', 'malawian': 'Malawi', 'lilongwe': 'Malawi',
    'zambia': 'Zambia', 'zambian': 'Zambia', 'lusaka': 'Zambia',
    'zimbabwe': 'Zimbabwe', 'zimbabwean': 'Zimbabwe', 'harare': 'Zimbabwe',
    'south africa': 'South Africa', 'south african': 'South Africa', 'johannesburg': 'South Africa', 'cape town': 'South Africa', 'pretoria': 'South Africa',
    'angola': 'Angola', 'angolan': 'Angola', 'luanda': 'Angola',
    'namibia': 'Namibia', 'namibian': 'Namibia', 'windhoek': 'Namibia',
    'botswana': 'Botswana', 'gaborone': 'Botswana',
    'lesotho': 'Lesotho', 'maseru': 'Lesotho',
    'ghana': 'Ghana', 'ghanaian': 'Ghana', 'accra': 'Ghana',
    'ivory coast': 'Ivory Coast', 'cote divoire': 'Ivory Coast', 'abidjan': 'Ivory Coast',
    'senegal': 'Senegal', 'senegalese': 'Senegal', 'dakar': 'Senegal',
    'liberia': 'Liberia', 'liberian': 'Liberia', 'monrovia': 'Liberia',
    'sierra leone': 'Sierra Leone', 'freetown': 'Sierra Leone',
    'morocco': 'Morocco', 'moroccan': 'Morocco', 'rabat': 'Morocco', 'casablanca': 'Morocco', 'marrakech': 'Morocco',
    'algeria': 'Algeria', 'algerian': 'Algeria', 'algiers': 'Algeria',
    'tunisia': 'Tunisia', 'tunisian': 'Tunisia', 'tunis': 'Tunisia',
    'libya': 'Libya', 'libyan': 'Libya', 'tripoli': 'Libya', 'benghazi': 'Libya', 'derna': 'Libya',
    'eritrea': 'Eritrea', 'eritrean': 'Eritrea', 'asmara': 'Eritrea',
    'djibouti': 'Djibouti',
    'central african republic': 'Central African Republic', 'car': 'Central African Republic', 'bangui': 'Central African Republic',
    'gabon': 'Gabon', 'libreville': 'Gabon',
    'equatorial guinea': 'Equatorial Guinea', 'malabo': 'Equatorial Guinea',
    'guinea': 'Guinea', 'conakry': 'Guinea',
    'guinea-bissau': 'Guinea-Bissau', 'bissau': 'Guinea-Bissau',
    'gambia': 'Gambia', 'banjul': 'Gambia',
    'togo': 'Togo', 'lome': 'Togo',
    'benin': 'Benin', 'porto-novo': 'Benin', 'cotonou': 'Benin',
    'mauritania': 'Mauritania', 'nouakchott': 'Mauritania',
    'comoros': 'Comoros', 'moroni': 'Comoros',
    'seychelles': 'Seychelles', 'victoria': 'Seychelles',
    'mauritius': 'Mauritius', 'port louis': 'Mauritius',
    'cape verde': 'Cape Verde', 'praia': 'Cape Verde',
    'sao tome': 'Sao Tome and Principe',
    'swaziland': 'Eswatini', 'eswatini': 'Eswatini', 'mbabane': 'Eswatini',

    # Middle East
    'iran': 'Iran', 'iranian': 'Iran', 'tehran': 'Iran',
    'iraq': 'Iraq', 'iraqi': 'Iraq', 'baghdad': 'Iraq', 'mosul': 'Iraq',
    'syria': 'Syria', 'syrian': 'Syria', 'damascus': 'Syria', 'aleppo': 'Syria',
    'lebanon': 'Lebanon', 'lebanese': 'Lebanon', 'beirut': 'Lebanon',
    'israel': 'Israel', 'israeli': 'Israel', 'jerusalem': 'Israel', 'tel aviv': 'Israel',
    'palestine': 'Palestine', 'palestinian': 'Palestine', 'gaza': 'Palestine', 'west bank': 'Palestine', 'ramallah': 'Palestine',
    'jordan': 'Jordan', 'jordanian': 'Jordan', 'amman': 'Jordan',
    'saudi arabia': 'Saudi Arabia', 'saudi': 'Saudi Arabia', 'riyadh': 'Saudi Arabia', 'jeddah': 'Saudi Arabia', 'mecca': 'Saudi Arabia',
    'yemen': 'Yemen', 'yemeni': 'Yemen', 'sanaa': 'Yemen', 'aden': 'Yemen',
    'oman': 'Oman', 'omani': 'Oman', 'muscat': 'Oman',
    'kuwait': 'Kuwait', 'kuwaiti': 'Kuwait',
    'qatar': 'Qatar', 'qatari': 'Qatar', 'doha': 'Qatar',
    'bahrain': 'Bahrain', 'bahraini': 'Bahrain', 'manama': 'Bahrain',
    'uae': 'UAE', 'united arab emirates': 'UAE', 'dubai': 'UAE', 'abu dhabi': 'UAE',
    'turkey': 'Turkey', 'turkish': 'Turkey', 'ankara': 'Turkey', 'istanbul': 'Turkey', 'gaziantep': 'Turkey', 'antakya': 'Turkey',
    'egypt': 'Egypt', 'egyptian': 'Egypt', 'cairo': 'Egypt', 'alexandria': 'Egypt',

    # Asia
    'china': 'China', 'chinese': 'China', 'beijing': 'China', 'shanghai': 'China', 'wuhan': 'China', 'sichuan': 'China',
    'india': 'India', 'indian': 'India', 'new delhi': 'India', 'mumbai': 'India', 'kolkata': 'India', 'chennai': 'India', 'kerala': 'India',
    'pakistan': 'Pakistan', 'pakistani': 'Pakistan', 'islamabad': 'Pakistan', 'karachi': 'Pakistan', 'lahore': 'Pakistan',
    'bangladesh': 'Bangladesh', 'bangladeshi': 'Bangladesh', 'dhaka': 'Bangladesh',
    'nepal': 'Nepal', 'nepali': 'Nepal', 'nepalese': 'Nepal', 'kathmandu': 'Nepal',
    'bhutan': 'Bhutan', 'bhutanese': 'Bhutan', 'thimphu': 'Bhutan',
    'sri lanka': 'Sri Lanka', 'sri lankan': 'Sri Lanka', 'colombo': 'Sri Lanka',
    'myanmar': 'Myanmar', 'burma': 'Myanmar', 'burmese': 'Myanmar', 'naypyidaw': 'Myanmar', 'yangon': 'Myanmar', 'mandalay': 'Myanmar',
    'thailand': 'Thailand', 'thai': 'Thailand', 'bangkok': 'Thailand', 'chiang mai': 'Thailand',
    'vietnam': 'Vietnam', 'vietnamese': 'Vietnam', 'hanoi': 'Vietnam', 'ho chi minh': 'Vietnam',
    'cambodia': 'Cambodia', 'cambodian': 'Cambodia', 'phnom penh': 'Cambodia',
    'laos': 'Laos', 'laotian': 'Laos', 'vientiane': 'Laos',
    'malaysia': 'Malaysia', 'malaysian': 'Malaysia', 'kuala lumpur': 'Malaysia',
    'indonesia': 'Indonesia', 'indonesian': 'Indonesia', 'jakarta': 'Indonesia', 'sumatra': 'Indonesia', 'java': 'Indonesia', 'bali': 'Indonesia', 'sulawesi': 'Indonesia',
    'philippines': 'Philippines', 'filipino': 'Philippines', 'philippine': 'Philippines', 'manila': 'Philippines', 'cebu': 'Philippines', 'mindanao': 'Philippines',
    'singapore': 'Singapore', 'singaporean': 'Singapore',
    'brunei': 'Brunei', 'bruneian': 'Brunei',
    'japan': 'Japan', 'japanese': 'Japan', 'tokyo': 'Japan', 'osaka': 'Japan', 'kyoto': 'Japan', 'fukushima': 'Japan',
    'south korea': 'South Korea', 'korea': 'South Korea', 'korean': 'South Korea', 'seoul': 'South Korea',
    'north korea': 'North Korea', 'pyongyang': 'North Korea',
    'mongolia': 'Mongolia', 'mongolian': 'Mongolia', 'ulaanbaatar': 'Mongolia',
    'taiwan': 'Taiwan', 'taiwanese': 'Taiwan', 'taipei': 'Taiwan',
    'afghanistan': 'Afghanistan', 'afghan': 'Afghanistan', 'kabul': 'Afghanistan', 'herat': 'Afghanistan',
    'kazakhstan': 'Kazakhstan', 'kazakh': 'Kazakhstan', 'astana': 'Kazakhstan', 'almaty': 'Kazakhstan',
    'uzbekistan': 'Uzbekistan', 'uzbek': 'Uzbekistan', 'tashkent': 'Uzbekistan',
    'turkmenistan': 'Turkmenistan', 'ashgabat': 'Turkmenistan',
    'kyrgyzstan': 'Kyrgyzstan', 'kyrgyz': 'Kyrgyzstan', 'bishkek': 'Kyrgyzstan',
    'tajikistan': 'Tajikistan', 'tajik': 'Tajikistan', 'dushanbe': 'Tajikistan',
    'maldives': 'Maldives', 'male': 'Maldives',
    'timor-leste': 'Timor-Leste', 'east timor': 'Timor-Leste', 'dili': 'Timor-Leste',

    # Europe
    'united kingdom': 'United Kingdom', 'uk': 'United Kingdom', 'britain': 'United Kingdom', 'british': 'United Kingdom', 'england': 'United Kingdom', 'london': 'United Kingdom', 'scotland': 'United Kingdom', 'wales': 'United Kingdom',
    'ireland': 'Ireland', 'irish': 'Ireland', 'dublin': 'Ireland',
    'france': 'France', 'french': 'France', 'paris': 'France', 'marseille': 'France', 'lyon': 'France',
    'germany': 'Germany', 'german': 'Germany', 'berlin': 'Germany', 'munich': 'Germany', 'hamburg': 'Germany',
    'spain': 'Spain', 'spanish': 'Spain', 'madrid': 'Spain', 'barcelona': 'Spain', 'valencia': 'Spain',
    'portugal': 'Portugal', 'portuguese': 'Portugal', 'lisbon': 'Portugal',
    'italy': 'Italy', 'italian': 'Italy', 'rome': 'Italy', 'milan': 'Italy', 'naples': 'Italy', 'sicily': 'Italy',
    'greece': 'Greece', 'greek': 'Greece', 'athens': 'Greece', 'thessaloniki': 'Greece',
    'netherlands': 'Netherlands', 'dutch': 'Netherlands', 'amsterdam': 'Netherlands', 'rotterdam': 'Netherlands',
    'belgium': 'Belgium', 'belgian': 'Belgium', 'brussels': 'Belgium',
    'luxembourg': 'Luxembourg',
    'switzerland': 'Switzerland', 'swiss': 'Switzerland', 'bern': 'Switzerland', 'zurich': 'Switzerland', 'geneva': 'Switzerland',
    'austria': 'Austria', 'austrian': 'Austria', 'vienna': 'Austria',
    'poland': 'Poland', 'polish': 'Poland', 'warsaw': 'Poland', 'krakow': 'Poland',
    'czech republic': 'Czech Republic', 'czechia': 'Czech Republic', 'prague': 'Czech Republic',
    'slovakia': 'Slovakia', 'slovak': 'Slovakia', 'bratislava': 'Slovakia',
    'hungary': 'Hungary', 'hungarian': 'Hungary', 'budapest': 'Hungary',
    'romania': 'Romania', 'romanian': 'Romania', 'bucharest': 'Romania',
    'bulgaria': 'Bulgaria', 'bulgarian': 'Bulgaria', 'sofia': 'Bulgaria',
    'serbia': 'Serbia', 'serbian': 'Serbia', 'belgrade': 'Serbia',
    'croatia': 'Croatia', 'croatian': 'Croatia', 'zagreb': 'Croatia',
    'slovenia': 'Slovenia', 'slovenian': 'Slovenia', 'ljubljana': 'Slovenia',
    'bosnia': 'Bosnia', 'sarajevo': 'Bosnia',
    'albania': 'Albania', 'albanian': 'Albania', 'tirana': 'Albania',
    'kosovo': 'Kosovo', 'pristina': 'Kosovo',
    'macedonia': 'North Macedonia', 'north macedonia': 'North Macedonia', 'skopje': 'North Macedonia',
    'montenegro': 'Montenegro', 'podgorica': 'Montenegro',
    'moldova': 'Moldova', 'chisinau': 'Moldova',
    'ukraine': 'Ukraine', 'ukrainian': 'Ukraine', 'kyiv': 'Ukraine', 'kiev': 'Ukraine', 'kharkiv': 'Ukraine', 'odesa': 'Ukraine',
    'belarus': 'Belarus', 'belarusian': 'Belarus', 'minsk': 'Belarus',
    'russia': 'Russia', 'russian': 'Russia', 'moscow': 'Russia', 'st petersburg': 'Russia', 'siberia': 'Russia', 'kamchatka': 'Russia',
    'norway': 'Norway', 'norwegian': 'Norway', 'oslo': 'Norway',
    'sweden': 'Sweden', 'swedish': 'Sweden', 'stockholm': 'Sweden',
    'finland': 'Finland', 'finnish': 'Finland', 'helsinki': 'Finland',
    'denmark': 'Denmark', 'danish': 'Denmark', 'copenhagen': 'Denmark',
    'iceland': 'Iceland', 'icelandic': 'Iceland', 'reykjavik': 'Iceland',
    'estonia': 'Estonia', 'estonian': 'Estonia', 'tallinn': 'Estonia',
    'latvia': 'Latvia', 'latvian': 'Latvia', 'riga': 'Latvia',
    'lithuania': 'Lithuania', 'lithuanian': 'Lithuania', 'vilnius': 'Lithuania',
    'cyprus': 'Cyprus', 'cypriot': 'Cyprus', 'nicosia': 'Cyprus',
    'malta': 'Malta', 'maltese': 'Malta', 'valletta': 'Malta',

    # Americas
    'united states': 'United States', 'usa': 'United States', 'us': 'United States', 'america': 'United States', 'american': 'United States',
    'washington': 'United States', 'new york': 'United States', 'los angeles': 'United States', 'california': 'United States',
    'florida': 'United States', 'texas': 'United States', 'louisiana': 'United States', 'new orleans': 'United States',
    'puerto rico': 'United States', 'hawaii': 'United States', 'alaska': 'United States',
    'canada': 'Canada', 'canadian': 'Canada', 'ottawa': 'Canada', 'toronto': 'Canada', 'vancouver': 'Canada', 'montreal': 'Canada', 'alberta': 'Canada', 'british columbia': 'Canada',
    'mexico': 'Mexico', 'mexican': 'Mexico', 'mexico city': 'Mexico', 'guadalajara': 'Mexico', 'acapulco': 'Mexico',
    'guatemala': 'Guatemala', 'guatemalan': 'Guatemala',
    'honduras': 'Honduras', 'honduran': 'Honduras', 'tegucigalpa': 'Honduras',
    'el salvador': 'El Salvador', 'salvadoran': 'El Salvador',
    'nicaragua': 'Nicaragua', 'nicaraguan': 'Nicaragua', 'managua': 'Nicaragua',
    'costa rica': 'Costa Rica', 'san jose': 'Costa Rica',
    'panama': 'Panama', 'panamanian': 'Panama',
    'belize': 'Belize',
    'cuba': 'Cuba', 'cuban': 'Cuba', 'havana': 'Cuba',
    'haiti': 'Haiti', 'haitian': 'Haiti', 'port-au-prince': 'Haiti',
    'dominican republic': 'Dominican Republic', 'santo domingo': 'Dominican Republic',
    'jamaica': 'Jamaica', 'jamaican': 'Jamaica', 'kingston': 'Jamaica',
    'bahamas': 'Bahamas', 'nassau': 'Bahamas',
    'trinidad': 'Trinidad and Tobago', 'tobago': 'Trinidad and Tobago',
    'colombia': 'Colombia', 'colombian': 'Colombia', 'bogota': 'Colombia', 'medellin': 'Colombia',
    'venezuela': 'Venezuela', 'venezuelan': 'Venezuela', 'caracas': 'Venezuela',
    'ecuador': 'Ecuador', 'ecuadorian': 'Ecuador', 'quito': 'Ecuador',
    'peru': 'Peru', 'peruvian': 'Peru', 'lima': 'Peru',
    'bolivia': 'Bolivia', 'bolivian': 'Bolivia', 'la paz': 'Bolivia',
    'brazil': 'Brazil', 'brazilian': 'Brazil', 'brasilia': 'Brazil', 'rio de janeiro': 'Brazil', 'sao paulo': 'Brazil', 'amazon': 'Brazil',
    'argentina': 'Argentina', 'argentine': 'Argentina', 'buenos aires': 'Argentina',
    'chile': 'Chile', 'chilean': 'Chile', 'santiago': 'Chile',
    'paraguay': 'Paraguay', 'asuncion': 'Paraguay',
    'uruguay': 'Uruguay', 'montevideo': 'Uruguay',
    'guyana': 'Guyana', 'georgetown': 'Guyana',
    'suriname': 'Suriname', 'paramaribo': 'Suriname',

    # Pacific
    'australia': 'Australia', 'australian': 'Australia', 'sydney': 'Australia', 'melbourne': 'Australia', 'brisbane': 'Australia', 'queensland': 'Australia',
    'new zealand': 'New Zealand', 'wellington': 'New Zealand', 'auckland': 'New Zealand', 'christchurch': 'New Zealand',
    'papua new guinea': 'Papua New Guinea', 'png': 'Papua New Guinea', 'port moresby': 'Papua New Guinea',
    'fiji': 'Fiji', 'fijian': 'Fiji', 'suva': 'Fiji',
    'samoa': 'Samoa', 'samoan': 'Samoa', 'apia': 'Samoa',
    'tonga': 'Tonga', 'tongan': 'Tonga', "nuku'alofa": 'Tonga',
    'vanuatu': 'Vanuatu', 'port vila': 'Vanuatu',
    'solomon islands': 'Solomon Islands', 'honiara': 'Solomon Islands',
    'kiribati': 'Kiribati',
    'tuvalu': 'Tuvalu',
    'micronesia': 'Micronesia',
    'marshall islands': 'Marshall Islands',
    'palau': 'Palau',
    'nauru': 'Nauru',
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def load_seen():
    if os.path.exists(SEEN_FILE):
        try:
            with open(SEEN_FILE, 'r') as f:
                return set(json.load(f))
        except Exception as e:
            log.warning(f'Could not load seen file: {e}')
    return set()

def save_seen(seen):
    try:
        with open(SEEN_FILE, 'w') as f:
            json.dump(sorted(seen), f, indent=2)
    except Exception as e:
        log.error(f'Could not save seen file: {e}')

def hash_item(title, link):
    return hashlib.md5(f'{title}|{link}'.encode('utf-8')).hexdigest()

def clean_text(s):
    if not s:
        return ''
    s = re.sub(r'<[^>]+>', ' ', s)
    s = re.sub(r'\s+', ' ', s)
    return s.strip()

def is_relevant(title, summary):
    text = f'{title} {summary}'.lower()

    for pat in EXCLUDE_PATTERNS:
        if pat in text:
            return False

    has_disaster = any(term in text for term in DISASTER_TERMS)
    has_signal = any(sig in text for sig in EVENT_SIGNALS)

    return has_disaster and has_signal

def extract_country(title, summary):
    text = f'{title} {summary}'.lower()
    matches = []
    for key, country in COUNTRY_LOOKUP.items():
        # word boundary match to avoid e.g. "us" inside "thus"
        pattern = r'\b' + re.escape(key) + r'\b'
        if re.search(pattern, text):
            matches.append((key, country, len(key)))
    if not matches:
        return None
    # prefer longest match (most specific)
    matches.sort(key=lambda x: -x[2])
    return matches[0][1]

def in_region(country, region_name):
    if not country or region_name not in REGIONS:
        return False
    return country in REGIONS[region_name]

# ---------------------------------------------------------------------------
# Article generation
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """You are a senior news writer for Global Witness Monitor's Natural Disaster Intelligence desk.

Your job: turn the supplied source headline and summary into a tight, factual news brief about the disaster event.

STRICT RULES:
- Write only what is supported by the source. Do NOT invent casualty figures, locations, magnitudes, or quotes.
- If the source does not give a number, do not give a number. Use phrases like "officials report casualties" rather than fabricated figures.
- Do NOT name individual victims unless the source names them.
- Neutral, wire-service tone. No speculation, no editorializing, no calls to action.
- 3 to 5 short paragraphs, plain prose.
- Open with the event, location, and immediate impact.
- Then context: response efforts, scale, related conditions if mentioned in the source.
- Close with what is currently known about ongoing risk or response, again only if the source supports it.
- Do NOT include a headline; only the body. Do NOT add a sign-off or byline.
- Do NOT use markdown headers. Plain paragraphs only.
"""

def generate_article(item, client):
    title = item['title']
    summary = item['summary']
    source = item['source']

    user_msg = (
        f"SOURCE OUTLET: {source}\n"
        f"HEADLINE: {title}\n"
        f"SOURCE SUMMARY:\n{summary}\n\n"
        "Write the news brief now."
    )

    try:
        resp = client.messages.create(
            model='claude-sonnet-4-5',
            max_tokens=1200,
            system=SYSTEM_PROMPT,
            messages=[{'role': 'user', 'content': user_msg}],
        )
        body = ''.join(b.text for b in resp.content if hasattr(b, 'text')).strip()
        return body
    except Exception as e:
        log.error(f'Claude generation failed for "{title[:60]}": {e}')
        return None

# ---------------------------------------------------------------------------
# WordPress publishing
# ---------------------------------------------------------------------------
def get_or_create_tag(country, auth):
    """Find an existing tag for the country, or create one. Return tag ID."""
    try:
        r = requests.get(
            f'{WP_URL}/wp-json/wp/v2/tags',
            params={'search': country, 'per_page': 20},
            auth=auth, timeout=20
        )
        if r.ok:
            for t in r.json():
                if t['name'].lower() == country.lower():
                    return t['id']
        # create
        r = requests.post(
            f'{WP_URL}/wp-json/wp/v2/tags',
            json={'name': country},
            auth=auth, timeout=20
        )
        if r.ok:
            return r.json()['id']
        log.warning(f'Could not create tag for {country}: {r.status_code} {r.text[:200]}')
    except Exception as e:
        log.warning(f'Tag error for {country}: {e}')
    return None

def publish_to_wordpress(item, article_body, country):
    auth = (WP_USER, WP_APP_PASSWORD)

    src_line = f'<p><em>Source: {item["source"]}. Original report: <a href="{item["link"]}" rel="noopener" target="_blank">link</a>.</em></p>'
    paragraphs = [p.strip() for p in article_body.split('\n\n') if p.strip()]
    content_html = '\n'.join(f'<p>{p}</p>' for p in paragraphs) + '\n' + src_line

    tag_ids = []
    if country:
        tid = get_or_create_tag(country, auth)
        if tid:
            tag_ids.append(tid)

    payload = {
        'title': item['title'],
        'content': content_html,
        'status': 'publish',
        'categories': [WP_CATEGORY_ID],
    }
    if tag_ids:
        payload['tags'] = tag_ids

    try:
        r = requests.post(
            f'{WP_URL}/wp-json/wp/v2/posts',
            json=payload, auth=auth, timeout=30
        )
        if r.status_code in (200, 201):
            post_id = r.json().get('id')
            log.info(f'Published #{post_id}: {item["title"][:80]}')
            return True
        else:
            log.error(f'Publish failed {r.status_code}: {r.text[:300]}')
            return False
    except Exception as e:
        log.error(f'Publish exception: {e}')
        return False

# ---------------------------------------------------------------------------
# Feed fetching
# ---------------------------------------------------------------------------
def fetch_feeds():
    items = []
    for name, url in RSS_FEEDS:
        try:
            log.info(f'Fetching {name}')
            feed = feedparser.parse(url, request_headers={'User-Agent': 'GWM-DisasterPipeline/1.0'})
            count = 0
            for entry in feed.entries:
                title = clean_text(entry.get('title', ''))
                summary = clean_text(entry.get('summary', '') or entry.get('description', ''))
                link = entry.get('link', '')
                if not title or not link:
                    continue
                items.append({
                    'source': name,
                    'title': title,
                    'summary': summary,
                    'link': link,
                    'hash': hash_item(title, link),
                })
                count += 1
            log.info(f'  {count} entries from {name}')
        except Exception as e:
            log.warning(f'Feed error {name}: {e}')
    return items

# ---------------------------------------------------------------------------
# Args
# ---------------------------------------------------------------------------
def parse_args():
    p = argparse.ArgumentParser(description='GWM Natural Disaster Pipeline')
    p.add_argument('--region', choices=list(REGIONS.keys()),
                   help='Only publish events in this region')
    p.add_argument('--country',
                   help='Only publish events for this exact country name (e.g. Indonesia)')
    p.add_argument('--limit', type=int, default=ARTICLES_PER_RUN,
                   help=f'Max articles to publish per run (default {ARTICLES_PER_RUN})')
    p.add_argument('--dry-run', action='store_true',
                   help='Filter and generate but do not publish')
    return p.parse_args()

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    args = parse_args()
    log.info('=' * 70)
    log.info('GWM Natural Disaster Pipeline starting')
    log.info(f'Region filter: {args.region or "none"} | Country filter: {args.country or "none"} | Limit: {args.limit} | Dry-run: {args.dry_run}')
    log.info('=' * 70)

    seen = load_seen()
    log.info(f'Loaded {len(seen)} seen item hashes')

    items = fetch_feeds()
    log.info(f'Total entries fetched: {len(items)}')

    # de-dup against seen
    fresh = [i for i in items if i['hash'] not in seen]
    log.info(f'After dedupe vs seen: {len(fresh)}')

    # relevance filter
    relevant = [i for i in fresh if is_relevant(i['title'], i['summary'])]
    log.info(f'After relevance filter: {len(relevant)}')

    # country / region filter
    enriched = []
    for i in relevant:
        country = extract_country(i['title'], i['summary'])
        i['country'] = country
        if args.country:
            if not country or country.lower() != args.country.lower():
                continue
        if args.region:
            if not in_region(country, args.region):
                continue
        enriched.append(i)
    log.info(f'After region/country filter: {len(enriched)}')

    if not enriched:
        log.info('Nothing to publish. Exiting.')
        return

    client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)

    published = 0
    for item in enriched:
        if published >= args.limit:
            break

        log.info(f'-> Generating: {item["title"][:80]}')
        body = generate_article(item, client)
        if not body:
            seen.add(item['hash'])
            continue

        if args.dry_run:
            log.info(f'[DRY-RUN] Would publish ({item.get("country") or "no country"}): {item["title"][:80]}')
            log.info(f'[DRY-RUN] Body preview: {body[:200]}...')
            seen.add(item['hash'])
            published += 1
            continue

        ok = publish_to_wordpress(item, body, item.get('country'))
        seen.add(item['hash'])
        if ok:
            published += 1
            time.sleep(2)  # gentle pacing on WP
        else:
            log.warning('Publish failed; continuing')

    save_seen(seen)
    log.info(f'Done. Published {published} article(s). Seen file now has {len(seen)} entries.')

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        log.info('Interrupted')
        sys.exit(1)
    except Exception as e:
        log.exception(f'Fatal error: {e}')
        sys.exit(1)
