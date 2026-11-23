import os
import tempfile

# Set before any test imports algoguard.commitment, so tests never create or read the real rules_lock.json.
os.environ.setdefault("ALGOGUARD_LOCK", os.path.join(tempfile.mkdtemp(), "rules_lock.json"))
