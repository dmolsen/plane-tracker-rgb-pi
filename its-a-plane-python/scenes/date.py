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
DATE_FORMAT = "%b %d"     # "Jan 09"

# Clear region for the date (RIGHT SIDE)
DATE_CLEAR_X0 = 40
DATE_CLEAR_Y0 = 7
DATE_CLEAR_X1 = 64
DATE_CLEAR_Y1 = 12


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

        # Moon phase cache
        self.today_moonphase = None
        self.last_fetched_moonphase_day = None  # day-of-month when we last fetched

        # Track Display-level full clears so we can redraw after canvas.Clear()
        self._last_clear_token_seen = None

    # -----------------------------
    # Helpers
    # -----------------------------
    def _clear_date_area(self):
        self.draw_square(
            DATE_CLEAR_X0, DATE_CLEAR_Y0, DATE_CLEAR_X1, DATE_CLEAR_Y1, colours.BLACK
        )

    def _draw_gradient_text(self, text: str, x: int, y: int, start_color, end_color):
        n = len(text)
        if n <= 1:
            self.draw_text(DATE_FONT, x, y, start_color, text)
            return

        char_width = 4  # matches your original extrasmall spacing
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
    # Keyframes
    # -----------------------------
    @Animator.KeyFrame.add(0, tag="default")
    def reset_date(self):
        """
        Called via Display.reset_scene() (divisor==0).
        Also useful when switching modes default<->flight and any full-screen clear.
        """
        self._last_date_str = None
        self._redraw_date = True
        self._last_clear_token_seen = getattr(self, "_clear_token", None)
        self._clear_date_area()

    @Animator.KeyFrame.add(frames.PER_SECOND * 1, tag="default")
    def date(self, count):
        # If Display performed a full canvas clear since we last drew, force redraw.
        clear_token = getattr(self, "_clear_token", None)
        if clear_token is not None and clear_token != self._last_clear_token_seen:
            self._redraw_date = True
            self._last_clear_token_seen = clear_token

        now = datetime.now()
        current_date_str = now.strftime(DATE_FORMAT)

        # Only redraw if changed or forced
        if (current_date_str == self._last_date_str) and (not self._redraw_date):
            return

        mp = self._moonphase()
        if mp is None:
            start_color = end_color = colours.RED
        else:
            start_color, end_color = map_moon_phase_to_color(mp)

        self._clear_date_area()
        self._draw_gradient_text(
            current_date_str,
            DATE_POSITION[0],
            DATE_POSITION[1],
            start_color,
            end_color,
        )

        self._last_date_str = current_date_str
        self._redraw_date = False