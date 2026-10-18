"""Run BlockForge from source (the installed app uses BlockForge.exe instead)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from blockforge import app_main  # noqa: E402

app_main.main()
