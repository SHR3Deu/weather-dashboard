#!/usr/bin/env python3

import argparse
import json
import math

from PIL import Image, ImageEnhance

import config
from utils.projection import latlon_to_world_pixel
from utils.tiles import TILE_SIZE, download_tile, get_style_config


def output_paths(style: str, style_config: dict):
    output_dir = config.RESOURCES / "basemap"
    extension = style_config["extension"]

    return (
        output_dir / f"{style}_z{config.ZOOM}.{extension}",
        output_dir / f"{style}_z{config.ZOOM}.json",
    )


def adjust_image(canvas: Image.Image, style_config: dict) -> Image.Image:
    """Použije nastavení jasu, kontrastu a barev daného podkladu."""
    result = canvas

    brightness = float(style_config.get("brightness", 1.0))
    contrast = float(style_config.get("contrast", 1.0))
    color = float(style_config.get("color", 1.0))

    if brightness != 1.0:
        result = ImageEnhance.Brightness(result).enhance(brightness)

    if contrast != 1.0:
        result = ImageEnhance.Contrast(result).enhance(contrast)

    if color != 1.0:
        result = ImageEnhance.Color(result).enhance(color)

    return result


def generate_style(style: str):
    selected_style, style_config = get_style_config(style)

    center_x, center_y = latlon_to_world_pixel(
        config.CENTER_LAT,
        config.CENTER_LON,
        config.ZOOM,
    )

    # Rezerva kolem viewportu, aby bylo možné výřez mírně posouvat.
    cols = math.ceil(config.MAP_WIDTH / TILE_SIZE) + 3
    rows = math.ceil(config.MAP_HEIGHT / TILE_SIZE) + 3

    left_world = center_x - config.MAP_WIDTH / 2
    top_world = center_y - config.MAP_HEIGHT / 2

    start_tile_x = int(left_world // TILE_SIZE)
    start_tile_y = int(top_world // TILE_SIZE)

    canvas = Image.new(
        "RGB",
        (cols * TILE_SIZE, rows * TILE_SIZE),
    )

    for row in range(rows):
        for col in range(cols):
            tile = download_tile(
                config.ZOOM,
                start_tile_x + col,
                start_tile_y + row,
                style=selected_style,
            )
            canvas.paste(
                tile,
                (col * TILE_SIZE, row * TILE_SIZE),
            )

    canvas = adjust_image(canvas, style_config)

    image_file, meta_file = output_paths(selected_style, style_config)
    image_file.parent.mkdir(parents=True, exist_ok=True)

    save_options = {}
    if style_config["format"].upper() == "JPEG":
        save_options = {"quality": 92, "optimize": True}

    canvas.save(
        image_file,
        format=style_config["format"],
        **save_options,
    )

    metadata = {
        "style": selected_style,
        "style_name": style_config["name"],
        "attribution": style_config.get("attribution", ""),
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
        "brightness": style_config.get("brightness", 1.0),
        "contrast": style_config.get("contrast", 1.0),
        "color": style_config.get("color", 1.0),
    }

    with open(meta_file, "w", encoding="utf-8") as file:
        json.dump(metadata, file, indent=4, ensure_ascii=False)

    print(f"Saved image : {image_file}")
    print(f"Saved meta  : {meta_file}")


def parse_args():
    styles = sorted(config.BASEMAP_STYLES)

    parser = argparse.ArgumentParser(
        description="Vygeneruje statický mapový podklad pro weather-dashboard.",
    )
    parser.add_argument(
        "style",
        nargs="?",
        default=config.BASEMAP_STYLE,
        choices=styles + ["all"],
        help=(
            "Podklad k vygenerování. Bez argumentu se použije "
            "BASEMAP_STYLE z config.py."
        ),
    )

    return parser.parse_args()


def main():
    args = parse_args()

    if args.style == "all":
        for style in sorted(config.BASEMAP_STYLES):
            print(f"Generating basemap: {style}")
            generate_style(style)
    else:
        generate_style(args.style)


if __name__ == "__main__":
    main()
