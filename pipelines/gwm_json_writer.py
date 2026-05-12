#!/usr/bin/env python3
"""
gwm_json_writer.py v2 — Shared library for Global Witness Monitor pipelines.

NOW SPLITS storage between two GitHub repos:

  PUBLIC repo (e.g. InnovativeGeospatial/GWM):
    /<feed>.json                        — last 500 events, sorted newest-first
                                          (served to dashboards via jsDelivr)

  PRIVATE repo (e.g. InnovativeGeospatial/GWM-archive):
    /archive/<feed>/<YYYY>-Q<n>.json    — every event, partitioned by quarter
                                          (NOT publicly accessible)

Each event is appended to its feed's quarterly archive in the PRIVATE repo
AND merged into the active list in the PUBLIC repo.

Public API:
    write_event(feed, event)
    finalize(feed)
    reset()

Configuration via environment variables:
    GITHUB_TOKEN          — PAT with write scope to BOTH repos
    GITHUB_OWNER          — e.g. InnovativeGeospatial
    GITHUB_REPO           — public repo for active feeds, e.g. GWM
    GITHUB_BRANCH         — public branch, default: main
    GITHUB_ARCHIVE_OWNER  — owner of private archive repo (default: GITHUB_OWNER)
    GITHUB_ARCHIVE_REPO   — private archive repo name, e.g. GWM-archive
    GITHUB_ARCHIVE_BRANCH — private branch, default: main

If GITHUB_ARCHIVE_REPO is not set, falls back to writing archives to the
public repo (backward compatible with v1 behavior).
"""

import os
import json
import base64
import logging
import requests
from datetime import datetime, timezone

log = logging.getLogger(__name__)

ACTIVE_LIMIT = 500

_pending = {}
_github_cache = {}


def _config_active():
    """Config for the PUBLIC repo (active feeds)."""
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    owner = os.environ.get("GITHUB_OWNER", "InnovativeGeospatial").strip()
    repo = os.environ.get("GITHUB_REPO", "GWM").strip()
    branch = os.environ.get("GITHUB_BRANCH", "main").strip()
    if not token:
        raise RuntimeError(
            "GITHUB_TOKEN missing from environment."
        )
    return token, owner, repo, branch


def _config_archive():
    """Config for the PRIVATE archive repo.
    If GITHUB_ARCHIVE_REPO is unset, returns the public repo (legacy mode)."""
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    archive_repo = os.environ.get("GITHUB_ARCHIVE_REPO", "").strip()
    if not archive_repo:
        # Legacy: archives in same repo as active
        return _config_active()
    owner = os.environ.get(
        "GITHUB_ARCHIVE_OWNER",
        os.environ.get("GITHUB_OWNER", "InnovativeGeospatial"),
    ).strip()
    branch = os.environ.get("GITHUB_ARCHIVE_BRANCH", "main").strip()
    if not token:
        raise RuntimeError("GITHUB_TOKEN missing from environment.")
    return token, owner, archive_repo, branch


# ── GitHub helpers ──────────────────────────────────────────────────────
def _gh_headers(token):
    return {
        "Authorization": "Bearer " + token,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _gh_url(owner, repo, path):
    return "https://api.github.com/repos/" + owner + "/" + repo + "/contents/" + path


def _cache_key(owner, repo, branch, path):
    return owner + "/" + repo + "@" + branch + ":" + path


def _gh_get(target, path):
    """target is 'active' or 'archive'. Returns (sha, items) or (None, [])."""
    if target == "archive":
        token, owner, repo, branch = _config_archive()
    else:
        token, owner, repo, branch = _config_active()

    key = _cache_key(owner, repo, branch, path)
    if key in _github_cache:
        return _github_cache[key]["sha"], _github_cache[key]["items"]

    r = requests.get(_gh_url(owner, repo, path),
                     headers=_gh_headers(token),
                     params={"ref": branch}, timeout=20)
    if r.status_code == 404:
        _github_cache[key] = {"sha": None, "items": []}
        return None, []
    if r.status_code != 200:
        log.warning("GitHub GET %s/%s/%s -> %s: %s",
                    owner, repo, path, r.status_code, r.text[:200])
        return None, []

    body = r.json()
    sha = body.get("sha")
    try:
        content_b64 = body.get("content", "")
        content = base64.b64decode(content_b64).decode("utf-8")
        data = json.loads(content)
        items = data.get("events", []) if isinstance(data, dict) else data
    except Exception as e:
        log.warning("Failed to decode %s/%s/%s: %s", owner, repo, path, e)
        items = []

    _github_cache[key] = {"sha": sha, "items": items}
    return sha, items


def _gh_put(target, path, content_str, sha, message):
    if target == "archive":
        token, owner, repo, branch = _config_archive()
    else:
        token, owner, repo, branch = _config_active()

    payload = {
        "message": message,
        "content": base64.b64encode(content_str.encode("utf-8")).decode("ascii"),
        "branch": branch,
    }
    if sha:
        payload["sha"] = sha
    r = requests.put(_gh_url(owner, repo, path),
                     headers=_gh_headers(token),
                     json=payload, timeout=30)
    if r.status_code in (200, 201):
        new_sha = r.json().get("content", {}).get("sha")
        key = _cache_key(owner, repo, branch, path)
        if key in _github_cache:
            _github_cache[key]["sha"] = new_sha
        return True
    log.error("GitHub PUT %s/%s/%s failed (%s): %s",
              owner, repo, path, r.status_code, r.text[:300])
    return False


def _quarter_key(iso_date):
    if not iso_date:
        dt = datetime.now(timezone.utc)
    else:
        try:
            dt = datetime.fromisoformat(iso_date.replace("Z", "+00:00"))
        except Exception:
            dt = datetime.now(timezone.utc)
    q = (dt.month - 1) // 3 + 1
    return "%d-Q%d" % (dt.year, q)


def write_event(feed, event):
    if feed not in _pending:
        _pending[feed] = {"active": {}, "archives": {}}

    key = str(event.get("wp_id") or event.get("id") or event.get("hash") or "")
    if not key:
        log.warning("write_event: event has no wp_id/hash, skipping: %r",
                    event.get("title", "")[:60])
        return

    qk = _quarter_key(event.get("date", ""))

    _pending[feed]["active"][key] = event

    if qk not in _pending[feed]["archives"]:
        _pending[feed]["archives"][qk] = {}
    _pending[feed]["archives"][qk][key] = event


def finalize(feed):
    if feed not in _pending or not _pending[feed]["active"]:
        log.info("finalize(%s): nothing pending", feed)
        return {"active": None, "archives": [], "events_added": 0}

    pending = _pending[feed]
    written = {"active": None, "archives": [], "events_added": len(pending["active"])}

    # ── Update each affected quarterly archive (PRIVATE repo) ──
    for qk, new_events in pending["archives"].items():
        archive_path = "archive/" + feed + "/" + qk + ".json"
        sha, existing = _gh_get("archive", archive_path)
        merged = {str(e.get("wp_id") or e.get("id") or e.get("hash")): e
                  for e in existing if e}
        merged.update(new_events)
        events_list = sorted(
            merged.values(),
            key=lambda e: e.get("date", ""),
            reverse=True,
        )
        body = {
            "feed": feed,
            "quarter": qk,
            "updated": datetime.now(timezone.utc).isoformat(),
            "count": len(events_list),
            "events": events_list,
        }
        ok = _gh_put(
            "archive",
            archive_path,
            json.dumps(body, ensure_ascii=False, indent=2),
            sha,
            "Archive update: " + feed + " " + qk + " (+" +
            str(len(new_events)) + ")",
        )
        if ok:
            written["archives"].append(archive_path)
            log.info("Archive written: %s (%d events total)",
                     archive_path, len(events_list))

    # ── Rebuild active list as the 500 most recent (PUBLIC repo) ──
    now = datetime.now(timezone.utc)
    cur_q = _quarter_key(now.isoformat())
    prev_year = now.year
    prev_q_num = (now.month - 1) // 3 + 1 - 1
    if prev_q_num < 1:
        prev_q_num = 4
        prev_year -= 1
    prev_q = "%d-Q%d" % (prev_year, prev_q_num)

    pool = {}
    for qk in [cur_q, prev_q]:
        archive_path = "archive/" + feed + "/" + qk + ".json"
        _, items = _gh_get("archive", archive_path)
        for e in items:
            k = str(e.get("wp_id") or e.get("id") or e.get("hash") or "")
            if k:
                pool[k] = e
    for k, e in pending["active"].items():
        pool[k] = e

    sorted_events = sorted(
        pool.values(),
        key=lambda e: e.get("date", ""),
        reverse=True,
    )[:ACTIVE_LIMIT]

    active_path = feed + ".json"
    sha, _ = _gh_get("active", active_path)
    body = {
        "feed": feed,
        "updated": datetime.now(timezone.utc).isoformat(),
        "count": len(sorted_events),
        "limit": ACTIVE_LIMIT,
        "events": sorted_events,
    }
    ok = _gh_put(
        "active",
        active_path,
        json.dumps(body, ensure_ascii=False, indent=2),
        sha,
        "Active feed update: " + feed + " (+" +
        str(len(pending["active"])) + ")",
    )
    if ok:
        written["active"] = active_path
        log.info("Active feed written: %s (%d events)",
                 active_path, len(sorted_events))

    _pending[feed] = {"active": {}, "archives": {}}

    return written


def reset():
    _pending.clear()
    _github_cache.clear()
