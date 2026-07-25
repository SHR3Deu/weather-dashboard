#!/usr/bin/env python3

import shutil

from PIL import Image

import config
from layers.aircraft import AircraftLayer
from layers.cities import CitiesLayer
from layers.clouds import CloudsLayer
from layers.debug import DebugLayer
from layers.radar import RadarLayer
from layers.scale import ScaleLayer
from utils.basemap import Basemap

# from layers.lightning import LightningLayer
# from layers.weather import WeatherLayer


# Pořadí je současně pořadím kreslení odspodu nahoru.
# 1) mapa
# 2) oblačnost
# 3) radar / srážky
# 4) debug a města
# 5) letadla a jejich trajektorie
# 6) měřítko úplně nahoře
LAYERS = {
    "clouds": CloudsLayer(),
    "radar": RadarLayer(),
    "debug": DebugLayer(),
    "cities": CitiesLayer(),
    "aircraft": AircraftLayer(),
    "scale": ScaleLayer(),
    # "lightning": LightningLayer(),
    # "weather": WeatherLayer(),
}


def build_hmi_image(source_image):
    hmi_width = int(getattr(config, "HMI_WIDTH", 0))
    hmi_height = int(getattr(config, "HMI_HEIGHT", 0))

    if hmi_width <= 0 or hmi_height <= 0:
        raise ValueError("HMI_WIDTH a HMI_HEIGHT musí být kladná čísla.")

    if source_image.size == (hmi_width, hmi_height):
        return source_image.copy()

    return source_image.resize(
        (hmi_width, hmi_height),
        Image.Resampling.LANCZOS,
    )


def main():
    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if hasattr(config, "PUBLIC_FILE"):
        config.PUBLIC_FILE.parent.mkdir(parents=True, exist_ok=True)

    basemap = Basemap()
    basemap.load()

    canvas = basemap.viewport()

    for name, layer in LAYERS.items():
        if not config.LAYERS.get(name, True):
            continue

        print(f"Drawing {name}")
        layer.draw(canvas, basemap)

    canvas.save(config.OUTPUT_FILE)
    print(f"Saved full-size : {config.OUTPUT_FILE}")

    hmi_image = build_hmi_image(canvas)
    hmi_output_file = getattr(
        config,
        "HMI_OUTPUT_FILE",
        config.OUTPUT_DIR / "weather_hmi.png",
    )
    hmi_image.save(hmi_output_file)
    print(
        "Saved HMI      : "
        f"{hmi_output_file} ({config.HMI_WIDTH}x{config.HMI_HEIGHT})"
    )

    if hasattr(config, "PUBLIC_FILE"):
        shutil.copy2(hmi_output_file, config.PUBLIC_FILE)
        print(f"Copied         : {config.PUBLIC_FILE}")


if __name__ == "__main__":
    main()
