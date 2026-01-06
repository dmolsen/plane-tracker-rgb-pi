from datetime import datetime
from PIL import Image

from utilities.animator import Animator
from setup import colours, fonts, frames, screen
from utilities.temperature import grab_forecast
from config import NIGHT_START, NIGHT_END
from rgbmatrix import graphics

# -----------------------------
# CONFIG
# -----------------------------
DAY_COLOUR = colours.LIGHT_PINK
MIN_T_COLOUR = colours.LIGHT_MID_BLUE
MAX_T_COLOUR = colours.LIGHT_DARK_ORANGE

TEXT_FONT = fonts.extrasmall
FONT_HEIGHT = 5

DISTANCE_FROM_TOP = 32
ICON_SIZE = 10
FORECAST_SIZE = FONT_HEIGHT * 2 + ICON_SIZE

DAY_POSITION = DISTANCE_FROM_TOP - FONT_HEIGHT - ICON_SIZE
ICON_POSITION = DISTANCE_FROM_TOP - FONT_HEIGHT - ICON_SIZE
TEMP_POSITION = DISTANCE_FROM_TOP

NIGHT_START_TIME = datetime.strptime(NIGHT_START, "%H:%M")
NIGHT_END_TIME = datetime.strptime(NIGHT_END, "%H:%M")


class DaysForecastScene(object):
    def __init__(self):
        super().__init__()
        self._redraw_forecast = True
        self._last_hour = None
        self._cached_forecast = None
        self._icon_cache = {}   # ← ICON CACHE (KEY FIX)

    # -----------------------------
    # ICON LOADER (CACHED)
    # -----------------------------
    def _get_icon(self, icon_name):
        if icon_name in self._icon_cache:
            return self._icon_cache[icon_name]

        try:
            image = Image.open(f"icons/{icon_name}.png")
            try:
                resample = Image.Resampling.LANCZOS  # Pillow 10+
            except AttributeError:
                resample = Image.ANTIALIAS          # Pillow <10

            image.thumbnail((ICON_SIZE, ICON_SIZE), resample)
            image = image.convert("RGB")

            self._icon_cache[icon_name] = image
            return image

        except Exception:
            # Cache failure to prevent repeated retries & flicker
            self._icon_cache[icon_name] = None
            return None

    # -----------------------------
    # MAIN RENDER LOOP
    # -----------------------------
    @Animator.KeyFrame.add(frames.PER_SECOND * 1)
    def day(self, count):
        now = datetime.now().replace(microsecond=0).time()

        # Redraw on night start/end (brightness changes)
        if now == NIGHT_START_TIME.time() or now == NIGHT_END_TIME.time():
            self._redraw_forecast = True
            return

        # Scene switch: redraw but don't fetch
        if len(self._data):
            self._redraw_forecast = True
            return

        current_hour = datetime.now().hour

        # Decide if forecast needs fetching
        need_fetch = (
            self._cached_forecast is None or
            self._last_hour != current_hour
        )

        # Only redraw when needed
        if self._last_hour != current_hour or self._redraw_forecast:

            # Clear old forecast area
            if self._last_hour is not None:
                self.draw_square(0, 12, 64, 32, colours.BLACK)

            self._last_hour = current_hour

            # -------------------------
            # FETCH OR USE CACHE
            # -------------------------
            if need_fetch:
                forecast = grab_forecast(tag="days")

                if not forecast:
                    if not self._cached_forecast:
                        return
                    forecast = self._cached_forecast
                else:
                    self._cached_forecast = forecast
            else:
                forecast = self._cached_forecast

            self._redraw_forecast = False

            # -------------------------
            # RENDER FORECAST
            # -------------------------
            offset = 1
            space_width = screen.WIDTH // 3

            for day in forecast:
                day_name = datetime.fromisoformat(
                    day["startTime"].rstrip("Z")
                ).strftime("%a")

                icon_name = day["values"]["weatherCodeFullDay"]

                min_temp = f"{day['values']['temperatureMin']:.0f}"
                max_temp = f"{day['values']['temperatureMax']:.0f}"

                min_temp_width = len(min_temp) * 4
                max_temp_width = len(max_temp) * 4

                temp_x = offset + (space_width - min_temp_width - max_temp_width - 1) // 2 + 1
                max_temp_x = temp_x
                min_temp_x = temp_x + max_temp_width

                icon_x = offset + (space_width - ICON_SIZE) // 2
                day_x = offset + (space_width - 12) // 2 + 1

                # Day label
                graphics.DrawText(
                    self.canvas,
                    TEXT_FONT,
                    day_x,
                    DAY_POSITION,
                    DAY_COLOUR,
                    day_name,
                )

                # Weather icon (CACHED — NO FLICKER)
                icon_image = self._get_icon(icon_name)
                if icon_image:
                    self.matrix.SetImage(
                        icon_image,
                        icon_x,
                        ICON_POSITION,
                    )

                # Temps
                graphics.DrawText(
                    self.canvas,
                    TEXT_FONT,
                    max_temp_x,
                    TEMP_POSITION,
                    MAX_T_COLOUR,
                    max_temp,
                )
                graphics.DrawText(
                    self.canvas,
                    TEXT_FONT,
                    min_temp_x,
                    TEMP_POSITION,
                    MIN_T_COLOUR,
                    min_temp,
                )

                offset += space_width
