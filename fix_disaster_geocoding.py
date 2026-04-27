#!/usr/bin/env python3
"""
fix_disaster_geocoding.py

Adds Mapbox geocoding to the disaster pipeline:

1. SYSTEM_PROMPT gains a LOCATION field in the required header.
2. parse_claude_response captures location.
3. New geocode_mapbox(location, country_hint) helper uses Mapbox forward
   geocoding API. Sanity-checks the result country vs the country_hint.
4. publish_to_wordpress geocodes the parsed location and uses those coords
   in the meta div. Falls back to item-level lat/lng (USGS), then empty
   (dashboard centroid).

Reads MAPBOX_TOKEN from environment.

AST-validates; restores backup on syntax error.
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

    # --- 1. Add MAPBOX_TOKEN to the config block ---
    if "MAPBOX_TOKEN" not in src:
        old_cfg = 'WP_CATEGORY_ID  = int(os.environ.get("WP_CATEGORY_ID", 38))'
        new_cfg = (
            'WP_CATEGORY_ID  = int(os.environ.get("WP_CATEGORY_ID", 38))\n'
            'MAPBOX_TOKEN    = os.environ.get("MAPBOX_TOKEN", "")'
        )
        if old_cfg not in src:
            shutil.copy2(BACKUP, TARGET)
            sys.exit("ERROR: could not find WP_CATEGORY_ID config line")
        src = src.replace(old_cfg, new_cfg, 1)
        print("Added: MAPBOX_TOKEN config")
    else:
        print("Skip: MAPBOX_TOKEN already configured")

    # --- 2. Add geocode_mapbox helper before publish_to_wordpress ---
    geocode_helper = '''
# -- GEOCODING --
def geocode_mapbox(location, country_hint=None):
    """Forward-geocode a place name via Mapbox.

    Args:
        location: a place name string (e.g. "Petropavlovsk-Kamchatsky").
        country_hint: canonical country name from Claude (e.g. "Russia").
            If provided, the returned feature MUST be in this country, or
            the result is rejected.

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

        # Try each feature in relevance order; accept first whose country
        # context matches the hint. If no hint, accept the top result.
        hint_lower = (country_hint or "").strip().lower() if country_hint else None
        for feat in features:
            center = feat.get("center")
            if not center or len(center) < 2:
                continue
            lng, lat = float(center[0]), float(center[1])

            # Mapbox encodes country in place_type or context
            feat_country = ""
            if feat.get("place_type") == ["country"] or "country" in (feat.get("place_type") or []):
                feat_country = (feat.get("text") or "").lower()
            for ctx in (feat.get("context") or []):
                if isinstance(ctx, dict) and (ctx.get("id", "").startswith("country.")):
                    feat_country = (ctx.get("text") or "").lower()

            if hint_lower:
                # Accept country match OR partial overlap (e.g. "Russia" vs "Russian Federation")
                if feat_country and (
                    hint_lower == feat_country
                    or hint_lower in feat_country
                    or feat_country in hint_lower
                ):
                    return lat, lng
                # No country context at all -- skip rather than risk wrong placement
                continue
            else:
                return lat, lng

        log.info("Mapbox: no feature matched country hint %r for %r",
                 country_hint, location)
        return None, None

    except Exception as e:
        log.warning("Mapbox geocode error for %r: %s", location, e)
        return None, None
'''.lstrip("\n")

    if "def geocode_mapbox(" in src:
        print("Skip: geocode_mapbox already present")
    else:
        m = re.search(r"^def publish_to_wordpress\b", src, re.MULTILINE)
        # find the immediately preceding "# -- WORDPRESS PUBLISH --" comment if present
        # to insert helper before that section
        pub_section = re.search(r"^# -- WORDPRESS PUBLISH --", src, re.MULTILINE)
        anchor_pos = pub_section.start() if pub_section else m.start()
        src = src[:anchor_pos] + geocode_helper + "\n\n" + src[anchor_pos:]
        print("Added: geocode_mapbox()")

    # --- 3. Update SYSTEM_PROMPT to include LOCATION field ---
    old_header = '''COUNTRY: <primary country where the event physically occurred>
DISASTER_TYPE: <Earthquake|Flood|Storm|Wildfire|Volcano|Tsunami|Landslide|Drought|Heatwave|Other>
---'''

    new_header = '''COUNTRY: <primary country where the event physically occurred>
DISASTER_TYPE: <Earthquake|Flood|Storm|Wildfire|Volcano|Tsunami|Landslide|Drought|Heatwave|Other>
LOCATION: <most specific named place from the source: city, town, region, or "UNKNOWN" if no specific place is named>
---'''

    if old_header in src:
        src = src.replace(old_header, new_header, 1)
        print("Patched: SYSTEM_PROMPT header (added LOCATION)")
    elif "LOCATION:" in src:
        print("Skip: LOCATION already in SYSTEM_PROMPT")
    else:
        shutil.copy2(BACKUP, TARGET)
        sys.exit("ERROR: could not find expected SYSTEM_PROMPT header")

    # Add LOCATION rule guidance to the prompt body
    location_rules = '''LOCATION field rules:
- Return the most specific named place mentioned in the source material.
- Examples: "Petropavlovsk-Kamchatsky", "Kerala", "Mocoa, Putumayo", "Mount Etna".
- Do NOT include the country in the LOCATION value (the COUNTRY field captures that).
- For events spanning a wide region with no specific place, use the most specific
  region name (e.g. "Sichuan Province", "Eastern Java").
- If no specific place is named in the source, output LOCATION: UNKNOWN.

'''

    rules_anchor = "DISASTER_TYPE field rules:"
    if location_rules.split("\n")[0] in src:
        print("Skip: LOCATION field rules already present")
    elif rules_anchor in src:
        src = src.replace(rules_anchor, location_rules + rules_anchor, 1)
        print("Patched: SYSTEM_PROMPT (LOCATION field rules)")
    else:
        shutil.copy2(BACKUP, TARGET)
        sys.exit("ERROR: could not find DISASTER_TYPE field rules anchor")

    # --- 4. Update parse_claude_response to capture location ---
    # Add "location" to the result dict default
    old_result = '''    result = {
        "countries": [],
        "disaster_type": "Other",
        "body": "",
        "raw_country_line": "",
        "status": "malformed",
    }'''
    new_result = '''    result = {
        "countries": [],
        "disaster_type": "Other",
        "location": "",
        "body": "",
        "raw_country_line": "",
        "status": "malformed",
    }'''
    if old_result in src:
        src = src.replace(old_result, new_result, 1)
        print("Patched: parse_claude_response result dict")
    elif '"location": "",' in src:
        print("Skip: parse_claude_response already has location")
    else:
        shutil.copy2(BACKUP, TARGET)
        sys.exit("ERROR: could not find parse_claude_response result dict")

    # Extend the header scan loop to capture LOCATION:
    old_scan = '''    country_line = None
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
            body_start_idx = max(body_start_idx, i + 1)'''

    new_scan = '''    country_line = None
    type_line = None
    location_line = None
    body_start_idx = 0

    # Scan first ~8 lines for header fields
    for i, line in enumerate(lines[:10]):
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
        elif up.startswith("LOCATION:"):
            location_line = stripped[len("LOCATION:"):].strip()
            body_start_idx = max(body_start_idx, i + 1)
        elif stripped == "---":
            body_start_idx = max(body_start_idx, i + 1)'''

    if old_scan in src:
        src = src.replace(old_scan, new_scan, 1)
        print("Patched: parse_claude_response header scan")
    elif "location_line = None" in src:
        print("Skip: header scan already updated")
    else:
        shutil.copy2(BACKUP, TARGET)
        sys.exit("ERROR: could not find header scan block")

    # Store location in result before status checks
    old_type_parse = '''    # Parse disaster_type
    if type_line:
        result["disaster_type"] = validate_disaster_type(type_line)'''
    new_type_parse = '''    # Parse disaster_type
    if type_line:
        result["disaster_type"] = validate_disaster_type(type_line)

    # Parse location (may be UNKNOWN; geocoding handles that)
    if location_line and location_line.upper() != "UNKNOWN":
        result["location"] = location_line'''

    if old_type_parse in src and 'result["location"] = location_line' not in src:
        src = src.replace(old_type_parse, new_type_parse, 1)
        print("Patched: parse_claude_response (capture location)")
    else:
        print("Skip: location capture already present (or anchor missing)")

    # --- 5. Update meta_div in publish_to_wordpress to use geocoded coords ---
    old_meta = '''    # Build hidden meta div for dashboard type/country detection.
    # Pull lat/lng from the source item (RSS feeds like USGS/GDACS supply them).
    _ilat = item.get("lat")
    _ilng = item.get("lng")
    _lat_str = ("%.4f" % _ilat) if isinstance(_ilat, (int, float)) else ""
    _lng_str = ("%.4f" % _ilng) if isinstance(_ilng, (int, float)) else ""
    meta_div = (
        \'<div class="gwm-disaster-meta"\'
        \' data-country="\' + (countries[0] if countries else "") + \'"\'
        \' data-type="\' + dtype + \'"\'
        \' data-lat="\' + _lat_str + \'"\'
        \' data-lng="\' + _lng_str + \'"\'
        \' style="display:none;"></div>\\n\'
    )'''

    new_meta = '''    # Build hidden meta div for dashboard type/country detection.
    # Coordinate priority: (1) Claude location -> Mapbox geocode,
    # (2) RSS feed-supplied coords (USGS/GDACS), (3) empty -> dashboard centroid.
    _final_lat = None
    _final_lng = None

    _claude_loc = parsed.get("location") if isinstance(parsed, dict) else None
    _country_hint = countries[0] if countries else None
    if _claude_loc:
        _glat, _glng = geocode_mapbox(_claude_loc, _country_hint)
        if _glat is not None and _glng is not None:
            _final_lat = _glat
            _final_lng = _glng
            log.info("Geocoded %r in %r -> %.4f, %.4f",
                     _claude_loc, _country_hint, _glat, _glng)
        else:
            log.info("Geocode failed for %r in %r", _claude_loc, _country_hint)

    if _final_lat is None or _final_lng is None:
        _ilat = item.get("lat")
        _ilng = item.get("lng")
        if isinstance(_ilat, (int, float)) and isinstance(_ilng, (int, float)):
            _final_lat = _ilat
            _final_lng = _ilng

    _lat_str = ("%.4f" % _final_lat) if isinstance(_final_lat, (int, float)) else ""
    _lng_str = ("%.4f" % _final_lng) if isinstance(_final_lng, (int, float)) else ""
    meta_div = (
        \'<div class="gwm-disaster-meta"\'
        \' data-country="\' + (countries[0] if countries else "") + \'"\'
        \' data-type="\' + dtype + \'"\'
        \' data-lat="\' + _lat_str + \'"\'
        \' data-lng="\' + _lng_str + \'"\'
        \' style="display:none;"></div>\\n\'
    )'''

    if old_meta in src:
        src = src.replace(old_meta, new_meta, 1)
        print("Patched: meta_div (geocode-first)")
    elif "Coordinate priority:" in src:
        print("Skip: meta_div already updated for geocoding")
    else:
        shutil.copy2(BACKUP, TARGET)
        sys.exit("ERROR: could not find meta_div block from prior patch")

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
    print("  grep -n 'def geocode_mapbox' /opt/disaster-pipeline/run_disaster_pipeline.py")
    print("  grep -n 'LOCATION:' /opt/disaster-pipeline/run_disaster_pipeline.py")
    print("  grep -n 'Coordinate priority' /opt/disaster-pipeline/run_disaster_pipeline.py")


if __name__ == "__main__":
    main()
