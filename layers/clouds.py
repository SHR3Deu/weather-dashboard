import re
from datetime import datetime, timezone
from io import BytesIO

import numpy as np
import requests
from PIL import Image

import config
from layers.base import Layer


class CloudsLayer(Layer):
    name = "Clouds"

    CACHE_DIR = config.CACHE / "clouds"
    CACHE_IMAGE = CACHE_DIR / "latest.jpg"
    CACHE_INFO = CACHE_DIR / "latest.txt"

    REQUEST_HEADERS = {
        "User-Agent": (
            "weather-dashboard/1.0 "
            "(+https://github.com/SHR3Deu/weather-dashboard)"
        )
    }

    def __init__(self):
        self.products = tuple(
            getattr(config, "CLOUDS_PRODUCTS", ("vis-ir", "ir108"))
        )
        self.region = str(getattr(config, "CLOUDS_REGION", "cz"))
        self.base_url = str(config.CLOUDS_INDEX_BASE_URL).rstrip("/")
        self.timeout = tuple(
            getattr(config, "CLOUDS_REQUEST_TIMEOUT", (10, 30))
        )

        self.opacity = float(getattr(config, "CLOUDS_OPACITY", 0.58))
        self.min_brightness = float(
            getattr(config, "CLOUDS_MIN_BRIGHTNESS", 55)
        )
        self.gamma = float(getattr(config, "CLOUDS_GAMMA", 1.6))
        self.hide_timestamp = bool(
            getattr(config, "CLOUDS_HIDE_TIMESTAMP", True)
        )

        self.save_debug_layer = bool(
            getattr(config, "CLOUDS_SAVE_DEBUG_LAYER", True)
        )
        self.debug_file = getattr(
            config,
            "CLOUDS_DEBUG_FILE",
            config.OUTPUT_DIR / "latest_clouds.png",
        )
        self.preview_file = getattr(
            config,
            "CLOUDS_PREVIEW_FILE",
            config.OUTPUT_DIR / "latest_clouds_preview.png",
        )

    def _index_url(self, product):
        return f"{self.base_url}/{product}/"

    def _parse_timestamp(self, filename):
        match = re.match(r"^(\d{12})_", filename)

        if not match:
            raise RuntimeError(
                f"Nelze přečíst čas ze satelitního souboru {filename}."
            )

        return datetime.strptime(
            match.group(1),
            "%Y%m%d%H%M",
        ).replace(tzinfo=timezone.utc)

    def _latest_file_for_product(self, product):
        index_url = self._index_url(product)
        response = requests.get(
            index_url,
            headers=self.REQUEST_HEADERS,
            timeout=self.timeout,
        )
        response.raise_for_status()

        product_pattern = re.escape(product)
        region_pattern = re.escape(self.region)
        pattern = (
            rf'href=["\']('
            rf'\d{{12}}_geo_{product_pattern}_{region_pattern}\.jpg'
            rf')["\']'
        )

        files = re.findall(
            pattern,
            response.text,
            flags=re.IGNORECASE,
        )

        if not files:
            return None

        filename = sorted(set(files))[-1]

        return {
            "product": product,
            "filename": filename,
            "timestamp": self._parse_timestamp(filename),
            "url": index_url + filename,
        }

    def _find_latest_source(self):
        candidates = []
        errors = []

        for product in self.products:
            try:
                candidate = self._latest_file_for_product(product)

                if candidate is not None:
                    candidates.append(candidate)
            except requests.RequestException as error:
                errors.append(f"{product}: {error}")

        if not candidates:
            message = "ČHMÚ nevrátilo žádný satelitní snímek."

            if errors:
                message += " " + "; ".join(errors)

            raise RuntimeError(message)

        # Při shodném čase zůstává pořadí podle CLOUDS_PRODUCTS,
        # takže má přes den přednost VIS-IR před IR 10.8.
        product_priority = {
            product: len(self.products) - index
            for index, product in enumerate(self.products)
        }

        return max(
            candidates,
            key=lambda item: (
                item["timestamp"],
                product_priority.get(item["product"], 0),
            ),
        )

    def _read_cache_info(self):
        if not self.CACHE_INFO.exists():
            return None

        lines = self.CACHE_INFO.read_text(
            encoding="utf-8"
        ).splitlines()

        if len(lines) < 2:
            return None

        return {
            "product": lines[0].strip(),
            "filename": lines[1].strip(),
        }

    def _write_cache_info(self, source):
        self.CACHE_INFO.write_text(
            f"{source['product']}\n{source['filename']}\n",
            encoding="utf-8",
        )

    def download(self):
        """Stáhne nejnovější satelitní snímek nebo použije cache."""
        self.CACHE_DIR.mkdir(parents=True, exist_ok=True)

        try:
            source = self._find_latest_source()
            cached = self._read_cache_info()

            if (
                cached is not None
                and self.CACHE_IMAGE.exists()
                and cached["product"] == source["product"]
                and cached["filename"] == source["filename"]
            ):
                return source

            response = requests.get(
                source["url"],
                headers=self.REQUEST_HEADERS,
                timeout=self.timeout,
            )
            response.raise_for_status()

            if not response.content:
                raise RuntimeError(
                    "Stažený satelitní obrázek je prázdný."
                )

            # Ověření obrázku ještě před nahrazením funkční cache.
            image = Image.open(BytesIO(response.content))
            image.verify()

            temporary_file = self.CACHE_DIR / "latest.tmp"
            temporary_file.write_bytes(response.content)
            temporary_file.replace(self.CACHE_IMAGE)
            self._write_cache_info(source)

            return source

        except (requests.RequestException, RuntimeError, OSError) as error:
            cached = self._read_cache_info()

            if cached is not None and self.CACHE_IMAGE.exists():
                print(
                    "[Clouds] ČHMÚ není dostupné, používám cache: "
                    f"{error}"
                )

                return {
                    "product": cached["product"],
                    "filename": cached["filename"],
                    "timestamp": self._parse_timestamp(
                        cached["filename"]
                    ),
                    "url": None,
                }

            raise

    def load(self):
        image = Image.open(self.CACHE_IMAGE)
        image.load()
        return image.convert("RGB")

    def create_cloud_mask(self, source):
        """Převede snímek ČHMÚ na bílou průhlednou cloud vrstvu."""
        rgb = np.asarray(source, dtype=np.float32)

        red = rgb[:, :, 0]
        green = rgb[:, :, 1]
        blue = rgb[:, :, 2]

        luminance = (
            red * 0.299
            + green * 0.587
            + blue * 0.114
        )

        # Minimální barevný kanál pomáhá potlačit tmavou zelenou pevninu,
        # zatímco zachová bílou, modrou i nažloutlou oblačnost.
        minimum_channel = np.minimum(np.minimum(red, green), blue)
        cloud_signal = luminance * 0.72 + minimum_channel * 0.28

        denominator = max(1.0, 255.0 - self.min_brightness)
        normalized = np.clip(
            (cloud_signal - self.min_brightness) / denominator,
            0.0,
            1.0,
        )

        gamma = max(self.gamma, 0.01)
        normalized = normalized ** (1.0 / gamma)

        alpha = np.clip(
            normalized * self.opacity * 255.0,
            0.0,
            255.0,
        ).astype(np.uint8)

        if self.hide_timestamp:
            # ČHMÚ vkládá čas do pravého horního rohu obrázku.
            timestamp_height = min(26, source.height)
            timestamp_width = min(290, source.width)
            alpha[
                0:timestamp_height,
                source.width - timestamp_width:source.width,
            ] = 0

        rgba = np.zeros(
            (source.height, source.width, 4),
            dtype=np.uint8,
        )
        rgba[:, :, 0] = 255
        rgba[:, :, 1] = 255
        rgba[:, :, 2] = 255
        rgba[:, :, 3] = alpha

        return Image.fromarray(rgba, mode="RGBA")

    def project_to_canvas(self, clouds, canvas, basemap):
        north = float(config.CLOUDS_SOURCE_NORTH)
        west = float(config.CLOUDS_SOURCE_WEST)
        south = float(config.CLOUDS_SOURCE_SOUTH)
        east = float(config.CLOUDS_SOURCE_EAST)

        left, top = basemap.screen_position(north, west)
        right, bottom = basemap.screen_position(south, east)

        width_on_map = right - left
        height_on_map = bottom - top

        if width_on_map <= 0 or height_on_map <= 0:
            raise RuntimeError(
                "Cloud vrstva má neplatné geografické hranice."
            )

        source_width, source_height = clouds.size
        scale_x = source_width / width_on_map
        scale_y = source_height / height_on_map

        transform = (
            scale_x,
            0.0,
            -left * scale_x,
            0.0,
            scale_y,
            -top * scale_y,
        )

        projected = clouds.transform(
            canvas.size,
            Image.Transform.AFFINE,
            transform,
            resample=Image.Resampling.BILINEAR,
            fillcolor=(0, 0, 0, 0),
        )

        visible_pixels = int(
            np.count_nonzero(np.asarray(projected.getchannel("A")))
        )

        return projected, {
            "left": left,
            "top": top,
            "right": right,
            "bottom": bottom,
            "visible_pixels": visible_pixels,
        }

    def save_debug_images(self, projected, canvas_before):
        if not self.save_debug_layer:
            return

        self.debug_file.parent.mkdir(parents=True, exist_ok=True)
        self.preview_file.parent.mkdir(parents=True, exist_ok=True)

        projected.save(self.debug_file)

        preview = canvas_before.convert("RGBA")
        preview.alpha_composite(projected)
        preview.convert("RGB").save(self.preview_file)

    def draw(self, canvas, basemap):
        try:
            source_info = self.download()
            source_image = self.load()
            cloud_mask = self.create_cloud_mask(source_image)
            projected, projection_info = self.project_to_canvas(
                cloud_mask,
                canvas,
                basemap,
            )

            canvas_before = canvas.copy()
            self.save_debug_images(projected, canvas_before)
            canvas.paste(projected, (0, 0), projected)

            age_minutes = int(
                (
                    datetime.now(timezone.utc)
                    - source_info["timestamp"]
                ).total_seconds()
                / 60
            )

            print(
                "[Clouds] Soubor: "
                f"{source_info['filename']}"
            )
            print(
                "[Clouds] Produkt: "
                f"{source_info['product']}"
            )
            print(
                "[Clouds] Stáří snímku: "
                f"{max(age_minutes, 0)} minut"
            )
            print(
                "[Clouds] Zdroj: "
                f"{source_image.width} x {source_image.height} px"
            )
            print(
                "[Clouds] Oblast na mapě: "
                f"({projection_info['left']}, {projection_info['top']}) až "
                f"({projection_info['right']}, {projection_info['bottom']})"
            )
            print(
                "[Clouds] Viditelné pixely ve viewportu: "
                f"{projection_info['visible_pixels']}"
            )

            if self.save_debug_layer:
                print(
                    "[Clouds] Uložena vrstva: "
                    f"{self.debug_file}"
                )
                print(
                    "[Clouds] Uložen náhled: "
                    f"{self.preview_file}"
                )

        except Exception as error:
            print(f"[Clouds] Chyba: {error}")
