from pathlib import Path
import os
import sys


def project_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[3]


def data_root() -> Path:
    path = Path(os.environ.get("MAHJONG_ASSISTANT_DATA", str(project_root() / "data")))
    path.mkdir(parents=True, exist_ok=True)
    return path

