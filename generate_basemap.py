#!/usr/bin/env python3

import json
import math
from pathlib import Path

from PIL import Image

import config
from utils.tiles import download_tile, TILE_SIZE
from utils.projection import latlon_to_world_pixel


def main():

    # ------------------------------------------------------------
    # Střed mapy ve světových pixelech
    # ------------------------------------------------------------

    center_x, center_y = latlon_to_world_pixel(
        config.CENTER_LAT,
        config.CENTER_LON,
        config.ZOOM,
    )

    # ------------------------------------------------------------
    # Kolik dlaždic potřebujeme
    # (+2 jako rezerva kolem viewportu)
    # ------------------------------------------------------------

    cols = math.ceil(config.MAP_WIDTH / TILE_SIZE) + 3
    rows = math.ceil(config.MAP_HEIGHT / TILE_SIZE) + 3

    # ------------------------------------------------------------
    # Levý horní roh viewportu
    # ------------------------------------------------------------

    left_world = center_x - config.MAP_WIDTH / 2
    top_world = center_y - config.MAP_HEIGHT / 2

    # ------------------------------------------------------------
    # Začínající dlaždice
    # ------------------------------------------------------------

    start_tile_x = int(left_world // TILE_SIZE)
    start_tile_y = int(top_world // TILE_SIZE)

    # ------------------------------------------------------------
    # Vytvoření mozaiky
    # ------------------------------------------------------------

    canvas = Image.new(
        "RGB",
        (
            cols * TILE_SIZE,
            rows * TILE_SIZE,
        ),
    )

    for row in range(rows):

        for col in range(cols):

            tile = download_tile(
                config.ZOOM,
                start_tile_x + col,
                start_tile_y + row,
            )

            canvas.paste(
                tile,
                (
                    col * TILE_SIZE,
                    row * TILE_SIZE,
                ),
            )

    # ------------------------------------------------------------
    # Výstupní adresář
    # ------------------------------------------------------------

    out_dir = config.RESOURCES / "basemap"
    out_dir.mkdir(parents=True, exist_ok=True)

    image_file = out_dir / f"z{config.ZOOM}.png"
    meta_file = out_dir / f"z{config.ZOOM}.json"

    canvas.save(image_file)

    # ------------------------------------------------------------
    # Metadata
    # ------------------------------------------------------------

    metadata = {

        "zoom": config.ZOOM,

        "tile_origin_x": start_tile_x,
        "tile_origin_y": start_tile_y,

        "tiles_x": cols,
        "tiles_y": rows,

        "tile_size": TILE_SIZE,

        "width": canvas.width,
        "height": canvas.height,

        "center_lat": config.CENTER_LAT,
        "center_lon": config.CENTER_LON,

        "center_world_x": center_x,
        "center_world_y": center_y,

    }

    with open(meta_file, "w", encoding="utf-8") as f:
        json.dump(
            metadata,
            f,
            indent=4,
        )

    print(f"Saved image : {image_file}")
    print(f"Saved meta  : {meta_file}")


if __name__ == "__main__":
    main()
