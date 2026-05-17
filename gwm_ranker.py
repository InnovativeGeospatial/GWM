#!/usr/bin/env python3
"""
gwm_ranker.py — GWM country persecution ranker

Reads:   /opt/conflict-pipeline/rankings_input.json
Writes:  /opt/conflict-pipeline/rankings.json (local)
Commits: rankings.json AND rankings_input.json to InnovativeGeospatial/GWM on main

Run:
    cd /opt/conflict-pipeline
    set -a && source .env && set +a
    venv/bin/python gwm_ranker.py

Then purge jsDelivr cache:
    curl https://purge.jsdelivr.net/gh/InnovativeGeospatial/GWM@main/rankings.json
"""

import json
import os
import sys
import base64
import datetime
import urllib.request
import urllib.error

# ── Paths ────────────────────────────────────────────────────
INPUT_PATH  = "/opt/conflict-pipeline/rankings_input.json"
OUTPUT_PATH = "/opt/conflict-pipeline/rankings.json"

# ── GitHub config (from environment) ─────────────────────────
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


# ─────────────────────────────────────────────────────────────
# Scoring
# ─────────────────────────────────────────────────────────────
def compute_score(country, cfg):
    """Compute 0-100 GWM score for one country entry."""

    # Manual override wins everything
    if country.get("score_override") is not None:
        s = float(country["score_override"])
        return max(cfg["score_floor"], min(cfg["score_ceiling"], s))

    # Base score: WWL rank if present, else tier base
    wwl = country.get("wwl_rank")
    if wwl and 1 <= wwl <= 50:
        top    = cfg["wwl_top50_scale"]["rank_1_score"]
        bottom = cfg["wwl_top50_scale"]["rank_50_score"]
        # Linear: rank 1 -> top, rank 50 -> bottom
        score = top - ((wwl - 1) / 49.0) * (top - bottom)
    else:
        tier = country.get("tier", 5)
        score = cfg["tier_base_scores"][str(tier)]

    # USCIRF bonus
    uscirf = country.get("uscirf")
    if uscirf == "CPC":
        score += cfg["uscirf_cpc_bonus"]
    elif uscirf == "SWL":
        score += cfg["uscirf_swl_bonus"]

    # Threat modifier
    threat = country.get("threat", "structural")
    score += cfg["threat_modifiers"].get(threat, 0)

    # Clamp
    return max(cfg["score_floor"], min(cfg["score_ceiling"], score))


def assign_tier_from_score(score):
    """Score-to-tier band. Independent of input tier hint."""
    if score >= 95: return 1
    if score >= 80: return 2
    if score >= 60: return 3
    if score >= 35: return 4
    return 5


# ─────────────────────────────────────────────────────────────
# Build rankings.json
# ─────────────────────────────────────────────────────────────
def build_rankings(input_data):
    cfg = input_data["scoring_config"]
    countries_in = input_data["countries"]

    # Compute scores
    enriched = []
    for c in countries_in:
        score = compute_score(c, cfg)
        # Use the score-derived tier (consistent w/ score), not the hint
        tier = assign_tier_from_score(score)
        enriched.append({
            "name": c["name"],
            "slug": c["slug"],
            "tier": tier,
            "tier_label": TIER_LABELS[tier],
            "score": round(score, 1),
            "wwl_rank": c.get("wwl_rank"),
            "uscirf": c.get("uscirf"),
            "threat": c.get("threat"),
        })

    # Sort by score desc, then by name asc (stable tiebreak)
    enriched.sort(key=lambda x: (-x["score"], x["name"]))

    # Assign rank (ties get same rank, next rank skips — competition ranking)
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
            "version":      input_data["metadata"].get("version", "1.0"),
            "generated_at": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "wwl_year":     input_data["metadata"].get("wwl_year"),
            "uscirf_year":  input_data["metadata"].get("uscirf_year"),
            "country_count": len(enriched),
            "methodology": "GWM multi-source ranking (WWL + USCIRF + State Dept IRF + ACN + editorial). See globalwitnessmonitor.com/methodology",
        },
        "countries": enriched,
    }


# ─────────────────────────────────────────────────────────────
# GitHub API helpers (GET sha then PUT)
# ─────────────────────────────────────────────────────────────
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


# ─────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────
def main():
    if not GH_TOKEN:
        print("ERROR: GITHUB_TOKEN not set in environment", file=sys.stderr)
        sys.exit(1)

    print(f"[ranker] reading {INPUT_PATH}")
    with open(INPUT_PATH, "r", encoding="utf-8") as f:
        input_data = json.load(f)

    print(f"[ranker] {len(input_data['countries'])} countries loaded")
    rankings = build_rankings(input_data)

    # Write local
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(rankings, f, ensure_ascii=False, indent=2)
    print(f"[ranker] wrote {OUTPUT_PATH}")

    # Summary
    tier_counts = {}
    for c in rankings["countries"]:
        tier_counts[c["tier"]] = tier_counts.get(c["tier"], 0) + 1
    print(f"[ranker] tier distribution: " + ", ".join(
        f"T{t}={tier_counts.get(t,0)}" for t in (1,2,3,4,5)
    ))
    print(f"[ranker] top 5:")
    for c in rankings["countries"][:5]:
        print(f"  #{c['rank']:>3}  {c['name']:<25}  score={c['score']:>5}  ({c['tier_label']})")

    # Push rankings.json
    print(f"[ranker] committing rankings.json to {GH_OWNER}/{GH_REPO}@{GH_BRANCH}")
    rj_bytes = json.dumps(rankings, ensure_ascii=False, indent=2).encode("utf-8")
    ok, info = gh_put_file(
        "rankings.json",
        rj_bytes,
        f"Update rankings.json — {rankings['metadata']['generated_at']}",
    )
    if not ok:
        print(f"[ranker] FAILED to push rankings.json: {info}", file=sys.stderr)
        sys.exit(2)
    print("[ranker] rankings.json committed")

    # Push rankings_input.json (backup of source data)
    print("[ranker] committing rankings_input.json (source data)")
    with open(INPUT_PATH, "rb") as f:
        in_bytes = f.read()
    ok, info = gh_put_file(
        "rankings_input.json",
        in_bytes,
        f"Sync rankings_input.json — {rankings['metadata']['generated_at']}",
    )
    if not ok:
        print(f"[ranker] WARN: rankings_input.json push failed: {info}", file=sys.stderr)
    else:
        print("[ranker] rankings_input.json committed")

    print("")
    print("DONE. Now purge jsDelivr cache:")
    print(f"  curl https://purge.jsdelivr.net/gh/{GH_OWNER}/{GH_REPO}@{GH_BRANCH}/rankings.json")
    print(f"  curl https://purge.jsdelivr.net/gh/{GH_OWNER}/{GH_REPO}@{GH_BRANCH}/rankings_input.json")


if __name__ == "__main__":
    main()
