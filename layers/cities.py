import json
from pathlib import Path

from PIL import ImageDraw
from PIL import ImageFont

import config


class CitiesLayer:

    def __init__(self):

        file = Path(__file__).with_name("cities.json")

        with open(file, encoding="utf-8") as f:
            self.cities = json.load(f)

        try:
            self.font = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                14
            )
        except Exception:
            self.font = ImageFont.load_default()

    def draw(self, canvas, basemap):

        draw = ImageDraw.Draw(canvas)

        for city in self.cities:

            x, y = basemap.screen_position(
                city["lat"],
                city["lon"]
            )

            # mimo viewport

            if x < 0 or x >= config.MAP_WIDTH:
                continue

            if y < 0 or y >= config.MAP_HEIGHT:
                continue

            #
            # bod města
            #

            draw.ellipse(
                (x - 3, y - 3, x + 3, y + 3),
                fill="yellow",
                outline="black"
            )

            #
            # název města s obrysem
            #

            text = city["name"]

            # obrys
            draw.text((x + 5, y - 7), text, font=self.font, fill="black")
            draw.text((x + 7, y - 7), text, font=self.font, fill="black")
            draw.text((x + 6, y - 8), text, font=self.font, fill="black")
            draw.text((x + 6, y - 6), text, font=self.font, fill="black")

            # vlastní text
            draw.text(
                (x + 6, y - 7),
                text,
                font=self.font,
                fill="white"
            )
