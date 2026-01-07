import os
from datetime import datetime
from PIL import Image

from utilities.animator import Animator
from setup import colours, fonts, frames, screen
from utilities.temperature import grab_forecast
from rgbmatrix import graphics

# -----------------------------
# CONFIG / LAYOUT
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

# Clear region for forecast
FORECAST_CLEAR_X0 = 0
FORECAST_CLEAR_Y0 = 12
FORECAST_CLEAR_X1 = 64
FORECAST_CLEAR_Y1 = 32

# Icons directory
_THIS_DIR = os.path.dirname(__file__)

# If your icons are in: scenes/icons/
ICONS_DIR = os.path.join(_THIS_DIR, "icons")

# If your icons are in: project-root/icons/, uncomment this instead:
# ICONS_DIR = os.path.join(os.path.dirname(_THIS_DIR), "icons")


class DaysForecastScene(object):
    def __init__(self):
        super().__init__()
        self._redraw_forecast = True
        self._cached_forecast = None
        self._last_fetch_hour = None

        # icon_name -> PIL.Image (RGB) or None if missing/bad
        self._icon_cache = {}

        # Track flight transitions (home <-> flight mode)
        self._was_showing_flights = False

    def _clear_forecast_region(self):
        self.draw_square(
            FORECAST_CLEAR_X0,
            FORECAST_CLEAR_Y0,
            FORECAST_CLEAR_X1,
            FORECAST_CLEAR_Y1,
            colours.BLACK,
        )

    def _get_icon(self, icon_name: str):
        """Load+resize icon once; return cached PIL RGB image or None."""
        if icon_name in self._icon_cache:
            return self._icon_cache[icon_name]

        path = os.path.join(ICONS_DIR, f"{icon_name}.png")
        try:
            img = Image.open(path)

            # Pillow 10+: Resampling.LANCZOS, older: ANTIALIAS
            try:
                resample = Image.Resampling.LANCZOS
            except AttributeError:
                resample = Image.ANTIALIAS

            img.thumbnail((ICON_SIZE, ICON_SIZE), resample)
            img = img.convert("RGB")

            self._icon_cache[icon_name] = img
            return img
        except Exception:
            # Cache miss/failure so we don't keep retrying every frame
            self._icon_cache[icon_name] = None
            return None

    def _need_fetch(self, now: datetime) -> bool:
        # Fetch if never fetched, or hour changed
        if self._cached_forecast is None:
            return True
        if self._last_fetch_hour is None:
            return True
        return now.hour != self._last_fetch_hour

    @Animator.KeyFrame.add(frames.PER_SECOND * 1)
    def day(self, count):
        showing_flights = len(getattr(self, "_data", [])) > 0

        # --- If flights just started, clear forecast once so it doesn't linger/overlay
        if showing_flights and not self._was_showing_flights:
            self._was_showing_flights = True
            self._clear_forecast_region()
            return

        # --- If flights still active, don't draw or fetch forecast
        if showing_flights:
            return

        # --- If flights just ended, force redraw so forecast returns immediately
        if (not showing_flights) and self._was_showing_flights:
            self._was_showing_flights = False
            self._redraw_forecast = True
            self._clear_forecast_region()

        now = datetime.now()

        # Fetch at most once per hour
        need_fetch = self._need_fetch(now)

        # If neither fetch nor redraw is needed, no-op
        if (not need_fetch) and (not self._redraw_forecast):
            return

        # Fetch if needed
        if need_fetch:
            forecast = grab_forecast(tag="days")
            if forecast:
                self._cached_forecast = forecast
                self._last_fetch_hour = now.hour
            # if fetch fails, keep cached_forecast as-is

        forecast = self._cached_forecast
        if not forecast:
            # nothing to draw yet; try again later
            self._redraw_forecast = True
            return

        # We are rendering: clear region once
        self._clear_forecast_region()

        # -------------------------
        # RENDER (3 columns)
        # -------------------------
        offset = 1
        space_width = screen.WIDTH // 3

        for day in forecast[:3]:
            day_name = datetime.fromisoformat(day["startTime"].rstrip("Z")).strftime("%a")

            values = day.get("values", {})
            icon_name = values.get("weatherCodeFullDay")

            min_temp_val = values.get("temperatureMin")
            max_temp_val = values.get("temperatureMax")

            min_temp = f"{min_temp_val:.0f}" if isinstance(min_temp_val, (int, float)) else "--"
            max_temp = f"{max_temp_val:.0f}" if isinstance(max_temp_val, (int, float)) else "--"

            min_temp_width = len(min_temp) * 4
            max_temp_width = len(max_temp) * 4

            temp_x = offset + (space_width - min_temp_width - max_temp_width - 1) // 2 + 1
            max_temp_x = temp_x
            min_temp_x = temp_x + max_temp_width

            icon_x = offset + (space_width - ICON_SIZE) // 2
            day_x = offset + (space_width - 12) // 2 + 1

            graphics.DrawText(self.canvas, TEXT_FONT, day_x, DAY_POSITION, DAY_COLOUR, day_name)

            if icon_name:
                icon_img = self._get_icon(str(icon_name))
                if icon_img is not None:
                    self.canvas.SetImage(icon_img, icon_x, ICON_POSITION)

            graphics.DrawText(self.canvas, TEXT_FONT, max_temp_x, TEMP_POSITION, MAX_T_COLOUR, max_temp)
            graphics.DrawText(self.canvas, TEXT_FONT, min_temp_x, TEMP_POSITION, MIN_T_COLOUR, min_temp)

            offset += space_width

        self._redraw_forecast = False