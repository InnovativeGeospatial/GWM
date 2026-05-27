#!/usr/bin/env python3
"""Prune conflict.json -- thin wrapper around prune_feed.py."""
import sys, os
sys.argv = [sys.argv[0], '--feed', 'conflict']
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from prune_feed import run
run('conflict')
