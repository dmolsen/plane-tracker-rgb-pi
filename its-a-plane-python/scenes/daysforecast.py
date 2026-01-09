# scenes/daysforecast.py
import os
from datetime import datetime
from PIL import Image

from utilities.animator import Animator
from setup import colours, fonts, frames, screen
from utilities.temperature import grab_forecast
from config import NIGHT_START, NIGHT_END

# Setup (keep original values)
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

# Clear region matches original
FORECAST_CLEAR_X0 = 0
FORECAST_CLEAR_Y0 = 12
FORECAST_CLEAR_X1 = 64
FORECAST_CLEAR_Y1 = 32

# Icons directory (relative-safe)
_THIS_DIR = os.path.dirname(__file__)
ICONS_DIR = os.path.join(_THIS_DIR, "icons")
# If your icons live at project-root/icons, use:
# ICONS_DIR = os.path.join(os.path.dirname(_THIS_DIR), "icons")


class DaysForecastScene(object):
    def __init__(self):
        super().__init__()
        self._redraw_forecast = True
        self._last_hour = None
        self._cached_forecast = None

        # icon filename -> cached PIL RGB image (resized) or None
        self._icon_cache = {}

        # Track Display-level full clears so we redraw after clear_canvas()
        self._last_clear_token_seen = None

    def _clear_forecast_region(self):
        self.draw_square(
            FORECAST_CLEAR_X0,
            FORECAST_CLEAR_Y0,
            FORECAST_CLEAR_X1,
            FORECAST_CLEAR_Y1,
            colours.BLACK,
        )

    def _get_icon(self, icon_name: str):
        """Load+resize once; return cached PIL RGB image or None."""
        if not icon_name:
            return None

        if icon_name in self._icon_cache:
            return self._icon_cache[icon_name]

        path = os.path.join(ICONS_DIR, f"{icon_name}.png")
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

    def _sync_with_canvas_clear(self):
        """
        If Display did a full backbuffer clear (mode switch, off/on, clear_screen),
        force us to redraw even if the hour didn't change.
        """
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

    @Animator.KeyFrame.add(0, tag="default")
    def reset_forecast(self):
        # Called on Display.reset_scene() (boot, mode switch, clear_screen, etc.)
        self._redraw_forecast = True
        self._last_hour = None
        self._last_clear_token_seen = getattr(self, "_clear_token", None)
        self._clear_forecast_region()

    @Animator.KeyFrame.add(frames.PER_SECOND * 1, tag="default")
    def day(self, count):
        self._sync_with_canvas_clear()

        # Ensure redraw when midnight brightness boundary events hit (original behavior)
        now_time = datetime.now().replace(microsecond=0).time()
        if now_time == NIGHT_START_TIME.time() or now_time == NIGHT_END_TIME.time():
            self._redraw_forecast = True
            # Don't return early forever; we still want to draw if redraw is set
            # (original code returned; that delays draw until next tick)
            # We'll fall through and render below.

        # If flights are active, default tag gating *should* already prevent calling us,
        # but keep this safe guard if something accidentally runs all tags.
        if len(getattr(self, "_data", [])):
            self._redraw_forecast = True
            return

        current_hour = datetime.now().hour

        # Determine if we need to fetch BEFORE updating last_hour (original logic)
        need_fetch = False
        if self._cached_forecast is None:
            need_fetch = True
        elif self._last_hour != current_hour:
            need_fetch = True

        # Draw only when hour changes or when scene is newly activated
        if (self._last_hour != current_hour) or self._redraw_forecast:
            # Clear previous area (original only cleared after first draw)
            if self._last_hour is not None or self._redraw_forecast:
                self._clear_forecast_region()

            # Update last_hour AFTER deciding if we need to fetch
            self._last_hour = current_hour

            # -------------------------
            # FETCH OR USE CACHE
            # -------------------------
            if need_fetch:
                forecast = grab_forecast(tag="days")

                # API failed -> use old cache (if any)
                if not forecast:
                    if self._cached_forecast:
                        forecast = self._cached_forecast
                    else:
                        # Nothing cached yet -> wait for next cycle
                        self._redraw_forecast = True
                        return
                else:
                    # Valid data -> update cache
                    self._cached_forecast = forecast
            else:
                # Use cached forecast
                forecast = self._cached_forecast

            # Done with forced redraw
            self._redraw_forecast = False

            # -------------------------
            # RENDER FORECAST (3 columns like original)
            # -------------------------
            offset = 1
            space_width = screen.WIDTH // 3

            # Original loop used "for day in forecast:" without slicing,
            # but the layout only supports 3 columns. Keep it at 3.
            for day in (forecast or [])[:3]:
                start_time = day.get("startTime", "")
                try:
                    day_name = datetime.fromisoformat(str(start_time).rstrip("Z")).strftime("%a")
                except Exception:
                    day_name = "--"

                values = day.get("values", {}) or {}
                icon = values.get("weatherCodeFullDay")

                min_val = values.get("temperatureMin")
                max_val = values.get("temperatureMax")

                # Original always formatted as integers
                min_temp = f"{min_val:.0f}" if isinstance(min_val, (int, float)) else "--"
                max_temp = f"{max_val:.0f}" if isinstance(max_val, (int, float)) else "--"

                min_temp_width = len(min_temp) * 4
                max_temp_width = len(max_temp) * 4

                temp_x = offset + (space_width - min_temp_width - max_temp_width - 1) // 2 + 1
                max_temp_x = temp_x
                min_temp_x = temp_x + max_temp_width

                icon_x = offset + (space_width - ICON_SIZE) // 2
                day_x = offset + (space_width - 12) // 2 + 1

                # Draw day name (NOW via Display helper)
                self.draw_text(TEXT_FONT, day_x, DAY_POSITION, DAY_COLOUR, day_name)

                # Draw icon (NOW via Display helper onto backbuffer)
                if icon:
                    img = self._get_icon(str(icon))
                    if img is not None:
                        self.set_image(img, icon_x, ICON_POSITION)

                # Draw temps (NOW via Display helper)
                self.draw_text(TEXT_FONT, max_temp_x, TEMP_POSITION, MAX_T_COLOUR, max_temp)
                self.draw_text(TEXT_FONT, min_temp_x, TEMP_POSITION, MIN_T_COLOUR, min_temp)

                offset += space_width