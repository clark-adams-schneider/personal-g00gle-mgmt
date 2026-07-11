import hashlib
import os
from typing import Optional


def get_file_hash(filepath: str) -> Optional[str]:
    """Calculate MD5 hash of a local file for change tracking."""
    if not os.path.exists(filepath):
        return None
    hasher = hashlib.md5()
    with open(filepath, "rb") as f:
        buf = f.read(65536)
        while len(buf) > 0:
            hasher.update(buf)
            buf = f.read(65536)
    return hasher.hexdigest()
