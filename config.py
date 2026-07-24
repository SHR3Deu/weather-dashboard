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
BASEMAP_IMAGE = RESOURCES / "basemap" / "z12.png"
BASEMAP_INFO = RESOURCES / "basemap" / "z12.json"


#
# Rozměry mapy
#
MAP_WIDTH = 1600
MAP_HEIGHT = 960


#
# Poloha mapy
#
CENTER_LAT = 49.9949023
CENTER_LON = 16.4978017
ZOOM = 12


#
# Vrstvy
#
LAYERS = {
    "clouds": True,
    "radar": True,
    "debug": True,
    "cities": True,
    "scale": True,
    "lightning": True,
    "aircraft": True,
    "weather": True,
}


#
# Radar ČHMÚ
#
RADAR_MIN_VISIBLE_DBZ = 0.0
RADAR_SAVE_DEBUG_LAYER = True
RADAR_DEBUG_FILE = OUTPUT_DIR / "latest_radar.png"


#
# Oblačnost ČHMÚ
#
# Přes den se přednostně používá VIS-IR. Pokud není aktuální,
# použije se infračervený snímek IR 10.8.
CLOUDS_PRODUCTS = ("vis-ir", "ir108")
CLOUDS_REGION = "cz"
CLOUDS_INDEX_BASE_URL = (
    "https://opendata.chmi.cz/meteorology/weather/satellite/geo"
)
CLOUDS_REQUEST_TIMEOUT = (10, 30)

# Přibližné zeměpisné hranice obrazu ČHMÚ s označením "cz".
# Pro HMI pozadí je tato přesnost dostačující. Po prvním vykreslení
# je možné hranice jemně doladit podle shody oblačnosti s mapou.
CLOUDS_SOURCE_NORTH = 53.0
CLOUDS_SOURCE_WEST = 11.0
CLOUDS_SOURCE_SOUTH = 47.0
CLOUDS_SOURCE_EAST = 20.0

# Vzhled oblačnosti nad mapou.
CLOUDS_PRODUCT = "vis-ir"
CLOUDS_MAX_AGE_MINUTES = 45

CLOUDS_OPACITY = 0.38
CLOUDS_GAMMA = 1.05
CLOUDS_MIN_STRENGTH = 0.035
CLOUDS_BASE_BRIGHTNESS = 24.0

CLOUDS_SOURCE_BLUR_RADIUS = 1.2
CLOUDS_BACKGROUND_BLUR_RADIUS = 24.0
CLOUDS_PROJECTED_BLUR_RADIUS = 4.0

CLOUDS_REQUEST_TIMEOUT = (10, 30)


# Ladicí výstupy.
CLOUDS_SAVE_DEBUG_LAYER = True
CLOUDS_DEBUG_FILE = OUTPUT_DIR / "latest_clouds.png"
CLOUDS_PREVIEW_FILE = OUTPUT_DIR / "latest_clouds_preview.png"
CLOUDS_SOURCE_DEBUG_FILE = OUTPUT_DIR / "latest_clouds_source.jpg"

LAYERS["clouds"] = True


