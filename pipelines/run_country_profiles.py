#!/usr/bin/env python3
"""
Country Profiles Pipeline — Global Witness Monitor
Parses a single Word doc (or .md/.txt) containing many country profiles
separated by `-----`, strips the YAML-style header, converts the markdown
body to plain HTML, and updates the existing top-level WordPress page
matching the country slug (e.g. /afghanistan/).

Usage:
  python3 run_country_profiles.py /path/to/profiles.docx          # dry-run, no writes
  python3 run_country_profiles.py /path/to/profiles.docx --apply  # write to WordPress
  python3 run_country_profiles.py /path/to/profiles.docx --apply --only afghanistan,albania
"""
import os
import re
import sys
import json
import argparse
import unicodedata
from pathlib import Path

import requests
from dotenv import load_dotenv

# ── Config ──────────────────────────────────────────────────────────────
load_dotenv(Path(__file__).parent / ".env")

WP_BASE = os.environ.get("WP_BASE", "https://globalwitnessmonitor.com").rstrip("/")
WP_USER = os.environ.get("WP_USER", "")
WP_APP_PASSWORD = os.environ.get("WP_APP_PASSWORD", "")
SEPARATOR = re.compile(r"^\s*-{5,}\s*$", re.MULTILINE)

if not WP_USER or not WP_APP_PASSWORD:
    sys.exit("ERROR: WP_USER and WP_APP_PASSWORD must be set in .env")

AUTH = (WP_USER, WP_APP_PASSWORD)


# ── Doc loader (.docx or plain text) ────────────────────────────────────
def load_doc(path: Path) -> str:
    if path.suffix.lower() == ".docx":
        try:
            from docx import Document
        except ImportError:
            sys.exit("ERROR: python-docx required for .docx. pip install python-docx")
        doc = Document(str(path))
        lines = []
        for p in doc.paragraphs:
            txt = p.text
            style = (p.style.name or "").lower() if p.style else ""
            if style.startswith("heading 1"):
                lines.append("# " + txt)
            elif style.startswith("heading 2"):
                lines.append("## " + txt)
            elif style.startswith("heading 3"):
                lines.append("### " + txt)
            else:
                lines.append(txt)
        return "\n".join(lines)
    return path.read_text(encoding="utf-8")


# ── Parse blocks ────────────────────────────────────────────────────────
def split_blocks(raw: str):
    parts = SEPARATOR.split(raw)
    out = []
    for part in parts:
        if "COUNTRY:" in part.upper():
            out.append(part.strip())
    return out


HEADER_KEYS = {
    "COUNTRY", "TITLE", "SLUG", "META DESCRIPTION", "CATEGORY",
    "TAGS", "PERSECUTION TIER", "WWL RANKING",
}


def parse_block(block: str):
    """Return (header_dict, body_markdown).

    Robust against:
      - Word collapsing the YAML-ish header into one paragraph
      - A document-title `# GWM Country Profiles` appearing above the first
        block's COUNTRY: line
      - Decorative `# =====` dividers
    """
    explode = re.sub(
        r"\s+(COUNTRY|TITLE|SLUG|META DESCRIPTION|CATEGORY|TAGS|"
        r"PERSECUTION TIER|WWL RANKING):",
        r"\n\1:",
        block,
    )

    lines = explode.splitlines()
    header = {}
    body_start = 0
    seen_header_key = False
    for i, line in enumerate(lines):
        s = line.strip()
        if not s:
            body_start = i + 1
            continue
        if re.match(r"^#\s*=+", s):
            body_start = i + 1
            continue
        # Once we've started reading header keys, a `#` heading means body begins
        if s.startswith("#") and seen_header_key:
            body_start = i
            break
        # Stray pre-header doc title (e.g. "# GWM Country Profiles") — skip
        if s.startswith("#") and not seen_header_key:
            body_start = i + 1
            continue
        m = re.match(r"^([A-Z][A-Z &]+):\s*(.*)$", s)
        if m and m.group(1).strip() in HEADER_KEYS:
            header[m.group(1).strip()] = m.group(2).strip()
            seen_header_key = True
            body_start = i + 1
        else:
            body_start = i
            break
    body = "\n".join(lines[body_start:]).strip()
    return header, body


# ── Slug ────────────────────────────────────────────────────────────────
def slugify(name: str) -> str:
    n = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    n = n.lower().strip()
    n = re.sub(r"[^a-z0-9]+", "-", n)
    return n.strip("-")


# ── Markdown → HTML (minimal, no external deps) ─────────────────────────
def md_inline(text: str) -> str:
    # bold **x**
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    # italic *x* (after bold so we don't eat ** marks)
    text = re.sub(r"(?<!\*)\*(?!\s)([^*\n]+?)\*(?!\*)", r"<em>\1</em>", text)
    return text


def md_to_html(md: str) -> str:
    """Convert the body markdown to clean WP-friendly HTML."""
    # Normalize smart quotes/dashes that may have leaked in from Word
    md = (md.replace("\u2018", "'").replace("\u2019", "'")
              .replace("\u201c", '"').replace("\u201d", '"')
              .replace("\u2013", "-").replace("\u2014", "—"))

    out = []
    lines = md.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()

        # Skip the top-level title that duplicates page title
        if re.match(r"^#\s+", line) and not re.match(r"^##", line):
            i += 1
            continue

        # H2
        m = re.match(r"^##\s+(.*)", line)
        if m:
            out.append(f"<h2>{md_inline(m.group(1).strip())}</h2>")
            i += 1
            continue

        # H3
        m = re.match(r"^###\s+(.*)", line)
        if m:
            out.append(f"<h3>{md_inline(m.group(1).strip())}</h3>")
            i += 1
            continue

        # UL block (lines starting with - or *)
        if re.match(r"^\s*[-*]\s+", line):
            items = []
            while i < len(lines) and re.match(r"^\s*[-*]\s+", lines[i]):
                item = re.sub(r"^\s*[-*]\s+", "", lines[i]).strip()
                items.append(f"  <li>{md_inline(item)}</li>")
                i += 1
            out.append("<ul>\n" + "\n".join(items) + "\n</ul>")
            continue

        # Blank line — paragraph break
        if not line.strip():
            i += 1
            continue

        # Paragraph: collect contiguous non-empty, non-special lines
        para = [line]
        i += 1
        while (i < len(lines)
               and lines[i].strip()
               and not re.match(r"^#{1,3}\s", lines[i])
               and not re.match(r"^\s*[-*]\s+", lines[i])):
            para.append(lines[i].rstrip())
            i += 1
        out.append(f"<p>{md_inline(' '.join(para).strip())}</p>")

    return "\n\n".join(out)


# ── WordPress ───────────────────────────────────────────────────────────
def find_page_by_slug(slug: str):
    """Look up a WP page by slug. Returns page dict or None."""
    url = f"{WP_BASE}/wp-json/wp/v2/pages"
    r = requests.get(url, params={"slug": slug, "_fields": "id,slug,title,link,status"},
                     auth=AUTH, timeout=30)
    r.raise_for_status()
    data = r.json()
    return data[0] if data else None


def update_page(page_id: int, html: str, title: str = None):
    url = f"{WP_BASE}/wp-json/wp/v2/pages/{page_id}"
    payload = {"content": html}
    if title:
        payload["title"] = title
    r = requests.post(url, json=payload, auth=AUTH, timeout=60)
    r.raise_for_status()
    return r.json()


# ── Main ────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("doc", help="Path to the country profiles document (.docx, .md, .txt)")
    ap.add_argument("--apply", action="store_true", help="Actually write to WordPress (default: dry run)")
    ap.add_argument("--only", help="Comma-separated list of country slugs to process")
    ap.add_argument("--skip-missing", action="store_true",
                    help="Silently skip countries with no matching WP page (default: warn)")
    args = ap.parse_args()

    doc_path = Path(args.doc).expanduser().resolve()
    if not doc_path.exists():
        sys.exit(f"File not found: {doc_path}")

    only = set()
    if args.only:
        only = {s.strip().lower() for s in args.only.split(",") if s.strip()}

    raw = load_doc(doc_path)
    blocks = split_blocks(raw)
    print(f"Found {len(blocks)} country blocks")

    summary = {"updated": [], "missing": [], "skipped": [], "errors": []}

    for block in blocks:
        header, body = parse_block(block)
        country = header.get("COUNTRY", "").strip()
        if not country:
            continue
        slug = slugify(country)
        title = header.get("TITLE", "").strip() or country

        if only and slug not in only:
            summary["skipped"].append(slug)
            continue

        html = md_to_html(body)
        if not html.strip():
            summary["errors"].append(f"{slug}: empty body after parse")
            continue

        page = find_page_by_slug(slug)
        if not page:
            msg = f"{slug}: no existing WP page"
            if not args.skip_missing:
                print(f"  ⚠  {msg}")
            summary["missing"].append(slug)
            continue

        if args.apply:
            try:
                update_page(page["id"], html, title=title)
                print(f"  ✓ {slug:30s} → page id {page['id']}")
                summary["updated"].append(slug)
            except Exception as e:
                print(f"  ✗ {slug}: {e}")
                summary["errors"].append(f"{slug}: {e}")
        else:
            print(f"  [dry-run] {slug:30s} → would update page id {page['id']} "
                  f"({len(html):,} chars HTML)")
            summary["updated"].append(slug)

    print("\n── Summary ─────────────────────────────")
    print(f"  Updated : {len(summary['updated'])}")
    print(f"  Missing : {len(summary['missing'])}  {summary['missing'] if summary['missing'] else ''}")
    print(f"  Skipped : {len(summary['skipped'])}")
    print(f"  Errors  : {len(summary['errors'])}")
    if summary["errors"]:
        for e in summary["errors"]:
            print(f"    - {e}")
    if not args.apply:
        print("\n  DRY RUN — re-run with --apply to write to WordPress.")


if __name__ == "__main__":
    main()
