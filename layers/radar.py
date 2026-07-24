import re

from osgeo import gdal
import numpy as np
import requests
from PIL import Image

import config
from layers.base import Layer


class RadarLayer(Layer):

    name = "Radar"

    INDEX_URL = (
        "https://opendata.chmi.cz/"
        "meteorology/weather/radar/composite/maxz/hdf5/"
    )

    CACHE_DIR = config.CACHE / "radar"
    CACHE_FILE = CACHE_DIR / "latest.hdf"

    def download(self):

        self.CACHE_DIR.mkdir(
            parents=True,
            exist_ok=True,
        )

        response = requests.get(
            self.INDEX_URL,
            timeout=30,
        )
        response.raise_for_status()

        files = re.findall(
            r'href="([^"]+\.hdf)"',
            response.text,
        )

        if not files:
            raise RuntimeError(
                "No HDF files found."
            )

        latest = sorted(files)[-1]

        response = requests.get(
            self.INDEX_URL + latest,
            timeout=30,
        )
        response.raise_for_status()

        self.CACHE_FILE.write_bytes(
            response.content
        )

    def load(self):

        ds = gdal.Open(
            f'HDF5:"{self.CACHE_FILE}"://dataset1/data1/data'
        )

        if ds is None:
            raise RuntimeError(
                "Unable to open radar dataset."
            )

        data = ds.ReadAsArray()

        meta = ds.GetMetadata()

        return data, {
            "ul_lat": float(meta["where_UL_lat"]),
            "ul_lon": float(meta["where_UL_lon"]),
            "lr_lat": float(meta["where_LR_lat"]),
            "lr_lon": float(meta["where_LR_lon"]),
            "gain": float(meta["dataset1_data1_what_gain"]),
            "offset": float(meta["dataset1_data1_what_offset"]),
            "nodata": int(meta["dataset1_data1_what_nodata"]),
            "undetect": int(meta["dataset1_data1_what_undetect"]),
        }

    def create_image(self, data, meta):

        rgba = np.zeros(
            (
                data.shape[0],
                data.shape[1],
                4,
            ),
            dtype=np.uint8,
        )

        valid = (
            (data != meta["nodata"]) &
            (data != meta["undetect"])
        )

        dbz = (
            data.astype(np.float32)
            * meta["gain"]
            + meta["offset"]
        )

        alpha = np.zeros_like(
            data,
            dtype=np.uint8,
        )

        alpha[valid] = 160

        rgba[..., 3] = alpha

        #
        # jednoduchá barevná škála
        #

        rgba[(dbz < 20) & valid] = (
            0,
            180,
            255,
            120,
        )

        rgba[(dbz >= 20) & (dbz < 35) & valid] = (
            0,
            255,
            0,
            150,
        )

        rgba[(dbz >= 35) & (dbz < 45) & valid] = (
            255,
            255,
            0,
            170,
        )

        rgba[(dbz >= 45) & (dbz < 55) & valid] = (
            255,
            140,
            0,
            190,
        )

        rgba[(dbz >= 55) & valid] = (
            255,
            0,
            0,
            220,
        )

        return Image.fromarray(
            rgba,
            "RGBA",
        )

    def draw(self, canvas, basemap):

        try:

            self.download()

            data, meta = self.load()

            radar = self.create_image(
                data,
                meta,
            )

            left, top = basemap.screen_position(
                meta["ul_lat"],
                meta["ul_lon"],
            )

            right, bottom = basemap.screen_position(
                meta["lr_lat"],
                meta["lr_lon"],
            )

            width = max(
                1,
                right - left,
            )

            height = max(
                1,
                bottom - top,
            )

            print(f"UL: {left}, {top}")
            print(f"LR: {right}, {bottom}")
            print(f"Size: {right-left} x {bottom-top}")

            #radar = radar.resize(
            #    (
            #        width,
            #        height,
            #    ),
            #    Image.Resampling.BILINEAR,
            #)

            #canvas.alpha_composite(
            #    radar,
            #    (
            #        left,
            #        top,
            #    ),
            #)

        except Exception as e:

            print(
                "[Radar]",
                e,
            )
