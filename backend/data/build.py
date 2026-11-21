"""One build for every engine (docs/architecture.md): easy, medium and hard.

    cd backend/data
    python build.py            # writes output/*.json and the QA reports
    python build.py --strict   # exit 1 if any engine left out a node or task with an error
"""
from __future__ import annotations

import sys

from easy import build as easy_build
from hard import build as hard_build
from medium import build as medium_build

ENGINES = {"easy": easy_build, "medium": medium_build, "hard": hard_build}


def main(argv=None) -> int:
    args = sys.argv[1:] if argv is None else argv
    status = 0
    for name, module in ENGINES.items():
        print(f"== {name}")
        status |= module.main(args)
    return status


if __name__ == "__main__":
    sys.exit(main())
