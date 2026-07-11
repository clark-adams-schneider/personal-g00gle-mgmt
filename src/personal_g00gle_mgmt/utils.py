import hashlib
from pathlib import Path
from typing import Optional


def get_file_hash(filepath: Optional[Path]) -> Optional[str]:
    """Calculate MD5 hash of a local file for change tracking."""
    if not filepath or not filepath.exists():
        return None
    hasher = hashlib.md5()
    with filepath.open("rb") as f:
        buf = f.read(65536)
        while len(buf) > 0:
            hasher.update(buf)
            buf = f.read(65536)
    return hasher.hexdigest()


def generate_resource_name(tree_name: str, resource_id: str) -> str:
    """Generate a clean Pulumi resource name by replacing dashes and spaces with underscores."""
    return f"{tree_name}-{resource_id}".replace("-", "_").replace(" ", "_")
