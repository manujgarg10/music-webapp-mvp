from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
DOWNLOADS_DIR = DATA_DIR / "downloads"
NORMALIZED_DIR = DATA_DIR / "normalized"
SEPARATED_DIR = DATA_DIR / "separated"
RENDERED_DIR = DATA_DIR / "rendered"
STATIC_DIR = ROOT_DIR / "app" / "static"


SUPPORTED_INSTRUMENTS = ("guitar", "vocals", "bass", "drums")


def ensure_directories() -> None:
    for path in (
        DATA_DIR,
        DOWNLOADS_DIR,
        NORMALIZED_DIR,
        SEPARATED_DIR,
        RENDERED_DIR,
        STATIC_DIR,
    ):
        path.mkdir(parents=True, exist_ok=True)

