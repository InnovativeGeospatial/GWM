#!/usr/bin/env python3
"""
gwm_ranker.py v2 — GWM country persecution ranker (5-dimension scoring)

Reads:   /opt/conflict-pipeline/rankings_input.json
Writes:  /opt/conflict-pipeline/rankings.json (local)
Commits: rankings.json AND rankings_input.json to InnovativeGeospatial/GWM on main

Each country scored 0-20 on five dimensions:
  state, non_state, legal, indigenous, trajectory
Composite = sum (0-100).
Tier from composite:
  >=85 Extreme | >=65 Very High | >=45 High | >=25 Medium | else Lower

Run:
    cd /opt/conflict-pipeline
    ( set -a; . ./.env; set +a; venv/bin/python gwm_ranker.py )

Then purge jsDelivr:
    curl https://purge.jsdelivr.net/gh/InnovativeGeospatial/GWM@main/rankings.json
"""

import json
import os
import sys
import base64
import datetime
import urllib.request
import urllib.error

INPUT_PATH  = "/opt/conflict-pipeline/rankings_input.json"
OUTPUT_PATH = "/opt/conflict-pipeline/rankings.json"

GH_TOKEN  = os.environ.get("GITHUB_TOKEN", "").strip()
GH_OWNER  = os.environ.get("GITHUB_OWNER", "InnovativeGeospatial").strip()
GH_REPO   = os.environ.get("GITHUB_REPO", "GWM").strip()
GH_BRANCH = os.environ.get("GITHUB_BRANCH", "main").strip()

TIER_LABELS = {
    1: "Extreme",
    2: "Very High",
    3: "High",
    4: "Medium",
    5: "Lower",
}


def compute_score(country):
    """Sum of 5 dimensions, each clamped 0-20."""
    s = 0
    for key in ("state", "non_state", "legal", "indigenous", "trajectory"):
        v = country.get(key, 0)
        try:
            v = float(v)
        except (TypeError, ValueError):
            v = 0
        v = max(0, min(20, v))
        s += v
    return s


def assign_tier(score, thresholds):
    if score >= thresholds["extreme"]:   return 1
    if score >= thresholds["very_high"]: return 2
    if score >= thresholds["high"]:      return 3
    if score >= thresholds["medium"]:    return 4
    return 5


def build_rankings(input_data):
    cfg = input_data["scoring_config"]
    thresholds = cfg["tier_thresholds"]
    enriched = []
    for c in input_data["countries"]:
        score = compute_score(c)
        tier  = assign_tier(score, thresholds)
        enriched.append({
            "name":       c["name"],
            "slug":       c["slug"],
            "tier":       tier,
            "tier_label": TIER_LABELS[tier],
            "score":      round(score, 1),
            "sub_scores": {
                "state":      c.get("state", 0),
                "non_state":  c.get("non_state", 0),
                "legal":      c.get("legal", 0),
                "indigenous": c.get("indigenous", 0),
                "trajectory": c.get("trajectory", 0),
            },
        })

    enriched.sort(key=lambda x: (-x["score"], x["name"]))

    last_score = None
    last_rank  = 0
    for i, c in enumerate(enriched, start=1):
        if c["score"] == last_score:
            c["rank"] = last_rank
        else:
            c["rank"] = i
            last_rank = i
            last_score = c["score"]

    return {
        "metadata": {
            "version":       input_data["metadata"].get("version", "2.0"),
            "generated_at":  datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "country_count": len(enriched),
            "methodology":   "GWM 5-dimension persecution scoring. See globalwitnessmonitor.com/methodology",
        },
        "countries": enriched,
    }


def gh_request(method, url, payload=None):
    data = json.dumps(payload).encode("utf-8") if payload else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"token {GH_TOKEN}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    if data:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            body = r.read().decode("utf-8")
            return r.status, json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        return e.code, {"error": body}


def gh_get_sha(path):
    url = f"https://api.github.com/repos/{GH_OWNER}/{GH_REPO}/contents/{path}?ref={GH_BRANCH}"
    code, body = gh_request("GET", url)
    if code == 200:
        return body.get("sha")
    return None


def gh_put_file(path, content_bytes, message):
    sha = gh_get_sha(path)
    url = f"https://api.github.com/repos/{GH_OWNER}/{GH_REPO}/contents/{path}"
    payload = {
        "message": message,
        "content": base64.b64encode(content_bytes).decode("ascii"),
        "branch":  GH_BRANCH,
    }
    if sha:
        payload["sha"] = sha
    code, body = gh_request("PUT", url, payload)
    if code in (200, 201):
        return True, body.get("content", {}).get("sha")
    return False, body


def main():
    if not GH_TOKEN:
        print("ERROR: GITHUB_TOKEN not set in environment", file=sys.stderr)
        sys.exit(1)

    print(f"[ranker] reading {INPUT_PATH}")
    with open(INPUT_PATH, "r", encoding="utf-8") as f:
        input_data = json.load(f)

    print(f"[ranker] {len(input_data['countries'])} countries loaded")
    rankings = build_rankings(input_data)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(rankings, f, ensure_ascii=False, indent=2)
    print(f"[ranker] wrote {OUTPUT_PATH}")

    tier_counts = {}
    for c in rankings["countries"]:
        tier_counts[c["tier"]] = tier_counts.get(c["tier"], 0) + 1
    print(f"[ranker] tier distribution: " + ", ".join(
        f"T{t}={tier_counts.get(t,0)}" for t in (1,2,3,4,5)
    ))
    print(f"[ranker] top 10:")
    for c in rankings["countries"][:10]:
        print(f"  #{c['rank']:>3}  {c['name']:<28}  score={c['score']:>5}  ({c['tier_label']})")

    print(f"[ranker] committing rankings.json")
    rj_bytes = json.dumps(rankings, ensure_ascii=False, indent=2).encode("utf-8")
    ok, info = gh_put_file(
        "rankings.json",
        rj_bytes,
        f"Update rankings.json {rankings['metadata']['generated_at']}",
    )
    if not ok:
        print(f"[ranker] FAILED to push rankings.json: {info}", file=sys.stderr)
        sys.exit(2)
    print("[ranker] rankings.json committed")

    print("[ranker] committing rankings_input.json")
    with open(INPUT_PATH, "rb") as f:
        in_bytes = f.read()
    ok, info = gh_put_file(
        "rankings_input.json",
        in_bytes,
        f"Sync rankings_input.json {rankings['metadata']['generated_at']}",
    )
    if not ok:
        print(f"[ranker] WARN: rankings_input.json push failed: {info}", file=sys.stderr)
    else:
        print("[ranker] rankings_input.json committed")

    print("")
    print("DONE. Purge jsDelivr next:")
    print(f"  curl https://purge.jsdelivr.net/gh/{GH_OWNER}/{GH_REPO}@{GH_BRANCH}/rankings.json")


if __name__ == "__main__":
    main()
