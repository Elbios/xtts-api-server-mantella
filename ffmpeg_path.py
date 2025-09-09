# ffmpeg_path.py
import os, sys
from pathlib import Path

root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
dll_dir = root / "ffmpeg"   # we'll place DLLs in dist\...\ffmpeg

try:
    os.add_dll_directory(str(dll_dir))  # Python 3.8+
except Exception:
    os.environ["PATH"] = str(dll_dir) + os.pathsep + os.environ.get("PATH", "")
