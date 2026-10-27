#!/usr/bin/env python3
"""Run this direct benchmark with the shared native-session supervisor."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'rigorous-proof/nl0/scripts'))
from direct_runner import main
if __name__=='__main__':main(default_work=Path(__file__).parent)
