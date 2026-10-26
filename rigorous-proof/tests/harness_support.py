"""Shared test paths and synthetic profiles; never imported by the runtime."""
from pathlib import Path
import sys

TESTS = Path(__file__).resolve().parent
CORE = TESTS.parent
LEAN = CORE / 'nl02lean'
FIXTURES = TESTS / 'fixtures'

# Every test can be selected independently; no earlier test import is required.
for directory in (CORE / 'nl0/scripts', LEAN / 'scripts', TESTS / 'tooling'):
    value = str(directory)
    if value not in sys.path:
        sys.path.insert(0, value)

PROFILES={'nl0':{'id':'gpt-6.1-sol','reasoning_effort':'high','speed':'standard','automatic_fallback':False},
          'lean':{'id':'gpt-6-luna','reasoning_effort':'medium','speed':'standard','automatic_fallback':False}}
