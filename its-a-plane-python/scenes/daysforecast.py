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

        # Cache icons so we don't hit disk + resize every frame (flicker fix)
        self._icon_cache = {}

        # Track screen off/on transitions so we redraw when returning
        self._was_screen_off = False

    def _is_screen_off(self) -> bool:
        return getattr(self.matrix, "brightness", 1) == 0

    def _flights_active(self) -> bool:
        return len(getattr(self, "_data", [])) > 0

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
                resample = Image.ANTIALIAS  # Pillow <10

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
        # --- Screen off gating ---
        if self._is_screen_off():
            self._was_screen_off = True
            return

        # --- Flights active gating (prevents forecast overlaying flights) ---
        if self._flights_active():
            # Ensure we redraw immediately when flights clear
            self._redraw_forecast = True
            return

        # If we were previously off and are now on, force a redraw
        if self._was_screen_off:
            self._was_screen_off = False
            self._redraw_forecast = True

        now = datetime.now()
        now_time = now.replace(microsecond=0).time()

        # Redraw on night start/end (brightness changes)
        if now_time == NIGHT_START_TIME.time() or now_time == NIGHT_END_TIME.time():
            self._redraw_forecast = True

        current_hour = now.hour

        # Decide if we need to fetch forecast
        need_fetch = (self._cached_forecast is None) or (self._last_hour != current_hour)

        # Decide if we need to redraw (hour tick or forced redraw)
        need_redraw = (self._last_hour != current_hour) or self._redraw_forecast

        # If we don't need either, bail
        if not need_fetch and not need_redraw:
            return

        # Update hour marker
        self._last_hour = current_hour

        # -------------------------
        # FETCH OR USE CACHE
        # -------------------------
        if need_fetch:
            forecast = grab_forecast(tag="days")
            if forecast:
                self._cached_forecast = forecast
            else:
                # If fetch failed and nothing cached, try again next tick
                if not self._cached_forecast:
                    self._redraw_forecast = True
                    return

        forecast = self._cached_forecast
        if not forecast:
            self._redraw_forecast = True
            return

        # -------------------------
        # DRAW
        # -------------------------
        # Clear previous area whenever we draw
        self.draw_square(0, 12, 64, 32, colours.BLACK)

        self._redraw_forecast = False

        offset = 1
        space_width = screen.WIDTH // 3

        # Only render first 3 days (layout assumes 3 columns)
        for day in forecast[:3]:
            day_name = datetime.fromisoformat(day["startTime"].rstrip("Z")).strftime("%a")
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
            graphics.DrawText(self.canvas, TEXT_FONT, day_x, DAY_POSITION, DAY_COLOUR, day_name)

            # Weather icon (cached — no flicker)
            icon_image = self._get_icon(icon_name)
            if icon_image is not None:
                self.matrix.SetImage(icon_image, icon_x, ICON_POSITION)

            # Temps
            graphics.DrawText(self.canvas, TEXT_FONT, max_temp_x, TEMP_POSITION, MAX_T_COLOUR, max_temp)
            graphics.DrawText(self.canvas, TEXT_FONT, min_temp_x, TEMP_POSITION, MIN_T_COLOUR, min_temp)

            offset += space_width