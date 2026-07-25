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
# Rozměry a poloha mapy
#
MAP_WIDTH = 1600
MAP_HEIGHT = 960
CENTER_LAT = 49.9949023
CENTER_LON = 16.4978017
ZOOM = 12


#
# Podkladová mapa
#
# Povolené hodnoty:
#   "topographic" - současná turistická OpenTopoMap
#   "satellite"   - satelitní Esri World Imagery
BASEMAP_STYLE = "topographic"

BASEMAP_STYLES = {
    "topographic": {
        "name": "OpenTopoMap",
        "url": "https://tile.opentopomap.org/{z}/{x}/{y}.png",
        "extension": "png",
        "format": "PNG",
        "brightness": 1.00,
        "contrast": 1.00,
        "color": 1.00,
        "attribution": (
            "© OpenStreetMap přispěvatelé, SRTM | "
            "© OpenTopoMap (CC-BY-SA)"
        ),
    },
    "satellite": {
        "name": "Esri World Imagery",
        # ArcGIS používá pořadí z / y / x.
        "url": (
            "https://services.arcgisonline.com/ArcGIS/rest/services/"
            "World_Imagery/MapServer/tile/{z}/{y}/{x}"
        ),
        "extension": "jpg",
        "format": "JPEG",
        # Záměrně lehce ztmaveno kvůli kontrastu oblačnosti a radaru.
        "brightness": 0.70,
        "contrast": 0.92,
        "color": 0.88,
        "attribution": "Zdroj podkladu: Esri World Imagery",
    },
}

BASEMAP_REQUEST_TIMEOUT = (10, 30)
BASEMAP_USER_AGENT = (
    "weather-dashboard/1.0 "
    "(+https://github.com/SHR3Deu/weather-dashboard)"
)
BASEMAP_SHOW_ATTRIBUTION = True
BASEMAP_ATTRIBUTION_FONT_SIZE = 13

# Odvozené cesty aktivní podkladové mapy.
BASEMAP_IMAGE = (
    RESOURCES
    / "basemap"
    / f"{BASEMAP_STYLE}_z{ZOOM}."
    f"{BASEMAP_STYLES[BASEMAP_STYLE]['extension']}"
)
BASEMAP_INFO = (
    RESOURCES
    / "basemap"
    / f"{BASEMAP_STYLE}_z{ZOOM}.json"
)


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
CLOUDS_SOURCE_NORTH = 53.0
CLOUDS_SOURCE_WEST = 11.0
CLOUDS_SOURCE_SOUTH = 47.0
CLOUDS_SOURCE_EAST = 20.0

# Vzhled oblačnosti nad mapou.
CLOUDS_PRODUCT = "vis-ir"
CLOUDS_MAX_AGE_MINUTES = 45
CLOUDS_OPACITY = 0.52
CLOUDS_GAMMA = 0.95
CLOUDS_MIN_STRENGTH = 0.020
CLOUDS_BASE_BRIGHTNESS = 12.0
CLOUDS_SOURCE_DOWNSCALE_FACTOR = 4
CLOUDS_SOURCE_BLUR_RADIUS = 1.6
CLOUDS_BACKGROUND_BLUR_RADIUS = 18.0
CLOUDS_PROJECTED_BLUR_RADIUS = 5.0

# Ladicí výstupy oblačnosti.
CLOUDS_SAVE_DEBUG_LAYER = True
CLOUDS_DEBUG_FILE = OUTPUT_DIR / "latest_clouds.png"
CLOUDS_PREVIEW_FILE = OUTPUT_DIR / "latest_clouds_preview.png"
CLOUDS_SOURCE_DEBUG_FILE = OUTPUT_DIR / "latest_clouds_source.jpg"


#
# Letecký provoz – ADSB.lol
#
# Velikost symbolu letadla a textu v pixelech.
AIRCRAFT_ICON_SIZE = 28
AIRCRAFT_TEXT_SIZE = 14

# Co se zobrazí v popisku. Položky odděluj čárkami.
# Povolené hodnoty:
#   flight        - vysílaný název/callsign letu, např. RYR123
#   altitude      - letová výška
#   speed         - pozemní rychlost
#   type          - typ letadla, např. A320
#   registration  - registrace letadla
#   hex           - ICAO 24bit adresa
# Prázdný řetězec vypne popisky.
AIRCRAFT_LABEL_FIELDS = "flight,altitude,speed,type"
AIRCRAFT_LABEL_SEPARATOR = " | "
AIRCRAFT_LABEL_OFFSET = (18, -16)

# Trajektorie: 0 = vypnuto, 2 = doporučené, 10 = maximum.
AIRCRAFT_TRAJECTORY_WIDTH = 2
AIRCRAFT_TRAJECTORY_COLOR = "#FFD400"
AIRCRAFT_TRAJECTORY_OUTLINE_COLOR = "#000000"
AIRCRAFT_TRAJECTORY_HISTORY_MINUTES = 30
AIRCRAFT_TRAJECTORY_MAX_POINTS = 60
AIRCRAFT_TRAJECTORY_MIN_DISTANCE_METERS = 250
AIRCRAFT_TRAJECTORY_MAX_JUMP_KM = 250

# Vzhled symbolu a popisku.
AIRCRAFT_ICON_COLOR = "#FFD400"
AIRCRAFT_ICON_OUTLINE_COLOR = "#101010"
AIRCRAFT_TEXT_COLOR = "#FFFFFF"
AIRCRAFT_TEXT_OUTLINE_COLOR = "#000000"
AIRCRAFT_TEXT_OUTLINE_WIDTH = 2

# Jednotky popisků: "m" nebo "ft", "kmh" nebo "kt".
AIRCRAFT_ALTITUDE_UNIT = "m"
AIRCRAFT_SPEED_UNIT = "kmh"

# Zdroj živých dat. AIRCRAFT_RADIUS_NM = 0 vypočítá poloměr automaticky
# podle velikosti aktuální mapy. Ručně lze nastavit 1 až 250 NM.
AIRCRAFT_API_BASE_URL = "https://api.adsb.lol"
AIRCRAFT_RADIUS_NM = 0
AIRCRAFT_RADIUS_MARGIN = 1.20
AIRCRAFT_MAX_SEEN_SECONDS = 45
AIRCRAFT_MAX_COUNT = 80
AIRCRAFT_REQUEST_TIMEOUT = (10, 25)
AIRCRAFT_CACHE_MAX_AGE_SECONDS = 180
AIRCRAFT_USER_AGENT = (
    "weather-dashboard/1.0 "
    "(+https://github.com/SHR3Deu/weather-dashboard)"
)

# Ladicí výstupy.
AIRCRAFT_SAVE_DEBUG_LAYER = True
AIRCRAFT_DEBUG_FILE = OUTPUT_DIR / "latest_aircraft.png"
AIRCRAFT_SAVE_RAW_JSON = True
AIRCRAFT_RAW_JSON_FILE = OUTPUT_DIR / "latest_aircraft.json"

# ADSB.lol poskytuje veřejná data pod licencí ODbL.
AIRCRAFT_SHOW_ATTRIBUTION = True
AIRCRAFT_ATTRIBUTION = "Data: ADSB.lol (ODbL)"
