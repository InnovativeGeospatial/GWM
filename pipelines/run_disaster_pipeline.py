#!/usr/bin/env python3
"""
patch_disaster_pipeline_polish.py

Two small fixes:
  1. Capitalize first letter of post titles after sanitize_title()
     ("flood alert in Kenya" -> "Flood alert in Kenya")
  2. Clean Mission Note formatting in article body:
     - Remove "**" wrappers around "Mission Note:"
     - Add HTML formatting matching conflict dashboard style
       (separate paragraph with bold label)

Backs up to run_disaster_pipeline.py.bak_polish before patching.
AST-validates output, restores backup on syntax error.
"""
import os
import re
import ast
import shutil
import sys

TARGET = "/opt/disaster-pipeline/run_disaster_pipeline.py"
BACKUP = TARGET + ".bak_polish"


def main():
    if not os.path.exists(TARGET):
        print("ERROR: " + TARGET + " not found.")
        sys.exit(1)

    shutil.copy2(TARGET, BACKUP)
    print("Backed up to: " + BACKUP)

    with open(TARGET, "r") as f:
        src = f.read()

    print("\n[1/2] Title capitalization in sanitize_title...")

    old_sanitize = '''def sanitize_title(title):
    """Decode HTML entities and replace en/em dashes with commas."""
    if not title:
        return title
    t = html.unescape(title)
    t = t.replace("\\u2013", ", ").replace("\\u2014", ", ")
    t = re.sub(r"\\s+", " ", t).strip()
    return t'''

    new_sanitize = '''def sanitize_title(title):
    """Decode HTML entities, replace en/em dashes with commas,
    and capitalize the first letter."""
    if not title:
        return title
    t = html.unescape(title)
    t = t.replace("\\u2013", ", ").replace("\\u2014", ", ")
    t = re.sub(r"\\s+", " ", t).strip()
    if t:
        t = t[0].upper() + t[1:]
    return t'''

    if old_sanitize not in src:
        print("  ERROR: sanitize_title body not in expected form")
        sys.exit(1)
    src = src.replace(old_sanitize, new_sanitize, 1)
    print("  applied: capitalize first letter")

    print("\n[2/2] Mission Note formatter...")

    # Insert format_mission_note helper above sanitize_title
    helper_fn = '''def format_mission_note(body):
    """Strip ** around 'Mission Note:' and wrap in HTML paragraph
    with bold label, matching conflict dashboard style."""
    if not body:
        return body
    # Pattern variants Claude might produce:
    #   **Mission Note:** ...
    #   **Mission Note**: ...
    #   Mission Note: ... (already plain)
    # We want all forms to render as a separate paragraph with a bold
    # "Mission Note:" prefix.
    pattern = re.compile(
        r"\\s*\\*{0,2}\\s*Mission Note\\s*\\*{0,2}\\s*:\\s*",
        re.IGNORECASE,
    )
    m = pattern.search(body)
    if not m:
        return body
    before = body[:m.start()].rstrip()
    after = body[m.end():].strip()
    if not after:
        return before
    formatted = (
        before
        + "\\n\\n<p><strong>Mission Note:</strong> "
        + after
        + "</p>"
    )
    return formatted


'''

    anchor = "def sanitize_title(title):"
    if anchor not in src:
        print("  ERROR: sanitize_title anchor not found")
        shutil.copy2(BACKUP, TARGET)
        sys.exit(1)
    src = src.replace(anchor, helper_fn + anchor, 1)
    print("  inserted: format_mission_note helper")

    # Wire it into publish_to_wordpress, just before final_content is built
    old_call_site = '''    # Sanitize title (decode HTML entities, replace en/em dashes with commas)
    clean_title = sanitize_title(item["title"])'''

    new_call_site = '''    # Sanitize title (decode HTML entities, replace en/em dashes with commas)
    clean_title = sanitize_title(item["title"])

    # Format Mission Note (strip ** wrappers, wrap in <p><strong>)
    article_body = format_mission_note(article_body)'''

    if old_call_site not in src:
        print("  ERROR: publish_to_wordpress call site not in expected form")
        shutil.copy2(BACKUP, TARGET)
        sys.exit(1)
    src = src.replace(old_call_site, new_call_site, 1)
    print("  applied: format_mission_note call in publish_to_wordpress")

    # Validate
    try:
        ast.parse(src)
    except SyntaxError as e:
        print("\nSYNTAX ERROR: " + str(e))
        shutil.copy2(BACKUP, TARGET)
        print("Restored backup.")
        sys.exit(1)

    with open(TARGET, "w") as f:
        f.write(src)

    print("\n" + "=" * 60)
    print("APPLIED:")
    print("  - 1: sanitize_title capitalizes first letter")
    print("  - 2: format_mission_note strips ** and wraps in <p><strong>")
    print("=" * 60)
    print("\nNext:")
    print("  cd /opt/disaster-pipeline && set -a && source .env && set +a \\")
    print("    && venv/bin/python run_disaster_pipeline.py")


if __name__ == "__main__":
    main()
