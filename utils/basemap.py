import json
from math import cos, radians

from PIL import Image

import config
from utils.projection import latlon_to_world_pixel


class Basemap:

    def __init__(self):

        self.image = None
        self.meta = None

        self.viewport_left = 0
        self.viewport_top = 0

    def load(self):

        directory = config.RESOURCES / "basemap"

        image_file = directory / f"z{config.ZOOM}.png"
        meta_file = directory / f"z{config.ZOOM}.json"

        self.image = Image.open(image_file)

        with open(meta_file, encoding="utf-8") as f:
            self.meta = json.load(f)

    def latlon_to_image(self, lat, lon):

        world_x, world_y = latlon_to_world_pixel(
            lat,
            lon,
            self.meta["zoom"],
        )

        image_x = world_x - (
            self.meta["tile_origin_x"] *
            self.meta["tile_size"]
        )

        image_y = world_y - (
            self.meta["tile_origin_y"] *
            self.meta["tile_size"]
        )

        return image_x, image_y

    def viewport(
        self,
        center_lat=None,
        center_lon=None,
        width=None,
        height=None,
    ):

        if center_lat is None:
            center_lat = config.CENTER_LAT

        if center_lon is None:
            center_lon = config.CENTER_LON

        if width is None:
            width = config.MAP_WIDTH

        if height is None:
            height = config.MAP_HEIGHT

        cx, cy = self.latlon_to_image(
            center_lat,
            center_lon,
        )

        self.viewport_left = int(cx - width / 2)
        self.viewport_top = int(cy - height / 2)

        return self.image.crop(
            (
                self.viewport_left,
                self.viewport_top,
                self.viewport_left + width,
                self.viewport_top + height,
            )
        )

    def screen_position(self, lat, lon):

        ix, iy = self.latlon_to_image(lat, lon)

        return (
            int(ix - self.viewport_left),
            int(iy - self.viewport_top),
        )

    def meters_per_pixel(self):

        return (
            156543.03392
            * cos(radians(config.CENTER_LAT))
            / (2 ** config.ZOOM)
        )
