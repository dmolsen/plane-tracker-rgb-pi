from datetime import datetime, timedelta
import colorsys
from rgbmatrix import graphics
from utilities.animator import Animator
from setup import colours, fonts, frames, screen
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
        self._cached_temp = None
        self._cached_humidity = None
        self._redraw_temp = True

    def colour_gradient(self, colour_A, colour_B, ratio):
        return graphics.Color(
            int(colour_A.red + ((colour_B.red - colour_A.red) * ratio)),
            int(colour_A.green + ((colour_B.green - colour_A.green) * ratio)),
            int(colour_A.blue + ((colour_B.blue - colour_A.blue) * ratio)),
        )

    @Animator.KeyFrame.add(frames.PER_SECOND * 1)
    def temperature(self, count):
        # Do NOTHING if screen is off (prevents flashing + scene corruption)
        if getattr(self.matrix, "brightness", 1) == 0:
            return

        now = datetime.now()
        retry_interval_on_error = 60

        # Time since last successful update
        seconds_since_update = (
            (now - self._last_updated).total_seconds()
            if self._last_updated else TEMPERATURE_REFRESH_SECONDS
        )

        need_fetch = (
            seconds_since_update >= TEMPERATURE_REFRESH_SECONDS or
            (
                self._cached_temp is None and
                seconds_since_update >= retry_interval_on_error
            )
        )

        # Fetch new data only when needed
        if need_fetch:
            current_temperature, current_humidity = grab_temperature_and_humidity()

            if current_temperature is not None and current_humidity is not None:
                self._cached_temp = (current_temperature, current_humidity)
                self._last_updated = now
                self._redraw_temp = True
            else:
                # Failed fetch: do NOT redraw unless nothing has ever rendered
                if self._cached_temp is None:
                    self._redraw_temp = True
                return

        # If nothing changed visually, stop
        if not self._redraw_temp or self._cached_temp is None:
            return

        current_temperature, current_humidity = self._cached_temp

        # Clear previous temperature area
        self.draw_square(40, 0, 64, 5, colours.BLACK)

        # Format display
        display_str = f"{round(current_temperature)}°"
        humidity_ratio = current_humidity / 100.0
        temp_colour = self.colour_gradient(
            colours.WHITE,
            colours.DARK_BLUE,
            humidity_ratio
        )

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

