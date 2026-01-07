from datetime import datetime, timedelta
from rgbmatrix import graphics

from utilities.animator import Animator
from setup import colours, fonts, frames
from utilities.temperature import grab_temperature_and_humidity

# -----------------------------
# CONFIG
# -----------------------------
TEMPERATURE_REFRESH_SECONDS = 600
TEMPERATURE_FONT = fonts.small
TEMPERATURE_FONT_HEIGHT = 6

# Clear region (top-right temperature area)
TEMP_CLEAR_X0 = 40
TEMP_CLEAR_Y0 = 0
TEMP_CLEAR_X1 = 64
TEMP_CLEAR_Y1 = 5


class TemperatureScene(object):
    def __init__(self):
        super().__init__()

        self._cached_temp = None          # (temp, humidity) or (None, None)
        self._last_updated = None

        self._last_drawn_str = None
        self._needs_redraw = True

        self._was_showing_flights = False

    def _flights_active(self) -> bool:
        return len(getattr(self, "_data", [])) > 0

    def _clear_temp_area(self):
        self.draw_square(
            TEMP_CLEAR_X0,
            TEMP_CLEAR_Y0,
            TEMP_CLEAR_X1,
            TEMP_CLEAR_Y1,
            colours.BLACK,
        )

    def _colour_gradient(self, colour_A, colour_B, ratio):
        return graphics.Color(
            int(colour_A.red + ((colour_B.red - colour_A.red) * ratio)),
            int(colour_A.green + ((colour_B.green - colour_A.green) * ratio)),
            int(colour_A.blue + ((colour_B.blue - colour_A.blue) * ratio)),
        )

    @Animator.KeyFrame.add(frames.PER_SECOND * 1, tag="defaultTemperature")
    def temperature(self, count):
        flights_active = self._flights_active()

        # -----------------------------
        # FLIGHT MODE HANDLING
        # -----------------------------
        if flights_active:
            if not self._was_showing_flights:
                self._was_showing_flights = True
                self._clear_temp_area()
            return

        if self._was_showing_flights:
            self._was_showing_flights = False
            self._needs_redraw = True
            self._last_drawn_str = None
            self._clear_temp_area()

        # -----------------------------
        # FETCH LOGIC
        # -----------------------------
        now = datetime.now()
        retry_interval_on_error = 60

        seconds_since_update = (
            (now - self._last_updated).total_seconds()
            if self._last_updated
            else TEMPERATURE_REFRESH_SECONDS
        )

        need_fetch = (
            seconds_since_update >= TEMPERATURE_REFRESH_SECONDS
            or (self._cached_temp is None and seconds_since_update >= retry_interval_on_error)
        )

        if need_fetch:
            temp, humidity = grab_temperature_and_humidity()

            if temp is not None and humidity is not None:
                self._cached_temp = (temp, humidity)
                self._last_updated = now
                self._needs_redraw = True
            else:
                # First failure: render ERR once, then retry ~60s later
                if self._cached_temp is None:
                    self._cached_temp = (None, None)
                    self._last_updated = now - timedelta(
                        seconds=TEMPERATURE_REFRESH_SECONDS - retry_interval_on_error
                    )
                    self._needs_redraw = True

        if not self._needs_redraw or not self._cached_temp:
            return

        # -----------------------------
        # RENDER
        # -----------------------------
        temp, humidity = self._cached_temp

        if temp is None or humidity is None:
            display_str = "ERR"
            colour = colours.RED
        else:
            display_str = f"{round(temp)}°"
            ratio = max(0.0, min(1.0, humidity / 100.0))
            colour = self._colour_gradient(colours.WHITE, colours.DARK_BLUE, ratio)

        # If unchanged visually, stop
        if display_str == self._last_drawn_str:
            self._needs_redraw = False
            return

        # Clear only when we know we are going to draw something new
        self._clear_temp_area()

        # Center text in temp region
        font_char_width = 5
        text_width = len(display_str) * font_char_width
        middle_x = (TEMP_CLEAR_X0 + TEMP_CLEAR_X1) // 2
        start_x = middle_x - text_width // 2

        # IMPORTANT: draw via Display helper so present() sees it
        self.draw_text(
            TEMPERATURE_FONT,
            start_x,
            TEMPERATURE_FONT_HEIGHT,
            colour,
            display_str,
        )

        self._last_drawn_str = display_str
        self._needs_redraw = False