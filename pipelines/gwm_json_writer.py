#!/usr/bin/env python3
"""
gwm_json_writer.py — Shared library for Global Witness Monitor pipelines.

Manages two layers of JSON output, both stored in the InnovativeGeospatial/GWM
GitHub repo and served via jsDelivr:

  ACTIVE LAYER (served to live dashboards):
    /<feed>.json                        — last 500 events, sorted newest-first
    e.g. /disasters.json, /conflict.json, /persecution.json

  ARCHIVE LAYER (permanent record, browsed on demand):
    /archive/<feed>/<YYYY>-Q<n>.json    — every event, partitioned by quarter
    e.g. /archive/disasters/2026-Q2.json

Each event is appended to its feed's quarterly archive AND merged into the
active list when published. The active list is a "tail" view of the archive:
the most recent 500 events sorted by date.

Public API:
    write_event(feed, event)
        Add a single event to its feed's active + archive files. Idempotent
        (events keyed by `wp_id`).

    finalize(feed)
        Push the updated active + archive files to GitHub. Call once per
        pipeline run after all events have been written.

Configuration via environment variables (read from /opt/global-witness/.env):
    GITHUB_TOKEN       — Personal access token with repo write scope
    GITHUB_OWNER       — e.g. InnovativeGeospatial
    GITHUB_REPO        — e.g. GWM
    GITHUB_BRANCH      — default: main

Designed to be safe to call repeatedly within one pipeline run. Multiple calls
to write_event() accumulate; finalize() flushes once at the end.
"""

import os
import json
import base64
import logging
import requests
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger(__name__)

ACTIVE_LIMIT = 500

# Pending state — accumulated across write_event() calls within one pipeline run.
# Structure: { feed_name: { "active": [...], "archives": { "2026-Q2": [...] } } }
_pending = {}

# Cache of files already pulled from GitHub this run, to avoid re-fetching.
# Structure: { path: { "sha": str, "items": [...] } }
_github_cache = {}


# ── Config ──────────────────────────────────────────────────────────────
def _config():
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    owner = os.environ.get("GITHUB_OWNER", "InnovativeGeospatial").strip()
    repo = os.environ.get("GITHUB_REPO", "GWM").strip()
    branch = os.environ.get("GITHUB_BRANCH", "main").strip()
    if not token:
        raise RuntimeError(
            "GITHUB_TOKEN missing from environment. "
            "Add it to /opt/global-witness/.env"
        )
    return token, owner, repo, branch


# ── GitHub helpers ──────────────────────────────────────────────────────
def _gh_headers():
    token, _, _, _ = _config()
    return {
        "Authorization": "Bearer " + token,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _gh_url(path):
    _, owner, repo, _ = _config()
    return "https://api.github.com/repos/" + owner + "/" + repo + "/contents/" + path


def _gh_get(path):
    """Fetch a JSON file from GitHub. Returns (sha, items) or (None, [])."""
    if path in _github_cache:
        return _github_cache[path]["sha"], _github_cache[path]["items"]

    _, _, _, branch = _config()
    r = requests.get(_gh_url(path), headers=_gh_headers(),
                     params={"ref": branch}, timeout=20)
    if r.status_code == 404:
        _github_cache[path] = {"sha": None, "items": []}
        return None, []
    if r.status_code != 200:
        log.warning("GitHub GET %s -> %s: %s", path, r.status_code, r.text[:200])
        return None, []

    body = r.json()
    sha = body.get("sha")
    try:
        content_b64 = body.get("content", "")
        content = base64.b64decode(content_b64).decode("utf-8")
        data = json.loads(content)
        items = data.get("events", []) if isinstance(data, dict) else data
    except Exception as e:
        log.warning("Failed to decode %s: %s", path, e)
        items = []

    _github_cache[path] = {"sha": sha, "items": items}
    return sha, items


def _gh_put(path, content_str, sha, message):
    """Create or update a file on GitHub."""
    _, _, _, branch = _config()
    payload = {
        "message": message,
        "content": base64.b64encode(content_str.encode("utf-8")).decode("ascii"),
        "branch": branch,
    }
    if sha:
        payload["sha"] = sha
    r = requests.put(_gh_url(path), headers=_gh_headers(),
                     json=payload, timeout=30)
    if r.status_code in (200, 201):
        new_sha = r.json().get("content", {}).get("sha")
        if path in _github_cache:
            _github_cache[path]["sha"] = new_sha
        return True
    log.error("GitHub PUT %s failed (%s): %s", path, r.status_code, r.text[:300])
    return False


# ── Quarter calculation ─────────────────────────────────────────────────
def _quarter_key(iso_date):
    """Return e.g. '2026-Q2' from an ISO datetime string."""
    if not iso_date:
        dt = datetime.now(timezone.utc)
    else:
        try:
            dt = datetime.fromisoformat(iso_date.replace("Z", "+00:00"))
        except Exception:
            dt = datetime.now(timezone.utc)
    q = (dt.month - 1) // 3 + 1
    return "%d-Q%d" % (dt.year, q)


# ── Public API ──────────────────────────────────────────────────────────
def write_event(feed, event):
    """Queue an event for inclusion in the active list and its quarter's archive.

    Args:
        feed: 'disasters' | 'conflict' | 'persecution'
        event: dict with at minimum a 'wp_id' or unique 'hash' key.

    Idempotent: re-writing the same event (same wp_id) replaces the prior copy.
    """
    if feed not in _pending:
        _pending[feed] = {"active": {}, "archives": {}}

    # Normalize key
    key = str(event.get("wp_id") or event.get("id") or event.get("hash") or "")
    if not key:
        log.warning("write_event: event has no wp_id/hash, skipping: %r",
                    event.get("title", "")[:60])
        return

    qk = _quarter_key(event.get("date", ""))

    # Active layer: dict keyed by id, deduplicated. Sorted at finalize time.
    _pending[feed]["active"][key] = event

    # Archive layer: dict per quarter, keyed by id.
    if qk not in _pending[feed]["archives"]:
        _pending[feed]["archives"][qk] = {}
    _pending[feed]["archives"][qk][key] = event


def finalize(feed):
    """Flush pending events for a feed: merge with GitHub state and push.

    Returns dict with paths written and counts:
        {"active": "<path>", "archives": ["<path>", ...], "events_added": N}
    """
    if feed not in _pending or not _pending[feed]["active"]:
        log.info("finalize(%s): nothing pending", feed)
        return {"active": None, "archives": [], "events_added": 0}

    pending = _pending[feed]
    written = {"active": None, "archives": [], "events_added": len(pending["active"])}

    # ── Update each affected quarterly archive ──
    for qk, new_events in pending["archives"].items():
        archive_path = "archive/" + feed + "/" + qk + ".json"
        sha, existing = _gh_get(archive_path)
        merged = {str(e.get("wp_id") or e.get("id") or e.get("hash")): e
                  for e in existing if e}
        merged.update(new_events)  # new events overwrite old by key
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

    # ── Rebuild active list as the 500 most recent across all archives ──
    # Strategy: take all archive quarters that *might* contribute to the top 500,
    # merged with pending events, sort by date, slice top 500.
    # We pull at most the current quarter and previous quarter's archive — that's
    # vastly more than 500 events for most feeds.
    now = datetime.now(timezone.utc)
    cur_q = _quarter_key(now.isoformat())
    # Previous quarter
    prev_year = now.year
    prev_q_num = (now.month - 1) // 3 + 1 - 1
    if prev_q_num < 1:
        prev_q_num = 4
        prev_year -= 1
    prev_q = "%d-Q%d" % (prev_year, prev_q_num)

    pool = {}
    for qk in [cur_q, prev_q]:
        archive_path = "archive/" + feed + "/" + qk + ".json"
        _, items = _gh_get(archive_path)
        for e in items:
            k = str(e.get("wp_id") or e.get("id") or e.get("hash") or "")
            if k:
                pool[k] = e
    # Layer in pending (most recent state wins)
    for k, e in pending["active"].items():
        pool[k] = e

    sorted_events = sorted(
        pool.values(),
        key=lambda e: e.get("date", ""),
        reverse=True,
    )[:ACTIVE_LIMIT]

    active_path = feed + ".json"
    sha, _ = _gh_get(active_path)
    body = {
        "feed": feed,
        "updated": datetime.now(timezone.utc).isoformat(),
        "count": len(sorted_events),
        "limit": ACTIVE_LIMIT,
        "events": sorted_events,
    }
    ok = _gh_put(
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

    # Clear pending for this feed so finalize() is safe to call again
    _pending[feed] = {"active": {}, "archives": {}}

    return written


def reset():
    """Clear all pending state and caches. Call between independent batches."""
    _pending.clear()
    _github_cache.clear()
