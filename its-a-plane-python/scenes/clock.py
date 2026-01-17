# scenes/clock.py
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
        self._last_colour_is_night = None
        self._redraw_time = True

        # Track Display-level full clears so we redraw after canvas.Clear()
        self._last_clear_token_seen = None

    def _clear_clock_area(self):
        self.draw_square(
            CLOCK_CLEAR_X0,
            CLOCK_CLEAR_Y0,
            CLOCK_CLEAR_X1,
            CLOCK_CLEAR_Y1,
            colours.BLACK,
        )

    @Animator.KeyFrame.add(0, tag="clock")
    def reset_clock(self):
        """
        Called via Display.reset_scene() (divisor==0) when:
        - boot / resume
        - mode switches (default<->flight)
        - any explicit clear_screen resets
        """
        self._last_time_str = None
        self._last_colour_is_night = None
        self._redraw_time = True
        self._last_clear_token_seen = getattr(self, "_clear_token", None)
        self._clear_clock_area()

    @Animator.KeyFrame.add(frames.PER_SECOND * 1, tag="clock")
    def clock(self, count):
        # If Display performed a full canvas clear since we last drew, force redraw.
        clear_token = getattr(self, "_clear_token", None)
        if clear_token is not None and clear_token != self._last_clear_token_seen:
            self._redraw_time = True
            self._last_clear_token_seen = clear_token

        now = datetime.now()
        current_time_str = _format_time(now)

        is_night = _is_night_now(now.time().replace(second=0, microsecond=0))
        clock_colour = NIGHT_COLOUR if is_night else DAY_COLOUR

        # Redraw if:
        # - minute changed
        # - forced (reset, mode entry, etc)
        # - colour regime changed (day<->night boundary)
        force = bool(getattr(self, "_redraw_all_this_frame", False))
        if (
            (current_time_str == self._last_time_str)
            and (not self._redraw_time)
            and (not force)
            and (is_night == self._last_colour_is_night)
        ):
            return

        self._clear_clock_area()

        # IMPORTANT: draw via Display helper so it marks the frame dirty
        self.draw_text(
            CLOCK_FONT,
            CLOCK_POSITION[0],
            CLOCK_POSITION[1],
            clock_colour,
            current_time_str,
        )

        self._last_time_str = current_time_str
        self._last_colour_is_night = is_night
        self._redraw_time = False
