from utilities.animator import Animator
from setup import colours, fonts
from rgbmatrix import graphics
from config import DISTANCE_UNITS

try:
    from config import JOURNEY_CODE_SELECTED
except (ModuleNotFoundError, NameError, ImportError):
    JOURNEY_CODE_SELECTED = "ORD"

try:
    from config import JOURNEY_BLANK_FILLER
except (ModuleNotFoundError, NameError, ImportError):
    JOURNEY_BLANK_FILLER = " ? "

# -----------------------------
# LAYOUT
# -----------------------------
JOURNEY_POSITION = (17, 0)
JOURNEY_HEIGHT = 10
JOURNEY_WIDTH = 48
JOURNEY_SPACING = 5
JOURNEY_FONT = fonts.regularplus
JOURNEY_FONT_SELECTED = fonts.regularplus_bold

DISTANCE_POSITION = (17, 16)
DISTANCE_WIDTH = 48
DISTANCE_FONT = fonts.extrasmall

ARROW_POINT_POSITION = (42, 5)
ARROW_WIDTH = 5
ARROW_HEIGHT = 8

# -----------------------------
# COLOURS
# -----------------------------
ARROW_COLOUR = colours.GREY
DISTANCE_ORIGIN_COLOUR = colours.LIGHT_GREEN
DISTANCE_DESTINATION_COLOUR = colours.LIGHT_LIGHT_RED
DISTANCE_COLOUR = colours.LIGHT_TEAL
DISTANCE_MEASURE = colours.LIGHT_DARK_TEAL

# Clear regions (journey band + distance band + arrow)
JOURNEY_CLEAR = (
    JOURNEY_POSITION[0],
    JOURNEY_POSITION[1],
    JOURNEY_POSITION[0] + JOURNEY_WIDTH - 1,
    JOURNEY_POSITION[1] + JOURNEY_HEIGHT - 1,
)
DIST_CLEAR = (
    DISTANCE_POSITION[0],
    DISTANCE_POSITION[1] - 7,  # a bit above baseline for safety
    DISTANCE_POSITION[0] + DISTANCE_WIDTH - 1,
    DISTANCE_POSITION[1] + 1,
)
ARROW_CLEAR = (
    ARROW_POINT_POSITION[0] - ARROW_WIDTH,
    ARROW_POINT_POSITION[1] - (ARROW_HEIGHT // 2),
    ARROW_POINT_POSITION[0],
    ARROW_POINT_POSITION[1] + (ARROW_HEIGHT // 2),
)


def _unit_label() -> str:
    if str(DISTANCE_UNITS).lower() == "imperial":
        return "mi"
    if str(DISTANCE_UNITS).lower() == "metric":
        return "km"
    return "u"


def _safe_num(v, default=0.0) -> float:
    try:
        if v is None:
            return default
        return float(v)
    except Exception:
        return default


def _safe_int(v, default=0) -> int:
    try:
        if v is None:
            return default
        return int(float(v))
    except Exception:
        return default


def _safe_delay_minutes(real_ts, sched_ts):
    # Both are expected to be epoch seconds
    try:
        if real_ts in (None, 0) or sched_ts in (None, 0):
            return None
        return (float(real_ts) - float(sched_ts)) / 60.0
    except Exception:
        return None


def _delay_colour(minutes):
    # Returns a colour based on delay minutes (None -> grey)
    if minutes is None:
        return colours.LIGHT_GREY
    try:
        m = float(minutes)
    except Exception:
        return colours.LIGHT_GREY

    # Your original bins (kept)
    if m <= 20:
        return colours.LIGHT_MID_GREEN
    if 20 < m <= 40:
        return colours.LIGHT_YELLOW
    if 40 < m <= 60:
        return colours.LIGHT_MID_ORANGE
    if 60 < m <= 240:
        return colours.LIGHT_RED
    if 240 < m <= 480:
        return colours.LIGHT_PURPLE
    return colours.LIGHT_DARK_BLUE


class JourneyScene(object):
    def __init__(self):
        super().__init__()
        self._was_showing_flights = False
        self._last_render_key = None  # detect flight/index changes

    def _flights_active(self) -> bool:
        return len(getattr(self, "_data", [])) > 0

    def _clear_all(self):
        self.draw_square(*JOURNEY_CLEAR, colours.BLACK)
        self.draw_square(*DIST_CLEAR, colours.BLACK)
        self.draw_square(*ARROW_CLEAR, colours.BLACK)

    def _current_flight(self):
        if not getattr(self, "_data", None):
            return None
        if getattr(self, "_data_index", 0) < 0 or self._data_index >= len(self._data):
            return None
        return self._data[self._data_index]

    @Animator.KeyFrame.add(1)
    def journey(self, count):
        flights_active = self._flights_active()

        # If flights ended, clear once and stop drawing.
        if not flights_active:
            if self._was_showing_flights:
                self._was_showing_flights = False
                self._last_render_key = None
                self._clear_all()
            return

        # Flights just started: clear areas once
        if not self._was_showing_flights:
            self._was_showing_flights = True
            self._clear_all()

        f = self._current_flight()
        if not f:
            return

        # Create a render key so we redraw when the flight or relevant values change
        render_key = (
            self._data_index,
            f.get("origin"),
            f.get("destination"),
            f.get("distance_origin"),
            f.get("distance_destination"),
            f.get("time_real_departure"),
            f.get("time_scheduled_departure"),
            f.get("time_estimated_arrival"),
            f.get("time_scheduled_arrival"),
        )

        if render_key == self._last_render_key:
            return
        self._last_render_key = render_key

        # Clear all journey regions before drawing fresh
        self._clear_all()

        origin = f.get("origin") or ""
        destination = f.get("destination") or ""

        dist_origin = _safe_num(f.get("distance_origin"), 0.0)
        dist_destination = _safe_num(f.get("distance_destination"), 0.0)

        # Compute delays
        dep_delay = _safe_delay_minutes(f.get("time_real_departure"), f.get("time_scheduled_departure"))
        arr_delay = _safe_delay_minutes(f.get("time_estimated_arrival"), f.get("time_scheduled_arrival"))

        origin_color = _delay_colour(dep_delay)
        destination_color = _delay_colour(arr_delay)

        # --- ROUTE TEXT (origin destination)
        origin_font = JOURNEY_FONT_SELECTED if origin == JOURNEY_CODE_SELECTED else JOURNEY_FONT
        dest_font = JOURNEY_FONT_SELECTED if destination == JOURNEY_CODE_SELECTED else JOURNEY_FONT

        text_length = self.draw_text(
            origin_font,
            JOURNEY_POSITION[0],
            JOURNEY_HEIGHT,
            origin_color,
            origin if origin else JOURNEY_BLANK_FILLER,
        )

        _ = self.draw_text(
            dest_font,
            JOURNEY_POSITION[0] + text_length + JOURNEY_SPACING + 1,
            JOURNEY_HEIGHT,
            destination_color,
            destination if destination else JOURNEY_BLANK_FILLER,
        )

        # --- DISTANCES
        units = _unit_label()
        distance_origin_text = f"{dist_origin:.0f}{units}"
        distance_destination_text = f"{dist_destination:.0f}{units}"

        center_x = (16 + 64) // 2
        half_width = (64 - 16) // 2
        font_character_width = 4

        w_o = len(distance_origin_text) * font_character_width
        w_d = len(distance_destination_text) * font_character_width

        distance_origin_x = center_x - half_width + (half_width - w_o) // 2
        distance_destination_x = center_x + (half_width - w_d) // 2

        # origin distance
        x = distance_origin_x
        for ch in distance_origin_text:
            x += self.draw_text(
                DISTANCE_FONT,
                x,
                DISTANCE_POSITION[1],
                DISTANCE_COLOUR if ch.isnumeric() else DISTANCE_MEASURE,
                ch,
            )

        # destination distance
        x = distance_destination_x
        for ch in distance_destination_text:
            x += self.draw_text(
                DISTANCE_FONT,
                x,
                DISTANCE_POSITION[1],
                DISTANCE_COLOUR if ch.isnumeric() else DISTANCE_MEASURE,
                ch,
            )

        # --- ARROW (proportional colouring)
        x = ARROW_POINT_POSITION[0] - ARROW_WIDTH + 1
        y1 = ARROW_POINT_POSITION[1] - (ARROW_HEIGHT // 2)
        y2 = ARROW_POINT_POSITION[1] + (ARROW_HEIGHT // 2)

        d_o = _safe_int(dist_origin, 0)
        d_d = _safe_int(dist_destination, 0)

        # If unknown/zero, draw a neutral arrow
        if d_o <= 0 or d_d <= 0:
            for _ in range(ARROW_WIDTH):
                graphics.DrawLine(self.canvas, x, y1, x, y2, ARROW_COLOUR)
                x += 1
                y1 += 1
                y2 -= 1
            return

        total = d_o + d_d
        origin_ratio = d_o / total

        # Map ratio to 0..5 pixels (same style as your original)
        if origin_ratio <= 0.10:
            origin_pixels = 0
        elif origin_ratio <= 0.30:
            origin_pixels = 1
        elif origin_ratio <= 0.50:
            origin_pixels = 2
        elif origin_ratio <= 0.70:
            origin_pixels = 3
        elif origin_ratio <= 0.90:
            origin_pixels = 4
        else:
            origin_pixels = 5

        dest_pixels = ARROW_WIDTH - origin_pixels

        for _ in range(origin_pixels):
            graphics.DrawLine(self.canvas, x, y1, x, y2, DISTANCE_ORIGIN_COLOUR)
            x += 1
            y1 += 1
            y2 -= 1

        for _ in range(dest_pixels):
            graphics.DrawLine(self.canvas, x, y1, x, y2, DISTANCE_DESTINATION_COLOUR)
            x += 1
            y1 += 1
            y2 -= 1