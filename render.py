#!/usr/bin/env python3

import shutil

import config
from layers.cities import CitiesLayer
from layers.clouds import CloudsLayer
from layers.debug import DebugLayer
from layers.radar import RadarLayer
from layers.scale import ScaleLayer
from utils.basemap import Basemap

# from layers.aircraft import AircraftLayer
# from layers.lightning import LightningLayer
# from layers.weather import WeatherLayer


# Pořadí je současně pořadím kreslení odspodu nahoru.
# 1) mapa
# 2) oblačnost
# 3) radar / srážky
# 4) popisky a měřítko
LAYERS = {
    "clouds": CloudsLayer(),
    "radar": RadarLayer(),
    "debug": DebugLayer(),
    "cities": CitiesLayer(),
    "scale": ScaleLayer(),
    # "lightning": LightningLayer(),
    # "aircraft": AircraftLayer(),
    # "weather": WeatherLayer(),
}


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

    if hasattr(config, "PUBLIC_FILE"):
        shutil.copy2(config.OUTPUT_FILE, config.PUBLIC_FILE)

    print(f"Saved : {config.OUTPUT_FILE}")

    if hasattr(config, "PUBLIC_FILE"):
        print(f"Copied: {config.PUBLIC_FILE}")


if __name__ == "__main__":
    main()
