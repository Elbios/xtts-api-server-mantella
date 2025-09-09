# run_server.py
import os, sys, types

import runpy
from pathlib import Path

# Ensure required folders exist next to the exe
base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
for d in ["speakers", "output", "xtts_models"]:
    (base / d).mkdir(parents=True, exist_ok=True)

# Point the server at our bundled folders
default_args = [
    "--device", "cuda",
    "--host", "0.0.0.0",   # or omit if you want localhost only
    "--port", "8020",
    "--model-folder", str(base / "xtts_models"),
    "--speaker-folder", str(base / "speakers"),
    "--output", str(base / "output"),
    "--listen"            # exposes on your LAN; remove if you want only localhost
]

# Append defaults if the user didn't pass their own
if len(sys.argv) == 1:
    sys.argv.extend(default_args)

# Run the package as if: python -m xtts_api_server
runpy.run_module("xtts_api_server", run_name="__main__")
