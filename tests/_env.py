"""Point BlockForge at throwaway data before it is imported."""
import os
import tempfile

os.environ.setdefault("BLOCKFORGE_DATA", tempfile.mkdtemp(prefix="bf_test_"))
os.environ.setdefault("BLOCKFORGE_PORT", "8799")
