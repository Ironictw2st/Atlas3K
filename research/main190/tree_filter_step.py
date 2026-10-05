#!/usr/bin/env python3
"""Atlas3K custom build step: drop compiled trees on town / road / lake hexes (tree_clear.tree_mask) from the
campaign tree list the native trees step wrote. Same as the inline filter in kit_edits_build.sh.
Usage: python tree_filter_step.py <trees.campaign_tree_list>"""
import sys
from pathlib import Path
from tree_clear import tree_mask, filter_tree_list

m, wh = tree_mask()
filter_tree_list(Path(sys.argv[1]), m, wh)
