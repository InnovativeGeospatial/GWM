#!/usr/bin/env python3
"""
prune_archive.py — Manual cleanup utility for Global Witness Monitor.

Purges specific events (by wp_id / id / hash) from GitHub-stored feeds.

Targets:
  archive  (PRIVATE repo)  archive/<feed>/<YYYY>-Q<n>.json   [default]
  active   (PUBLIC repo)   <feed>.json

NOTE: With writer v3 the active feed is the source of truth. Pruning the
archive alone will NOT remove an event from the live dashboard — for that
you must prune the 'active' target. Pruning 'archive' only affects private
history.

Usage:
  # Remove two events from the disaster archive (auto-scan all quarters)
  python prune_archive.py --feed disasters --ids 1234 1255

  # Remove from a specific quarter only (skips the scan)
  python prune_archive.py --feed disasters --quarter 2026-Q2 --ids 1234

  # Remove from the LIVE active feed (this is what hides it from the dashboard)
  python prune_archive.py --feed disasters --target active --ids 1234

  # Preview without writing
  python prune_archive.py --feed disasters --ids 1234 --dry-run

Env vars: same as gwm_json_writer.py
  GITHUB_TOKEN, GITHUB_OWNER, GITHUB_REPO, GITHUB_BRANCH,
  GITHUB_ARCHIVE_OWNER, GITHUB_ARCHIVE_REPO, GITHUB_ARCHIVE_BRANCH
"""

import os
import sys
import json
import base64
import argparse
import requests
from datetime import datetime, timezone


def _config(target):
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if not token:
        sys.exit("ERROR: GITHUB_TOKEN missing from environment.")
    if target == "active":
        owner = os.environ.get("GITHUB_OWNER", "InnovativeGeospatial").strip()
        repo = os.environ.get("GITHUB_REPO", "GWM").strip()
        branch = os.environ.get("GITHUB_BRANCH", "main").strip()
    else:
        archive_repo = os.environ.get("GITHUB_ARCHIVE_REPO", "").strip()
        if not archive_repo:
            sys.exit("ERROR: GITHUB_ARCHIVE_REPO not set; cannot target archive.")
        owner = os.environ.get(
            "GITHUB_ARCHIVE_OWNER",
            os.environ.get("GITHUB_OWNER", "InnovativeGeospatial"),
        ).strip()
        repo = archive_repo
        branch = os.environ.get("GITHUB_ARCHIVE_BRANCH", "main").strip()
    return token, owner, repo, branch


def _headers(token):
    return {
        "Authorization": "Bearer " + token,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _contents_url(owner, repo, path):
    return "https://api.github.com/repos/" + owner + "/" + repo + "/contents/" + path


def _event_key(e):
    return str(e.get("wp_id") or e.get("id") or e.get("hash") or "")


def _get(token, owner, repo, branch, path):
    """Returns (sha, parsed_dict_or_None)."""
    r = requests.get(_contents_url(owner, repo, path),
                     headers=_headers(token), params={"ref": branch}, timeout=20)
    if r.status_code == 404:
        return None, None
    if r.status_code != 200:
        sys.exit("ERROR: GET %s -> %s: %s" % (path, r.status_code, r.text[:200]))
    body = r.json()
    sha = body.get("sha")
    content = base64.b64decode(body.get("content", "")).decode("utf-8")
    return sha, json.loads(content)


def _put(token, owner, repo, branch, path, obj, sha, message):
    payload = {
        "message": message,
        "content": base64.b64encode(
            json.dumps(obj, ensure_ascii=False, indent=2).encode("utf-8")
        ).decode("ascii"),
        "branch": branch,
    }
    if sha:
        payload["sha"] = sha
    r = requests.put(_contents_url(owner, repo, path),
                     headers=_headers(token), json=payload, timeout=30)
    if r.status_code not in (200, 201):
        sys.exit("ERROR: PUT %s -> %s: %s" % (path, r.status_code, r.text[:300]))


def _list_quarter_files(token, owner, repo, branch, feed):
    """List archive/<feed>/*.json filenames in the repo."""
    dir_path = "archive/" + feed
    r = requests.get(_contents_url(owner, repo, dir_path),
                     headers=_headers(token), params={"ref": branch}, timeout=20)
    if r.status_code == 404:
        return []
    if r.status_code != 200:
        sys.exit("ERROR: listing %s -> %s: %s" % (dir_path, r.status_code, r.text[:200]))
    return [dir_path + "/" + item["name"]
            for item in r.json()
            if item.get("type") == "file" and item.get("name", "").endswith(".json")]


def _prune_file(token, owner, repo, branch, path, ids, dry_run):
    sha, data = _get(token, owner, repo, branch, path)
    if data is None:
        print("  skip (not found): %s" % path)
        return 0
    events = data.get("events", []) if isinstance(data, dict) else data
    kept = [e for e in events if _event_key(e) not in ids]
    removed = len(events) - len(kept)
    if removed == 0:
        print("  no match: %s" % path)
        return 0
    print("  removing %d from %s (%d -> %d)" % (removed, path, len(events), len(kept)))
    if dry_run:
        return removed
    if isinstance(data, dict):
        data["events"] = kept
        data["count"] = len(kept)
        data["updated"] = datetime.now(timezone.utc).isoformat()
        out = data
    else:
        out = kept
    _put(token, owner, repo, branch, path, out, sha,
         "Prune: remove %d event(s) from %s" % (removed, path))
    return removed


def main():
    ap = argparse.ArgumentParser(description="Prune events from GWM feeds.")
    ap.add_argument("--feed", required=True,
                    help="feed name, e.g. disasters / conflict / persecution")
    ap.add_argument("--ids", required=True, nargs="+",
                    help="one or more wp_id / id / hash values to remove")
    ap.add_argument("--target", choices=["archive", "active"], default="archive",
                    help="archive (private history) or active (live feed)")
    ap.add_argument("--quarter",
                    help="archive only: limit to one quarter, e.g. 2026-Q2")
    ap.add_argument("--dry-run", action="store_true",
                    help="report what would change without writing")
    args = ap.parse_args()

    ids = set(str(i) for i in args.ids)
    token, owner, repo, branch = _config(args.target)
    print("Target: %s -> %s/%s@%s" % (args.target, owner, repo, branch))
    print("Removing ids: %s" % ", ".join(sorted(ids)))

    total = 0
    if args.target == "active":
        total = _prune_file(token, owner, repo, branch,
                            args.feed + ".json", ids, args.dry_run)
    else:
        if args.quarter:
            paths = ["archive/" + args.feed + "/" + args.quarter + ".json"]
        else:
            paths = _list_quarter_files(token, owner, repo, branch, args.feed)
            if not paths:
                print("No archive files found for feed '%s'." % args.feed)
        for p in paths:
            total += _prune_file(token, owner, repo, branch, p, ids, args.dry_run)

    verb = "would remove" if args.dry_run else "removed"
    print("Done. %s %d event(s)." % (verb, total))


if __name__ == "__main__":
    main()
