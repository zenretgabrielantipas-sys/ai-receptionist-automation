"""
Pytest configuration for AI Receptionist Automation tests.

Adds project root and src/ to sys.path for proper imports.
"""

import os
import sys

_src_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
_root_dir = os.path.dirname(_src_dir)

# Insert at position 0 so these paths take priority over rootdir
for _p in (_root_dir, _src_dir):
    if _p not in sys.path:
        sys.path.insert(0, _p)

pytest_plugins = ["pytest_asyncio"]
