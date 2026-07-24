from pathlib import Path
import requests
from PIL import Image

import config

TILE_SIZE = 256

CACHE_DIR = config.CACHE / "tiles"


def tile_filename(z: int, x: int, y: int) -> Path:
    """Vrátí cestu k souboru dlaždice v cache."""
    return CACHE_DIR / str(z) / str(x) / f"{y}.png"


def download_tile(z: int, x: int, y: int) -> Image.Image:
    """
    Stáhne jednu OpenTopoMap dlaždici nebo ji načte z cache.
    """

    filename = tile_filename(z, x, y)

    if filename.exists():
        return Image.open(filename).convert("RGB")

    filename.parent.mkdir(parents=True, exist_ok=True)

    url = f"https://tile.opentopomap.org/{z}/{x}/{y}.png"

    print(f"Downloading {z}/{x}/{y}")

    response = requests.get(url, timeout=20)
    response.raise_for_status()

    filename.write_bytes(response.content)

    return Image.open(filename).convert("RGB")
