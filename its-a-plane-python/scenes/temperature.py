from datetime import datetime, timedelta
from rgbmatrix import graphics
from utilities.animator import Animator
from setup import colours, fonts, frames
from utilities.temperature import grab_temperature_and_humidity
from config import NIGHT_START, NIGHT_END

# Scene Setup
TEMPERATURE_REFRESH_SECONDS = 600
TEMPERATURE_FONT = fonts.small
TEMPERATURE_FONT_HEIGHT = 6

NIGHT_START_TIME = datetime.strptime(NIGHT_START, "%H:%M")
NIGHT_END_TIME = datetime.strptime(NIGHT_END, "%H:%M")


class TemperatureScene(object):
    def __init__(self):
        super().__init__()
        self._last_temperature = None
        self._last_temperature_str = None
        self._last_updated = None
        self._cached_temp = None  # (temp, humidity)
        self._redraw_temp = True

        # Track screen on/off transitions to force a redraw when turning back on
        self._was_screen_off = False

    def colour_gradient(self, colour_A, colour_B, ratio):
        return graphics.Color(
            int(colour_A.red + ((colour_B.red - colour_A.red) * ratio)),
            int(colour_A.green + ((colour_B.green - colour_A.green) * ratio)),
            int(colour_A.blue + ((colour_B.blue - colour_A.blue) * ratio)),
        )

    def _is_screen_off(self) -> bool:
        # Using brightness=0 as the “screen off” signal.
        return getattr(self.matrix, "brightness", 1) == 0

    def _flights_active(self) -> bool:
        # When flights are being shown, self._data is non-empty.
        return len(getattr(self, "_data", [])) > 0

    @Animator.KeyFrame.add(frames.PER_SECOND * 1)
    def temperature(self, count):
        # --- Screen off gating ---
        if self._is_screen_off():
            self._was_screen_off = True
            return

        # If flights are currently on-screen, do NOT draw temperature.
        # Mark redraw so it returns immediately when flights clear.
        if self._flights_active():
            self._redraw_temp = True
            return

        # If we were previously off and are now on, force a redraw
        if self._was_screen_off:
            self._was_screen_off = False
            self._redraw_temp = True

        now = datetime.now()
        retry_interval_on_error = 60

        # Time since last successful update
        seconds_since_update = (
            (now - self._last_updated).total_seconds()
            if self._last_updated
            else TEMPERATURE_REFRESH_SECONDS
        )

        # Decide whether to fetch
        need_fetch = (
            seconds_since_update >= TEMPERATURE_REFRESH_SECONDS
            or (self._cached_temp is None and seconds_since_update >= retry_interval_on_error)
        )

        if need_fetch:
            current_temperature, current_humidity = grab_temperature_and_humidity()

            if current_temperature is not None and current_humidity is not None:
                self._cached_temp = (current_temperature, current_humidity)
                self._last_updated = now
                self._redraw_temp = True
            else:
                # If we have nothing cached yet, show ERR once and retry in ~60s
                if self._cached_temp is None:
                    self._cached_temp = (None, None)
                    self._redraw_temp = True
                    self._last_updated = now - timedelta(
                        seconds=TEMPERATURE_REFRESH_SECONDS - retry_interval_on_error
                    )
                else:
                    # Keep cached data; don’t flicker.
                    return

        # If nothing to draw, exit
        if not self._redraw_temp or self._cached_temp is None:
            return

        # Clear previous temperature area
        self.draw_square(40, 0, 64, 5, colours.BLACK)

        current_temperature, current_humidity = self._cached_temp

        if current_temperature is None or current_humidity is None:
            display_str = "ERR"
            temp_colour = colours.RED
        else:
            display_str = f"{round(current_temperature)}°"
            humidity_ratio = max(0.0, min(1.0, current_humidity / 100.0))
            temp_colour = self.colour_gradient(colours.WHITE, colours.DARK_BLUE, humidity_ratio)

        # Center text
        font_character_width = 5
        temperature_string_width = len(display_str) * font_character_width
        middle_x = (40 + 64) // 2
        start_x = middle_x - temperature_string_width // 2

        graphics.DrawText(
            self.canvas,
            TEMPERATURE_FONT,
            start_x,
            TEMPERATURE_FONT_HEIGHT,
            temp_colour,
            display_str,
        )

        self._last_temperature_str = display_str
        self._last_temperature = current_temperature
        self._redraw_temp = False