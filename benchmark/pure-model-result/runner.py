#!/usr/bin/env python3
"""Run this direct benchmark with the shared native-session supervisor."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'rigorous-proof/nl0/scripts'))
from direct_runner import main
from prompt import render
if __name__=='__main__':
    main(default_work=Path(__file__).resolve().parent,prompt_factory=render,
         default_paper=Path(__file__).resolve().parents[1]/'aim-518-kdv-log-loss.pdf')
