#!/usr/bin/env python3
"""
finish_structured_patch.py

Completes the structured-output patch by updating the two call sites
that Patch 5 couldn't match. Uses line-based editing instead of
string replacement.

Finds:
    <indent>article_body = generate_article(item)
and replaces with a 5-line tuple-unpacking block.

Finds:
    <indent>success = publish_to_wordpress(item, article_body)
and replaces with the parsed=parsed version.

Idempotent: safe to run multiple times. Detects already-patched state.
"""

import os
import re
import shutil
import sys
import ast

TARGET = "/opt/disaster-pipeline/run_disaster_pipeline.py"
BACKUP = TARGET + ".bak4"


def main():
    if not os.path.exists(TARGET):
        print("ERROR: target not found:", TARGET)
        sys.exit(1)

    shutil.copy2(TARGET, BACKUP)
    print("Backed up to:", BACKUP)

    with open(TARGET, "r") as f:
        lines = f.readlines()

    # Idempotency check
    src = "".join(lines)
    if "_gen_result = generate_article" in src or "parsed=parsed" in src:
        print("Already patched. No changes made.")
        sys.exit(0)

    # Find the line with article_body = generate_article(item)
    gen_pattern = re.compile(r"^(\s+)article_body\s*=\s*generate_article\(item\)\s*$")
    pub_pattern = re.compile(r"^(\s+)success\s*=\s*publish_to_wordpress\(item,\s*article_body\)\s*$")

    gen_idx = None
    gen_indent = None
    pub_idx = None
    pub_indent = None

    for i, line in enumerate(lines):
        m = gen_pattern.match(line)
        if m and gen_idx is None:
            gen_idx = i
            gen_indent = m.group(1)
        m2 = pub_pattern.match(line)
        if m2 and pub_idx is None:
            pub_idx = i
            pub_indent = m2.group(1)

    if gen_idx is None:
        print("ERROR: could not find 'article_body = generate_article(item)'")
        print("Restoring from backup.")
        shutil.copy2(BACKUP, TARGET)
        sys.exit(1)

    if pub_idx is None:
        print("ERROR: could not find 'success = publish_to_wordpress(item, article_body)'")
        print("Restoring from backup.")
        shutil.copy2(BACKUP, TARGET)
        sys.exit(1)

    print("Found generate_article call at line", gen_idx + 1, "with indent", repr(gen_indent))
    print("Found publish_to_wordpress call at line", pub_idx + 1, "with indent", repr(pub_indent))

    # Build the new generate_article block
    new_gen_block = [
        gen_indent + "_gen_result = generate_article(item)\n",
        gen_indent + "if isinstance(_gen_result, tuple):\n",
        gen_indent + "    raw_response, parsed = _gen_result\n",
        gen_indent + "else:\n",
        gen_indent + "    raw_response, parsed = _gen_result, None\n",
        gen_indent + 'article_body = parsed["body"] if (parsed and parsed.get("body")) else raw_response\n',
    ]

    # Build the new publish line
    new_pub_line = pub_indent + "success = publish_to_wordpress(item, article_body, parsed=parsed)\n"

    # Apply edits -- do publish first since it's later in the file
    # (so line index of gen_idx doesn't shift)
    if pub_idx > gen_idx:
        lines[pub_idx] = new_pub_line
        # Now replace gen line with 6 lines
        lines[gen_idx:gen_idx + 1] = new_gen_block
    else:
        lines[gen_idx:gen_idx + 1] = new_gen_block
        # gen expanded by 5 lines, shift pub_idx
        lines[pub_idx + 5] = new_pub_line

    new_src = "".join(lines)

    # Validate syntax
    try:
        ast.parse(new_src)
    except SyntaxError as e:
        print("SYNTAX ERROR after edits:", e)
        print("Restoring from backup.")
        shutil.copy2(BACKUP, TARGET)
        sys.exit(1)

    # Write
    with open(TARGET, "w") as f:
        f.write(new_src)

    print()
    print("APPLIED:")
    print("  - line", gen_idx + 1, ": unpacked generate_article() tuple")
    print("  - updated publish_to_wordpress() call to pass parsed=parsed")
    print()
    print("Valid Python. Backup at", BACKUP)
    print()
    print("Next:")
    print("  cd /opt/disaster-pipeline && set -a && source .env && set +a \\")
    print("    && venv/bin/python run_disaster_pipeline.py")


if __name__ == "__main__":
    main()
