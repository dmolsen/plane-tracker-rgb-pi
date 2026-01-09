# scenes/daysforecast.py
from datetime import datetime
from PIL import Image

from utilities.animator import Animator
from setup import colours, fonts, frames, screen
from utilities.temperature import grab_forecast
from config import NIGHT_START, NIGHT_END

# -----------------------------
# CONFIG / LAYOUT (original)
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

# Clear region for forecast (same area you used)
FORECAST_CLEAR_X0 = 0
FORECAST_CLEAR_Y0 = 12
FORECAST_CLEAR_X1 = 64
FORECAST_CLEAR_Y1 = 32

NIGHT_START_TIME = datetime.strptime(NIGHT_START, "%H:%M").time()
NIGHT_END_TIME = datetime.strptime(NIGHT_END, "%H:%M").time()


class DaysForecastScene(object):
    def __init__(self):
        super().__init__()
        self._redraw_forecast = True
        self._last_hour = None
        self._cached_forecast = None

        # icon_name -> PIL.Image(RGB) or None
        self._icon_cache = {}

    def _clear_forecast_region(self):
        self.draw_square(
            FORECAST_CLEAR_X0,
            FORECAST_CLEAR_Y0,
            FORECAST_CLEAR_X1,
            FORECAST_CLEAR_Y1,
            colours.BLACK,
        )

    def _load_icon_old_path(self, icon_name: str):
        """
        OLD BEHAVIOR:
        Load icons from ./icons/<icon_name>.png relative to the process CWD.
        """
        if not icon_name:
            return None

        icon_name = str(icon_name).strip()
        if icon_name in self._icon_cache:
            return self._icon_cache[icon_name]

        path = f"icons/{icon_name}.png"  # <-- exactly like original
        try:
            img = Image.open(path)

            try:
                resample = Image.Resampling.LANCZOS  # Pillow 10+
            except AttributeError:
                resample = Image.ANTIALIAS          # Pillow <10

            img.thumbnail((ICON_SIZE, ICON_SIZE), resample)
            img = img.convert("RGB")

            self._icon_cache[icon_name] = img
            return img
        except Exception:
            self._icon_cache[icon_name] = None
            return None

    @Animator.KeyFrame.add(frames.PER_SECOND * 1, tag="default")
    def day(self, count):
        # Force redraw on night boundary (kept from original intent)
        now_time = datetime.now().replace(microsecond=0).time()
        if now_time == NIGHT_START_TIME or now_time == NIGHT_END_TIME:
            self._redraw_forecast = True
            return

        # If flights active, don't draw forecast (your new tag gating should handle this,
        # but this preserves the original “if len(self._data)” behavior)
        if len(getattr(self, "_data", [])):
            self._redraw_forecast = True
            return

        current_hour = datetime.now().hour

        need_fetch = False
        if self._cached_forecast is None:
            need_fetch = True
        elif self._last_hour != current_hour:
            need_fetch = True

        # Draw only when hour changes or when forced
        if (self._last_hour == current_hour) and (not self._redraw_forecast):
            return

        # Clear region before drawing
        if self._last_hour is not None:
            self._clear_forecast_region()

        # Update last_hour after deciding
        self._last_hour = current_hour

        # -------------------------
        # FETCH OR USE CACHE
        # -------------------------
        if need_fetch:
            forecast = grab_forecast(tag="days")

            # API failed -> use cache if available
            if not forecast:
                if self._cached_forecast:
                    forecast = self._cached_forecast
                else:
                    return
            else:
                self._cached_forecast = forecast
        else:
            forecast = self._cached_forecast

        self._redraw_forecast = False

        # -------------------------
        # RENDER FORECAST (3 columns)
        # -------------------------
        offset = 1
        space_width = screen.WIDTH // 3

        for day in forecast[:3]:
            start_time = day.get("startTime", "")
            try:
                day_name = datetime.fromisoformat(start_time.rstrip("Z")).strftime("%a")
            except Exception:
                day_name = "--"

            values = day.get("values", {}) or {}
            icon_name = values.get("weatherCodeFullDay")

            min_v = values.get("temperatureMin")
            max_v = values.get("temperatureMax")

            min_temp = f"{min_v:.0f}" if isinstance(min_v, (int, float)) else "--"
            max_temp = f"{max_v:.0f}" if isinstance(max_v, (int, float)) else "--"

            min_temp_width = len(min_temp) * 4
            max_temp_width = len(max_temp) * 4

            temp_x = offset + (space_width - min_temp_width - max_temp_width - 1) // 2 + 1
            max_temp_x = temp_x
            min_temp_x = temp_x + max_temp_width

            icon_x = offset + (space_width - ICON_SIZE) // 2
            day_x = offset + (space_width - 12) // 2 + 1

            # Draw day name
            self.draw_text(TEXT_FONT, day_x, DAY_POSITION, DAY_COLOUR, day_name)

            # Draw icon (OLD PATH) but using backbuffer-safe helper
            if icon_name:
                icon_img = self._load_icon_old_path(icon_name)
                if icon_img is not None:
                    self.set_image(icon_img, icon_x, ICON_POSITION)

            # Draw temps
            self.draw_text(TEXT_FONT, max_temp_x, TEMP_POSITION, MAX_T_COLOUR, max_temp)
            self.draw_text(TEXT_FONT, min_temp_x, TEMP_POSITION, MIN_T_COLOUR, min_temp)

            offset += space_width