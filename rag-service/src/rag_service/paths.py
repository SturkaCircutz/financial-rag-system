import os
from pathlib import Path


def data_root() -> Path:
    configured_root = os.getenv("RAG_DATA_ROOT")
    if configured_root:
        return Path(configured_root)

    return Path(__file__).resolve().parents[2] / "data"
