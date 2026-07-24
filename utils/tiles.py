from io import BytesIO
from pathlib import Path

import requests
from PIL import Image

import config


TILE_SIZE = 256
CACHE_DIR = config.CACHE / "tiles"


def get_style_config(style: str | None = None) -> tuple[str, dict]:
    """Vrátí název a konfiguraci zvoleného mapového podkladu."""
    selected_style = style or config.BASEMAP_STYLE

    if selected_style not in config.BASEMAP_STYLES:
        allowed = ", ".join(sorted(config.BASEMAP_STYLES))
        raise ValueError(
            f"Neznámý BASEMAP_STYLE '{selected_style}'. "
            f"Povolené hodnoty: {allowed}."
        )

    return selected_style, config.BASEMAP_STYLES[selected_style]


def tile_filename(
    z: int,
    x: int,
    y: int,
    style: str | None = None,
) -> Path:
    """Vrátí cestu dlaždice v cache oddělené podle stylu."""
    selected_style, style_config = get_style_config(style)
    extension = style_config["extension"]

    return (
        CACHE_DIR
        / selected_style
        / str(z)
        / str(x)
        / f"{y}.{extension}"
    )


def download_tile(
    z: int,
    x: int,
    y: int,
    style: str | None = None,
) -> Image.Image:
    """Stáhne jednu dlaždici nebo ji načte z lokální cache."""
    selected_style, style_config = get_style_config(style)

    tile_count = 2 ** z
    wrapped_x = x % tile_count

    if y < 0 or y >= tile_count:
        return Image.new("RGB", (TILE_SIZE, TILE_SIZE), (0, 0, 0))

    filename = tile_filename(z, wrapped_x, y, selected_style)

    if filename.exists():
        return Image.open(filename).convert("RGB")

    filename.parent.mkdir(parents=True, exist_ok=True)

    url = style_config["url"].format(
        z=z,
        x=wrapped_x,
        y=y,
    )

    print(f"Downloading {selected_style} {z}/{wrapped_x}/{y}")

    response = requests.get(
        url,
        headers={"User-Agent": config.BASEMAP_USER_AGENT},
        timeout=config.BASEMAP_REQUEST_TIMEOUT,
    )
    response.raise_for_status()

    try:
        tile = Image.open(BytesIO(response.content)).convert("RGB")
        tile.load()
    except Exception as error:
        raise RuntimeError(
            f"Stažená dlaždice není platný obrázek: {url}"
        ) from error

    if tile.size != (TILE_SIZE, TILE_SIZE):
        tile = tile.resize(
            (TILE_SIZE, TILE_SIZE),
            Image.Resampling.BILINEAR,
        )

    save_options = {}
    if style_config["format"].upper() == "JPEG":
        save_options = {"quality": 92, "optimize": True}

    temporary_file = filename.with_suffix(filename.suffix + ".tmp")
    tile.save(
        temporary_file,
        format=style_config["format"],
        **save_options,
    )
    temporary_file.replace(filename)

    return tile
