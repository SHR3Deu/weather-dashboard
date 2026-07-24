#!/usr/bin/env python3

import shutil

import config

from utils.basemap import Basemap

from layers.debug import DebugLayer
from layers.cities import CitiesLayer
from layers.scale import ScaleLayer
from layers.radar import RadarLayer
# from layers.lightning import LightningLayer
# from layers.aircraft import AircraftLayer
# from layers.weather import WeatherLayer


LAYERS = {
    "debug": DebugLayer(),
    "cities": CitiesLayer(),
    "scale": ScaleLayer(),
    "radar": RadarLayer(),
    # "lightning": LightningLayer(),
    # "aircraft": AircraftLayer(),
    # "weather": WeatherLayer(),
}


def main():

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
