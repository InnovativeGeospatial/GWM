#!/usr/bin/env python3
"""
Add skip-reason diagnostic to conflict pipeline's is_valid_article.
Prints WHY each article was rejected so we can tune BAD_RESPONSE_PATTERNS
or word_count threshold.
"""
import re
import ast
import shutil
import sys
from pathlib import Path

TARGET = Path("/opt/conflict-pipeline/run_conflict_pipeline.py")
BACKUP = Path("/opt/conflict-pipeline/run_conflict_pipeline.py.bak_skipreason")

if not TARGET.exists():
    print(f"ERROR: {TARGET} not found")
    sys.exit(1)

src = TARGET.read_text()
shutil.copy(TARGET, BACKUP)
print(f"Backed up to: {BACKUP}\n")

# Find the is_valid_article function and replace it
# Match: def is_valid_article(article_body): ... return True
pattern = re.compile(
    r"def is_valid_article\(article_body\):\n"
    r"(?:    .*\n)+?"
    r"    return True\n",
    re.MULTILINE,
)

new_func = '''def is_valid_article(article_body):
    lower = article_body.lower()
    for pattern in BAD_RESPONSE_PATTERNS:
        if pattern in lower:
            logger.info(f"INVALID_REASON: matched bad pattern '{pattern}'")
            return False
    word_count = len(article_body.split())
    if word_count < 80:
        preview = article_body[:200].replace("\\n", " ")
        logger.info(f"INVALID_REASON: word_count={word_count} preview='{preview}'")
        return False
    return True
'''

m = pattern.search(src)
if not m:
    print("ERROR: could not find is_valid_article function")
    sys.exit(1)

src2 = src[:m.start()] + new_func + src[m.end():]

# Validate
try:
    ast.parse(src2)
except SyntaxError as e:
    print(f"ERROR: syntax error in patched file: {e}")
    shutil.copy(BACKUP, TARGET)
    print("Restored backup.")
    sys.exit(1)

TARGET.write_text(src2)
print("Applied: is_valid_article now logs skip reasons\n")
print("Re-run pipeline to see reasons:")
print("  cd /opt/conflict-pipeline && set -a && source .env && set +a && venv/bin/python run_conflict_pipeline.py")
