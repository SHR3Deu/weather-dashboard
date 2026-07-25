import json
import math
import time
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFont

import config
from layers.base import Layer


class AircraftLayer(Layer):
    name = "Aircraft"

    LABEL_ALIASES = {
        "flight": "flight",
        "callsign": "flight",
        "let": "flight",
        "altitude": "altitude",
        "height": "altitude",
        "vyska": "altitude",
        "výška": "altitude",
        "speed": "speed",
        "rychlost": "speed",
        "type": "type",
        "typ": "type",
        "registration": "registration",
        "registrace": "registration",
        "hex": "hex",
        "icao": "hex",
    }

    def __init__(self):
        self.api_base_url = str(
            getattr(config, "AIRCRAFT_API_BASE_URL", "https://api.adsb.lol")
        ).rstrip("/")
        self.request_timeout = tuple(
            getattr(config, "AIRCRAFT_REQUEST_TIMEOUT", (10, 25))
        )
        self.user_agent = str(
            getattr(
                config,
                "AIRCRAFT_USER_AGENT",
                "weather-dashboard/1.0 "
                "(+https://github.com/SHR3Deu/weather-dashboard)",
            )
        )

        self.icon_size = self._clamp_int(
            getattr(config, "AIRCRAFT_ICON_SIZE", 28), 8, 100
        )
        self.text_size = self._clamp_int(
            getattr(config, "AIRCRAFT_TEXT_SIZE", 14), 8, 72
        )
        self.label_fields = self._parse_label_fields(
            getattr(
                config,
                "AIRCRAFT_LABEL_FIELDS",
                "flight,altitude,speed,type",
            )
        )
        self.label_separator = str(
            getattr(config, "AIRCRAFT_LABEL_SEPARATOR", " | ")
        )
        self.label_offset = tuple(
            getattr(config, "AIRCRAFT_LABEL_OFFSET", (18, -16))
        )

        self.icon_color = str(
            getattr(config, "AIRCRAFT_ICON_COLOR", "#FFD400")
        )
        self.icon_outline_color = str(
            getattr(config, "AIRCRAFT_ICON_OUTLINE_COLOR", "#101010")
        )
        self.text_color = str(
            getattr(config, "AIRCRAFT_TEXT_COLOR", "#FFFFFF")
        )
        self.text_outline_color = str(
            getattr(config, "AIRCRAFT_TEXT_OUTLINE_COLOR", "#000000")
        )
        self.text_outline_width = self._clamp_int(
            getattr(config, "AIRCRAFT_TEXT_OUTLINE_WIDTH", 2), 0, 6
        )

        self.trajectory_width = self._clamp_int(
            getattr(config, "AIRCRAFT_TRAJECTORY_WIDTH", 2), 0, 10
        )
        self.trajectory_color = str(
            getattr(config, "AIRCRAFT_TRAJECTORY_COLOR", "#FFD400")
        )
        self.trajectory_outline_color = str(
            getattr(config, "AIRCRAFT_TRAJECTORY_OUTLINE_COLOR", "#000000")
        )
        self.trajectory_history_minutes = max(
            1,
            int(getattr(config, "AIRCRAFT_TRAJECTORY_HISTORY_MINUTES", 30)),
        )
        self.trajectory_max_points = max(
            2,
            int(getattr(config, "AIRCRAFT_TRAJECTORY_MAX_POINTS", 60)),
        )
        self.trajectory_min_distance_m = max(
            0.0,
            float(
                getattr(
                    config,
                    "AIRCRAFT_TRAJECTORY_MIN_DISTANCE_METERS",
                    250.0,
                )
            ),
        )
        self.trajectory_max_jump_km = max(
            1.0,
            float(
                getattr(config, "AIRCRAFT_TRAJECTORY_MAX_JUMP_KM", 250.0)
            ),
        )

        self.radius_nm = self._clamp_int(
            getattr(config, "AIRCRAFT_RADIUS_NM", 0), 0, 250
        )
        self.radius_margin = max(
            1.0,
            float(getattr(config, "AIRCRAFT_RADIUS_MARGIN", 1.20)),
        )
        self.max_seen_seconds = max(
            1.0,
            float(getattr(config, "AIRCRAFT_MAX_SEEN_SECONDS", 45.0)),
        )
        self.max_aircraft = max(
            1,
            int(getattr(config, "AIRCRAFT_MAX_COUNT", 80)),
        )

        self.altitude_unit = str(
            getattr(config, "AIRCRAFT_ALTITUDE_UNIT", "m")
        ).strip().lower()
        self.speed_unit = str(
            getattr(config, "AIRCRAFT_SPEED_UNIT", "kmh")
        ).strip().lower()

        self.cache_dir = config.CACHE / "aircraft"
        self.response_cache_file = self.cache_dir / "latest.json"
        self.history_file = self.cache_dir / "history.json"
        self.response_cache_max_age = max(
            0,
            int(getattr(config, "AIRCRAFT_CACHE_MAX_AGE_SECONDS", 180)),
        )

        self.save_debug_layer = bool(
            getattr(config, "AIRCRAFT_SAVE_DEBUG_LAYER", True)
        )
        self.debug_file = Path(
            getattr(
                config,
                "AIRCRAFT_DEBUG_FILE",
                config.OUTPUT_DIR / "latest_aircraft.png",
            )
        )
        self.save_raw_json = bool(
            getattr(config, "AIRCRAFT_SAVE_RAW_JSON", True)
        )
        self.raw_json_file = Path(
            getattr(
                config,
                "AIRCRAFT_RAW_JSON_FILE",
                config.OUTPUT_DIR / "latest_aircraft.json",
            )
        )

        self.show_attribution = bool(
            getattr(config, "AIRCRAFT_SHOW_ATTRIBUTION", True)
        )
        self.attribution_text = str(
            getattr(config, "AIRCRAFT_ATTRIBUTION", "Data: ADSB.lol (ODbL)")
        )

        self.font = self._load_font(self.text_size)
        self.attribution_font = self._load_font(max(9, self.text_size - 3))

    @staticmethod
    def _clamp_int(value, minimum, maximum):
        try:
            number = int(value)
        except (TypeError, ValueError):
            number = minimum
        return max(minimum, min(maximum, number))

    @staticmethod
    def _load_font(size):
        try:
            return ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                size,
            )
        except Exception:
            return ImageFont.load_default()

    def _parse_label_fields(self, value):
        if isinstance(value, (list, tuple)):
            raw_fields = value
        else:
            raw_fields = str(value).split(",")

        fields = []
        for raw_field in raw_fields:
            key = str(raw_field).strip().lower()
            normalized = self.LABEL_ALIASES.get(key)
            if normalized and normalized not in fields:
                fields.append(normalized)
        return fields

    def _query_radius_nm(self, basemap):
        if self.radius_nm > 0:
            return self.radius_nm

        meters_per_pixel = basemap.meters_per_pixel()
        half_width_m = config.MAP_WIDTH * meters_per_pixel / 2.0
        half_height_m = config.MAP_HEIGHT * meters_per_pixel / 2.0
        diagonal_radius_m = math.hypot(half_width_m, half_height_m)
        radius_nm = math.ceil(
            diagonal_radius_m * self.radius_margin / 1852.0
        )
        return max(1, min(250, radius_nm))

    def _api_url(self, radius_nm):
        return (
            f"{self.api_base_url}/v2/lat/{config.CENTER_LAT}/"
            f"lon/{config.CENTER_LON}/dist/{radius_nm}"
        )

    def _atomic_write_json(self, path, payload):
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary_file = path.with_suffix(path.suffix + ".tmp")
        temporary_file.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary_file.replace(path)

    def _load_json(self, path, default):
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, TypeError):
            return default

    def download(self, radius_nm):
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        try:
            response = requests.get(
                self._api_url(radius_nm),
                headers={"User-Agent": self.user_agent},
                timeout=self.request_timeout,
            )
            response.raise_for_status()
            payload = response.json()

            if not isinstance(payload, dict) or not isinstance(
                payload.get("ac"), list
            ):
                raise RuntimeError("API vrátilo neočekávaný formát dat.")

            payload["_weather_dashboard_downloaded_at"] = int(time.time())
            self._atomic_write_json(self.response_cache_file, payload)
            return payload, False

        except (requests.RequestException, ValueError, RuntimeError) as error:
            cached = self._load_json(self.response_cache_file, None)
            if isinstance(cached, dict):
                downloaded_at = int(
                    cached.get("_weather_dashboard_downloaded_at", 0)
                )
                age = max(0, int(time.time()) - downloaded_at)
                if age <= self.response_cache_max_age:
                    print(
                        "[Aircraft] API není dostupné, používám cache "
                        f"starou {age} s: {error}"
                    )
                    return cached, True
            raise

    def _normalize_aircraft(self, payload):
        aircraft = []

        for item in payload.get("ac", []):
            if not isinstance(item, dict):
                continue

            lat = item.get("lat")
            lon = item.get("lon")
            seen_pos = item.get("seen_pos")

            if not isinstance(lat, (int, float)):
                continue
            if not isinstance(lon, (int, float)):
                continue
            if isinstance(seen_pos, (int, float)) and seen_pos > self.max_seen_seconds:
                continue

            hex_code = str(item.get("hex") or "").strip().lower()
            if not hex_code:
                continue

            track = item.get("track")
            if not isinstance(track, (int, float)):
                track = item.get("true_heading")
            if not isinstance(track, (int, float)):
                track = item.get("mag_heading")
            if not isinstance(track, (int, float)):
                track = 0.0

            aircraft.append(
                {
                    "hex": hex_code,
                    "lat": float(lat),
                    "lon": float(lon),
                    "track": float(track) % 360.0,
                    "flight": str(item.get("flight") or "").strip(),
                    "altitude": item.get("alt_baro", item.get("alt_geom")),
                    "speed": item.get("gs"),
                    "type": str(item.get("t") or "").strip(),
                    "registration": str(item.get("r") or "").strip(),
                    "seen_pos": float(seen_pos or 0.0),
                    "raw": item,
                }
            )

        aircraft.sort(key=lambda ac: ac["seen_pos"])
        return aircraft[: self.max_aircraft]

    @staticmethod
    def _distance_m(lat1, lon1, lat2, lon2):
        radius_m = 6371000.0
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lon2 - lon1)
        value = (
            math.sin(delta_phi / 2.0) ** 2
            + math.cos(phi1)
            * math.cos(phi2)
            * math.sin(delta_lambda / 2.0) ** 2
        )
        return radius_m * 2.0 * math.atan2(math.sqrt(value), math.sqrt(1.0 - value))

    def _update_history(self, aircraft):
        now = int(time.time())
        cutoff = now - self.trajectory_history_minutes * 60
        history = self._load_json(self.history_file, {"aircraft": {}})

        if not isinstance(history, dict):
            history = {"aircraft": {}}
        if not isinstance(history.get("aircraft"), dict):
            history["aircraft"] = {}

        aircraft_history = history["aircraft"]

        for hex_code in list(aircraft_history.keys()):
            points = aircraft_history.get(hex_code)
            if not isinstance(points, list):
                del aircraft_history[hex_code]
                continue

            valid_points = []
            for point in points:
                if not isinstance(point, dict):
                    continue
                timestamp = int(point.get("time", 0))
                lat = point.get("lat")
                lon = point.get("lon")
                if timestamp < cutoff:
                    continue
                if not isinstance(lat, (int, float)) or not isinstance(
                    lon, (int, float)
                ):
                    continue
                valid_points.append(
                    {"time": timestamp, "lat": float(lat), "lon": float(lon)}
                )

            if valid_points:
                aircraft_history[hex_code] = valid_points[-self.trajectory_max_points :]
            else:
                del aircraft_history[hex_code]

        for item in aircraft:
            points = aircraft_history.setdefault(item["hex"], [])
            new_point = {
                "time": now,
                "lat": item["lat"],
                "lon": item["lon"],
            }

            if points:
                previous = points[-1]
                distance_m = self._distance_m(
                    previous["lat"],
                    previous["lon"],
                    new_point["lat"],
                    new_point["lon"],
                )

                if distance_m > self.trajectory_max_jump_km * 1000.0:
                    points.clear()
                elif distance_m < self.trajectory_min_distance_m:
                    previous.update(new_point)
                    continue

            points.append(new_point)
            aircraft_history[item["hex"]] = points[-self.trajectory_max_points :]

        history["updated_at"] = now
        self._atomic_write_json(self.history_file, history)
        return aircraft_history

    def _format_altitude(self, value):
        if isinstance(value, str):
            if value.lower() == "ground":
                return "země"
            try:
                value = float(value)
            except ValueError:
                return "?"

        if not isinstance(value, (int, float)):
            return "?"

        feet = float(value)
        if self.altitude_unit in ("ft", "feet"):
            return f"{int(round(feet / 100.0) * 100):,} ft".replace(",", " ")

        meters = feet * 0.3048
        return f"{int(round(meters / 100.0) * 100):,} m".replace(",", " ")

    def _format_speed(self, value):
        if not isinstance(value, (int, float)):
            return "?"

        knots = float(value)
        if self.speed_unit in ("kt", "kts", "knot", "knots"):
            return f"{int(round(knots))} kt"

        return f"{int(round(knots * 1.852))} km/h"

    def _label_text(self, aircraft):
        values = []
        for field in self.label_fields:
            if field == "flight":
                value = aircraft["flight"] or aircraft["hex"].upper()
            elif field == "altitude":
                value = self._format_altitude(aircraft["altitude"])
            elif field == "speed":
                value = self._format_speed(aircraft["speed"])
            elif field == "type":
                value = aircraft["type"] or "?"
            elif field == "registration":
                value = aircraft["registration"] or "?"
            elif field == "hex":
                value = aircraft["hex"].upper()
            else:
                continue
            values.append(value)
        return self.label_separator.join(values)

    def _plane_icon(self, heading):
        supersampling = 4
        size = self.icon_size * supersampling
        center = size / 2.0
        scale = size * 0.44

        shape = [
            (0.00, -1.00),
            (0.15, -0.28),
            (0.72, 0.02),
            (0.70, 0.22),
            (0.16, 0.13),
            (0.12, 0.62),
            (0.34, 0.82),
            (0.28, 0.96),
            (0.00, 0.79),
            (-0.28, 0.96),
            (-0.34, 0.82),
            (-0.12, 0.62),
            (-0.16, 0.13),
            (-0.70, 0.22),
            (-0.72, 0.02),
            (-0.15, -0.28),
        ]

        points = [
            (center + x * scale, center + y * scale)
            for x, y in shape
        ]

        icon = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(icon)
        draw.polygon(
            points,
            fill=self.icon_color,
            outline=self.icon_outline_color,
            width=max(2, supersampling),
        )

        icon = icon.rotate(
            -float(heading),
            resample=Image.Resampling.BICUBIC,
            expand=False,
        )
        return icon.resize(
            (self.icon_size, self.icon_size),
            Image.Resampling.LANCZOS,
        )

    @staticmethod
    def _boxes_overlap(first, second, padding=3):
        return not (
            first[2] + padding < second[0]
            or second[2] + padding < first[0]
            or first[3] + padding < second[1]
            or second[3] + padding < first[1]
        )

    def _choose_label_position(self, draw, x, y, text, occupied_boxes):
        bbox = draw.textbbox((0, 0), text, font=self.font, stroke_width=self.text_outline_width)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        offset_x = int(self.label_offset[0])
        offset_y = int(self.label_offset[1])
        icon_half = self.icon_size // 2

        candidates = [
            (x + offset_x, y + offset_y),
            (x + offset_x, y + icon_half + 3),
            (x - text_width - offset_x, y + offset_y),
            (x - text_width - offset_x, y + icon_half + 3),
            (x - text_width // 2, y - icon_half - text_height - 3),
            (x - text_width // 2, y + icon_half + 3),
        ]

        for tx, ty in candidates:
            box = (tx, ty, tx + text_width, ty + text_height)
            if box[0] < 0 or box[1] < 0:
                continue
            if box[2] >= config.MAP_WIDTH or box[3] >= config.MAP_HEIGHT:
                continue
            if any(self._boxes_overlap(box, other) for other in occupied_boxes):
                continue
            occupied_boxes.append(box)
            return tx, ty

        tx = min(max(0, x + offset_x), max(0, config.MAP_WIDTH - text_width - 1))
        ty = min(max(0, y + offset_y), max(0, config.MAP_HEIGHT - text_height - 1))
        occupied_boxes.append((tx, ty, tx + text_width, ty + text_height))
        return tx, ty

    def _draw_trajectories(self, overlay, basemap, aircraft, history):
        if self.trajectory_width <= 0:
            return 0

        draw = ImageDraw.Draw(overlay)
        drawn = 0

        for item in aircraft:
            points = history.get(item["hex"], [])
            if len(points) < 2:
                continue

            screen_points = [
                basemap.screen_position(point["lat"], point["lon"])
                for point in points
            ]

            draw.line(
                screen_points,
                fill=self.trajectory_outline_color,
                width=min(12, self.trajectory_width + 2),
                joint="curve",
            )
            draw.line(
                screen_points,
                fill=self.trajectory_color,
                width=self.trajectory_width,
                joint="curve",
            )
            drawn += 1

        return drawn

    def _draw_aircraft(self, overlay, basemap, aircraft):
        draw = ImageDraw.Draw(overlay)
        occupied_boxes = []
        visible = 0

        for item in aircraft:
            x, y = basemap.screen_position(item["lat"], item["lon"])
            margin = self.icon_size
            if x < -margin or x >= config.MAP_WIDTH + margin:
                continue
            if y < -margin or y >= config.MAP_HEIGHT + margin:
                continue

            icon = self._plane_icon(item["track"])
            icon_x = int(x - icon.width / 2)
            icon_y = int(y - icon.height / 2)
            overlay.alpha_composite(icon, (icon_x, icon_y))
            visible += 1

            text = self._label_text(item)
            if not text:
                continue

            tx, ty = self._choose_label_position(
                draw,
                x,
                y,
                text,
                occupied_boxes,
            )
            draw.text(
                (tx, ty),
                text,
                font=self.font,
                fill=self.text_color,
                stroke_width=self.text_outline_width,
                stroke_fill=self.text_outline_color,
            )

        return visible

    def _draw_attribution(self, overlay):
        if not self.show_attribution:
            return

        draw = ImageDraw.Draw(overlay)
        bbox = draw.textbbox((0, 0), self.attribution_text, font=self.attribution_font)
        width = bbox[2] - bbox[0]
        height = bbox[3] - bbox[1]
        x = config.MAP_WIDTH - width - 8
        y = config.MAP_HEIGHT - height - 7
        draw.text(
            (x, y),
            self.attribution_text,
            font=self.attribution_font,
            fill="#FFFFFF",
            stroke_width=2,
            stroke_fill="#000000",
        )

    def draw(self, canvas, basemap):
        try:
            radius_nm = self._query_radius_nm(basemap)
            payload, from_cache = self.download(radius_nm)
            aircraft = self._normalize_aircraft(payload)
            history = self._update_history(aircraft)

            if self.save_raw_json:
                self._atomic_write_json(self.raw_json_file, payload)

            overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
            trajectories = self._draw_trajectories(
                overlay,
                basemap,
                aircraft,
                history,
            )
            visible = self._draw_aircraft(overlay, basemap, aircraft)
            self._draw_attribution(overlay)

            if self.save_debug_layer:
                self.debug_file.parent.mkdir(parents=True, exist_ok=True)
                overlay.save(self.debug_file)

            canvas.paste(overlay, (0, 0), overlay)

            print(f"[Aircraft] Zdroj: ADSB.lol")
            print(f"[Aircraft] Dotazovaný poloměr: {radius_nm} NM")
            print(f"[Aircraft] Přijatá letadla: {len(payload.get('ac', []))}")
            print(f"[Aircraft] Platná čerstvá letadla: {len(aircraft)}")
            print(f"[Aircraft] Letadla ve viewportu: {visible}")
            print(f"[Aircraft] Vykreslené trajektorie: {trajectories}")
            print(
                "[Aircraft] Data: "
                + ("cache" if from_cache else "online")
            )

            if self.save_debug_layer:
                print(f"[Aircraft] Uložena vrstva: {self.debug_file}")
            if self.save_raw_json:
                print(f"[Aircraft] Uložena data: {self.raw_json_file}")

        except Exception as error:
            print(f"[Aircraft] Chyba: {error}")
