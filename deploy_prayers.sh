#!/usr/bin/env bash
# deploy_prayers.sh — pull the prayer-update files from the GWM repo onto the
# droplet, into their correct directories. Each file is downloaded to /tmp and
# syntax-checked BEFORE it replaces the live file, so a bad URL or corrupt
# download can never break a working pipeline.
#
# Run on the droplet:
#   curl -fsSL https://raw.githubusercontent.com/InnovativeGeospatial/GWM/main/deploy_prayers.sh -o /tmp/deploy_prayers.sh && bash /tmp/deploy_prayers.sh

RAW="https://raw.githubusercontent.com/InnovativeGeospatial/GWM/main"

OK_LIST=""
BAD_LIST=""

deploy() {
  url="$1"; dir="$2"; name="$3"; allow_new="${4:-no}"
  dest="$dir/$name"
  echo "── $name  →  $dir"

  if [ ! -d "$dir" ]; then
    echo "   SKIP: directory $dir not found"
    BAD_LIST="$BAD_LIST $name(dir-missing)"
    return
  fi
  if [ ! -f "$dest" ] && [ "$allow_new" != "new" ]; then
    echo "   SKIP: $dest does not exist — filename/path likely wrong; not creating a stray file"
    BAD_LIST="$BAD_LIST $name(no-existing-file)"
    return
  fi

  tmp="/tmp/$name.new"
  if ! curl -fsSL "$url" -o "$tmp"; then
    echo "   FAILED: download error (check the URL/path) — live file untouched"
    BAD_LIST="$BAD_LIST $name(download)"
    return
  fi
  if ! python3 -m py_compile "$tmp"; then
    echo "   FAILED: syntax error in downloaded file — live file untouched"
    BAD_LIST="$BAD_LIST $name(syntax)"
    return
  fi
  cp "$tmp" "$dest" && echo "   OK" && OK_LIST="$OK_LIST $name"
}

echo "=== GWM prayer-update deploy ==="

# Going-forward fixes (the 4 files you edited in the repo):
deploy "$RAW/pipelines/run_conflict_pipeline.py"    /opt/conflict-pipeline  run_conflict_pipeline.py
deploy "$RAW/pipelines/run_persecution_pipeline.py" /opt/global-witness     run_persecution_pipeline.py
deploy "$RAW/pipelines/run_disaster_pipeline.py"    /opt/disaster-pipeline  run_disaster_pipeline.py
deploy "$RAW/generate_prayer_summary.py"            /opt/conflict-pipeline  generate_prayer_summary.py

# New one-time backfill tool (allowed to create, since it's new):
deploy "$RAW/backfill_prayers.py"                   /opt/conflict-pipeline  backfill_prayers.py  new

echo ""
echo "=== SUMMARY ==="
echo "OK:    ${OK_LIST:- (none)}"
echo "ISSUES:${BAD_LIST:- (none)}"
echo "==============="
echo "Any ISSUES above mean that file's repo path or droplet filename differs"
echo "from what this script assumed. Nothing was overwritten for those."
