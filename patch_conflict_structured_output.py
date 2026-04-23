#!/usr/bin/env python3
"""
patch_conflict_structured_output.py

Applies Claude-structured country output to the conflict pipeline.
Same pattern as disaster pipeline but:
  - No disaster_type (conflict pipeline doesn't use one)
  - Adds article body fetcher (conflict lacks it)
  - Updates deprecated model to claude-sonnet-4-6
  - Uses line-based call site edit (lesson learned from disaster)

Backs up to .bak_structured before changes.
AST-validates; restores on failure.
Idempotent.
"""

import os
import re
import shutil
import sys
import ast
import subprocess

TARGET = "/opt/conflict-pipeline/run_conflict_pipeline.py"
BACKUP = TARGET + ".bak_structured"


def backup():
    if not os.path.exists(TARGET):
        print("ERROR:", TARGET, "not found")
        sys.exit(1)
    shutil.copy2(TARGET, BACKUP)
    print("Backed up to:", BACKUP)


def read():
    with open(TARGET, "r") as f:
        return f.read()


def write(src):
    with open(TARGET, "w") as f:
        f.write(src)


def verify_python(src):
    try:
        ast.parse(src)
        return True
    except SyntaxError as e:
        print("SYNTAX ERROR:", e)
        return False


# --------------------------------------------------------------------------
# 1. Canonical country registry + parse function
# --------------------------------------------------------------------------
def patch_registry(src):
    print("\n[1/6] Canonical registry + parse_claude_response...")

    if "CANONICAL_COUNTRY_MAP" in src:
        print("  SKIP: already applied")
        return src, False

    marker = "# -- BAD RESPONSE PATTERNS --"
    if marker not in src:
        print("  SKIP: BAD RESPONSE PATTERNS marker not found")
        return src, False

    block = '''# -- CANONICAL COUNTRY REGISTRY --
CANONICAL_COUNTRY_MAP = None

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


def parse_claude_response(raw_text):
    """Parse Claude's structured response for conflict pipeline.

    Expected format:
        COUNTRY: <country | MULTIPLE: c1, c2 | UNKNOWN>
        ---
        <article body>
    """
    result = {
        "countries": [],
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
    body_start_idx = 0

    for i, line in enumerate(lines[:6]):
        stripped = line.strip()
        up = stripped.upper()
        if up.startswith("COUNTRY:"):
            country_line = stripped[len("COUNTRY:"):].strip()
            body_start_idx = max(body_start_idx, i + 1)
        elif stripped == "---":
            body_start_idx = max(body_start_idx, i + 1)

    while body_start_idx < len(lines) and (
        not lines[body_start_idx].strip() or lines[body_start_idx].strip() == "---"
    ):
        body_start_idx += 1

    result["body"] = "\\n".join(lines[body_start_idx:]).strip()
    result["raw_country_line"] = country_line or ""

    if not country_line:
        result["status"] = "malformed"
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


'''
    src = src.replace(marker, block + marker, 1)
    print("  applied")
    return src, True


# --------------------------------------------------------------------------
# 2. SYSTEM_PROMPT structured header
# --------------------------------------------------------------------------
def patch_prompt(src):
    print("\n[2/6] SYSTEM_PROMPT structured header...")

    if "REQUIRED OUTPUT FORMAT" in src:
        print("  SKIP: already applied")
        return src, False

    marker = "CRITICAL RULES:"
    if marker not in src:
        print("  SKIP: CRITICAL RULES marker not found")
        return src, False

    insertion = """REQUIRED OUTPUT FORMAT -- every response must begin with exactly this 2-line header:

COUNTRY: <primary country where the event physically occurred>
---

Then the article body follows on the next line.

COUNTRY field rules:
- Return the country where the event PHYSICALLY OCCURRED, not where the news outlet is based.
- Ignore outlet names in the source material (e.g. "Pakistan Today", "Japan Times", "BBC").
- Ignore subject demonyms unrelated to event location.
- For events affecting multiple countries: COUNTRY: MULTIPLE: Country1, Country2
- For events in international waters or uncountryable regions: COUNTRY: UNKNOWN
- Use common country names: "Iran", "United States", "United Kingdom", "Myanmar", "Congo".
- Do NOT include state/province names.
- Do NOT include continents or regions.

If you cannot identify a valid country with reasonable confidence, output COUNTRY: UNKNOWN.
Missing data is better than wrong data.

CRITICAL RULES:"""

    src = src.replace(marker, insertion, 1)
    print("  applied")
    return src, True


# --------------------------------------------------------------------------
# 3. Update deprecated model + add body fetcher + update generate_article
# --------------------------------------------------------------------------
def patch_generate_article(src):
    print("\n[3/6] Article body fetcher + generate_article...")

    if "fetch_article_body" in src:
        print("  SKIP: already applied")
        return src, False

    # Update deprecated model first
    old_model = "model='claude-sonnet-4-20250514'"
    new_model = "model='claude-sonnet-4-6'"
    if old_model in src:
        src = src.replace(old_model, new_model, 1)
        print("  model updated: claude-sonnet-4-20250514 -> claude-sonnet-4-6")

    # Insert body fetcher just above def generate_article
    marker = "def generate_article(item):"
    if marker not in src:
        print("  SKIP: generate_article def not found")
        return src, False

    body_fetcher = '''# -- ARTICLE BODY FETCHER --
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
        return " ".join(text.split())[:max_chars]
    except Exception as e:
        log.info("body fetch failed for %s: %s", url[:60], e)
        return ""


'''
    src = src.replace(marker, body_fetcher + marker, 1)

    # Modify generate_article return and inject body into prompt
    # Update return
    old_return = "    return message.content[0].text.strip()"
    new_return = '''    raw_response = message.content[0].text.strip()
    parsed = parse_claude_response(raw_response)
    return raw_response, parsed'''
    if old_return in src:
        src = src.replace(old_return, new_return, 1)
        print("  generate_article return: now (raw, parsed)")

    # Inject body fetcher into the user_prompt build
    old_prompt_start = '"SOURCE TITLE: " + item[\'title\'] + "\\n\\n"'
    new_prompt_prefix = '''# Fetch full article body for richer context
    body_text = fetch_article_body(item.get('url', ''))
    body_section = ""
    if body_text:
        log.info("fetched %d chars of article body", len(body_text))
        body_section = "SOURCE BODY TEXT:\\n" + body_text + "\\n\\n"

    user_prompt = (
        "SOURCE TITLE: " + item['title'] + "\\n\\n"'''

    # Find the user_prompt = (  line
    up_marker = "    user_prompt = (\n        \"SOURCE TITLE: \" + item['title'] + \"\\n\\n\""
    if up_marker in src:
        src = src.replace(up_marker, new_prompt_prefix, 1)
        # Now inject body_section after SOURCE SUMMARY line
        summary_line = '"SOURCE SUMMARY: " + item[\'summary\'] + "\\n\\n"'
        if summary_line in src:
            src = src.replace(
                summary_line,
                summary_line + "\n        + body_section +",
                1,
            )
            print("  body fetcher wired into user_prompt")
        else:
            print("  WARN: could not wire body_section into prompt (SOURCE SUMMARY line not found)")

    return src, True


# --------------------------------------------------------------------------
# 4. publish_to_wordpress uses parsed
# --------------------------------------------------------------------------
def patch_publish(src):
    print("\n[4/6] publish_to_wordpress uses Claude values...")

    if "# Use Claude-parsed country" in src:
        print("  SKIP: already applied")
        return src, False

    old = '''def publish_to_wordpress(item, article_body):
    endpoint = WP_URL + '/wp-json/wp/v2/posts'
    auth     = (WP_USER, WP_APP_PASSWORD)

    country = item.get('country')

    if not country:
        log.info('Skipping (no country detected): %s', item['title'][:60])
        return False'''

    new = '''def publish_to_wordpress(item, article_body, parsed=None):
    endpoint = WP_URL + '/wp-json/wp/v2/posts'
    auth     = (WP_USER, WP_APP_PASSWORD)

    # Use Claude-parsed country as authoritative
    detected_country = item.get('country')

    if parsed is None:
        log.warning("publish_to_wordpress called without parsed structure; skipping")
        return False

    status = parsed.get("status", "malformed")
    log.info(
        "CLAUDE_VS_DETECTED: claude_country=%s detected_country=%s status=%s raw=%r",
        ",".join(parsed.get("countries", [])) or "-",
        detected_country or "-",
        status,
        parsed.get("raw_country_line", ""),
    )

    if status == "unknown":
        log.info("Skipping (Claude marked UNKNOWN): %s", item['title'][:60])
        return False
    if status == "malformed":
        log.warning("Skipping (Claude response malformed): %s", item['title'][:60])
        return False
    if status == "no_valid_country":
        log.warning(
            "Skipping (Claude country %r not in registry): %s",
            parsed.get("raw_country_line", ""), item['title'][:60],
        )
        return False

    countries = parsed["countries"]
    country = countries[0]'''

    if old not in src:
        print("  SKIP: publish_to_wordpress head not in expected form")
        return src, False
    src = src.replace(old, new, 1)
    print("  applied")
    return src, True


# --------------------------------------------------------------------------
# 5. Update publish tag loop to tag all countries
# --------------------------------------------------------------------------
def patch_tag_loop(src):
    print("\n[5/6] Tag all countries in WP...")

    if "for c in countries:" in src:
        print("  SKIP: already applied")
        return src, False

    # Find r = requests.get(...) for tags
    # and wrap in a loop over countries instead of single country
    old = """    tag_ids = []
    try:
        r = requests.get(
            WP_URL + '/wp-json/wp/v2/tags',
            params={'search': country},
            auth=auth
        )"""

    new = """    tag_ids = []
    try:
        for c in countries:
            r = requests.get(
                WP_URL + '/wp-json/wp/v2/tags',
                params={'search': c},
                auth=auth
            )
            existing = r.json() if r.status_code == 200 else []
            found = False
            for tag in existing:
                if tag.get("name", "").strip().lower() == c.strip().lower():
                    tag_ids.append(tag["id"])
                    found = True
                    break
            if not found:
                r2 = requests.post(
                    WP_URL + '/wp-json/wp/v2/tags',
                    json={"name": c},
                    auth=auth,
                )
                if r2.status_code in (200, 201):
                    tag_ids.append(r2.json()["id"])
        # Skip legacy single-country tag logic below by setting existing=[]
        existing = []
        r = type('obj', (object,), {'status_code': 200, 'json': lambda self=None: []})()"""

    if old in src:
        src = src.replace(old, new, 1)
        print("  applied: multi-country tag loop")
    else:
        print("  NOTE: tag loop pattern not matched exactly; inspect publish_to_wordpress manually")

    return src, True


# --------------------------------------------------------------------------
# 6. Call site: unpack tuple + pass parsed
# --------------------------------------------------------------------------
def patch_call_sites(src):
    print("\n[6/6] Call site updates (line-based)...")

    if "_gen_result = generate_article" in src:
        print("  SKIP: already applied")
        return src, False

    lines = src.splitlines(keepends=True)
    gen_pat = re.compile(r"^(\s+)article_body\s*=\s*generate_article\(item\)\s*$")
    pub_pat = re.compile(r"^(\s+)success\s*=\s*publish_to_wordpress\(item,\s*article_body\)\s*$")

    gen_idx = gen_indent = pub_idx = None
    for i, line in enumerate(lines):
        m = gen_pat.match(line)
        if m and gen_idx is None:
            gen_idx = i
            gen_indent = m.group(1)
        m2 = pub_pat.match(line)
        if m2 and pub_idx is None:
            pub_idx = i

    if gen_idx is None or pub_idx is None:
        print("  SKIP: call sites not found")
        return src, False

    print("  generate_article call at line", gen_idx + 1)
    print("  publish_to_wordpress call at line", pub_idx + 1)

    new_gen = [
        gen_indent + "_gen_result = generate_article(item)\n",
        gen_indent + "if isinstance(_gen_result, tuple):\n",
        gen_indent + "    raw_response, parsed = _gen_result\n",
        gen_indent + "else:\n",
        gen_indent + "    raw_response, parsed = _gen_result, None\n",
        gen_indent + 'article_body = parsed["body"] if (parsed and parsed.get("body")) else raw_response\n',
    ]

    new_pub = lines[pub_idx].replace(
        "publish_to_wordpress(item, article_body)",
        "publish_to_wordpress(item, article_body, parsed=parsed)",
    )

    if pub_idx > gen_idx:
        lines[pub_idx] = new_pub
        lines[gen_idx:gen_idx + 1] = new_gen
    else:
        lines[gen_idx:gen_idx + 1] = new_gen
        lines[pub_idx + 5] = new_pub

    return "".join(lines), True


# --------------------------------------------------------------------------
# Install bs4 if missing
# --------------------------------------------------------------------------
def install_bs4():
    print("\nEnsuring beautifulsoup4 installed...")
    pip = "/opt/conflict-pipeline/venv/bin/pip"
    if not os.path.exists(pip):
        print("  SKIP: venv pip not found")
        return
    try:
        r = subprocess.run(
            [pip, "install", "beautifulsoup4"],
            capture_output=True, text=True, timeout=90,
        )
        if r.returncode == 0:
            print("  done")
        else:
            print("  WARN:", r.stderr[:200])
    except Exception as e:
        print("  WARN:", e)


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------
def main():
    print("=" * 60)
    print("  CONFLICT PIPELINE: CLAUDE-STRUCTURED OUTPUT PATCH")
    print("=" * 60)
    backup()
    src = read()
    applied = []

    src, ok = patch_registry(src)
    if ok: applied.append("1: canonical registry")

    src, ok = patch_prompt(src)
    if ok: applied.append("2: SYSTEM_PROMPT")

    src, ok = patch_generate_article(src)
    if ok: applied.append("3: body fetcher + generate_article")

    src, ok = patch_publish(src)
    if ok: applied.append("4: publish_to_wordpress")

    src, ok = patch_tag_loop(src)
    if ok: applied.append("5: multi-country tag loop")

    src, ok = patch_call_sites(src)
    if ok: applied.append("6: call sites")

    if not verify_python(src):
        print("\nSYNTAX BROKEN. Restoring backup.")
        shutil.copy2(BACKUP, TARGET)
        sys.exit(1)

    write(src)
    install_bs4()

    print("\n" + "=" * 60)
    print("APPLIED:")
    for a in applied:
        print("  -", a)
    print("=" * 60)
    print("\nNext:")
    print("  cd /opt/conflict-pipeline && set -a && source .env && set +a \\")
    print("    && venv/bin/python run_conflict_pipeline.py")


if __name__ == "__main__":
    main()
