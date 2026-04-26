#!/usr/bin/env python3
"""
fix_persecution_redaction.py

Replaces the single "Replace individual names with..." line in the
persecution pipeline's STRICT RULES with a fuller redaction block
covering personal names, church names, local denominations, and
sub-national locations.

AST-validates; restores backup on syntax error.
"""
import ast
import shutil
import sys
from pathlib import Path
from datetime import datetime

TARGET = Path("/opt/global-witness/run_pipeline.py")
BACKUP = Path(f"/opt/global-witness/run_pipeline.py.bak.{datetime.now():%Y%m%d_%H%M%S}")

OLD_LINE = '"- Replace individual names with: man, woman, pastor, bishop, girl, boy, family, group, convert, believer\\n"'

NEW_BLOCK = (
    '"- Redact identifying details to protect local communities:\\n"\n'
    '        "  - No personal names (replace with: man, woman, pastor, bishop, girl, boy, family, group, convert, believer)\\n"\n'
    '        "  - No specific church names (e.g. \'Linfen Covenant Home Church\' -> \'a house church\')\\n"\n'
    '        "  - No specific local ministry or denomination names within the country (e.g. \'Three-Self Patriotic Movement\' -> \'a state-sanctioned church body\')\\n"\n'
    '        "  - No towns, villages, counties, districts, or provinces (use the country only, or generic phrasing like \'a rural area\' or \'a northern province\')\\n"\n'
    '        "  - You MAY name the external reporting watchdog (e.g. \'according to ChinaAid\', \'according to Open Doors\') since those are not local community identifiers\\n"\n'
    '        "- These redaction rules apply EVEN IF the source material includes the specific names. Redaction is required, not optional.\\n"'
)


def main():
    if not TARGET.exists():
        sys.exit(f"ERROR: {TARGET} not found")

    src = TARGET.read_text()
    shutil.copy2(TARGET, BACKUP)
    print(f"Backup: {BACKUP}")

    if "Redact identifying details to protect local communities" in src:
        print("Skip: redaction block already present")
        return

    if OLD_LINE not in src:
        shutil.copy2(BACKUP, TARGET)
        sys.exit("ERROR: could not find expected line. Restored backup.\n"
                 "Looked for:\n  " + OLD_LINE)

    src = src.replace(OLD_LINE, NEW_BLOCK, 1)
    print("Replaced: redaction rule")

    try:
        ast.parse(src)
    except SyntaxError as e:
        shutil.copy2(BACKUP, TARGET)
        sys.exit(f"ERROR: AST validation failed: {e}\nRestored from backup.")

    TARGET.write_text(src)
    print(f"OK: wrote {TARGET}")
    print()
    print("Verify with:")
    print("  grep -n 'Redact identifying details' /opt/global-witness/run_pipeline.py")


if __name__ == "__main__":
    main()
