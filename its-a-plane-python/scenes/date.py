# scenes/date.py
import logging
from datetime import datetime

from rgbmatrix import graphics
from utilities.animator import Animator
from utilities.temperature import grab_forecast
from setup import colours, fonts, frames

# -----------------------------
# CONFIG (keep original look)
# -----------------------------
DATE_FONT = fonts.extrasmall
DATE_POSITION = (40, 11)  # right-side, baseline y
DATE_FORMAT = "%b %d"     # original: "Jan 09"

# Clear region for the date (RIGHT SIDE)
# This keeps clock/date-left separate and prevents overlap.
# extrasmall baseline ~11, height ~5-ish; clear a safe box.
DATE_CLEAR_X0 = 40
DATE_CLEAR_Y0 = 7
DATE_CLEAR_X1 = 64
DATE_CLEAR_Y1 = 12  # exclusive-ish in your draw_square usage

# -----------------------------
# Moon phase gradient mapping
# -----------------------------
def map_moon_phase_to_color(moonphase: int):
    colors = [
        [colours.DARK_PURPLE, colours.DARK_PURPLE],         # 0
        [colours.DARK_PURPLE, colours.DARK_MID_PURPLE],     # 1
        [colours.DARK_PURPLE, colours.WHITE],               # 2
        [colours.DARK_MID_PURPLE, colours.WHITE],           # 3
        [colours.GREY, colours.GREY],                       # 4
        [colours.WHITE, colours.DARK_MID_PURPLE],           # 5
        [colours.WHITE, colours.DARK_PURPLE],               # 6
        [colours.DARK_MID_PURPLE, colours.DARK_PURPLE],     # 7
    ]
    m = 0 if moonphase is None else int(moonphase)
    m = min(max(m, 0), 7)
    return colors[m][0], colors[m][1]


class DateScene(object):
    def __init__(self):
        super().__init__()
        self._last_date_str = None
        self._redraw_date = True

        # Flight/home transition tracking
        self._was_showing_flights = False

        # Moon phase cache
        self.today_moonphase = None
        self.last_fetched_moonphase_day = None  # day-of-month when we last fetched

    # -----------------------------
    # Helpers
    # -----------------------------
    def _clear_date_area(self):
        # Use Display.draw_square so dirty gets set.
        self.draw_square(
            DATE_CLEAR_X0, DATE_CLEAR_Y0, DATE_CLEAR_X1, DATE_CLEAR_Y1, colours.BLACK
        )

    def _draw_gradient_text(self, text: str, x: int, y: int, start_color, end_color):
        # Draw each char via Display.draw_text to mark dirty.
        # Character width for extrasmall is ~4 in your original code.
        n = len(text)
        if n <= 1:
            self.draw_text(DATE_FONT, x, y, start_color, text)
            return

        char_width = 4
        for i, ch in enumerate(text):
            t = i / (n - 1)
            r = int(start_color.red + (end_color.red - start_color.red) * t)
            g = int(start_color.green + (end_color.green - start_color.green) * t)
            b = int(start_color.blue + (end_color.blue - start_color.blue) * t)
            col = graphics.Color(r, g, b)
            self.draw_text(DATE_FONT, x + i * char_width, y, col, ch)

    def _moonphase(self):
        """
        Fetch moonphase once per day; cache and return the value.
        Uses grab_forecast(tag="DateScene") like your original.
        """
        now = datetime.now()
        if self.last_fetched_moonphase_day == now.day:
            return self.today_moonphase

        try:
            forecast = grab_forecast(tag="DateScene")
            if not forecast:
                logging.error("Forecast missing/API error (moon phase).")
                return self.today_moonphase

            today_str = now.strftime("%Y-%m-%d")
            for day in forecast:
                # startTime like "2026-01-09T00:00:00Z" -> date part
                forecast_date = str(day.get("startTime", ""))[:10]
                if forecast_date == today_str:
                    values = day.get("values", {}) or {}
                    mp = values.get("moonPhase", None)
                    if mp is not None:
                        self.today_moonphase = int(mp)
                        self.last_fetched_moonphase_day = now.day
                    break

        except Exception as e:
            logging.error(f"Error fetching forecast for moon phase: {e}")
            return self.today_moonphase

        return self.today_moonphase

    # -----------------------------
    # Keyframe
    # -----------------------------
    @Animator.KeyFrame.add(frames.PER_SECOND * 1, tag="defaultDate")
    def date(self, count):
        # Flights active?
        showing_flights = len(getattr(self, "_data", [])) > 0

        # If flights just started, clear date once so it doesn't linger
        if showing_flights and not self._was_showing_flights:
            self._was_showing_flights = True
            self._clear_date_area()
            return

        # If flights still active, don't draw date
        if showing_flights:
            return

        # If flights just ended, force redraw immediately
        if (not showing_flights) and self._was_showing_flights:
            self._was_showing_flights = False
            self._redraw_date = True
            self._last_date_str = None
            self._clear_date_area()

        now = datetime.now()
        current_date_str = now.strftime(DATE_FORMAT)

        # Only redraw if changed or forced
        if (current_date_str == self._last_date_str) and (not self._redraw_date) and (not getattr(self, "_redraw_all_this_frame", False)):
            return

        # Moon phase gradient colors
        mp = self._moonphase()
        if mp is None:
            start_color = end_color = colours.RED
        else:
            start_color, end_color = map_moon_phase_to_color(mp)

        # Clear region and draw
        self._clear_date_area()
        self._draw_gradient_text(current_date_str, DATE_POSITION[0], DATE_POSITION[1], start_color, end_color)

        self._last_date_str = current_date_str
        self._redraw_date = False