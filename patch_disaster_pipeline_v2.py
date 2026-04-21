#!/usr/bin/env python3
"""
patch_disaster_pipeline_v2.py

Four patches to boost disaster pipeline yield and quality:

  1. USGS/GDACS trusted-source bypass -- articles from these feeds skip the
     keyword and event-signal filters (the feed itself is the authority)

  2. Magnitude pattern recognition -- any title matching "M X.Y" qualifies as
     both a disaster keyword and an event signal (safety net)

  3. Claude prompt loosening -- accept thin source material when a factual
     kernel exists; only SKIP_NO_EVENT for pure opinion/editorial content

  4. Article body fetcher -- attempt to fetch full article body via HTTP
     before Claude generation, giving Claude real material to work with
     instead of thin RSS summaries

Usage on the server:
    curl -sL <raw-gist-url> -o /tmp/patch_disaster_pipeline_v2.py
    python3 /tmp/patch_disaster_pipeline_v2.py
    /opt/disaster-pipeline/venv/bin/pip install beautifulsoup4

This also installs beautifulsoup4 via pip (needed for patch 4).
"""

import os
import shutil
import sys
import subprocess

TARGET = "/opt/disaster-pipeline/run_disaster_pipeline.py"
BACKUP = TARGET + ".bak2"


def backup():
    if not os.path.exists(TARGET):
        print("ERROR: " + TARGET + " does not exist.")
        sys.exit(1)
    shutil.copy2(TARGET, BACKUP)
    print("Backed up to: " + BACKUP)


def read():
    with open(TARGET, "r") as f:
        return f.read()


def write(src):
    with open(TARGET, "w") as f:
        f.write(src)


def verify_python(src):
    import ast
    try:
        ast.parse(src)
        return True
    except SyntaxError as e:
        print("SYNTAX ERROR: " + str(e))
        return False


# ==========================================================================
#  PATCH 1: USGS/GDACS trusted-source bypass
# ==========================================================================
def patch_1_trusted_sources(src):
    print("")
    print("[1/4] Trusted-source bypass (USGS/GDACS)...")

    # Add a helper function above is_relevant()
    old_is_relevant_def = "def is_relevant(title, summary):"
    new_helper_and_def = '''# Feeds whose items are inherently disaster events -- skip keyword/signal filters
TRUSTED_DISASTER_FEEDS = (
    "earthquake.usgs.gov",
    "gdacs.org",
)

def is_trusted_feed(feed_url):
    return any(domain in (feed_url or "") for domain in TRUSTED_DISASTER_FEEDS)

def is_relevant(title, summary):'''

    if old_is_relevant_def not in src:
        print("  SKIP: is_relevant() not found")
        return src, False
    src = src.replace(old_is_relevant_def, new_helper_and_def, 1)

    # Modify the RSS fetch loop so trusted feeds bypass is_relevant()
    old_rss_filter = '''                if not is_relevant(title, summary):
                    continue'''
    new_rss_filter = '''                if not is_trusted_feed(feed_url) and not is_relevant(title, summary):
                    continue'''

    if old_rss_filter not in src:
        print("  SKIP: is_relevant() call in RSS loop not found")
        return src, False
    src = src.replace(old_rss_filter, new_rss_filter, 1)

    print("  applied: TRUSTED_DISASTER_FEEDS helper + bypass in fetch loop")
    return src, True


# ==========================================================================
#  PATCH 2: Magnitude pattern recognition
# ==========================================================================
def patch_2_magnitude_pattern(src):
    print("")
    print("[2/4] Magnitude pattern (M X.Y auto-qualifies as earthquake event)...")

    # Add regex import at top if not already present
    if "import re" not in src:
        src = src.replace("import os", "import os\nimport re", 1)
        print("  added: import re")

    # Update is_relevant to check for magnitude pattern
    old_body = '''def is_relevant(title, summary):
    """Check if article is relevant AND is an actual event (not opinion/explainer)."""
    text = (title + " " + summary).lower()

    has_disaster = any(term in text for term in DISASTER_TERMS)
    if not has_disaster:
        return False

    has_event = any(signal in text for signal in EVENT_SIGNALS)
    if not has_event:
        return False'''

    new_body = '''MAGNITUDE_PATTERN = re.compile(r"\\bM\\s?\\d+\\.\\d+\\b", re.IGNORECASE)

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
        return False'''

    if old_body not in src:
        print("  SKIP: is_relevant() body not in expected form")
        return src, False
    src = src.replace(old_body, new_body, 1)

    print("  applied: MAGNITUDE_PATTERN regex, auto-qualifies keyword + event")
    return src, True


# ==========================================================================
#  PATCH 3: Loosen Claude SKIP_NO_EVENT prompt
# ==========================================================================
def patch_3_claude_prompt(src):
    print("")
    print("[3/4] Loosening Claude SKIP_NO_EVENT threshold...")

    old_prompt_tail = '''IMPORTANT: If the source material does not describe an actual disaster event (something that
happened), or if there is insufficient factual information to write a proper intelligence brief,
respond with exactly: SKIP_NO_EVENT"""'''

    new_prompt_tail = '''IMPORTANT: Only respond with SKIP_NO_EVENT if the source is pure opinion, commentary, or an
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
  - Duplicates of news you've already covered (not your concern to detect -- pipeline handles it)"""'''

    if old_prompt_tail not in src:
        print("  SKIP: SKIP_NO_EVENT prompt section not found in expected form")
        return src, False
    src = src.replace(old_prompt_tail, new_prompt_tail, 1)

    # Also loosen is_valid_article's word count minimum (was 80, now 60)
    old_wc = '''    word_count = len(article_body.split())
    if word_count < 80:
        return False'''
    new_wc = '''    word_count = len(article_body.split())
    if word_count < 60:
        return False'''

    if old_wc in src:
        src = src.replace(old_wc, new_wc, 1)
        print("  applied: min word count 80 -> 60")
    else:
        print("  SKIP: word count check not found")

    print("  applied: loosened SKIP_NO_EVENT criteria in system prompt")
    return src, True


# ==========================================================================
#  PATCH 4: Article body fetcher
# ==========================================================================
def patch_4_article_body_fetcher(src):
    print("")
    print("[4/4] Article body fetcher (pre-Claude enrichment)...")

    # Add body-fetch helper just above generate_article()
    body_fetcher_fn = '''
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


'''

    old_generate_def = "def generate_article(item):"
    if old_generate_def not in src:
        print("  SKIP: generate_article not found")
        return src, False
    src = src.replace(old_generate_def, body_fetcher_fn + old_generate_def, 1)

    # Now modify generate_article to use the body fetcher
    old_user_prompt = '''    user_prompt = (
        "Write a natural disaster intelligence brief based on this source material only.\\n\\n"
        "SOURCE TITLE: " + item["title"] + "\\n\\n"
        "SOURCE SUMMARY: " + item["summary"] + "\\n\\n"
        "SOURCE URL: " + item["url"] + "\\n\\n"
        "SOURCE OUTLET: " + item["source"] + "\\n\\n"
        "DETECTED DISASTER TYPE: " + item.get("disaster_type", "Other") + "\\n\\n"
        "Remember: only use facts present in the source material above. "
        "If this is not an actual disaster event or lacks sufficient detail, "
        "respond with SKIP_NO_EVENT."
    )'''

    new_user_prompt = '''    # Attempt to fetch full article body for richer context
    body_text = fetch_article_body(item["url"])
    body_section = ""
    if body_text:
        log.info("fetched %d chars of article body", len(body_text))
        body_section = "SOURCE BODY TEXT:\\n" + body_text + "\\n\\n"

    user_prompt = (
        "Write a natural disaster intelligence brief based on this source material only.\\n\\n"
        "SOURCE TITLE: " + item["title"] + "\\n\\n"
        "SOURCE SUMMARY: " + item["summary"] + "\\n\\n"
        + body_section +
        "SOURCE URL: " + item["url"] + "\\n\\n"
        "SOURCE OUTLET: " + item["source"] + "\\n\\n"
        "DETECTED DISASTER TYPE: " + item.get("disaster_type", "Other") + "\\n\\n"
        "Use only facts present in the source material above. Prefer the SOURCE BODY TEXT when "
        "available for specific numbers, locations, and quotes. If the content is pure opinion "
        "or a non-event explainer with no reported disaster, respond with SKIP_NO_EVENT."
    )'''

    if old_user_prompt not in src:
        print("  SKIP: user_prompt not found in expected form")
        return src, False
    src = src.replace(old_user_prompt, new_user_prompt, 1)

    print("  applied: fetch_article_body() + enriched user_prompt")
    return src, True


# ==========================================================================
#  INSTALL beautifulsoup4
# ==========================================================================
def install_bs4():
    print("")
    print("Installing beautifulsoup4 into pipeline venv...")
    pip = "/opt/disaster-pipeline/venv/bin/pip"
    if not os.path.exists(pip):
        print("  SKIP: venv pip not found at " + pip)
        return
    try:
        r = subprocess.run([pip, "install", "beautifulsoup4"],
                           capture_output=True, text=True, timeout=90)
        if r.returncode == 0:
            print("  done.")
        else:
            print("  ERROR: " + r.stderr[:300])
    except Exception as e:
        print("  ERROR: " + str(e))


# ==========================================================================
#  MAIN
# ==========================================================================
def main():
    print("=" * 64)
    print("  DISASTER PIPELINE PATCH v2")
    print("=" * 64)

    backup()
    src = read()

    applied = []

    src, ok = patch_1_trusted_sources(src)
    if ok: applied.append("1: trusted-source bypass")

    src, ok = patch_2_magnitude_pattern(src)
    if ok: applied.append("2: magnitude pattern")

    src, ok = patch_3_claude_prompt(src)
    if ok: applied.append("3: Claude prompt loosened")

    src, ok = patch_4_article_body_fetcher(src)
    if ok: applied.append("4: article body fetcher")

    # Verify still valid Python
    if not verify_python(src):
        print("")
        print("SYNTAX BROKEN. Restoring backup.")
        shutil.copy2(BACKUP, TARGET)
        print("Restored from " + BACKUP)
        sys.exit(1)

    write(src)

    install_bs4()

    print("")
    print("=" * 64)
    print("  APPLIED:")
    for a in applied:
        print("    - " + a)
    print("=" * 64)
    print("")
    print("Next:")
    print("  cd /opt/disaster-pipeline && set -a && source .env && set +a \\")
    print("    && venv/bin/python run_disaster_pipeline.py")
    print("")


if __name__ == "__main__":
    main()
