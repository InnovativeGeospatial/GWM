#!/usr/bin/env python3
"""
Patch /opt/disaster-pipeline/run_disaster_pipeline.py:
1. Sanitize titles (decode HTML entities, replace en/em dashes with commas)
2. Embed gwm-disaster-meta div in post content for dashboard type detection

AST-validates before writing. Restores from backup on syntax error.
"""
import ast
import shutil
import sys
import re
from pathlib import Path
from datetime import datetime

TARGET = Path("/opt/disaster-pipeline/run_disaster_pipeline.py")
BACKUP = Path(f"/opt/disaster-pipeline/run_disaster_pipeline.py.bak.{datetime.now():%Y%m%d_%H%M%S}")


def main():
    if not TARGET.exists():
        sys.exit(f"ERROR: {TARGET} not found")

    src = TARGET.read_text()

    # Backup first
    shutil.copy2(TARGET, BACKUP)
    print(f"Backup: {BACKUP}")

    # --- Ensure `import html` is present ---
    if not re.search(r"^import html\b", src, re.MULTILINE):
        # Insert after the last top-level `import` near the top
        lines = src.splitlines(keepends=True)
        insert_at = 0
        for i, line in enumerate(lines[:50]):
            if re.match(r"^(import |from )", line):
                insert_at = i + 1
        lines.insert(insert_at, "import html\n")
        src = "".join(lines)
        print("Added: import html")
    else:
        print("Already imported: html")

    # --- Add sanitize_title helper if missing ---
    if "def sanitize_title(" not in src:
        helper = '''

def sanitize_title(title):
    """Decode HTML entities and replace en/em dashes with commas."""
    if not title:
        return title
    t = html.unescape(title)
    t = t.replace("\\u2013", ", ").replace("\\u2014", ", ")
    t = re.sub(r"\\s+", " ", t).strip()
    return t
'''
        # Insert helper before the publish_to_wordpress definition
        m = re.search(r"^def publish_to_wordpress\b", src, re.MULTILINE)
        if not m:
            sys.exit("ERROR: publish_to_wordpress() not found")
        src = src[:m.start()] + helper.lstrip("\n") + "\n" + src[m.start():]
        print("Added: sanitize_title()")
    else:
        print("Already present: sanitize_title()")

    # Make sure `re` is imported (sanitize_title uses it)
    if not re.search(r"^import re\b", src, re.MULTILINE):
        src = "import re\n" + src
        print("Added: import re")

    # --- Patch publish_to_wordpress to sanitize title + inject meta div ---
    # Find the function body and insert sanitization + meta-div construction
    # at the top of the function. We look for the def line and insert after it.
    pattern = re.compile(
        r"(def publish_to_wordpress\([^)]*\):\s*\n"
        r"(?:[ \t]*\"\"\".*?\"\"\"\s*\n)?)",
        re.DOTALL,
    )

    sentinel = "# --- GWM patch: title sanitize + meta div ---"
    if sentinel in src:
        print("Already patched: publish_to_wordpress body")
    else:
        m = pattern.search(src)
        if not m:
            shutil.copy2(BACKUP, TARGET)
            sys.exit("ERROR: could not locate publish_to_wordpress signature")

        # Determine indentation by looking at the next non-blank line after match
        tail = src[m.end():]
        indent_match = re.match(r"([ \t]+)\S", tail)
        indent = indent_match.group(1) if indent_match else "    "

        injection = (
            f"{indent}{sentinel}\n"
            f"{indent}try:\n"
            f"{indent}    title = sanitize_title(title)\n"
            f"{indent}except Exception:\n"
            f"{indent}    pass\n"
            f"{indent}try:\n"
            f"{indent}    _country = (parsed.get('country') or '') if isinstance(parsed, dict) else ''\n"
            f"{indent}    _dtype   = (parsed.get('disaster_type') or '') if isinstance(parsed, dict) else ''\n"
            f"{indent}    _lat     = (parsed.get('lat') or parsed.get('latitude') or '') if isinstance(parsed, dict) else ''\n"
            f"{indent}    _lng     = (parsed.get('lng') or parsed.get('lon') or parsed.get('longitude') or '') if isinstance(parsed, dict) else ''\n"
            f"{indent}    _meta_div = (\n"
            f"{indent}        '<div class=\"gwm-disaster-meta\" '\n"
            f"{indent}        'data-country=\"' + str(_country) + '\" '\n"
            f"{indent}        'data-type=\"' + str(_dtype) + '\" '\n"
            f"{indent}        'data-lat=\"' + str(_lat) + '\" '\n"
            f"{indent}        'data-lng=\"' + str(_lng) + '\" '\n"
            f"{indent}        'style=\"display:none;\"></div>\\n'\n"
            f"{indent}    )\n"
            f"{indent}    if isinstance(content, str) and 'gwm-disaster-meta' not in content:\n"
            f"{indent}        content = _meta_div + content\n"
            f"{indent}except Exception as _e:\n"
            f"{indent}    pass\n"
        )

        src = src[:m.end()] + injection + src[m.end():]
        print("Patched: publish_to_wordpress (title + meta div)")

    # --- AST validate ---
    try:
        ast.parse(src)
    except SyntaxError as e:
        shutil.copy2(BACKUP, TARGET)
        sys.exit(f"ERROR: AST validation failed: {e}\nRestored from backup.")

    TARGET.write_text(src)
    print(f"OK: wrote {TARGET}")
    print("Run: python3 -c 'import ast; ast.parse(open(\"/opt/disaster-pipeline/run_disaster_pipeline.py\").read()); print(\"AST OK\")'")


if __name__ == "__main__":
    main()
