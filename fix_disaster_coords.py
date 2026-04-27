#!/usr/bin/env python3
"""
fix_disaster_coords.py

Disaster pipeline currently emits empty data-lat/data-lng. Result: dashboard
falls back to country centroid (e.g., Alaska earthquake plotted in DC because
US centroid is Washington).

Fix:
  1. Add extract_coords(entry) helper that reads georss/where/geo_lat,geo_long.
  2. Capture lat/lng on each candidate in fetch_rss_feeds.
  3. Use item-level lat/lng in the meta div instead of parsed (which never
     had them — that was a bug from earlier).

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

# --- helper to insert if missing ---
EXTRACT_COORDS_FN = '''
def extract_coords(entry):
    """Return (lat, lng) floats from a feedparser entry, or (None, None).

    Supports:
      - GeoRSS Simple: entry.where = {"type":"Point","coordinates":(lon,lat)} (USGS)
      - GeoRSS W3C: entry.geo_lat / entry.geo_long
      - GeoRSS plain: entry.georss_point = "lat lon"
    """
    try:
        where = entry.get("where") if hasattr(entry, "get") else None
        if isinstance(where, dict):
            coords = where.get("coordinates")
            if coords and len(coords) >= 2:
                lon, lat = float(coords[0]), float(coords[1])
                return lat, lon
    except Exception:
        pass
    try:
        lat = entry.get("geo_lat") if hasattr(entry, "get") else None
        lng = entry.get("geo_long") if hasattr(entry, "get") else None
        if lat and lng:
            return float(lat), float(lng)
    except Exception:
        pass
    try:
        pt = entry.get("georss_point") if hasattr(entry, "get") else None
        if pt and isinstance(pt, str):
            parts = pt.strip().split()
            if len(parts) >= 2:
                return float(parts[0]), float(parts[1])
    except Exception:
        pass
    return None, None
'''.lstrip("\n")


def main():
    if not TARGET.exists():
        sys.exit(f"ERROR: {TARGET} not found")

    src = TARGET.read_text()
    shutil.copy2(TARGET, BACKUP)
    print(f"Backup: {BACKUP}")

    # --- 1. Insert extract_coords helper before fetch_rss_feeds ---
    if "def extract_coords(" in src:
        print("Skip: extract_coords already present")
    else:
        m = re.search(r"^def fetch_rss_feeds\b", src, re.MULTILINE)
        if not m:
            shutil.copy2(BACKUP, TARGET)
            sys.exit("ERROR: could not find fetch_rss_feeds")
        src = src[:m.start()] + EXTRACT_COORDS_FN + "\n\n" + src[m.start():]
        print("Added: extract_coords()")

    # --- 2. Add lat/lng capture in fetch_rss_feeds ---
    # Find the candidates.append({...}) block that has "disaster_type": dtype,
    # in fetch_rss_feeds and add lat/lng entries.
    rss_old = '''                candidates.append({
                    "title":        title,
                    "summary":      summary,
                    "url":          url,
                    "hash":         h,
                    "source":       feed.feed.get("title", feed_url),
                    "published":    entry.get("published", ""),
                    "country":      country,
                    "disaster_type": dtype,
                })'''

    rss_new = '''                lat, lng = extract_coords(entry)
                candidates.append({
                    "title":        title,
                    "summary":      summary,
                    "url":          url,
                    "hash":         h,
                    "source":       feed.feed.get("title", feed_url),
                    "published":    entry.get("published", ""),
                    "country":      country,
                    "disaster_type": dtype,
                    "lat":          lat,
                    "lng":          lng,
                })'''

    if rss_old in src:
        src = src.replace(rss_old, rss_new, 1)
        print("Patched: fetch_rss_feeds (lat/lng capture)")
    elif '"lat":          lat' in src:
        print("Skip: fetch_rss_feeds already updated")
    else:
        shutil.copy2(BACKUP, TARGET)
        sys.exit("ERROR: could not find expected RSS candidates.append block")

    # --- 3. Add empty lat/lng to GDELT candidates (consistency, no real coords) ---
    gdelt_old = '''                candidates.append({
                    "title":         title,
                    "summary":       title,
                    "url":           url_art,
                    "hash":          h,
                    "source":        source,
                    "published":     article.get("seendate", ""),
                    "country":       country,
                    "disaster_type": dtype,
                })'''

    gdelt_new = '''                candidates.append({
                    "title":         title,
                    "summary":       title,
                    "url":           url_art,
                    "hash":          h,
                    "source":        source,
                    "published":     article.get("seendate", ""),
                    "country":       country,
                    "disaster_type": dtype,
                    "lat":           None,
                    "lng":           None,
                })'''

    if gdelt_old in src:
        src = src.replace(gdelt_old, gdelt_new, 1)
        print("Patched: fetch_gdelt (lat/lng = None)")
    elif '"lat":           None' in src or '"lat":          lat' in src:
        # Either already patched or different formatting; not fatal
        print("Skip: fetch_gdelt already updated (or formatting differs; non-fatal)")

    # --- 4. Update meta div to use item-level lat/lng ---
    meta_old = '''    # Build hidden meta div for dashboard type/country detection
    meta_div = (
        \'<div class="gwm-disaster-meta"\'
        \' data-country="\' + (countries[0] if countries else "") + \'"\'
        \' data-type="\' + dtype + \'"\'
        \' style="display:none;"></div>\\n\'
    )'''

    meta_new = '''    # Build hidden meta div for dashboard type/country detection.
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

    if meta_old in src:
        src = src.replace(meta_old, meta_new, 1)
        print("Patched: meta_div (uses item lat/lng)")
    elif "_lat_str = " in src:
        print("Skip: meta_div already updated")
    else:
        shutil.copy2(BACKUP, TARGET)
        sys.exit("ERROR: could not find expected meta_div block")

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
    print("  grep -n 'def extract_coords' /opt/disaster-pipeline/run_disaster_pipeline.py")
    print("  grep -n '_lat_str' /opt/disaster-pipeline/run_disaster_pipeline.py")


if __name__ == "__main__":
    main()
