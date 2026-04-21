#!/usr/bin/env python3
"""
patch_disaster_structured_output.py

Replaces the broken title-scan country/type detection with Claude-authored
structured output. Claude reads the article body text (from Patch 4) and
returns a 3-line header with COUNTRY and DISASTER_TYPE, validated against
a canonical registry built from the existing country list.

No fallback to title-scan. If Claude can't identify a valid country,
the article is skipped. Better to lose an article than misattribute it.

Usage:
    python3 patch_disaster_structured_output.py

This script:
  1. Backs up run_disaster_pipeline.py to .bak3
  2. Inserts CANONICAL_COUNTRY_MAP and validation helpers near top
  3. Inserts parse_claude_response() function
  4. Modifies SYSTEM_PROMPT to require structured header
  5. Modifies generate_article() return type
  6. Modifies publish_to_wordpress() to use Claude's values
  7. AST-validates output; auto-restores on syntax error

Safe to run multiple times: if patches already applied, it will report
SKIP for each section rather than double-patching.
"""

import os
import shutil
import sys
import ast

TARGET = "/opt/disaster-pipeline/run_disaster_pipeline.py"
BACKUP = TARGET + ".bak3"


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
    try:
        ast.parse(src)
        return True
    except SyntaxError as e:
        print("SYNTAX ERROR: " + str(e))
        return False


# ==========================================================================
# PATCH 1: Insert CANONICAL_COUNTRY_MAP and validation helpers
# ==========================================================================
def patch_canonical_registry(src):
    print("")
    print("[1/5] Inserting canonical country registry and validators...")

    marker = "# -- COUNTRY EXTRACTION --"
    if marker not in src:
        print("  SKIP: marker not found")
        return src, False

    if "CANONICAL_COUNTRY_MAP" in src:
        print("  SKIP: already applied (CANONICAL_COUNTRY_MAP exists)")
        return src, False

    block = '''# -- CANONICAL COUNTRY REGISTRY --
# Built lazily from ALL_COUNTRIES plus known aliases so we can validate
# Claude's returned country string against a single source of truth.
CANONICAL_COUNTRY_MAP = None  # populated on first use

# Manual aliases for common country-name variations Claude might produce
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


def _build_country_map():
    """Build lookup map from normalized name -> canonical name. Idempotent."""
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


def _normalize_country_key(s):
    """Lowercase, strip punctuation, collapse whitespace."""
    if not s:
        return ""
    s = s.lower().strip()
    # Remove common punctuation
    for ch in [".", ",", "(", ")", "-", "'", '"']:
        s = s.replace(ch, " ")
    # Collapse whitespace
    s = " ".join(s.split())
    return s


def validate_country(claude_country):
    """Validate Claude's country string against canonical registry.
    Returns canonical country name or None."""
    if not claude_country or not isinstance(claude_country, str):
        return None
    key = _normalize_country_key(claude_country)
    if not key:
        return None
    m = _build_country_map()
    return m.get(key)


VALID_DISASTER_TYPES = {
    "earthquake", "flood", "storm", "wildfire", "volcano",
    "tsunami", "landslide", "drought", "heatwave", "other",
}


def validate_disaster_type(claude_type):
    """Validate Claude's disaster type. Returns canonical Title-Case
    string or 'Other' if invalid."""
    if not claude_type or not isinstance(claude_type, str):
        return "Other"
    key = claude_type.strip().lower()
    if key in VALID_DISASTER_TYPES:
        return key.capitalize() if key != "other" else "Other"
    return "Other"


def parse_claude_response(raw_text):
    """Parse Claude's structured response.

    Expected format:
        COUNTRY: <country name | MULTIPLE: c1, c2 | UNKNOWN>
        DISASTER_TYPE: <type>
        ---
        <article body...>

    Returns dict with keys:
        countries: list of canonical country names (may be empty)
        disaster_type: canonical disaster type string
        body: article body text with header stripped
        raw_country_line: what Claude actually wrote (for logging)
        status: "ok" | "unknown" | "malformed" | "no_valid_country"
    """
    result = {
        "countries": [],
        "disaster_type": "Other",
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
    body_start_idx = 0

    # Scan first ~6 lines for header fields
    for i, line in enumerate(lines[:8]):
        stripped = line.strip()
        up = stripped.upper()
        if up.startswith("COUNTRY:"):
            country_line = stripped[len("COUNTRY:"):].strip()
            body_start_idx = max(body_start_idx, i + 1)
        elif up.startswith("DISASTER_TYPE:") or up.startswith("DISASTER TYPE:"):
            # accept either spelling
            if up.startswith("DISASTER_TYPE:"):
                type_line = stripped[len("DISASTER_TYPE:"):].strip()
            else:
                type_line = stripped[len("DISASTER TYPE:"):].strip()
            body_start_idx = max(body_start_idx, i + 1)
        elif stripped == "---":
            body_start_idx = max(body_start_idx, i + 1)

    # Skip blank lines and separator after header
    while body_start_idx < len(lines) and (
        not lines[body_start_idx].strip() or lines[body_start_idx].strip() == "---"
    ):
        body_start_idx += 1

    result["body"] = "\\n".join(lines[body_start_idx:]).strip()
    result["raw_country_line"] = country_line or ""

    # Parse disaster_type
    if type_line:
        result["disaster_type"] = validate_disaster_type(type_line)

    # Parse country line
    if not country_line:
        result["status"] = "malformed"
        return result

    up = country_line.upper()
    if up == "UNKNOWN":
        result["status"] = "unknown"
        return result

    if up.startswith("MULTIPLE:") or up.startswith("MULTIPLE "):
        # Parse comma-separated list
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

    # Single country
    c = validate_country(country_line)
    if c:
        result["countries"] = [c]
        result["status"] = "ok"
    else:
        result["status"] = "no_valid_country"
    return result


'''

    src = src.replace(marker, block + marker, 1)
    print("  applied: canonical registry + validators + parse_claude_response")
    return src, True


# ==========================================================================
# PATCH 2: Modify SYSTEM_PROMPT to require structured header
# ==========================================================================
def patch_system_prompt(src):
    print("")
    print("[2/5] Modifying SYSTEM_PROMPT for structured output...")

    if "REQUIRED OUTPUT FORMAT" in src:
        print("  SKIP: already applied")
        return src, False

    marker = "CRITICAL RULES:"
    if marker not in src:
        print("  SKIP: CRITICAL RULES marker not found")
        return src, False

    insertion = """REQUIRED OUTPUT FORMAT -- every response must begin with exactly this 3-line header:

COUNTRY: <primary country where the event physically occurred>
DISASTER_TYPE: <Earthquake|Flood|Storm|Wildfire|Volcano|Tsunami|Landslide|Drought|Heatwave|Other>
---

Then the article body follows on the next line.

COUNTRY field rules:
- Return the country where the event PHYSICALLY OCCURRED, not where the news outlet is based.
- Ignore outlet names in the source material (e.g. "Pakistan Today", "Japan Times", "BBC").
- Ignore subject demonyms unrelated to event location (e.g. "Vietnamese in Japan earthquake" -- the
  event is in Japan, not Vietnam).
- For events affecting multiple countries: COUNTRY: MULTIPLE: Country1, Country2
- For events in international waters, Antarctica, or uncountryable regions: COUNTRY: UNKNOWN
- Use common country names: "Japan", "United States", "United Kingdom", "Myanmar", "Congo".
- Do NOT include state/province names (write "India" not "Manipur"; "United States" not "California").
- Do NOT include continents or regions (write "UNKNOWN" for "Southeast Asia floods" without a
  specific country, UNLESS one country is clearly the primary location).

DISASTER_TYPE field rules:
- Return the PRIMARY event type, not secondary consequences.
- "Tsunami advisory lifted after Japan earthquake" -> DISASTER_TYPE: Earthquake (earthquake is
  the event; tsunami was a warning response).
- "Earthquake triggers tsunami" -> DISASTER_TYPE: Earthquake unless the tsunami itself caused
  the main damage reported.
- If truly unclassifiable, use DISASTER_TYPE: Other.

If you cannot identify a valid country with reasonable confidence from the source material, output
COUNTRY: UNKNOWN. Do not guess. Missing data is better than wrong data.

CRITICAL RULES:"""

    src = src.replace(marker, insertion, 1)
    print("  applied: structured output header requirements added to SYSTEM_PROMPT")
    return src, True


# ==========================================================================
# PATCH 3: Modify generate_article to return parsed result
# ==========================================================================
def patch_generate_article(src):
    print("")
    print("[3/5] Modifying generate_article() to return parsed structure...")

    marker = "    return message.content[0].text.strip()"
    if marker not in src:
        print("  SKIP: generate_article return line not found")
        return src, False

    if "parse_claude_response(raw_response" in src:
        print("  SKIP: already applied")
        return src, False

    replacement = """    raw_response = message.content[0].text.strip()
    parsed = parse_claude_response(raw_response)
    return raw_response, parsed"""

    src = src.replace(marker, replacement, 1)
    print("  applied: generate_article now returns (raw_response, parsed_dict)")
    return src, True


# ==========================================================================
# PATCH 4: Modify publish_to_wordpress to accept parsed structure
# ==========================================================================
def patch_publish_function(src):
    print("")
    print("[4/5] Modifying publish_to_wordpress() to use Claude's values...")

    if "# Use Claude-parsed country" in src:
        print("  SKIP: already applied")
        return src, False

    old_sig_and_head = '''def publish_to_wordpress(item, article_body):
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
        tag_ids.append(type_tag_id)'''

    new_sig_and_head = '''def publish_to_wordpress(item, article_body, parsed=None):
    endpoint = WP_URL + "/wp-json/wp/v2/posts"
    auth     = (WP_USER, WP_APP_PASSWORD)

    # Use Claude-parsed country and disaster type as authoritative values.
    # Fall back to item-level detected values ONLY for the audit log comparison.
    detected_country = item.get("country")
    detected_dtype   = item.get("disaster_type", "Other")

    if parsed is None:
        # Old code path (should not occur after this patch)
        log.warning("publish_to_wordpress called without parsed structure; skipping")
        return False

    status = parsed.get("status", "malformed")

    # Audit log: show Claude vs title-scan divergence for every article
    log.info(
        "CLAUDE_VS_DETECTED: claude_country=%s claude_type=%s detected_country=%s detected_type=%s status=%s raw=%r",
        ",".join(parsed.get("countries", [])) or "-",
        parsed.get("disaster_type", "Other"),
        detected_country or "-",
        detected_dtype,
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
            "Skipping (Claude country %r did not match registry): %s",
            parsed.get("raw_country_line", ""), item["title"][:60],
        )
        return False

    countries = parsed["countries"]
    dtype = parsed["disaster_type"]
    country = countries[0]  # primary country for logging

    tag_ids = []
    for c in countries:
        cid = get_or_create_tag(c, auth)
        if cid:
            tag_ids.append(cid)
    type_tag_id = get_or_create_tag(dtype, auth)
    if type_tag_id:
        tag_ids.append(type_tag_id)'''

    if old_sig_and_head not in src:
        print("  SKIP: publish_to_wordpress signature not in expected form")
        return src, False
    src = src.replace(old_sig_and_head, new_sig_and_head, 1)
    print("  applied: publish_to_wordpress now uses Claude's validated values")
    return src, True


# ==========================================================================
# PATCH 5: Update call site(s) of generate_article + publish_to_wordpress
# ==========================================================================
def patch_call_sites(src):
    print("")
    print("[5/5] Updating generate_article + publish_to_wordpress call sites...")

    # Try to detect if call sites already updated
    if "generate_article(item)\\n" not in src and "article_body = generate_article" not in src:
        # Best-effort check: look for old pattern
        pass

    # Common old pattern variants to update:
    old_patterns = [
        (
            "article_body = generate_article(item)\n        if not is_valid_article(article_body):",
            '''result = generate_article(item)
        if isinstance(result, tuple):
            raw_response, parsed = result
        else:
            raw_response, parsed = result, None
        article_body = parsed["body"] if (parsed and parsed.get("body")) else raw_response
        if not is_valid_article(article_body):''',
        ),
    ]

    applied_any = False
    for old, new in old_patterns:
        if old in src:
            src = src.replace(old, new, 1)
            applied_any = True
            print("  applied: updated generate_article call site")

    # Update publish_to_wordpress call to pass parsed
    pub_old = "publish_to_wordpress(item, article_body)"
    pub_new = "publish_to_wordpress(item, article_body, parsed=parsed)"
    if pub_old in src and pub_new not in src:
        src = src.replace(pub_old, pub_new)
        applied_any = True
        print("  applied: updated publish_to_wordpress call site")

    if not applied_any:
        print("  NOTE: no recognized call sites updated. Check manually:")
        print("         grep -n 'generate_article\\|publish_to_wordpress' " + TARGET)

    return src, applied_any


# ==========================================================================
# MAIN
# ==========================================================================
def main():
    print("=" * 64)
    print("  DISASTER PIPELINE: CLAUDE-STRUCTURED OUTPUT PATCH")
    print("=" * 64)

    backup()
    src = read()
    applied = []

    src, ok = patch_canonical_registry(src)
    if ok: applied.append("1: canonical country registry")

    src, ok = patch_system_prompt(src)
    if ok: applied.append("2: SYSTEM_PROMPT structured header")

    src, ok = patch_generate_article(src)
    if ok: applied.append("3: generate_article return tuple")

    src, ok = patch_publish_function(src)
    if ok: applied.append("4: publish_to_wordpress uses Claude values")

    src, ok = patch_call_sites(src)
    if ok: applied.append("5: call sites updated")

    if not verify_python(src):
        print("")
        print("SYNTAX BROKEN. Restoring backup.")
        shutil.copy2(BACKUP, TARGET)
        print("Restored from " + BACKUP)
        sys.exit(1)

    write(src)

    print("")
    print("=" * 64)
    print("  APPLIED:")
    if applied:
        for a in applied:
            print("    - " + a)
    else:
        print("    (nothing applied; file may already be patched)")
    print("=" * 64)
    print("")
    print("Next:")
    print("  cd /opt/disaster-pipeline && set -a && source .env && set +a \\\\")
    print("    && venv/bin/python run_disaster_pipeline.py")
    print("")
    print("Watch the log for CLAUDE_VS_DETECTED audit lines to spot")
    print("any country mismatches Claude is flagging.")
    print("")


if __name__ == "__main__":
    main()
