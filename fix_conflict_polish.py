#!/usr/bin/env python3
"""
fix_conflict_polish.py

Three fixes for the conflict pipeline after the geocoding patch:

1. Add United States and Canada to the 'americas' REGIONS list so they
   actually populate ALL_COUNTRIES, fixing the "United States not in
   registry" rejection.

2. Tighten the LOCATION prompt rule: Claude must return the most specific
   place mentioned in the source (city, town, district, or named region).
   Only return UNKNOWN if literally no place is named.

3. Loosen geocode_mapbox country sanity check for known politically
   contested territories: Hebron, Gaza, West Bank can match either
   Israel OR Palestine without the result being rejected.

AST-validates; restores backup on syntax error.
"""
import ast
import shutil
import sys
import re
from pathlib import Path
from datetime import datetime

TARGET = Path("/opt/conflict-pipeline/run_conflict_pipeline.py")
BACKUP = Path(f"/opt/conflict-pipeline/run_conflict_pipeline.py.bak.{datetime.now():%Y%m%d_%H%M%S}")


def main():
    if not TARGET.exists():
        sys.exit(f"ERROR: {TARGET} not found")

    src = TARGET.read_text()
    shutil.copy2(TARGET, BACKUP)
    print(f"Backup: {BACKUP}")

    # --- 1. Add US + Canada to americas region ---
    old_americas = """    'americas': [
        'Bolivia', 'Brazil', 'Chile', 'Colombia', 'Cuba', 'Ecuador',
        'El Salvador', 'Guatemala', 'Guyana', 'Haiti', 'Honduras', 'Jamaica',
        'Mexico', 'Nicaragua', 'Panama', 'Paraguay', 'Peru', 'Trinidad',
        'Venezuela',
    ],"""

    new_americas = """    'americas': [
        'Argentina', 'Bolivia', 'Brazil', 'Canada', 'Chile', 'Colombia',
        'Costa Rica', 'Cuba', 'Dominican Republic', 'Ecuador',
        'El Salvador', 'Guatemala', 'Guyana', 'Haiti', 'Honduras', 'Jamaica',
        'Mexico', 'Nicaragua', 'Panama', 'Paraguay', 'Peru', 'Trinidad',
        'United States', 'Uruguay', 'Venezuela',
    ],"""

    if old_americas in src:
        src = src.replace(old_americas, new_americas, 1)
        print("Patched: 'americas' region (added US, Canada, Argentina, Costa Rica, Dominican Republic, Uruguay)")
    elif "'United States'," in src:
        print("Skip: americas region already includes United States")
    else:
        shutil.copy2(BACKUP, TARGET)
        sys.exit("ERROR: could not find 'americas' region block")

    # --- 2. Tighten LOCATION prompt rule ---
    # Find the existing LOCATION rule (added by previous patch) and replace.
    # Look for the block we inserted earlier.
    old_location_intro = "LOCATION: <most specific named place from the source: city, town, region, or UNKNOWN if no specific place is named>"
    new_location_intro = "LOCATION: <most specific named place from the source -- city, town, district, or named region. Use UNKNOWN ONLY if no place is named anywhere in the source>"

    if old_location_intro in src:
        src = src.replace(old_location_intro, new_location_intro, 1)
        print("Patched: LOCATION header text (stricter wording)")
    elif new_location_intro in src:
        print("Skip: LOCATION header already updated")
    else:
        print("Skip: LOCATION header anchor not found (continuing)")

    # Inject explicit LOCATION field rules block before the COUNTRY field rules.
    # The original conflict pipeline doesn't have a "DISASTER_TYPE field rules"
    # anchor -- so target "COUNTRY field rules:" or "COUNTRY field" if present;
    # if no such anchor exists, append the LOCATION rules right after the
    # existing "COUNTRY:" header lines (after the --- separator).

    location_rules = (
        "LOCATION field rules:\n"
        "- Return the most specific named place mentioned ANYWHERE in the source material.\n"
        "- Examples: \"Hebron\", \"Cauca\", \"Gaziantep\", \"Mocoa, Putumayo\", \"Aleppo\", \"northern Mali\".\n"
        "- Do NOT include the country in the LOCATION value (the COUNTRY field captures that).\n"
        "- Prefer the smallest geographic unit named (city > district > province > region).\n"
        "- For events spanning a wide region with no named place, use the most specific\n"
        "  region name available (e.g. \"Sahel\", \"Eastern Ukraine\", \"Donbas\").\n"
        "- Output LOCATION: UNKNOWN ONLY when truly no place name appears in the source.\n"
        "  If the source mentions any town, city, province, or named region, return it.\n"
        "\n"
    )

    if "LOCATION field rules:" in src:
        print("Skip: LOCATION field rules block already present")
    else:
        # Try to insert before "COUNTRY field rules:" if present, else before "CRITICAL RULES:"
        anchor_country_rules = re.search(r"^COUNTRY field rules:", src, re.MULTILINE)
        anchor_critical = re.search(r"^CRITICAL RULES:", src, re.MULTILINE)
        anchor = anchor_country_rules or anchor_critical
        if anchor:
            src = src[:anchor.start()] + location_rules + src[anchor.start():]
            print("Patched: SYSTEM_PROMPT (LOCATION field rules block)")
        else:
            print("Skip: no anchor found for LOCATION rules block")

    # --- 3. Loosen Mapbox country sanity for Israel/Palestine ---
    # Add a small territory-equivalence map and consult it before rejecting.
    old_check = '''            if hint_lower:
                if feat_country and (
                    hint_lower == feat_country
                    or hint_lower in feat_country
                    or feat_country in hint_lower
                ):
                    return lat, lng
                continue
            else:
                return lat, lng'''

    new_check = '''            if hint_lower:
                # Disputed/contested territory equivalences. If the hint and
                # Mapbox's country tag both map to the same disputed cluster,
                # accept the result.
                _disputed = {
                    "israel": "il_ps",
                    "palestine": "il_ps",
                    "palestinian territories": "il_ps",
                    "west bank": "il_ps",
                    "gaza": "il_ps",
                }
                hint_disputed = _disputed.get(hint_lower)
                feat_disputed = _disputed.get(feat_country) if feat_country else None
                if feat_country and (
                    hint_lower == feat_country
                    or hint_lower in feat_country
                    or feat_country in hint_lower
                    or (hint_disputed and hint_disputed == feat_disputed)
                ):
                    return lat, lng
                continue
            else:
                return lat, lng'''

    if old_check in src:
        src = src.replace(old_check, new_check, 1)
        print("Patched: geocode_mapbox (Israel/Palestine territory equivalence)")
    elif "_disputed = {" in src:
        print("Skip: territory equivalence already added")
    else:
        print("Skip: geocode_mapbox sanity check not found (geocoding patch may differ)")

    # --- AST validate ---
    try:
        ast.parse(src)
    except SyntaxError as e:
        shutil.copy2(BACKUP, TARGET)
        sys.exit(f"ERROR: AST validation failed: {e}\nRestored from backup.")

    TARGET.write_text(src)
    print(f"OK: wrote {TARGET}")
    print()
    print("Verify:")
    print("  grep -c \"'United States',\" /opt/conflict-pipeline/run_conflict_pipeline.py")
    print("  grep -c 'LOCATION field rules' /opt/conflict-pipeline/run_conflict_pipeline.py")
    print("  grep -c '_disputed' /opt/conflict-pipeline/run_conflict_pipeline.py")


if __name__ == "__main__":
    main()
