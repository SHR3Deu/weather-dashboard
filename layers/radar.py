import re

import numpy as np
import requests
from osgeo import gdal
from PIL import Image

import config
from layers.base import Layer


gdal.UseExceptions()


class RadarLayer(Layer):
    name = "Radar"

    INDEX_URL = (
        "https://opendata.chmi.cz/"
        "meteorology/weather/radar/composite/maxz/hdf5/"
    )

    CACHE_DIR = config.CACHE / "radar"
    CACHE_FILE = CACHE_DIR / "latest.hdf"
    CACHE_SOURCE_FILE = CACHE_DIR / "latest.txt"

    REQUEST_HEADERS = {
        "User-Agent": (
            "weather-dashboard/1.0 "
            "(+https://github.com/SHR3Deu/weather-dashboard)"
        )
    }

    # Slabší radarové odrazy zůstanou průhledné, aby nezakrývaly mapu.
    MIN_VISIBLE_DBZ = 5.0

    def get_cached_filename(self):
        if self.CACHE_SOURCE_FILE.exists():
            cached_name = self.CACHE_SOURCE_FILE.read_text(
                encoding="utf-8"
            ).strip()

            if cached_name:
                return cached_name

        return self.CACHE_FILE.name

    def download(self):
        """Stáhne nejnovější radarový snímek ČHMÚ."""
        self.CACHE_DIR.mkdir(parents=True, exist_ok=True)

        try:
            response = requests.get(
                self.INDEX_URL,
                headers=self.REQUEST_HEADERS,
                timeout=(10, 30),
            )
            response.raise_for_status()

            files = re.findall(
                r'href=["\']([^"\']+\.hdf)["\']',
                response.text,
                flags=re.IGNORECASE,
            )

            if not files:
                raise RuntimeError(
                    "Na serveru ČHMÚ nebyly nalezeny žádné HDF soubory."
                )

            latest = sorted(set(files))[-1]

            if self.CACHE_FILE.exists() and self.CACHE_SOURCE_FILE.exists():
                cached_name = self.CACHE_SOURCE_FILE.read_text(
                    encoding="utf-8"
                ).strip()

                if cached_name == latest:
                    return latest

            response = requests.get(
                self.INDEX_URL + latest,
                headers=self.REQUEST_HEADERS,
                timeout=(10, 60),
            )
            response.raise_for_status()

            if not response.content:
                raise RuntimeError("Stažený radarový soubor je prázdný.")

            temporary_file = self.CACHE_DIR / "latest.tmp"
            temporary_file.write_bytes(response.content)
            temporary_file.replace(self.CACHE_FILE)

            self.CACHE_SOURCE_FILE.write_text(
                latest,
                encoding="utf-8",
            )

            return latest

        except (requests.RequestException, RuntimeError) as error:
            if self.CACHE_FILE.exists():
                print(
                    "[Radar] ČHMÚ není dostupné, používám poslední cache: "
                    f"{error}"
                )
                return self.get_cached_filename()

            raise

    def load(self):
        """Načte radarová data a metadata z HDF5 souboru."""
        dataset_path = (
            f'HDF5:"{self.CACHE_FILE}"://dataset1/data1/data'
        )

        dataset = gdal.Open(dataset_path)

        if dataset is None:
            raise RuntimeError("Radarový dataset nelze otevřít.")

        data = dataset.ReadAsArray()
        metadata = dataset.GetMetadata()
        dataset = None

        if data is None:
            raise RuntimeError("Radarový dataset neobsahuje obrazová data.")

        required_keys = (
            "where_UL_lat",
            "where_UL_lon",
            "where_LR_lat",
            "where_LR_lon",
            "dataset1_data1_what_gain",
            "dataset1_data1_what_offset",
            "dataset1_data1_what_nodata",
            "dataset1_data1_what_undetect",
        )

        missing_keys = [
            key for key in required_keys if key not in metadata
        ]

        if missing_keys:
            raise RuntimeError(
                "V HDF souboru chybí metadata: "
                + ", ".join(missing_keys)
            )

        return data, {
            "ul_lat": float(metadata["where_UL_lat"]),
            "ul_lon": float(metadata["where_UL_lon"]),
            "lr_lat": float(metadata["where_LR_lat"]),
            "lr_lon": float(metadata["where_LR_lon"]),
            "gain": float(metadata["dataset1_data1_what_gain"]),
            "offset": float(metadata["dataset1_data1_what_offset"]),
            "nodata": float(metadata["dataset1_data1_what_nodata"]),
            "undetect": float(metadata["dataset1_data1_what_undetect"]),
        }

    def create_image(self, data, metadata):
        """Převede hodnoty dBZ na průhlednou barevnou radarovou vrstvu."""
        rgba = np.zeros(
            (data.shape[0], data.shape[1], 4),
            dtype=np.uint8,
        )

        valid = (
            (data != metadata["nodata"])
            & (data != metadata["undetect"])
        )

        dbz = (
            data.astype(np.float32) * metadata["gain"]
            + metadata["offset"]
        )

        visible = valid & (dbz >= self.MIN_VISIBLE_DBZ)

        rgba[(dbz >= 5) & (dbz < 15) & visible] = (
            0,
            170,
            255,
            85,
        )
        rgba[(dbz >= 15) & (dbz < 25) & visible] = (
            0,
            255,
            190,
            110,
        )
        rgba[(dbz >= 25) & (dbz < 35) & visible] = (
            50,
            230,
            50,
            140,
        )
        rgba[(dbz >= 35) & (dbz < 45) & visible] = (
            255,
            230,
            0,
            165,
        )
        rgba[(dbz >= 45) & (dbz < 55) & visible] = (
            255,
            130,
            0,
            190,
        )
        rgba[(dbz >= 55) & visible] = (
            255,
            0,
            40,
            220,
        )

        return Image.fromarray(rgba)

    def project_to_canvas(self, radar, metadata, canvas, basemap):
        """
        Přibližně promítne radar do viewportu mapy.

        Radarový rastr se považuje za obdélník mezi souřadnicemi UL a LR.
        Pillow rovnou vytvoří jen vrstvu o velikosti výsledného viewportu,
        takže nevzniká velký mezilehlý obraz celé radarové oblasti.
        """
        left, top = basemap.screen_position(
            metadata["ul_lat"],
            metadata["ul_lon"],
        )
        right, bottom = basemap.screen_position(
            metadata["lr_lat"],
            metadata["lr_lon"],
        )

        radar_width_on_map = right - left
        radar_height_on_map = bottom - top

        if radar_width_on_map <= 0 or radar_height_on_map <= 0:
            raise RuntimeError(
                "Radar má neplatné krajní souřadnice nebo orientaci."
            )

        source_width, source_height = radar.size

        scale_x = source_width / radar_width_on_map
        scale_y = source_height / radar_height_on_map

        transform = (
            scale_x,
            0.0,
            -left * scale_x,
            0.0,
            scale_y,
            -top * scale_y,
        )

        projected = radar.transform(
            canvas.size,
            Image.Transform.AFFINE,
            transform,
            resample=Image.Resampling.BILINEAR,
            fillcolor=(0, 0, 0, 0),
        )

        visible_pixels = int(
            np.count_nonzero(np.asarray(projected.getchannel("A")))
        )

        # Canvas basemapy je RGB, proto se vrstva vkládá přes alfa masku.
        canvas.paste(projected, (0, 0), projected)

        return left, top, right, bottom, visible_pixels

    def draw(self, canvas, basemap):
        try:
            filename = self.download()
            data, metadata = self.load()
            radar = self.create_image(data, metadata)

            left, top, right, bottom, visible_pixels = (
                self.project_to_canvas(
                    radar,
                    metadata,
                    canvas,
                    basemap,
                )
            )

            print(f"[Radar] Soubor: {filename}")
            print(f"[Radar] Zdroj: {data.shape[1]} x {data.shape[0]} px")
            print(
                "[Radar] Oblast na mapě: "
                f"({left}, {top}) až ({right}, {bottom})"
            )
            print(
                "[Radar] Viditelné pixely ve viewportu: "
                f"{visible_pixels}"
            )

            if visible_pixels == 0:
                print(
                    "[Radar] Ve zobrazené oblasti nyní není odraz "
                    f"nad {self.MIN_VISIBLE_DBZ:g} dBZ."
                )

        except Exception as error:
            print(f"[Radar] Chyba: {error}")
