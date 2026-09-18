"""Streaming file checksums."""

from hashlib import sha256
from pathlib import Path


def file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        while block := stream.read(64 * 1024):
            digest.update(block)
    return digest.hexdigest()
