from PIL import ImageDraw
from PIL import ImageFont

import config


class ScaleLayer:

    def __init__(self):

        try:
            self.font = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                14
            )
        except Exception:
            self.font = ImageFont.load_default()

    def draw(self, canvas, basemap):

        draw = ImageDraw.Draw(canvas)

        meters_per_pixel = basemap.meters_per_pixel()

        #
        # dostupné délky měřítka
        #

        values = (
            100,
            200,
            500,
            1000,
            2000,
            5000,
            10000,
            20000,
            50000,
        )

        length_m = values[0]

        for value in values:

            if value / meters_per_pixel <= 180:
                length_m = value

        length_px = int(length_m / meters_per_pixel)

        #
        # pozice
        #

        margin = 30

        x1 = margin
        y1 = config.MAP_HEIGHT - margin

        x2 = x1 + length_px

        #
        # černý podklad
        #

        draw.line(
            (x1, y1, x2, y1),
            fill="black",
            width=6
        )

        draw.line(
            (x1, y1 - 6, x1, y1 + 6),
            fill="black",
            width=4
        )

        draw.line(
            (x2, y1 - 6, x2, y1 + 6),
            fill="black",
            width=4
        )

        #
        # bílá čára
        #

        draw.line(
            (x1, y1, x2, y1),
            fill="white",
            width=2
        )

        draw.line(
            (x1, y1 - 5, x1, y1 + 5),
            fill="white",
            width=2
        )

        draw.line(
            (x2, y1 - 5, x2, y1 + 5),
            fill="white",
            width=2
        )

        #
        # popisek
        #

        if length_m >= 1000:
            text = f"{length_m // 1000} km"
        else:
            text = f"{length_m} m"

        bbox = draw.textbbox(
            (0, 0),
            text,
            font=self.font
        )

        text_width = bbox[2] - bbox[0]

        tx = x1 + (length_px - text_width) // 2
        ty = y1 + 10

        #
        # obrys textu
        #

        draw.text((tx - 1, ty), text, fill="black", font=self.font)
        draw.text((tx + 1, ty), text, fill="black", font=self.font)
        draw.text((tx, ty - 1), text, fill="black", font=self.font)
        draw.text((tx, ty + 1), text, fill="black", font=self.font)

        #
        # vlastní text
        #

        draw.text(
            (tx, ty),
            text,
            fill="white",
            font=self.font
        )
