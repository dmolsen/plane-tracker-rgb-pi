# scenes/journey.py
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

DISTANCE_POSITION = (17, 15)
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

# -----------------------------
# Clear regions (EXCLUSIVE x1/y1)
# -----------------------------
JOURNEY_CLEAR = (
    JOURNEY_POSITION[0],
    JOURNEY_POSITION[1],
    JOURNEY_POSITION[0] + JOURNEY_WIDTH,
    JOURNEY_POSITION[1] + JOURNEY_HEIGHT,
)

# extrasmall baseline is y=15 now; clear a safe band around it
DIST_CLEAR = (
    DISTANCE_POSITION[0],
    DISTANCE_POSITION[1] - 6,     # 8
    DISTANCE_POSITION[0] + DISTANCE_WIDTH,
    16,     # 15 (exclusive) -> clears up to row 14
)

ARROW_CLEAR = (
    ARROW_POINT_POSITION[0] - ARROW_WIDTH,
    ARROW_POINT_POSITION[1] - (ARROW_HEIGHT // 2),
    ARROW_POINT_POSITION[0] + 1,
    ARROW_POINT_POSITION[1] + (ARROW_HEIGHT // 2) + 1,
)


def _unit_label() -> str:
    u = str(DISTANCE_UNITS).lower()
    if u == "imperial":
        return "mi"
    if u == "metric":
        return "km"
    return "u"


def _safe_num(v, default=0.0) -> float:
    try:
        return default if v is None else float(v)
    except Exception:
        return default


def _safe_int(v, default=0) -> int:
    try:
        return default if v is None else int(float(v))
    except Exception:
        return default


def _safe_delay_minutes(real_ts, sched_ts):
    try:
        if real_ts in (None, 0) or sched_ts in (None, 0):
            return None
        return (float(real_ts) - float(sched_ts)) / 60.0
    except Exception:
        return None


def _delay_colour(minutes):
    if minutes is None:
        return colours.LIGHT_GREY
    try:
        m = float(minutes)
    except Exception:
        return colours.LIGHT_GREY

    # match your newer thresholds (same style you’ve been using)
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
        self._last_render_key = None
        self._last_clear_token_seen = None

    def _clear_all(self):
        self.draw_square(*JOURNEY_CLEAR, colours.BLACK)
        self.draw_square(*DIST_CLEAR, colours.BLACK)
        self.draw_square(*ARROW_CLEAR, colours.BLACK)

    def _current_flight(self):
        data = getattr(self, "_data", None)
        idx = getattr(self, "_data_index", 0)
        if not data or idx < 0 or idx >= len(data):
            return None
        return data[idx]

    def _sync_with_canvas_clear(self):
        """
        If Display did a full backbuffer clear (clear_canvas), force a redraw.
        """
        clear_token = getattr(self, "_clear_token", None)
        if clear_token is None:
            return False

        if self._last_clear_token_seen is None:
            self._last_clear_token_seen = clear_token
            return True

        if clear_token != self._last_clear_token_seen:
            self._last_clear_token_seen = clear_token
            return True

        return False

    def _draw_line(self, x0, y0, x1, y1, colour):
        # If you ever call raw graphics, mark dirty explicitly.
        self.mark_dirty()
        graphics.DrawLine(self.canvas, x0, y0, x1, y1, colour)

    @Animator.KeyFrame.add(0, tag="flight")
    def reset_journey(self):
        self._last_render_key = None
        self._last_clear_token_seen = getattr(self, "_clear_token", None)
        self._clear_all()

    @Animator.KeyFrame.add(1, tag="flight")
    def journey(self, count):
        f = self._current_flight()
        if not f:
            return

        force = bool(getattr(self, "_redraw_all_this_frame", False))
        force = force or self._sync_with_canvas_clear()

        # Only redraw when relevant flight data changes
        render_key = (
            getattr(self, "_data_index", 0),
            f.get("origin"),
            f.get("destination"),
            f.get("distance_origin"),
            f.get("distance_destination"),
            f.get("time_real_departure"),
            f.get("time_scheduled_departure"),
            f.get("time_estimated_arrival"),
            f.get("time_scheduled_arrival"),
        )
        if (not force) and (render_key == self._last_render_key):
            return
        self._last_render_key = render_key

        self._clear_all()

        origin = f.get("origin") or ""
        destination = f.get("destination") or ""

        dist_origin = _safe_num(f.get("distance_origin"), 0.0)
        dist_destination = _safe_num(f.get("distance_destination"), 0.0)

        dep_delay = _safe_delay_minutes(
            f.get("time_real_departure"), f.get("time_scheduled_departure")
        )
        arr_delay = _safe_delay_minutes(
            f.get("time_estimated_arrival"), f.get("time_scheduled_arrival")
        )

        origin_color = _delay_colour(dep_delay)
        destination_color = _delay_colour(arr_delay)

        origin_font = JOURNEY_FONT_SELECTED if origin == JOURNEY_CODE_SELECTED else JOURNEY_FONT
        dest_font = JOURNEY_FONT_SELECTED if destination == JOURNEY_CODE_SELECTED else JOURNEY_FONT

        # --- ORIGIN / DEST TEXT
        left_text = origin if origin else JOURNEY_BLANK_FILLER
        right_text = destination if destination else JOURNEY_BLANK_FILLER

        origin_w = self.draw_text(
            origin_font,
            JOURNEY_POSITION[0],
            JOURNEY_HEIGHT,
            origin_color,
            left_text,
        )

        self.draw_text(
            dest_font,
            JOURNEY_POSITION[0] + origin_w + JOURNEY_SPACING + 1,
            JOURNEY_HEIGHT,
            destination_color,
            right_text,
        )

        # --- DISTANCES (two halves)
        units = _unit_label()
        distance_origin_text = f"{dist_origin:.0f}{units}"
        distance_destination_text = f"{dist_destination:.0f}{units}"

        center_x = (16 + 64) // 2
        half_width = (64 - 16) // 2
        char_w = 4  # extrasmall approx width

        w_o = len(distance_origin_text) * char_w
        w_d = len(distance_destination_text) * char_w

        distance_origin_x = center_x - half_width + (half_width - w_o) // 2
        distance_destination_x = center_x + (half_width - w_d) // 2

        x = distance_origin_x
        for ch in distance_origin_text:
            x += self.draw_text(
                DISTANCE_FONT,
                x,
                DISTANCE_POSITION[1],
                DISTANCE_COLOUR if ch.isnumeric() else DISTANCE_MEASURE,
                ch,
            )

        x = distance_destination_x
        for ch in distance_destination_text:
            x += self.draw_text(
                DISTANCE_FONT,
                x,
                DISTANCE_POSITION[1],
                DISTANCE_COLOUR if ch.isnumeric() else DISTANCE_MEASURE,
                ch,
            )

        # --- ARROW (5 columns, tapered)
        x = ARROW_POINT_POSITION[0] - ARROW_WIDTH + 1
        y1 = ARROW_POINT_POSITION[1] - (ARROW_HEIGHT // 2)
        y2 = ARROW_POINT_POSITION[1] + (ARROW_HEIGHT // 2)

        d_o = _safe_int(dist_origin, 0)
        d_d = _safe_int(dist_destination, 0)

        # Unknown/zero distances: grey arrow
        if d_o <= 0 or d_d <= 0:
            for _ in range(ARROW_WIDTH):
                self._draw_line(x, y1, x, y2, ARROW_COLOUR)
                x += 1
                y1 += 1
                y2 -= 1
            return

        total = d_o + d_d
        origin_ratio = d_o / total

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
            self._draw_line(x, y1, x, y2, DISTANCE_ORIGIN_COLOUR)
            x += 1
            y1 += 1
            y2 -= 1

        for _ in range(dest_pixels):
            self._draw_line(x, y1, x, y2, DISTANCE_DESTINATION_COLOUR)
            x += 1
            y1 += 1
            y2 -= 1