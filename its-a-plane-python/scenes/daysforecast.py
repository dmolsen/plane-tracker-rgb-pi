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
FORECAST_CLEAR_Y1 = 32  # exclusive; safe once draw_square is fixed

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

        # Track Display-level full clears so we redraw after canvas.Clear()
        self._last_clear_token_seen = None

    def _clear_forecast_region(self):
        self.draw_square(
            FORECAST_CLEAR_X0,
            FORECAST_CLEAR_Y0,
            FORECAST_CLEAR_X1,
            FORECAST_CLEAR_Y1,
            colours.BLACK,
        )

    def _sync_with_canvas_clear(self):
        clear_token = getattr(self, "_clear_token", None)
        if clear_token is None:
            return

        if self._last_clear_token_seen is None:
            self._last_clear_token_seen = clear_token
            self._redraw_forecast = True
            return

        if clear_token != self._last_clear_token_seen:
            self._last_clear_token_seen = clear_token
            self._redraw_forecast = True

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

        path = f"icons/{icon_name}.png"  # exactly like original
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

    @Animator.KeyFrame.add(0, tag="default")
    def reset_forecast(self):
        # Called on reset_scene() (mode switch etc)
        self._redraw_forecast = True
        self._last_hour = None
        self._last_clear_token_seen = getattr(self, "_clear_token", None)
        self._clear_forecast_region()

    @Animator.KeyFrame.add(frames.PER_SECOND * 1, tag="default")
    def day(self, count):
        # If Display performed a full canvas clear since we last drew, force redraw.
        self._sync_with_canvas_clear()

        # Force redraw on night boundary (kept from original intent)
        now_time = datetime.now().replace(microsecond=0).time()
        if now_time == NIGHT_START_TIME or now_time == NIGHT_END_TIME:
            self._redraw_forecast = True
            return

        # If flights active, don't draw forecast
        if len(getattr(self, "_data", [])):
            self._redraw_forecast = True
            return

        current_hour = datetime.now().hour

        need_fetch = False
        if self._cached_forecast is None:
            need_fetch = True
        elif self._last_hour != current_hour:
            need_fetch = True

        # If nothing changed and no forced redraw, no-op
        if (self._last_hour == current_hour) and (not self._redraw_forecast):
            return

        # Update last_hour
        self._last_hour = current_hour

        # -------------------------
        # FETCH OR USE CACHE
        # -------------------------
        if need_fetch:
            forecast = grab_forecast(tag="days")
            if not forecast:
                # API failed -> use cache if available
                if self._cached_forecast:
                    forecast = self._cached_forecast
                else:
                    # Nothing cached yet
                    return
            else:
                self._cached_forecast = forecast
        else:
            forecast = self._cached_forecast

        if not forecast:
            return

        self._redraw_forecast = False

        # -------------------------
        # RENDER FORECAST (3 columns)
        # -------------------------
        self._clear_forecast_region()

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

            # Day name
            self.draw_text(TEXT_FONT, day_x, DAY_POSITION, DAY_COLOUR, day_name)

            # Icon (OLD PATH) but using backbuffer-safe helper
            if icon_name:
                icon_img = self._load_icon_old_path(icon_name)
                if icon_img is not None:
                    self.set_image(icon_img, icon_x, ICON_POSITION)

            # Temps
            self.draw_text(TEXT_FONT, max_temp_x, TEMP_POSITION, MAX_T_COLOUR, max_temp)
            self.draw_text(TEXT_FONT, min_temp_x, TEMP_POSITION, MIN_T_COLOUR, min_temp)

            offset += space_width