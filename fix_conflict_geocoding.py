#!/usr/bin/env python3
"""
fix_conflict_geocoding.py

Bring the conflict pipeline up to parity with the disaster pipeline:

1. Add MAPBOX_TOKEN to config block.
2. Add geocode_mapbox() helper.
3. Add `import html` and `import re` if missing.
4. Add LOCATION and EVENT_TYPE fields to SYSTEM_PROMPT header.
5. Update parse_claude_response to capture both.
6. Add sanitize_title() helper.
7. Add a publish patch: sanitize title + inject <div class="gwm-conflict-meta">
   with country, type, lat, lng (geocoded).

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


GEOCODE_HELPER = '''
# -- GEOCODING --
def geocode_mapbox(location, country_hint=None):
    """Forward-geocode a place name via Mapbox.
    Returns (lat, lng) floats, or (None, None) on failure / mismatch.
    """
    if not location or not MAPBOX_TOKEN:
        return None, None
    try:
        url = (
            "https://api.mapbox.com/geocoding/v5/mapbox.places/"
            + requests.utils.quote(location.strip())
            + ".json"
        )
        params = {
            "access_token": MAPBOX_TOKEN,
            "limit": 5,
            "types": "place,locality,region,district,country,neighborhood,address",
        }
        r = requests.get(url, params=params, timeout=10)
        if r.status_code != 200:
            log.warning("Mapbox returned %s for %r", r.status_code, location)
            return None, None
        features = (r.json() or {}).get("features", [])
        if not features:
            return None, None
        hint_lower = (country_hint or "").strip().lower() if country_hint else None
        for feat in features:
            center = feat.get("center")
            if not center or len(center) < 2:
                continue
            lng, lat = float(center[0]), float(center[1])
            feat_country = ""
            if "country" in (feat.get("place_type") or []):
                feat_country = (feat.get("text") or "").lower()
            for ctx in (feat.get("context") or []):
                if isinstance(ctx, dict) and ctx.get("id", "").startswith("country."):
                    feat_country = (ctx.get("text") or "").lower()
            if hint_lower:
                if feat_country and (
                    hint_lower == feat_country
                    or hint_lower in feat_country
                    or feat_country in hint_lower
                ):
                    return lat, lng
                continue
            else:
                return lat, lng
        log.info("Mapbox: no feature matched country hint %r for %r",
                 country_hint, location)
        return None, None
    except Exception as e:
        log.warning("Mapbox geocode error for %r: %s", location, e)
        return None, None


def sanitize_title(title):
    """Decode HTML entities and replace en/em dashes with commas."""
    if not title:
        return title
    t = html.unescape(title)
    t = t.replace("\u2013", ", ").replace("\u2014", ", ")
    t = re.sub(r"\\s+", " ", t).strip()
    return t

'''.lstrip("\n")


PUBLISH_PATCH_BLOCK = '''    # --- GWM patch: title sanitize + meta div + geocoding ---
    try:
        item["title"] = sanitize_title(item["title"])
    except Exception:
        pass

    _final_lat = None
    _final_lng = None
    _claude_loc = parsed.get("location") if isinstance(parsed, dict) else None
    _country_hint = parsed.get("countries", [None])[0] if isinstance(parsed, dict) and parsed.get("countries") else None
    if _claude_loc:
        try:
            _glat, _glng = geocode_mapbox(_claude_loc, _country_hint)
            if _glat is not None and _glng is not None:
                _final_lat = _glat
                _final_lng = _glng
                log.info("Geocoded %r in %r -> %.4f, %.4f",
                         _claude_loc, _country_hint, _glat, _glng)
            else:
                log.info("Geocode failed for %r in %r", _claude_loc, _country_hint)
        except Exception as _ge:
            log.warning("Geocode exception: %s", _ge)

    _lat_str = ("%.4f" % _final_lat) if isinstance(_final_lat, (int, float)) else ""
    _lng_str = ("%.4f" % _final_lng) if isinstance(_final_lng, (int, float)) else ""
    _ctype = parsed.get("event_type", "Other") if isinstance(parsed, dict) else "Other"
    _country_for_meta = _country_hint or ""
    _meta_div = (
        \'<div class="gwm-conflict-meta"\'
        \' data-country="\' + str(_country_for_meta) + \'"\'
        \' data-type="\' + str(_ctype) + \'"\'
        \' data-lat="\' + _lat_str + \'"\'
        \' data-lng="\' + _lng_str + \'"\'
        \' style="display:none;"></div>\\n\'
    )
    if isinstance(article_body, str) and "gwm-conflict-meta" not in article_body:
        article_body = _meta_div + article_body

'''


def main():
    if not TARGET.exists():
        sys.exit(f"ERROR: {TARGET} not found")

    src = TARGET.read_text()
    shutil.copy2(TARGET, BACKUP)
    print(f"Backup: {BACKUP}")

    # --- 1. Ensure imports ---
    if not re.search(r"^import html\b", src, re.MULTILINE):
        # Insert after last top-level import in first 60 lines
        lines = src.splitlines(keepends=True)
        insert_at = 0
        for i, line in enumerate(lines[:60]):
            if re.match(r"^(import |from )", line):
                insert_at = i + 1
        lines.insert(insert_at, "import html\n")
        src = "".join(lines)
        print("Added: import html")
    if not re.search(r"^import re\b", src, re.MULTILINE):
        src = "import re\n" + src
        print("Added: import re")

    # --- 2. Add MAPBOX_TOKEN to config ---
    if "MAPBOX_TOKEN" not in src:
        old_cfg = "WP_CATEGORY_ID  = int(os.environ.get('WP_CATEGORY_ID', 8))"
        new_cfg = (
            "WP_CATEGORY_ID  = int(os.environ.get('WP_CATEGORY_ID', 8))\n"
            "MAPBOX_TOKEN    = os.environ.get('MAPBOX_TOKEN', '')"
        )
        if old_cfg not in src:
            shutil.copy2(BACKUP, TARGET)
            sys.exit("ERROR: could not find WP_CATEGORY_ID config line")
        src = src.replace(old_cfg, new_cfg, 1)
        print("Added: MAPBOX_TOKEN config")
    else:
        print("Skip: MAPBOX_TOKEN already configured")

    # --- 3. Add geocode_mapbox + sanitize_title helpers before publish_to_wordpress ---
    if "def geocode_mapbox(" in src:
        print("Skip: geocode_mapbox already present")
    else:
        # Anchor at the "# -- WORDPRESS PUBLISH --" comment if present, else publish_to_wordpress
        pub_section = re.search(r"^# -- WORDPRESS PUBLISH --", src, re.MULTILINE)
        m = re.search(r"^def publish_to_wordpress\b", src, re.MULTILINE)
        if not m:
            shutil.copy2(BACKUP, TARGET)
            sys.exit("ERROR: could not find publish_to_wordpress")
        anchor_pos = pub_section.start() if pub_section else m.start()
        src = src[:anchor_pos] + GEOCODE_HELPER + "\n\n" + src[anchor_pos:]
        print("Added: geocode_mapbox() and sanitize_title()")

    # --- 4. Update SYSTEM_PROMPT to include LOCATION and EVENT_TYPE fields ---
    # The conflict pipeline currently only has COUNTRY in its header.
    # We add EVENT_TYPE and LOCATION lines and a separator.
    old_header_marker = "COUNTRY: <primary country where the event physically occurred>"
    if old_header_marker not in src:
        shutil.copy2(BACKUP, TARGET)
        sys.exit("ERROR: could not find SYSTEM_PROMPT header line")

    if "EVENT_TYPE:" not in src:
        # Find the line and add EVENT_TYPE + LOCATION right after.
        # Look for whatever follows COUNTRY: ... and inject below.
        old_line = (
            "COUNTRY: <primary country where the event physically occurred>"
        )
        new_lines = (
            "COUNTRY: <primary country where the event physically occurred>\n"
            "EVENT_TYPE: <Armed Conflict|Civil Unrest|Coup or Crisis|Displacement|Other>\n"
            "LOCATION: <most specific named place from the source: city, town, region, or UNKNOWN if no specific place is named>"
        )
        src = src.replace(old_line, new_lines, 1)
        print("Patched: SYSTEM_PROMPT header (added EVENT_TYPE and LOCATION)")
    else:
        print("Skip: EVENT_TYPE already in SYSTEM_PROMPT")

    # --- 5. Update parse_claude_response result dict + scan loop ---
    old_result = '''    result = {
        "countries": [],
        "body": "",
        "raw_country_line": "",
        "status": "malformed",
    }'''
    new_result = '''    result = {
        "countries": [],
        "event_type": "Other",
        "location": "",
        "body": "",
        "raw_country_line": "",
        "status": "malformed",
    }'''
    if old_result in src:
        src = src.replace(old_result, new_result, 1)
        print("Patched: parse_claude_response result dict")
    elif '"event_type": "Other",' in src:
        print("Skip: result dict already updated")
    else:
        shutil.copy2(BACKUP, TARGET)
        sys.exit("ERROR: could not find parse_claude_response result dict")

    old_scan = '''    country_line = None
    body_start_idx = 0

    for i, line in enumerate(lines[:6]):
        stripped = line.strip()
        up = stripped.upper()
        if up.startswith("COUNTRY:"):
            country_line = stripped[len("COUNTRY:"):].strip()
            body_start_idx = max(body_start_idx, i + 1)
        elif stripped == "---":
            body_start_idx = max(body_start_idx, i + 1)'''

    new_scan = '''    country_line = None
    type_line = None
    location_line = None
    body_start_idx = 0

    for i, line in enumerate(lines[:10]):
        stripped = line.strip()
        up = stripped.upper()
        if up.startswith("COUNTRY:"):
            country_line = stripped[len("COUNTRY:"):].strip()
            body_start_idx = max(body_start_idx, i + 1)
        elif up.startswith("EVENT_TYPE:") or up.startswith("EVENT TYPE:"):
            if up.startswith("EVENT_TYPE:"):
                type_line = stripped[len("EVENT_TYPE:"):].strip()
            else:
                type_line = stripped[len("EVENT TYPE:"):].strip()
            body_start_idx = max(body_start_idx, i + 1)
        elif up.startswith("LOCATION:"):
            location_line = stripped[len("LOCATION:"):].strip()
            body_start_idx = max(body_start_idx, i + 1)
        elif stripped == "---":
            body_start_idx = max(body_start_idx, i + 1)'''

    if old_scan in src:
        src = src.replace(old_scan, new_scan, 1)
        print("Patched: parse_claude_response scan loop")
    elif "type_line = None" in src:
        print("Skip: scan loop already updated")
    else:
        shutil.copy2(BACKUP, TARGET)
        sys.exit("ERROR: could not find parse_claude_response scan loop")

    # Capture event_type and location values into result
    # Insert right after raw_country_line is set
    capture_old = '    result["raw_country_line"] = country_line or ""'
    capture_new = (
        '    result["raw_country_line"] = country_line or ""\n'
        '\n'
        '    # Capture event_type (default to Other)\n'
        '    if type_line:\n'
        '        _t_norm = type_line.strip().lower()\n'
        '        _valid = {\n'
        '            "armed conflict": "Armed Conflict",\n'
        '            "civil unrest": "Civil Unrest",\n'
        '            "coup or crisis": "Coup or Crisis",\n'
        '            "coup": "Coup or Crisis",\n'
        '            "crisis": "Coup or Crisis",\n'
        '            "displacement": "Displacement",\n'
        '            "other": "Other",\n'
        '        }\n'
        '        result["event_type"] = _valid.get(_t_norm, "Other")\n'
        '\n'
        '    if location_line and location_line.upper() != "UNKNOWN":\n'
        '        result["location"] = location_line\n'
    )
    if capture_old in src and 'result["event_type"] = _valid.get' not in src:
        src = src.replace(capture_old, capture_new, 1)
        print("Patched: parse_claude_response (capture event_type and location)")
    else:
        print("Skip: event_type/location capture already present (or anchor missing)")

    # --- 6. Inject patch block into publish_to_wordpress body ---
    # Find the def line and the first non-blank non-docstring line, insert before it.
    if "GWM patch: title sanitize + meta div + geocoding" in src:
        print("Skip: publish_to_wordpress patch block already present")
    else:
        m = re.search(
            r"(def publish_to_wordpress\([^)]*\):\s*\n)",
            src,
        )
        if not m:
            shutil.copy2(BACKUP, TARGET)
            sys.exit("ERROR: could not find publish_to_wordpress signature")
        # Insert immediately after the def line.
        insert_pos = m.end()
        src = src[:insert_pos] + PUBLISH_PATCH_BLOCK + src[insert_pos:]
        print("Patched: publish_to_wordpress (sanitize + meta div + geocode)")

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
    print("  grep -c 'def geocode_mapbox' /opt/conflict-pipeline/run_conflict_pipeline.py")
    print("  grep -c 'EVENT_TYPE:' /opt/conflict-pipeline/run_conflict_pipeline.py")
    print("  grep -c 'gwm-conflict-meta' /opt/conflict-pipeline/run_conflict_pipeline.py")
    print("  grep -c 'MAPBOX_TOKEN' /opt/conflict-pipeline/run_conflict_pipeline.py")


if __name__ == "__main__":
    main()
