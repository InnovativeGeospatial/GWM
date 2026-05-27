#!/usr/bin/env python3
"""Prune disasters.json -- thin wrapper around prune_feed.py."""
import sys, os
sys.argv = [sys.argv[0], '--feed', 'disasters']
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from prune_feed import run
run('disasters')
