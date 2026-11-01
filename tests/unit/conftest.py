"""Expose Collection source for local unit tests; acceptance uses installed packages only."""
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for name, path in (("ansible_collections", ROOT.parent.parent),
                   ("ansible_collections.cloudchef", ROOT.parent),
                   ("ansible_collections.cloudchef.smartcmp", ROOT)):
    module = types.ModuleType(name)
    module.__path__ = [str(path)]
    sys.modules[name] = module
