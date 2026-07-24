#!/usr/bin/env python3

from pathlib import Path


#
# Adresáře
#

BASE_DIR = Path(__file__).parent

CACHE = BASE_DIR / "cache"
OUTPUT_DIR = BASE_DIR / "output"
RESOURCES = BASE_DIR / "resources"
LOGS = BASE_DIR / "logs"


#
# Výstupy
#

OUTPUT_FILE = OUTPUT_DIR / "weather.png"
PUBLIC_FILE = Path.home() / ".node-red" / "public" / "weather.png"


#
# Basemapa
#

BASEMAP_IMAGE = RESOURCES / "basemap" / f"z12.png"
BASEMAP_INFO = RESOURCES / "basemap" / f"z12.json"


#
# Rozměry mapy
#

MAP_WIDTH = 1600
MAP_HEIGHT = 960


#
# Poloha mapy  16.4978017&y=49.9949023
#

CENTER_LAT = 49.9949023
CENTER_LON = 16.4978017

ZOOM = 12


#
# Vrstvy
#

LAYERS = {
    "debug": True,
    "cities": True,
    "scale": True,
    "radar": True,
    "lightning": True,
    "aircraft": True,
    "weather": True,
}
