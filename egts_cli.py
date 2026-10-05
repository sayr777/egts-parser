"""Root entry point — called by Excel VBA macro (ThisWorkbook.Path\\egts_cli.py)."""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from egts.cli import main

if __name__ == "__main__":
    main(sys.argv[1:])
