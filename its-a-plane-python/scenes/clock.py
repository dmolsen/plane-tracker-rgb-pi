from datetime import datetime

from utilities.animator import Animator
from setup import colours, fonts, frames
from config import CLOCK_FORMAT, NIGHT_START, NIGHT_END

# -----------------------------
# CONFIG
# -----------------------------
CLOCK_FONT = fonts.large_bold
CLOCK_POSITION = (0, 11)  # (x, baseline_y)

DAY_COLOUR = colours.LIGHT_ORANGE
NIGHT_COLOUR = colours.LIGHT_BLUE

# Clear region for the clock (top-left)
CLOCK_CLEAR_X0 = 0
CLOCK_CLEAR_Y0 = 0
CLOCK_CLEAR_X1 = 40
CLOCK_CLEAR_Y1 = 12

# Parse night window once
_NIGHT_START = datetime.strptime(NIGHT_START, "%H:%M").time()
_NIGHT_END = datetime.strptime(NIGHT_END, "%H:%M").time()


def _is_night_now(now_time) -> bool:
    """True if now_time is inside NIGHT_START..NIGHT_END (handles crossing midnight)."""
    if _NIGHT_START < _NIGHT_END:
        return _NIGHT_START <= now_time < _NIGHT_END
    return now_time >= _NIGHT_START or now_time < _NIGHT_END


def _format_time(dt: datetime) -> str:
    if str(CLOCK_FORMAT).lower() == "24hr":
        return dt.strftime("%H:%M")
    s = dt.strftime("%I:%M")
    return s.lstrip("0") or "0:00"


class ClockScene(object):
    def __init__(self):
        super().__init__()
        self._last_time_str = None
        self._redraw_time = True
        self._was_showing_flights = False

    def _clear_clock_area(self):
        self.draw_square(
            CLOCK_CLEAR_X0,
            CLOCK_CLEAR_Y0,
            CLOCK_CLEAR_X1,
            CLOCK_CLEAR_Y1,
            colours.BLACK,
        )

    @Animator.KeyFrame.add(frames.PER_SECOND * 1)
    def clock(self, count):
        # Flights active?
        showing_flights = len(getattr(self, "_data", [])) > 0

        # If flights just started, clear clock once so it doesn't linger
        if showing_flights and not self._was_showing_flights:
            self._was_showing_flights = True
            self._clear_clock_area()
            return

        # If flights still active, do not draw the clock
        if showing_flights:
            return

        # If flights just ended, force redraw immediately
        if (not showing_flights) and self._was_showing_flights:
            self._was_showing_flights = False
            self._redraw_time = True
            self._last_time_str = None
            self._clear_clock_area()

        now = datetime.now()
        current_time_str = _format_time(now)

        # Only redraw if minute changed or forced
        if (current_time_str == self._last_time_str) and (not self._redraw_time):
            return

        # Clear old clock area
        self._clear_clock_area()

        # Choose colour based on night window (purely a color choice now)
        clock_colour = NIGHT_COLOUR if _is_night_now(now.time().replace(second=0, microsecond=0)) else DAY_COLOUR

        # IMPORTANT: draw via Display helper so it marks the frame dirty
        self.draw_text(
            CLOCK_FONT,
            CLOCK_POSITION[0],
            CLOCK_POSITION[1],
            clock_colour,
            current_time_str,
        )

        self._last_time_str = current_time_str
        self._redraw_time = False