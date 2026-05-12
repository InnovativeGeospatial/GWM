#!/usr/bin/env python3
"""
migrate_archives_to_private.py — one-off migration

Moves every file under archive/* from the PUBLIC repo to the PRIVATE repo,
then deletes them from the public repo.

Run ONCE after creating the private repo and updating .env with
GITHUB_ARCHIVE_REPO etc. Then delete this script.

Usage:
  cd /opt/<any-pipeline-dir>     # disaster-pipeline, conflict-pipeline, or global-witness
  set -a && source .env && set +a
  venv/bin/python migrate_archives_to_private.py

Dry-run (just lists what would happen) by default. Add --execute to actually run.
"""

import os
import sys
import json
import base64
import argparse
import requests

TOKEN = os.environ.get("GITHUB_TOKEN", "").strip()
PUB_OWNER = os.environ.get("GITHUB_OWNER", "InnovativeGeospatial").strip()
PUB_REPO = os.environ.get("GITHUB_REPO", "GWM").strip()
PUB_BRANCH = os.environ.get("GITHUB_BRANCH", "main").strip()
ARC_OWNER = os.environ.get(
    "GITHUB_ARCHIVE_OWNER",
    os.environ.get("GITHUB_OWNER", "InnovativeGeospatial"),
).strip()
ARC_REPO = os.environ.get("GITHUB_ARCHIVE_REPO", "").strip()
ARC_BRANCH = os.environ.get("GITHUB_ARCHIVE_BRANCH", "main").strip()

if not TOKEN:
    sys.exit("ERROR: GITHUB_TOKEN missing")
if not ARC_REPO:
    sys.exit("ERROR: GITHUB_ARCHIVE_REPO missing from .env")


def headers():
    return {
        "Authorization": "Bearer " + TOKEN,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def gh_get_tree(owner, repo, branch):
    """Get full file tree of a repo."""
    url = ("https://api.github.com/repos/" + owner + "/" + repo +
           "/git/trees/" + branch + "?recursive=1")
    r = requests.get(url, headers=headers(), timeout=30)
    if r.status_code != 200:
        return None
    return r.json().get("tree", [])


def gh_get_file(owner, repo, path, branch):
    """Get a file's content + sha."""
    url = ("https://api.github.com/repos/" + owner + "/" + repo +
           "/contents/" + path + "?ref=" + branch)
    r = requests.get(url, headers=headers(), timeout=20)
    if r.status_code != 200:
        return None, None
    body = r.json()
    content_b64 = body.get("content", "")
    return base64.b64decode(content_b64).decode("utf-8"), body.get("sha")


def gh_put_file(owner, repo, path, content_str, branch, message):
    """Create or update a file. Returns (ok, sha)."""
    url = ("https://api.github.com/repos/" + owner + "/" + repo +
           "/contents/" + path)
    # Check if file already exists
    existing_sha = None
    r = requests.get(url + "?ref=" + branch, headers=headers(), timeout=20)
    if r.status_code == 200:
        existing_sha = r.json().get("sha")
    payload = {
        "message": message,
        "content": base64.b64encode(content_str.encode("utf-8")).decode("ascii"),
        "branch": branch,
    }
    if existing_sha:
        payload["sha"] = existing_sha
    r = requests.put(url, headers=headers(), json=payload, timeout=30)
    if r.status_code in (200, 201):
        return True, r.json().get("content", {}).get("sha")
    print("  PUT failed (" + str(r.status_code) + "): " + r.text[:200])
    return False, None


def gh_delete_file(owner, repo, path, branch, message):
    """Delete a file. Returns ok."""
    url = ("https://api.github.com/repos/" + owner + "/" + repo +
           "/contents/" + path)
    # Need current sha to delete
    r = requests.get(url + "?ref=" + branch, headers=headers(), timeout=20)
    if r.status_code != 200:
        return False
    sha = r.json().get("sha")
    payload = {"message": message, "sha": sha, "branch": branch}
    r = requests.delete(url, headers=headers(), json=payload, timeout=30)
    return r.status_code in (200, 204)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true",
                        help="Actually run. Without this flag, dry-run only.")
    args = parser.parse_args()

    print("Source     : " + PUB_OWNER + "/" + PUB_REPO + "@" + PUB_BRANCH)
    print("Destination: " + ARC_OWNER + "/" + ARC_REPO + "@" + ARC_BRANCH)
    print("Mode       : " + ("EXECUTE" if args.execute else "DRY-RUN"))
    print()

    tree = gh_get_tree(PUB_OWNER, PUB_REPO, PUB_BRANCH)
    if tree is None:
        sys.exit("ERROR: failed to fetch public repo tree")

    archive_files = [
        item for item in tree
        if item.get("type") == "blob" and item.get("path", "").startswith("archive/")
    ]
    print("Found " + str(len(archive_files)) + " archive files in public repo")
    print()

    if not archive_files:
        print("Nothing to migrate.")
        return

    migrated = 0
    failed = 0
    for item in archive_files:
        path = item["path"]
        print("- " + path)
        if not args.execute:
            continue
        # Fetch content
        content, _ = gh_get_file(PUB_OWNER, PUB_REPO, path, PUB_BRANCH)
        if content is None:
            print("  FAIL: could not fetch from public repo")
            failed += 1
            continue
        # Push to private repo
        ok, _ = gh_put_file(
            ARC_OWNER, ARC_REPO, path, content, ARC_BRANCH,
            "Migrate from " + PUB_REPO + ": " + path,
        )
        if not ok:
            print("  FAIL: could not push to private repo")
            failed += 1
            continue
        print("  -> private repo: OK")
        # Delete from public repo
        ok = gh_delete_file(
            PUB_OWNER, PUB_REPO, path, PUB_BRANCH,
            "Move to private archive repo: " + path,
        )
        if not ok:
            print("  WARN: deleted from public failed (file copied to private OK)")
        else:
            print("  -> deleted from public: OK")
        migrated += 1

    print()
    if args.execute:
        print("Done. Migrated: " + str(migrated) + " Failed: " + str(failed))
    else:
        print("DRY RUN complete. Re-run with --execute to actually migrate.")


if __name__ == "__main__":
    main()
