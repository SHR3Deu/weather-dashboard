import json
from math import cos, radians

from PIL import Image, ImageDraw, ImageFont

import config
from utils.projection import latlon_to_world_pixel
from utils.tiles import get_style_config


class Basemap:
    def __init__(self):
        self.image = None
        self.meta = None
        self.viewport_left = 0
        self.viewport_top = 0
        self.style = config.BASEMAP_STYLE
        self.style_config = None

    def _paths(self):
        self.style, self.style_config = get_style_config(self.style)
        directory = config.RESOURCES / "basemap"
        extension = self.style_config["extension"]

        return (
            directory / f"{self.style}_z{config.ZOOM}.{extension}",
            directory / f"{self.style}_z{config.ZOOM}.json",
        )

    def load(self):
        image_file, meta_file = self._paths()

        # Zpětná kompatibilita se starým z12.png podkladem.
        if self.style == "topographic" and not image_file.exists():
            legacy_image = config.RESOURCES / "basemap" / f"z{config.ZOOM}.png"
            legacy_meta = config.RESOURCES / "basemap" / f"z{config.ZOOM}.json"

            if legacy_image.exists() and legacy_meta.exists():
                image_file = legacy_image
                meta_file = legacy_meta

        if not image_file.exists() or not meta_file.exists():
            raise FileNotFoundError(
                f"Podklad '{self.style}' není vygenerovaný. "
                f"Spusť: python generate_basemap.py {self.style}"
            )

        self.image = Image.open(image_file).convert("RGB")

        with open(meta_file, encoding="utf-8") as file:
            self.meta = json.load(file)

        meta_zoom = int(self.meta.get("zoom", -1))
        if meta_zoom != config.ZOOM:
            raise RuntimeError(
                f"Podklad má zoom {meta_zoom}, ale config používá "
                f"zoom {config.ZOOM}. Vygeneruj ho znovu."
            )

        print(
            f"[Basemap] Styl: {self.style} "
            f"({self.style_config['name']})"
        )

    def latlon_to_image(self, lat, lon):
        world_x, world_y = latlon_to_world_pixel(
            lat,
            lon,
            self.meta["zoom"],
        )

        image_x = world_x - (
            self.meta["tile_origin_x"]
            * self.meta["tile_size"]
        )
        image_y = world_y - (
            self.meta["tile_origin_y"]
            * self.meta["tile_size"]
        )

        return image_x, image_y

    def _draw_attribution(self, image):
        if not getattr(config, "BASEMAP_SHOW_ATTRIBUTION", True):
            return image

        attribution = self.style_config.get("attribution", "")
        if not attribution:
            return image

        result = image.copy()
        draw = ImageDraw.Draw(result, "RGBA")
        font_size = int(
            getattr(config, "BASEMAP_ATTRIBUTION_FONT_SIZE", 13)
        )

        try:
            font = ImageFont.truetype("DejaVuSans.ttf", font_size)
        except OSError:
            font = ImageFont.load_default()

        padding_x = 7
        padding_y = 4
        box = draw.textbbox((0, 0), attribution, font=font)
        text_width = box[2] - box[0]
        text_height = box[3] - box[1]

        x = result.width - text_width - (2 * padding_x) - 5
        y = result.height - text_height - (2 * padding_y) - 5

        draw.rounded_rectangle(
            (
                x,
                y,
                result.width - 5,
                result.height - 5,
            ),
            radius=4,
            fill=(0, 0, 0, 115),
        )
        draw.text(
            (x + padding_x, y + padding_y - box[1]),
            attribution,
            font=font,
            fill=(255, 255, 255, 225),
        )

        return result

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

        viewport = self.image.crop(
            (
                self.viewport_left,
                self.viewport_top,
                self.viewport_left + width,
                self.viewport_top + height,
            )
        )

        return self._draw_attribution(viewport)

    def screen_position(self, lat, lon):
        image_x, image_y = self.latlon_to_image(lat, lon)

        return (
            int(image_x - self.viewport_left),
            int(image_y - self.viewport_top),
        )

    def meters_per_pixel(self):
        return (
            156543.03392
            * cos(radians(config.CENTER_LAT))
            / (2 ** config.ZOOM)
        )

    def viewport_bounds_3857(self):
        tile = self.meta["tile_size"]

        world_left = (
            self.meta["tile_origin_x"] * tile
            + self.viewport_left
        )
        world_top = (
            self.meta["tile_origin_y"] * tile
            + self.viewport_top
        )
        world_right = world_left + config.MAP_WIDTH
        world_bottom = world_top + config.MAP_HEIGHT

        origin = (2 * 6378137 * 3.141592653589793) / 2
        scale = (
            (2 * origin)
            / (tile * (2 ** self.meta["zoom"]))
        )

        min_x = world_left * scale - origin
        max_x = world_right * scale - origin
        max_y = origin - world_top * scale
        min_y = origin - world_bottom * scale

        return min_x, min_y, max_x, max_y
