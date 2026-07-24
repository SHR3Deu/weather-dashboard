import datetime as dt
import re
import shutil

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

    PRODUCT_DIRECTORIES = {
        "vis-ir": "vis-ir",
        "ir108": "ir108",
        "24m": "24M",
    }

    CACHE_DIR = config.CACHE / "clouds"

    REQUEST_HEADERS = {
        "User-Agent": (
            "weather-dashboard/1.0 "
            "(+https://github.com/SHR3Deu/weather-dashboard)"
        )
    }

    def __init__(self):
        self.product = getattr(config, "CLOUDS_PRODUCT", "vis-ir")
        self.opacity = float(getattr(config, "CLOUDS_OPACITY", 0.78))
        self.gamma = float(getattr(config, "CLOUDS_GAMMA", 0.95))
        self.min_strength = float(
            getattr(config, "CLOUDS_MIN_STRENGTH", 0.015)
        )
        self.source_blur_radius = float(
            getattr(config, "CLOUDS_SOURCE_BLUR_RADIUS", 0.8)
        )
        self.projected_blur_radius = float(
            getattr(config, "CLOUDS_PROJECTED_BLUR_RADIUS", 10.0)
        )
        self.base_brightness = float(
            getattr(config, "CLOUDS_BASE_BRIGHTNESS", 42.0)
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
        self.source_debug_file = getattr(
            config,
            "CLOUDS_SOURCE_DEBUG_FILE",
            config.OUTPUT_DIR / "latest_clouds_source.jpg",
        )
        self.timeout = tuple(
            getattr(config, "CLOUDS_REQUEST_TIMEOUT", (10, 30))
        )
        self.max_age_minutes = int(
            getattr(config, "CLOUDS_MAX_AGE_MINUTES", 45)
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

    def _normalize_product(self, product):
        return str(product).strip().lower()

    def _product_url(self, product):
        normalized = self._normalize_product(product)
        directory = self.PRODUCT_DIRECTORIES.get(normalized)

        if directory is None:
            raise RuntimeError(f"Neznámý cloud produkt: {product}")

        return normalized, f"{self.INDEX_URL}{directory}/"

    def _list_available_files(self, product):
        """Načte seznam JPG přímo z adresáře daného produktu."""
        normalized, product_url = self._product_url(product)

        response = requests.get(
            product_url,
            headers=self.REQUEST_HEADERS,
            timeout=self.timeout,
        )
        response.raise_for_status()

        files = re.findall(
            r'href=["\']([^"\']+_geo_[^"\']+_cz\.jpg)["\']',
            response.text,
            flags=re.IGNORECASE,
        )

        expected_suffix = f"_geo_{normalized}_cz.jpg"
        matching = [
            name for name in files
            if name.lower().endswith(expected_suffix)
        ]

        return normalized, product_url, sorted(set(matching))

    def _product_order(self):
        requested = self._normalize_product(self.product)
        order = [requested, "vis-ir", "ir108", "24m"]

        result = []
        for product in order:
            if product in self.PRODUCT_DIRECTORIES and product not in result:
                result.append(product)

        return result

    def _file_age_minutes(self, filename):
        timestamp = self._parse_timestamp(filename)
        if timestamp is None:
            return None

        age = dt.datetime.utcnow() - timestamp
        return max(0, int(age.total_seconds() // 60))

    def _find_latest_product(self):
        errors = []

        for product in self._product_order():
            try:
                normalized, product_url, files = (
                    self._list_available_files(product)
                )
            except requests.RequestException as error:
                errors.append(f"{product}: {error}")
                continue

            if not files:
                errors.append(f"{product}: bez CZ snímků")
                continue

            latest = files[-1]
            age_minutes = self._file_age_minutes(latest)

            if (
                self.max_age_minutes > 0
                and age_minutes is not None
                and age_minutes > self.max_age_minutes
            ):
                print(
                    f"[Clouds] Produkt {normalized} je starý "
                    f"{age_minutes} minut, zkouším další produkt."
                )
                continue

            return normalized, latest, product_url

        detail = "; ".join(errors) if errors else "bez detailu"
        raise RuntimeError(
            "Na serveru ČHMÚ nebyl nalezen čerstvý použitelný "
            f"satelitní snímek ({detail})."
        )

    def download(self):
        """Stáhne nejnovější satelitní snímek oblačnosti z ČHMÚ."""
        self.CACHE_DIR.mkdir(parents=True, exist_ok=True)

        try:
            product, latest, product_url = self._find_latest_product()

            cache_file = self._cache_file(product)
            cache_source_file = self._cache_source_file(product)

            if cache_file.exists() and cache_source_file.exists():
                cached_name = cache_source_file.read_text(
                    encoding="utf-8"
                ).strip()
                if cached_name == latest:
                    return product, latest, cache_file

            response = requests.get(
                product_url + latest,
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
            for fallback_product in self._product_order():
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
        return Image.open(image_file).convert("RGB")

    def _parse_timestamp(self, filename):
        match = re.search(r"(\d{12})_geo_", filename)
        if not match:
            return None

        try:
            return dt.datetime.strptime(match.group(1), "%Y%m%d%H%M")
        except ValueError:
            return None

    def _prepare_source(self, source):
        if self.source_blur_radius <= 0:
            return source

        return source.filter(
            ImageFilter.GaussianBlur(self.source_blur_radius)
        )

    def create_image(self, source, product):
        """
        Převede satelitní JPG na poloprůhlednou vrstvu oblačnosti.

        VIS-IR používá tmavý povrch a světlé žluté, bílé nebo namodralé
        mraky. Maska proto kombinuje jas, barevný nádech oblačnosti a
        potlačení zeleného povrchu. Není zde tvrdý vysoký práh, takže
        zůstane viditelná i slabší oblačnost.
        """
        prepared = self._prepare_source(source)
        data = np.asarray(prepared, dtype=np.float32)

        r = data[:, :, 0]
        g = data[:, :, 1]
        b = data[:, :, 2]

        brightness = (0.299 * r) + (0.587 * g) + (0.114 * b)
        saturation = np.max(data, axis=2) - np.min(data, axis=2)

        green_dominance = np.clip(
            (g - ((r + b) / 2.0) - 2.0) / 30.0,
            0.0,
            1.0,
        )

        general_brightness = np.clip(
            (brightness - self.base_brightness) / 85.0,
            0.0,
            1.0,
        )
        general_brightness *= 1.0 - (0.65 * green_dominance)

        white_strength = np.clip(
            (brightness - (self.base_brightness + 6.0)) / 95.0,
            0.0,
            1.0,
        )
        white_strength *= np.clip(
            (65.0 - saturation) / 65.0,
            0.0,
            1.0,
        )

        yellow_strength = np.clip(
            (np.minimum(r, g) - b + 3.0) / 35.0,
            0.0,
            1.0,
        )
        yellow_strength *= np.clip(
            (np.minimum(r, g) - self.base_brightness) / 100.0,
            0.0,
            1.0,
        )

        violet_strength = np.clip(
            (((r + b) / 2.0) - g + 5.0) / 35.0,
            0.0,
            1.0,
        )
        violet_strength *= np.clip(
            (np.maximum(r, b) - self.base_brightness) / 100.0,
            0.0,
            1.0,
        )

        if product == "ir108":
            cloud_strength = np.clip(
                (brightness - 52.0) / 105.0,
                0.0,
                1.0,
            )
        else:
            cloud_strength = np.maximum.reduce([
                general_brightness * 0.65,
                white_strength * 0.90,
                yellow_strength,
                violet_strength,
            ])

        if self.gamma > 0:
            cloud_strength = np.power(
                np.clip(cloud_strength, 0.0, 1.0),
                self.gamma,
            )

        cloud_strength[cloud_strength < self.min_strength] = 0.0

        alpha = np.clip(
            cloud_strength * self.opacity * 255.0,
            0.0,
            255.0,
        )

        # Slabá oblačnost je světle šedá, silná téměř bílá. Na světlé
        # topografické mapě je tak vrstva viditelnější než čistě bílá.
        cloud_gray = np.clip(
            190.0 + (55.0 * cloud_strength),
            0.0,
            255.0,
        ).astype(np.uint8)

        rgba = np.zeros((source.height, source.width, 4), dtype=np.uint8)
        rgba[:, :, 0] = cloud_gray
        rgba[:, :, 1] = cloud_gray
        rgba[:, :, 2] = np.clip(
            cloud_gray.astype(np.int16) + 3,
            0,
            255,
        ).astype(np.uint8)
        rgba[:, :, 3] = alpha.astype(np.uint8)

        layer = Image.fromarray(rgba, "RGBA")

        return layer, {
            "visible_pixels": int(np.count_nonzero(rgba[:, :, 3])),
            "mean_alpha": float(alpha.mean()),
            "max_alpha": int(alpha.max()),
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

        # Satelitní zdroj má proti lokální mapě nízké rozlišení. Změkčení
        # až po promítnutí odstraní zvětšené bloky jednotlivých pixelů.
        if self.projected_blur_radius > 0:
            alpha = projected.getchannel("A").filter(
                ImageFilter.GaussianBlur(self.projected_blur_radius)
            )
            projected.putalpha(alpha)

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

    def save_debug_images(self, projected, canvas, image_file):
        if not self.save_debug_layer:
            return

        self.debug_file.parent.mkdir(parents=True, exist_ok=True)
        projected.save(self.debug_file)

        preview = canvas.copy()
        preview.paste(projected, (0, 0), projected)
        preview.save(self.preview_file)

        shutil.copy2(image_file, self.source_debug_file)

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

            self.save_debug_images(projected, canvas, image_file)
            canvas.paste(projected, (0, 0), projected)

            age_minutes = self._file_age_minutes(filename)
            age_text = (
                f"{age_minutes} minut"
                if age_minutes is not None
                else "neznámé"
            )

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
                print(
                    "[Clouds] Uložen zdrojový snímek: "
                    f"{self.source_debug_file}"
                )

            if source_info["visible_pixels"] == 0:
                print(
                    "[Clouds] Zdrojová maska je prázdná. Sniž "
                    "CLOUDS_BASE_BRIGHTNESS nebo CLOUDS_MIN_STRENGTH."
                )
            elif projection_info["visible_pixels"] == 0:
                print(
                    "[Clouds] Oblačnost ve zdroji existuje, ale mimo "
                    "aktuální zobrazenou oblast."
                )

        except Exception as error:
            print(f"[Clouds] Chyba: {error}")
