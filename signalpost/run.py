from __future__ import annotations

import os
import sys

from .runner import run


if __name__ == "__main__":
    input_path = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("SIGNALPOST_INPUT", "data/demo_companies.jsonl")
    raise SystemExit(run(input_path))
