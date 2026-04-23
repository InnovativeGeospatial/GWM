#!/usr/bin/env python3
"""
PERSECUTION PIPELINE: Claude-structured-output patch.

Makes Claude the source of truth for country attribution.
Claude returns a 2-line header (COUNTRY, ---) parsed before the article body.
Validates against canonical country registry built from COUNTRY_CENTROIDS keys.

Changes:
  1. Update model claude-sonnet-4-5 -> claude-sonnet-4-6
  2. Add country aliases + validate_country() + parse_claude_response()
  3. Rewrite generate_article() to request structured header + return (raw, parsed)
  4. Rewrite run() main loop to use parsed country (override detect_country)
  5. Skip if Claude returns UNKNOWN or invalid country
  6. Add CLAUDE_VS_DETECTED audit print on every article

Backs up original to run_pipeline.py.bak_structured before patching.
"""
import re
import ast
import shutil
import sys
from pathlib import Path

TARGET = Path("/opt/global-witness/run_pipeline.py")
BACKUP = Path("/opt/global-witness/run_pipeline.py.bak_structured")

if not TARGET.exists():
    print(f"ERROR: {TARGET} not found")
    sys.exit(1)

src = TARGET.read_text()
shutil.copy(TARGET, BACKUP)
print(f"Backed up to: {BACKUP}\n")

print("=" * 60)
print(" PERSECUTION PIPELINE: STRUCTURED-OUTPUT PATCH")
print("=" * 60)

# ---------------------------------------------------------------
# [1/5] Update model
# ---------------------------------------------------------------
print("\n[1/5] Update model...")
if 'model="claude-sonnet-4-5"' not in src:
    print("  ERROR: model string not found")
    sys.exit(1)
src = src.replace('model="claude-sonnet-4-5"', 'model="claude-sonnet-4-6"')
print("  claude-sonnet-4-5 -> claude-sonnet-4-6")

# ---------------------------------------------------------------
# [2/5] Insert canonical registry + parse_claude_response
#       Place right after COUNTRY_CENTROIDS dict ends.
# ---------------------------------------------------------------
print("\n[2/5] Canonical registry + parse_claude_response...")

REGISTRY_BLOCK = '''
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

    lines = text.split("\\n", 3)
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
    body = lines[2] if len(lines) == 3 else (lines[2] + "\\n" + lines[3])
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

'''

# Find end of COUNTRY_CENTROIDS dict
m = re.search(r"COUNTRY_CENTROIDS\s*=\s*\{", src)
if not m:
    print("  ERROR: COUNTRY_CENTROIDS not found")
    sys.exit(1)

# Walk braces to find the matching close
start = m.end() - 1
depth = 0
end = None
for i in range(start, len(src)):
    ch = src[i]
    if ch == "{":
        depth += 1
    elif ch == "}":
        depth -= 1
        if depth == 0:
            end = i + 1
            break
if end is None:
    print("  ERROR: COUNTRY_CENTROIDS close brace not found")
    sys.exit(1)

# Insert after the closing brace + newline
insert_at = end
# advance past newline if present
while insert_at < len(src) and src[insert_at] == "\n":
    insert_at += 1

src = src[:insert_at] + REGISTRY_BLOCK + src[insert_at:]
print("  inserted registry + validate_country + parse_claude_response")

# ---------------------------------------------------------------
# [3/5] Rewrite generate_article to request structured header
#       and return (raw, parsed) tuple
# ---------------------------------------------------------------
print("\n[3/5] Rewrite generate_article...")

# Match the entire generate_article function
ga_pattern = re.compile(
    r"def generate_article\(article\):\n"
    r"(?:    .*\n)+?"
    r"    return response\.content\[0\]\.text\n",
    re.MULTILINE,
)

new_ga = '''def generate_article(article):
    prompt = (
        "You are a journalist for Global Witness Monitor, a Christian persecution intelligence platform.\\n\\n"
        "STRUCTURED OUTPUT REQUIRED. Your response must begin with exactly these two header lines:\\n"
        "COUNTRY: <country_name | MULTIPLE: country1, country2 | UNKNOWN>\\n"
        "---\\n"
        "Then the article body.\\n\\n"
        "COUNTRY rules:\\n"
        "- Use the country where the persecution event occurred, not the country of the outlet.\\n"
        "- If multiple countries are substantively involved (e.g. cross-border refugees, diaspora incident with country of origin), use MULTIPLE: c1, c2.\\n"
        "- Use UNKNOWN only if no country can be reasonably determined.\\n"
        "- Use common country names: united states, united kingdom, dr congo, north korea, south korea, etc.\\n\\n"
        "Write a factual 100-250 word news report based ONLY on the source material below.\\n\\n"
        "STRICT RULES:\\n"
        "- Only include facts present in the source material\\n"
        "- Never invent names, statistics, dates, or locations\\n"
        "- Never fabricate quotes\\n"
        "- Replace individual names with: man, woman, pastor, bishop, girl, boy, family, group, convert, believer\\n"
        "- Mention the source naturally in the text\\n"
        "- No source list at the end\\n"
        "- No headers or sections\\n"
        "- Never repeat the same point twice\\n"
        "- End with one short prayer prompt sentence\\n"
        "- 100-250 words maximum\\n\\n"
        "After the article write on a new line: HEADLINE: [short descriptive headline, no personal names]\\n\\n"
        "SOURCE: " + article["source"] + "\\n"
        "TITLE: " + article["title"] + "\\n"
        "CONTENT: " + article["content"] + "\\n\\nWrite now:"
    )
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=900,
        messages=[{"role": "user", "content": prompt}]
    )
    raw = response.content[0].text
    parsed = parse_claude_response(raw)
    return raw, parsed
'''

m = ga_pattern.search(src)
if not m:
    print("  ERROR: generate_article not found in expected form")
    sys.exit(1)

src = src[:m.start()] + new_ga + src[m.end():]
print("  generate_article now returns (raw, parsed)")

# ---------------------------------------------------------------
# [4/5] Rewrite run() main loop to use parsed output
# ---------------------------------------------------------------
print("\n[4/5] Rewrite run() main loop...")

# We need to replace the try block inside run() that processes each article.
# Match from "print(\"Processing: \" ..." through "print(\"Error: \" + str(e))"
loop_pattern = re.compile(
    r"        try:\n"
    r"            print\(\"Processing: \" \+ article\[\"title\"\]\[:60\]\)\n"
    r"            generated = generate_article\(article\)\n"
    r"(?:            .*\n)+?"
    r"        except Exception as e:\n"
    r"            print\(\"Error: \" \+ str\(e\)\)\n",
    re.MULTILINE,
)

new_loop = '''        try:
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
'''

m = loop_pattern.search(src)
if not m:
    print("  ERROR: run() main loop not found in expected form")
    sys.exit(1)

src = src[:m.start()] + new_loop + src[m.end():]
print("  main loop now uses Claude's country as source of truth")

# ---------------------------------------------------------------
# [5/5] Validate final output
# ---------------------------------------------------------------
print("\n[5/5] Validating syntax...")
try:
    ast.parse(src)
    print("  AST parse: ok")
except SyntaxError as e:
    print(f"  ERROR: syntax error: {e}")
    print(f"  Line {e.lineno}: {e.text}")
    shutil.copy(BACKUP, TARGET)
    print("  Restored backup.")
    sys.exit(1)

TARGET.write_text(src)

print("\n" + "=" * 60)
print("APPLIED:")
print("  - 1: model claude-sonnet-4-5 -> claude-sonnet-4-6")
print("  - 2: canonical registry + parse_claude_response")
print("  - 3: generate_article returns (raw, parsed)")
print("  - 4: run() loop uses Claude as country source of truth")
print("  - 5: AST validated")
print("=" * 60)
print("\nNext:")
print("  cd /opt/global-witness && set -a && source .env && set +a \\")
print("    && python3 run_pipeline.py")
print("\nNOTE: write_pipeline.py still regenerates run_pipeline.py.")
print("      Re-run write_pipeline.py will OVERWRITE this patch.")
print("      Apply same changes to write_pipeline.py before next regeneration.")
