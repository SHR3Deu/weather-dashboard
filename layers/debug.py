from PIL import ImageDraw

import config

from layers.base import Layer


class DebugLayer(Layer):

    name = "Debug"

    def draw(self, canvas, basemap):

        draw = ImageDraw.Draw(canvas)

        #
        # Grid
        #

        for x in range(0, config.MAP_WIDTH, 100):
            draw.line(
                (x, 0, x, config.MAP_HEIGHT),
                fill="#808080"
            )

        for y in range(0, config.MAP_HEIGHT, 100):
            draw.line(
                (0, y, config.MAP_WIDTH, y),
                fill="#808080"
            )

        #
        # Cross
        #

        cx = config.MAP_WIDTH // 2
        cy = config.MAP_HEIGHT // 2

        draw.line(
            (cx - 20, cy, cx + 20, cy),
            fill="red",
            width=3,
        )

        draw.line(
            (cx, cy - 20, cx, cy + 20),
            fill="red",
            width=3,
        )

        #
        # GPS center
        #

        x, y = basemap.screen_position(
            config.CENTER_LAT,
            config.CENTER_LON,
        )

        r = 8

        draw.ellipse(
            (
                x - r,
                y - r,
                x + r,
                y + r,
            ),
            fill="yellow",
            outline="black",
            width=2,
        )
