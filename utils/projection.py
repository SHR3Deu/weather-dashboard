import math

TILE_SIZE = 256


def latlon_to_world_pixel(lat, lon, zoom):
    """
    Převod GPS souřadnic na globální pixelové souřadnice
    (Web Mercator).
    """

    scale = TILE_SIZE * (2 ** zoom)

    x = (lon + 180.0) / 360.0 * scale

    lat_rad = math.radians(lat)

    y = (
        1
        - math.log(
            math.tan(lat_rad) + 1 / math.cos(lat_rad)
        ) / math.pi
    ) / 2 * scale

    return x, y


def world_pixel_to_tile(px, py):
    """
    Převod globálních pixelů na číslo dlaždice.
    """

    tx = int(px // TILE_SIZE)
    ty = int(py // TILE_SIZE)

    return tx, ty


def pixel_inside_tile(px, py):
    """
    Vrátí pixel uvnitř konkrétní dlaždice.
    """

    return (
        int(px % TILE_SIZE),
        int(py % TILE_SIZE),
    )
