import os

# No background refresh thread during tests.
os.environ.setdefault("WEAVE_BACKGROUND", "0")
