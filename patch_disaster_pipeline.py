#!/usr/bin/env python3
"""
patch_disaster_pipeline.py

Small patch to fix two issues in run_disaster_pipeline.py:
  1. Update deprecated model 'claude-sonnet-4-20250514' to current 'claude-sonnet-4-6'
  2. Slow down GDELT requests to avoid HTTP 429 rate limiting
     (5-second delay between queries instead of 1 second, and skip remaining
      queries after first 429 response)

Usage on the server:
    curl -sL <raw-gist-url> -o /tmp/patch_disaster_pipeline.py
    python3 /tmp/patch_disaster_pipeline.py
"""

import os
import shutil
import sys

TARGET = "/opt/disaster-pipeline/run_disaster_pipeline.py"
BACKUP = TARGET + ".bak"


def main():
    if not os.path.exists(TARGET):
        print("ERROR: " + TARGET + " does not exist. Run write_disaster_pipeline.py first.")
        sys.exit(1)

    # Backup
    shutil.copy2(TARGET, BACKUP)
    print("Backed up: " + BACKUP)

    with open(TARGET, "r") as f:
        src = f.read()

    # Patch 1: model name
    old_model = 'model="claude-sonnet-4-20250514"'
    new_model = 'model="claude-sonnet-4-6"'
    if old_model in src:
        src = src.replace(old_model, new_model)
        print("[1/2] Updated model: claude-sonnet-4-20250514 -> claude-sonnet-4-6")
    else:
        print("[1/2] SKIP: model line not found in expected form")

    # Patch 2: GDELT throttle + early exit on 429
    old_gdelt_block = '''            r = requests.get(url, timeout=15)
            if r.status_code != 200:
                log.warning("GDELT returned %s", r.status_code)
                continue'''
    new_gdelt_block = '''            r = requests.get(url, timeout=15)
            if r.status_code == 429:
                log.warning("GDELT rate limited (429). Stopping GDELT for this run.")
                break
            if r.status_code != 200:
                log.warning("GDELT returned %s", r.status_code)
                time.sleep(5)
                continue'''
    if old_gdelt_block in src:
        src = src.replace(old_gdelt_block, new_gdelt_block)
        print("[2a/2] Updated GDELT 429 handling (break on rate limit)")
    else:
        print("[2a/2] SKIP: GDELT block not found in expected form")

    # Patch 2b: increase inter-query delay from 1s to 5s
    old_delay = "            time.sleep(1)\n\n        except Exception as e:\n            log.warning(\"GDELT error: %s\", e)"
    new_delay = "            time.sleep(5)\n\n        except Exception as e:\n            log.warning(\"GDELT error: %s\", e)"
    if old_delay in src:
        src = src.replace(old_delay, new_delay)
        print("[2b/2] Updated GDELT inter-query delay: 1s -> 5s")
    else:
        print("[2b/2] SKIP: inter-query delay line not found in expected form")

    with open(TARGET, "w") as f:
        f.write(src)

    # Verify still valid Python
    import ast
    try:
        ast.parse(src)
        print("\nSUCCESS: file is still valid Python")
    except SyntaxError as e:
        print("\nERROR: patched file has syntax error: " + str(e))
        print("Restoring backup...")
        shutil.copy2(BACKUP, TARGET)
        print("Restored from " + BACKUP)
        sys.exit(1)

    print("\nNext: cd /opt/disaster-pipeline && set -a && source .env && set +a && venv/bin/python run_disaster_pipeline.py")


if __name__ == "__main__":
    main()
