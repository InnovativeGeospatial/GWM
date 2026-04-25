#!/usr/bin/env python3
"""
fix_disaster_publish.py

Surgical fix for /opt/disaster-pipeline/run_disaster_pipeline.py.
The previous patch referenced undefined vars (`title`, `content`) so both
title sanitization and meta-div injection silently failed.

This script:
  1. Removes the broken `# --- GWM patch: title sanitize + meta div ---` block
  2. Replaces the payload construction to:
       - sanitize item["title"] before sending
       - prepend gwm-disaster-meta div to article_body
  3. AST-validates; restores backup on syntax error
"""
import ast
import shutil
import sys
import re
from pathlib import Path
from datetime import datetime

TARGET = Path("/opt/disaster-pipeline/run_disaster_pipeline.py")
BACKUP = Path(f"/opt/disaster-pipeline/run_disaster_pipeline.py.bak.{datetime.now():%Y%m%d_%H%M%S}")


def main():
    if not TARGET.exists():
        sys.exit(f"ERROR: {TARGET} not found")

    src = TARGET.read_text()
    shutil.copy2(TARGET, BACKUP)
    print(f"Backup: {BACKUP}")

    # --- 1. Remove the broken patch block ---
    # It starts with the sentinel and ends just before `endpoint = WP_URL ...`
    broken_block_pattern = re.compile(
        r"[ \t]*# --- GWM patch: title sanitize \+ meta div ---\n"
        r"(?:.*\n)*?"
        r"(?=[ \t]*endpoint = WP_URL)",
    )
    if broken_block_pattern.search(src):
        src = broken_block_pattern.sub("", src)
        print("Removed: broken patch block")
    else:
        print("Skip: broken patch block not found (already cleaned?)")

    # --- 2. Replace the payload block ---
    old_payload = '''    payload = {
        "title":      item["title"],
        "content":    article_body,
        "status":     "publish",
        "categories": [WP_CATEGORY_ID],
        "tags":       tag_ids,
    }'''

    new_payload = '''    # Sanitize title (decode HTML entities, replace en/em dashes with commas)
    clean_title = sanitize_title(item["title"])

    # Build hidden meta div for dashboard type/country detection
    meta_div = (
        '<div class="gwm-disaster-meta"'
        ' data-country="' + (countries[0] if countries else "") + '"'
        ' data-type="' + dtype + '"'
        ' style="display:none;"></div>\\n'
    )
    final_content = meta_div + article_body

    payload = {
        "title":      clean_title,
        "content":    final_content,
        "status":     "publish",
        "categories": [WP_CATEGORY_ID],
        "tags":       tag_ids,
    }'''

    if old_payload in src:
        src = src.replace(old_payload, new_payload, 1)
        print("Replaced: payload block (sanitized title + meta div)")
    elif "clean_title = sanitize_title(item" in src:
        print("Skip: payload already updated")
    else:
        shutil.copy2(BACKUP, TARGET)
        sys.exit("ERROR: could not find expected payload block; restored backup")

    # --- 3. AST validate ---
    try:
        ast.parse(src)
    except SyntaxError as e:
        shutil.copy2(BACKUP, TARGET)
        sys.exit(f"ERROR: AST validation failed: {e}\nRestored from backup.")

    TARGET.write_text(src)
    print(f"OK: wrote {TARGET}")
    print()
    print("Verify with:")
    print("  grep -n 'clean_title = sanitize_title' /opt/disaster-pipeline/run_disaster_pipeline.py")
    print("  grep -n 'GWM patch: title sanitize' /opt/disaster-pipeline/run_disaster_pipeline.py  # should be 0 hits")


if __name__ == "__main__":
    main()
