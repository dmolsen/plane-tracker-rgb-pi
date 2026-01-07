from datetime import datetime

from utilities.animator import Animator
from setup import colours, fonts, frames

# -----------------------------
# CONFIG
# -----------------------------
DATE_FONT = fonts.small
DATE_POSITION = (0, 6)  # (x, baseline_y)
DATE_COLOUR = colours.GREY

# Clear region for the date (top-left strip)
DATE_CLEAR_X0 = 0
DATE_CLEAR_Y0 = 0
DATE_CLEAR_X1 = 40
DATE_CLEAR_Y1 = 7


def _format_date(dt: datetime) -> str:
    # compact for 64x32
    return dt.strftime("%a %m/%d")


class DateScene(object):
    def __init__(self):
        super().__init__()
        self._last_date_str = None
        self._redraw_date = True

        # track whether we were previously showing flights
        self._was_showing_flights = False

    def _clear_date_area(self):
        self.draw_square(
            DATE_CLEAR_X0,
            DATE_CLEAR_Y0,
            DATE_CLEAR_X1,
            DATE_CLEAR_Y1,
            colours.BLACK,
        )

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
        current_date_str = _format_date(now)

        # Only redraw if changed or forced
        if (current_date_str == self._last_date_str) and (not self._redraw_date):
            return

        # Clear old date area
        self._clear_date_area()

        # IMPORTANT: draw via Display helper so present() sees it
        self.draw_text(
            DATE_FONT,
            DATE_POSITION[0],
            DATE_POSITION[1],
            DATE_COLOUR,
            current_date_str,
        )

        self._last_date_str = current_date_str
        self._redraw_date = False