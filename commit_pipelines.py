#!/usr/bin/env python3
"""
commit_pipelines.py

Commits the three live pipeline files from /opt/* on the droplet to the
InnovativeGeospatial/GWM repo under pipelines/.

Reads GITHUB_TOKEN from /opt/conflict-pipeline/.env.
Each file: fetches current SHA if it exists, then PUTs new content.

Run once. After this, the repo holds the canonical pipeline source.
"""
import base64
import json
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path

REPO = "InnovativeGeospatial/GWM"
BRANCH = "main"

# Local source -> repo destination
FILES = [
    ("/opt/conflict-pipeline/run_conflict_pipeline.py", "pipelines/run_conflict_pipeline.py"),
    ("/opt/disaster-pipeline/run_disaster_pipeline.py", "pipelines/run_disaster_pipeline.py"),
    ("/opt/global-witness/run_pipeline.py", "pipelines/persecution_pipeline.py"),
]

ENV_FILE = "/opt/conflict-pipeline/.env"


def load_token():
    if not Path(ENV_FILE).exists():
        sys.exit(f"ERROR: {ENV_FILE} not found")
    with open(ENV_FILE) as f:
        for line in f:
            line = line.strip()
            if line.startswith("GITHUB_TOKEN="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    sys.exit("ERROR: GITHUB_TOKEN not found in env file")


def gh_request(method, path, token, data=None):
    url = f"https://api.github.com{path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "gwm-pipeline-committer",
    }
    body = None
    if data is not None:
        body = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        return e.code, {"_error": body}


def get_existing_sha(token, repo_path):
    status, body = gh_request(
        "GET",
        f"/repos/{REPO}/contents/{repo_path}?ref={BRANCH}",
        token,
    )
    if status == 200:
        return body.get("sha")
    if status == 404:
        return None
    print(f"  WARN: unexpected status {status} fetching SHA: {body}")
    return None


def put_file(token, local_path, repo_path):
    if not Path(local_path).exists():
        print(f"  SKIP: {local_path} does not exist")
        return False

    content = Path(local_path).read_bytes()
    encoded = base64.b64encode(content).decode("ascii")

    sha = get_existing_sha(token, repo_path)
    payload = {
        "message": f"Sync {repo_path} from droplet",
        "content": encoded,
        "branch": BRANCH,
    }
    if sha:
        payload["sha"] = sha
        print(f"  Updating existing file (sha {sha[:8]})")
    else:
        print(f"  Creating new file")

    status, body = gh_request(
        "PUT",
        f"/repos/{REPO}/contents/{repo_path}",
        token,
        data=payload,
    )
    if status in (200, 201):
        commit = body.get("commit", {}).get("sha", "?")[:8]
        print(f"  OK ({status}) commit {commit}")
        return True
    print(f"  FAIL ({status}): {body}")
    return False


def main():
    token = load_token()
    print(f"Loaded token (starts with {token[:14]}..., length {len(token)})")
    print(f"Target: {REPO}@{BRANCH}")
    print()

    success_paths = []
    for local, repo_path in FILES:
        print(f"-> {local}")
        print(f"   {repo_path}")
        if put_file(token, local, repo_path):
            success_paths.append(repo_path)
        print()

    if success_paths:
        print("=" * 60)
        print("Raw URLs:")
        for p in success_paths:
            print(f"  https://raw.githubusercontent.com/{REPO}/refs/heads/{BRANCH}/{p}")


if __name__ == "__main__":
    main()
