import datetime as dt
import re

import numpy as np
import requests
from PIL import Image, ImageFilter

import config
from layers.base import Layer


class CloudsLayer(Layer):
    name = "Clouds"

    INDEX_URL = (
        "https://opendata.chmi.cz/"
        "meteorology/weather/satellite/geo/"
    )

    CACHE_DIR = config.CACHE / "clouds"

    REQUEST_HEADERS = {
        "User-Agent": (
            "weather-dashboard/1.0 "
            "(+https://github.com/SHR3Deu/weather-dashboard)"
        )
    }

    def __init__(self):
        self.product = getattr(config, "CLOUDS_PRODUCT", "vis-ir")
        self.opacity = float(getattr(config, "CLOUDS_OPACITY", 0.42))
        self.gamma = float(getattr(config, "CLOUDS_GAMMA", 1.15))
        self.min_strength = float(
            getattr(config, "CLOUDS_MIN_STRENGTH", 0.10)
        )
        self.blur_radius = float(
            getattr(config, "CLOUDS_BLUR_RADIUS", 2.0)
        )
        self.downscale_factor = int(
            getattr(config, "CLOUDS_DOWNSCALE_FACTOR", 4)
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
        self.timeout = tuple(
            getattr(config, "CLOUDS_REQUEST_TIMEOUT", (10, 30))
        )

        self.source_north = float(
            getattr(config, "CLOUDS_SOURCE_NORTH", 53.0)
        )
        self.source_west = float(
            getattr(config, "CLOUDS_SOURCE_WEST", 11.0)
        )
        self.source_south = float(
            getattr(config, "CLOUDS_SOURCE_SOUTH", 47.0)
        )
        self.source_east = float(
            getattr(config, "CLOUDS_SOURCE_EAST", 20.0)
        )

    def _cache_file(self, product=None):
        name = product or self.product
        return self.CACHE_DIR / f"latest_{name}.jpg"

    def _cache_source_file(self, product=None):
        name = product or self.product
        return self.CACHE_DIR / f"latest_{name}.txt"

    def _get_cached_filename(self, product=None):
        source_file = self._cache_source_file(product)
        cache_file = self._cache_file(product)

        if source_file.exists():
            cached_name = source_file.read_text(encoding="utf-8").strip()
            if cached_name:
                return cached_name

        return cache_file.name

    def _list_available_files(self):
        response = requests.get(
            self.INDEX_URL,
            headers=self.REQUEST_HEADERS,
            timeout=self.timeout,
        )
        response.raise_for_status()

        files = re.findall(
            r'href=["\']([^"\']+_geo_[a-z0-9\-]+_cz\.jpg)["\']',
            response.text,
            flags=re.IGNORECASE,
        )

        return sorted(set(files))

    def _detect_product(self, available_files):
        requested = self.product.lower()
        matching = [
            name for name in available_files
            if f"_geo_{requested}_cz.jpg" in name.lower()
        ]

        if matching:
            return requested, matching[-1]

        fallback_order = ["vis-ir", "ir108", "24m"]

        for fallback in fallback_order:
            matching = [
                name for name in available_files
                if f"_geo_{fallback}_cz.jpg" in name.lower()
            ]
            if matching:
                return fallback, matching[-1]

        raise RuntimeError(
            "Na serveru ČHMÚ nebyl nalezen použitelný satelitní snímek."
        )

    def download(self):
        """Stáhne nejnovější satelitní snímek oblačnosti z ČHMÚ."""
        self.CACHE_DIR.mkdir(parents=True, exist_ok=True)

        try:
            available_files = self._list_available_files()
            product, latest = self._detect_product(available_files)

            cache_file = self._cache_file(product)
            cache_source_file = self._cache_source_file(product)

            if cache_file.exists() and cache_source_file.exists():
                cached_name = cache_source_file.read_text(
                    encoding="utf-8"
                ).strip()
                if cached_name == latest:
                    return product, latest, cache_file

            response = requests.get(
                self.INDEX_URL + latest,
                headers=self.REQUEST_HEADERS,
                timeout=self.timeout,
            )
            response.raise_for_status()

            if not response.content:
                raise RuntimeError("Stažený cloud snímek je prázdný.")

            temporary_file = cache_file.with_suffix(".tmp")
            temporary_file.write_bytes(response.content)
            temporary_file.replace(cache_file)

            cache_source_file.write_text(latest, encoding="utf-8")

            return product, latest, cache_file

        except (requests.RequestException, RuntimeError) as error:
            for fallback_product in [self.product, "vis-ir", "ir108", "24m"]:
                cache_file = self._cache_file(fallback_product)
                if cache_file.exists():
                    print(
                        "[Clouds] ČHMÚ není dostupné, používám poslední cache: "
                        f"{error}"
                    )
                    return (
                        fallback_product,
                        self._get_cached_filename(fallback_product),
                        cache_file,
                    )

            raise

    def load(self, image_file):
        image = Image.open(image_file).convert("RGB")
        return image

    def _parse_timestamp(self, filename):
        match = re.search(r"(\d{12})_geo_", filename)
        if not match:
            return None

        try:
            return dt.datetime.strptime(match.group(1), "%Y%m%d%H%M")
        except ValueError:
            return None

    def _prepare_source(self, source):
        image = source

        if self.downscale_factor > 1:
            reduced_size = (
                max(1, source.width // self.downscale_factor),
                max(1, source.height // self.downscale_factor),
            )
            image = image.resize(reduced_size, Image.Resampling.BILINEAR)

        if self.blur_radius > 0:
            image = image.filter(ImageFilter.GaussianBlur(self.blur_radius))

        if image.size != source.size:
            image = image.resize(source.size, Image.Resampling.BILINEAR)

        return image

    def create_image(self, source, product):
        """
        Převede satelitní JPG na jemnou cloud vrstvu.

        Předchozí jednoduché prahování jasu zachytávalo i JPEG bloky.
        Nová verze proto nejdřív zdroj zjemní a pak hledá pouze barevné
        charakteristiky odpovídající oblačnosti ve VIS-IR / IR snímku.
        """
        prepared = self._prepare_source(source)
        data = np.asarray(prepared, dtype=np.float32)

        r = data[:, :, 0]
        g = data[:, :, 1]
        b = data[:, :, 2]

        brightness = (0.299 * r) + (0.587 * g) + (0.114 * b)
        maxc = np.max(data, axis=2)
        minc = np.min(data, axis=2)
        saturation = maxc - minc

        # Jasná bílá oblačnost.
        white_strength = np.clip((brightness - 150.0) / 85.0, 0.0, 1.0)
        white_strength *= np.clip((80.0 - saturation) / 80.0, 0.0, 1.0)

        # Vysoká oblačnost ve VIS-IR bývá modravá až cyan.
        blue_strength = np.clip((b - 125.0) / 100.0, 0.0, 1.0)
        blue_strength *= np.clip((b - g + 18.0) / 90.0, 0.0, 1.0)
        blue_strength *= np.clip((b - r + 12.0) / 90.0, 0.0, 1.0)

        # Nízká a střední oblačnost může být nažloutlá.
        yellow_base = np.minimum(r, g)
        yellow_strength = np.clip((yellow_base - 150.0) / 90.0, 0.0, 1.0)
        yellow_strength *= np.clip((170.0 - b) / 120.0, 0.0, 1.0)
        yellow_strength *= np.clip((r - 120.0) / 100.0, 0.0, 1.0)
        yellow_strength *= np.clip((g - 120.0) / 100.0, 0.0, 1.0)

        if product == "ir108":
            # Noční / IR snímek je spíš šedotónový.
            cloud_strength = np.clip((brightness - 120.0) / 120.0, 0.0, 1.0)
        else:
            cloud_strength = np.maximum.reduce([
                white_strength,
                blue_strength * 0.90,
                yellow_strength * 0.85,
            ])

        if self.gamma > 0:
            cloud_strength = np.power(cloud_strength, self.gamma)

        cloud_strength[cloud_strength < self.min_strength] = 0.0

        alpha = np.clip(cloud_strength * self.opacity * 255.0, 0, 255)

        rgba = np.zeros((source.height, source.width, 4), dtype=np.uint8)

        # Jemné zabarvení podle typu oblačnosti, aby to působilo živěji,
        # ale zároveň nerušilo HMI pozadí.
        rgba[:, :, 0] = np.clip(
            255.0 - (blue_strength * 18.0),
            0,
            255,
        ).astype(np.uint8)
        rgba[:, :, 1] = np.clip(
            255.0 - (yellow_strength * 8.0),
            0,
            255,
        ).astype(np.uint8)
        rgba[:, :, 2] = np.clip(
            255.0 - (yellow_strength * 28.0),
            0,
            255,
        ).astype(np.uint8)
        rgba[:, :, 3] = alpha.astype(np.uint8)

        layer = Image.fromarray(rgba, mode="RGBA")

        visible_pixels = int(np.count_nonzero(rgba[:, :, 3]))

        return layer, {
            "visible_pixels": visible_pixels,
            "mean_alpha": float(alpha.mean()),
        }

    def project_to_canvas(self, layer, canvas, basemap):
        left, top = basemap.screen_position(
            self.source_north,
            self.source_west,
        )
        right, bottom = basemap.screen_position(
            self.source_south,
            self.source_east,
        )

        source_width_on_map = right - left
        source_height_on_map = bottom - top

        if source_width_on_map <= 0 or source_height_on_map <= 0:
            raise RuntimeError(
                "Cloud vrstva má neplatné krajní souřadnice nebo orientaci."
            )

        source_width, source_height = layer.size

        scale_x = source_width / source_width_on_map
        scale_y = source_height / source_height_on_map

        transform = (
            scale_x,
            0.0,
            -left * scale_x,
            0.0,
            scale_y,
            -top * scale_y,
        )

        projected = layer.transform(
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

    def save_debug_images(self, projected, canvas):
        if not self.save_debug_layer:
            return

        self.debug_file.parent.mkdir(parents=True, exist_ok=True)
        projected.save(self.debug_file)

        preview = canvas.copy()
        preview.paste(projected, (0, 0), projected)
        preview.save(self.preview_file)

    def draw(self, canvas, basemap):
        try:
            product, filename, image_file = self.download()
            source = self.load(image_file)
            layer, source_info = self.create_image(source, product)
            projected, projection_info = self.project_to_canvas(
                layer,
                canvas,
                basemap,
            )

            self.save_debug_images(projected, canvas)
            canvas.paste(projected, (0, 0), projected)

            timestamp = self._parse_timestamp(filename)
            age_text = "neznámé"

            if timestamp is not None:
                age = dt.datetime.utcnow() - timestamp
                age_minutes = max(0, int(age.total_seconds() // 60))
                age_text = f"{age_minutes} minut"

            print(f"[Clouds] Soubor: {filename}")
            print(f"[Clouds] Produkt: {product}")
            print(f"[Clouds] Stáří snímku: {age_text}")
            print(f"[Clouds] Zdroj: {source.width} x {source.height} px")
            print(
                "[Clouds] Oblast na mapě: "
                f"({projection_info['left']}, {projection_info['top']}) až "
                f"({projection_info['right']}, {projection_info['bottom']})"
            )
            print(
                "[Clouds] Viditelné pixely ve zdroji: "
                f"{source_info['visible_pixels']}"
            )
            print(
                "[Clouds] Viditelné pixely ve viewportu: "
                f"{projection_info['visible_pixels']}"
            )
            print(
                f"[Clouds] Průměrná alfa: {source_info['mean_alpha']:.2f}"
            )

            if self.save_debug_layer:
                print(f"[Clouds] Uložena vrstva: {self.debug_file}")
                print(f"[Clouds] Uložen náhled: {self.preview_file}")

        except Exception as error:
            print(f"[Clouds] Chyba: {error}")
