import datetime as dt
import re
from pathlib import Path

import numpy as np
import requests
from PIL import Image, ImageFilter

import config
from layers.base import Layer


class CloudsLayer(Layer):
    name = "Clouds"

    BASE_URL = (
        "https://opendata.chmi.cz/"
        "meteorology/weather/satellite/geo/"
    )

    REQUEST_HEADERS = {
        "User-Agent": (
            "weather-dashboard/1.0 "
            "(+https://github.com/SHR3Deu/weather-dashboard)"
        )
    }

    def __init__(self):
        self.cache_dir = config.CACHE / "clouds"

        self.product = getattr(config, "CLOUDS_PRODUCT", "vis-ir")
        self.max_age_minutes = int(
            getattr(config, "CLOUDS_MAX_AGE_MINUTES", 45)
        )

        self.opacity = float(getattr(config, "CLOUDS_OPACITY", 0.52))
        self.gamma = float(getattr(config, "CLOUDS_GAMMA", 0.95))
        self.min_strength = float(
            getattr(config, "CLOUDS_MIN_STRENGTH", 0.020)
        )
        self.base_brightness = float(
            getattr(config, "CLOUDS_BASE_BRIGHTNESS", 12.0)
        )

        self.source_downscale_factor = int(
            getattr(config, "CLOUDS_SOURCE_DOWNSCALE_FACTOR", 4)
        )
        self.source_blur_radius = float(
            getattr(config, "CLOUDS_SOURCE_BLUR_RADIUS", 1.6)
        )
        self.background_blur_radius = float(
            getattr(config, "CLOUDS_BACKGROUND_BLUR_RADIUS", 18.0)
        )
        self.projected_blur_radius = float(
            getattr(config, "CLOUDS_PROJECTED_BLUR_RADIUS", 5.0)
        )

        self.save_debug_layer = bool(
            getattr(config, "CLOUDS_SAVE_DEBUG_LAYER", True)
        )
        self.debug_file = Path(
            getattr(
                config,
                "CLOUDS_DEBUG_FILE",
                config.OUTPUT_DIR / "latest_clouds.png",
            )
        )
        self.preview_file = Path(
            getattr(
                config,
                "CLOUDS_PREVIEW_FILE",
                config.OUTPUT_DIR / "latest_clouds_preview.png",
            )
        )
        self.source_debug_file = Path(
            getattr(
                config,
                "CLOUDS_SOURCE_DEBUG_FILE",
                config.OUTPUT_DIR / "latest_clouds_source.jpg",
            )
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

    def _product_dir(self, product):
        if product == "24m":
            return "24M"
        return product

    def _product_url(self, product):
        return f"{self.BASE_URL}{self._product_dir(product)}/"

    def _cache_file(self, product):
        return self.cache_dir / f"latest_{product}.jpg"

    def _cache_source_file(self, product):
        return self.cache_dir / f"latest_{product}.txt"

    def _parse_timestamp(self, filename):
        match = re.search(r"(\d{12})_geo_", filename)
        if not match:
            return None

        try:
            return dt.datetime.strptime(match.group(1), "%Y%m%d%H%M")
        except ValueError:
            return None

    def _get_latest_filename_for_product(self, product):
        response = requests.get(
            self._product_url(product),
            headers=self.REQUEST_HEADERS,
            timeout=self.timeout,
        )
        response.raise_for_status()

        pattern = rf'href=["\']([^"\']+_geo_{re.escape(product)}_cz\.jpg)["\']'
        files = re.findall(pattern, response.text, flags=re.IGNORECASE)

        if not files:
            raise RuntimeError(
                f"Na serveru ČHMÚ nebyl nalezen snímek produktu {product}."
            )

        return sorted(set(files))[-1]

    def _download_file(self, product, filename):
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        cache_file = self._cache_file(product)
        cache_source_file = self._cache_source_file(product)

        if cache_file.exists() and cache_source_file.exists():
            cached_name = cache_source_file.read_text(encoding="utf-8").strip()
            if cached_name == filename:
                return cache_file

        response = requests.get(
            self._product_url(product) + filename,
            headers=self.REQUEST_HEADERS,
            timeout=self.timeout,
        )
        response.raise_for_status()

        if not response.content:
            raise RuntimeError("Stažený cloud snímek je prázdný.")

        temporary_file = cache_file.with_suffix(".tmp")
        temporary_file.write_bytes(response.content)
        temporary_file.replace(cache_file)
        cache_source_file.write_text(filename, encoding="utf-8")

        return cache_file

    def download(self):
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        fallback_order = []
        for product in [self.product, "vis-ir", "ir108", "24m"]:
            if product not in fallback_order:
                fallback_order.append(product)

        last_error = None

        for product in fallback_order:
            try:
                filename = self._get_latest_filename_for_product(product)
                timestamp = self._parse_timestamp(filename)

                if timestamp is not None:
                    age = dt.datetime.utcnow() - timestamp
                    age_minutes = max(0, int(age.total_seconds() // 60))
                    if product == self.product and age_minutes > self.max_age_minutes:
                        print(
                            f"[Clouds] Produkt {product} je starý {age_minutes} minut, zkouším další produkt."
                        )
                        continue

                cache_file = self._download_file(product, filename)
                return product, filename, cache_file

            except Exception as error:
                last_error = error

        for product in fallback_order:
            cache_file = self._cache_file(product)
            if cache_file.exists():
                print(
                    "[Clouds] ČHMÚ není dostupné, používám poslední cache: "
                    f"{last_error}"
                )
                cache_source_file = self._cache_source_file(product)
                filename = (
                    cache_source_file.read_text(encoding="utf-8").strip()
                    if cache_source_file.exists() else cache_file.name
                )
                return product, filename, cache_file

        raise RuntimeError(last_error or "Cloud snímek se nepodařilo získat.")

    def load(self, image_file):
        source = Image.open(image_file).convert("RGB")
        if self.save_debug_layer:
            self.source_debug_file.parent.mkdir(parents=True, exist_ok=True)
            source.save(self.source_debug_file, quality=95)
        return source

    def _mask_timestamp_overlay(self, strength):
        h, w = strength.shape
        strength[0:min(24, h), max(0, w - 260):w] = 0.0
        return strength

    def _preprocess_source(self, source):
        image = source

        if self.source_downscale_factor > 1:
            reduced_size = (
                max(1, source.width // self.source_downscale_factor),
                max(1, source.height // self.source_downscale_factor),
            )
            image = image.resize(reduced_size, Image.Resampling.BILINEAR)

        if self.source_blur_radius > 0:
            image = image.filter(ImageFilter.GaussianBlur(self.source_blur_radius))

        if image.size != source.size:
            image = image.resize(source.size, Image.Resampling.BILINEAR)

        return image

    def create_image(self, source, product):
        prepared = self._preprocess_source(source)
        data = np.asarray(prepared, dtype=np.float32)
        r = data[:, :, 0]
        g = data[:, :, 1]
        b = data[:, :, 2]
        gray = (0.299 * r) + (0.587 * g) + (0.114 * b)

        background_img = Image.fromarray(gray.astype(np.uint8), mode="L")
        if self.background_blur_radius > 0:
            background_img = background_img.filter(
                ImageFilter.GaussianBlur(self.background_blur_radius)
            )
        background = np.asarray(background_img, dtype=np.float32)

        detail = gray - background
        p10 = float(np.percentile(gray, 10))
        p90 = float(np.percentile(gray, 90))
        p98 = float(np.percentile(gray, 98))
        denom90 = max(1.0, p90 - p10)
        denom98 = max(1.0, p98 - p10)

        if product == "ir108":
            local_strength = np.clip((detail - 0.8) / 10.0, 0.0, 1.0)
            abs_strength = np.clip((gray - (p10 + 0.55 * denom98)) / (0.45 * denom98), 0.0, 1.0)
            cloud_strength = np.maximum(local_strength * 0.95, abs_strength * 0.50)

            color_rgb = np.dstack([
                np.full_like(gray, 246.0),
                np.full_like(gray, 246.0),
                np.full_like(gray, 246.0),
            ])
        else:
            saturation = np.max(data, axis=2) - np.min(data, axis=2)

            white_strength = np.clip((gray - (p10 + 0.58 * denom90)) / (0.42 * denom90), 0.0, 1.0)
            white_strength *= np.clip((70.0 - saturation) / 70.0, 0.0, 1.0)

            blue_strength = np.clip((b - (p10 + 0.50 * denom90)) / (0.55 * denom90), 0.0, 1.0)
            blue_strength *= np.clip((b - g + 8.0) / 45.0, 0.0, 1.0)
            blue_strength *= np.clip((b - r + 8.0) / 45.0, 0.0, 1.0)

            yellow_base = np.minimum(r, g)
            yellow_strength = np.clip((yellow_base - (p10 + 0.48 * denom90)) / (0.60 * denom90), 0.0, 1.0)
            yellow_strength *= np.clip((r - b + 8.0) / 55.0, 0.0, 1.0)
            yellow_strength *= np.clip((g - b + 8.0) / 55.0, 0.0, 1.0)

            local_strength = np.clip((detail - 0.8) / 9.0, 0.0, 1.0)

            cloud_strength = np.maximum.reduce([
                white_strength,
                blue_strength * 0.85,
                yellow_strength * 0.75,
                local_strength * 0.55,
            ])

            color_rgb = np.dstack([
                248.0 - (blue_strength * 9.0),
                248.0 - (yellow_strength * 3.0),
                248.0 - (yellow_strength * 12.0),
            ])

        if self.base_brightness > 0:
            base_strength = np.clip((gray - self.base_brightness) / 255.0, 0.0, 1.0)
            cloud_strength = np.maximum(cloud_strength, base_strength * 0.06)

        cloud_strength = self._mask_timestamp_overlay(cloud_strength)

        if self.gamma > 0:
            cloud_strength = np.power(cloud_strength, self.gamma)

        cloud_strength[cloud_strength < self.min_strength] = 0.0

        alpha = np.clip(cloud_strength * self.opacity * 255.0, 0.0, 255.0)
        alpha_img = Image.fromarray(alpha.astype(np.uint8), mode="L")
        alpha_img = alpha_img.filter(ImageFilter.MedianFilter(size=3))
        alpha = np.asarray(alpha_img, dtype=np.float32)

        rgba = np.zeros((source.height, source.width, 4), dtype=np.uint8)
        rgba[:, :, :3] = np.clip(color_rgb, 0.0, 255.0).astype(np.uint8)
        rgba[:, :, 3] = alpha.astype(np.uint8)

        layer = Image.fromarray(rgba, mode="RGBA")
        visible_pixels = int(np.count_nonzero(rgba[:, :, 3]))

        return layer, {
            "visible_pixels": visible_pixels,
            "mean_alpha": float(alpha.mean()),
            "max_alpha": int(alpha.max()) if alpha.size else 0,
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

        if self.projected_blur_radius > 0:
            projected = projected.filter(
                ImageFilter.GaussianBlur(self.projected_blur_radius)
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
            print(f"[Clouds] Maximální alfa: {source_info['max_alpha']}")

            if self.save_debug_layer:
                print(f"[Clouds] Uložena vrstva: {self.debug_file}")
                print(f"[Clouds] Uložen náhled: {self.preview_file}")
                print(f"[Clouds] Uložen zdrojový snímek: {self.source_debug_file}")

        except Exception as error:
            print(f"[Clouds] Chyba: {error}")
