#!/usr/bin/env python3
"""
audit_disaster_pipeline.py

Diagnostic tool: runs the same RSS/GDELT fetch + filter logic as the disaster
pipeline, but prints every candidate and WHY it passed or failed each filter.
No Claude API calls. No WordPress posts. Just shows where events are leaking.

Run on the server:
    curl -sL <raw-gist-url> -o /tmp/audit_disaster_pipeline.py
    cd /opt/disaster-pipeline
    set -a && source .env && set +a
    venv/bin/python /tmp/audit_disaster_pipeline.py
"""

import os
import sys
import json
import time
import hashlib
import requests
import feedparser
from collections import defaultdict, Counter

# =====================================================================
# Import the pipeline module so we use its EXACT filter functions
# =====================================================================
sys.path.insert(0, "/opt/disaster-pipeline")
import run_disaster_pipeline as pipe  # noqa


# =====================================================================
# Stats tracking
# =====================================================================
class AuditStats:
    def __init__(self):
        self.per_feed_total = defaultdict(int)
        self.per_feed_pass  = defaultdict(int)
        self.reject_reasons = Counter()
        self.passed_items = []
        self.rejected_samples = defaultdict(list)  # reason -> up to 3 samples

    def note_seen(self, feed):
        self.per_feed_total[feed] += 1

    def note_pass(self, feed, title):
        self.per_feed_pass[feed] += 1
        self.passed_items.append((feed, title))

    def note_reject(self, feed, title, reason):
        self.reject_reasons[reason] += 1
        if len(self.rejected_samples[reason]) < 3:
            self.rejected_samples[reason].append((feed, title))

    def print_report(self):
        print("")
        print("=" * 72)
        print("  AUDIT REPORT")
        print("=" * 72)
        print("")
        print("PER-FEED YIELD:")
        print("-" * 72)
        for feed in sorted(self.per_feed_total.keys()):
            total = self.per_feed_total[feed]
            passed = self.per_feed_pass[feed]
            label = feed if len(feed) <= 50 else feed[:47] + "..."
            print(f"  {label:50s}  {passed:3d} / {total:3d} passed")
        print("")
        print("REJECTION REASONS:")
        print("-" * 72)
        total_rejected = sum(self.reject_reasons.values())
        for reason, count in self.reject_reasons.most_common():
            pct = (count * 100 // total_rejected) if total_rejected else 0
            print(f"  {count:4d}  ({pct:3d}%)  {reason}")
        print("")
        print("SAMPLE REJECTIONS BY REASON:")
        print("-" * 72)
        for reason, samples in self.rejected_samples.items():
            print(f"\n  [{reason}]")
            for feed, title in samples:
                short_feed = feed.split("/")[-2] if "/" in feed else feed
                short_title = title[:70]
                print(f"    - ({short_feed}) {short_title}")
        print("")
        print("PASSED CANDIDATES:")
        print("-" * 72)
        if not self.passed_items:
            print("  (none)")
        else:
            for feed, title in self.passed_items:
                short_feed = feed.split("/")[-2] if "/" in feed else feed
                short_title = title[:70]
                print(f"  + ({short_feed}) {short_title}")
        print("")
        print("=" * 72)
        print(f"  TOTAL: {sum(self.per_feed_pass.values())} candidates"
              f" from {sum(self.per_feed_total.values())} articles scanned")
        print("=" * 72)


stats = AuditStats()


# =====================================================================
# Replicate the pipeline's filter sequence, annotating each step
# =====================================================================
def audit_article(feed_label, title, summary, url):
    """Run the same filters the pipeline uses, but log decisions."""
    stats.note_seen(feed_label)

    if not title or not url:
        stats.note_reject(feed_label, title or "(no title)", "no title or url")
        return

    text = (title + " " + summary).lower()

    # Filter 1: disaster keyword
    has_disaster = any(term in text for term in pipe.DISASTER_TERMS)
    if not has_disaster:
        stats.note_reject(feed_label, title, "no disaster keyword")
        return

    # Filter 2: event signal
    has_event = any(signal in text for signal in pipe.EVENT_SIGNALS)
    if not has_event:
        stats.note_reject(feed_label, title, "no event signal verb")
        return

    # Filter 3: exclude patterns
    title_lower = title.lower()
    for pattern in pipe.EXCLUDE_PATTERNS:
        if pattern in title_lower:
            stats.note_reject(feed_label, title, f"exclude pattern: {pattern}")
            return

    # Filter 4: country extraction
    country = pipe.extract_country(title, summary)
    if not country:
        stats.note_reject(feed_label, title, "no country detected")
        return

    # All pipeline-side filters passed (Claude SKIP_NO_EVENT is not simulated here)
    stats.note_pass(feed_label, title)


# =====================================================================
# Fetch feeds (same URLs as the pipeline)
# =====================================================================
def audit_rss():
    print("Auditing RSS feeds...")
    print("")
    for feed_url in pipe.RSS_FEEDS:
        feed_label = feed_url
        print(f"  fetching: {feed_url}")
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:30]:
                title   = (entry.get("title", "") or "").strip()
                summary = (entry.get("summary", entry.get("description", "")) or "").strip()
                url     = entry.get("link", "") or ""
                audit_article(feed_label, title, summary, url)
        except Exception as e:
            print(f"    ERROR: {e}")


def audit_gdelt():
    print("")
    print("Auditing GDELT queries...")
    print("")
    query_terms = [
        "earthquake magnitude killed",
        "flood flooding evacuated displaced",
        "hurricane typhoon cyclone landfall",
        "wildfire bushfire destroyed evacuated",
        "volcano eruption ash evacuated",
        "tsunami warning struck",
        "landslide mudslide buried killed",
    ]
    for query in query_terms:
        print(f"  query: {query}")
        try:
            url = (
                "https://api.gdeltproject.org/api/v2/doc/doc"
                "?query=" + requests.utils.quote(query) +
                "&mode=artlist&maxrecords=10&timespan=24h&sort=DateDesc&format=json"
            )
            r = requests.get(url, timeout=15)
            if r.status_code == 429:
                print("    rate limited (429) -- stopping GDELT audit")
                break
            if r.status_code != 200:
                print(f"    HTTP {r.status_code}")
                time.sleep(5)
                continue
            data = r.json()
            articles = data.get("articles", [])
            for article in articles:
                title   = (article.get("title", "") or "").strip()
                url_art = article.get("url", "") or ""
                audit_article("GDELT:" + query, title, title, url_art)
            time.sleep(5)
        except Exception as e:
            print(f"    ERROR: {e}")


# =====================================================================
# Main
# =====================================================================
def main():
    print("")
    print("=" * 72)
    print("  DISASTER PIPELINE AUDIT")
    print("  (no Claude calls, no WordPress posts -- diagnostic only)")
    print("=" * 72)
    print("")

    audit_rss()
    audit_gdelt()
    stats.print_report()


if __name__ == "__main__":
    main()
