# scenes/planedetails.py
from utilities.animator import Animator
from setup import colours, fonts, screen
from config import DISTANCE_UNITS

# -----------------------------
# CONFIG / LAYOUT
# -----------------------------
PLANE_COLOUR = colours.LIGHT_MID_BLUE
PLANE_DISTANCE_COLOUR = colours.LIGHT_PINK

PLANE_DISTANCE_FROM_TOP = 31  # baseline Y (bottom row baseline for 5x8 font)
PLANE_TEXT_HEIGHT = 8         # 5x8 font height
PLANE_FONT = fonts.small

# Clear only the bottom band we own.
# Display.draw_square treats x1/y1 as EXCLUSIVE bounds.
# With PLANE_TEXT_HEIGHT=8 and baseline=31, a safe clear is y=23..31 inclusive.
PLANE_CLEAR_X0 = 0
PLANE_CLEAR_X1 = screen.WIDTH
PLANE_CLEAR_Y0 = PLANE_DISTANCE_FROM_TOP - PLANE_TEXT_HEIGHT   # 31 - 8 = 23
PLANE_CLEAR_Y1 = screen.HEIGHT                                 # 32 (exclusive)


def _unit_label() -> str:
    return "mi" if str(DISTANCE_UNITS).lower() == "imperial" else "KM"


class PlaneDetailsScene(object):
    def __init__(self):
        super().__init__()
        self.plane_position = screen.WIDTH
        self._data_all_looped = False

    def _clear_band(self):
        self.draw_square(
            PLANE_CLEAR_X0,
            PLANE_CLEAR_Y0,
            PLANE_CLEAR_X1,
            PLANE_CLEAR_Y1,
            colours.BLACK,
        )

    def _current_flight(self):
        data = getattr(self, "_data", None)
        idx = getattr(self, "_data_index", 0)
        if not data or idx < 0 or idx >= len(data):
            return None
        return data[idx]

    # NOTE: We prefix these with zzzzz_ so they run late in keyframe order
    # (prevents other flight scenes from overpainting the bottom band after us).

    @Animator.KeyFrame.add(0, tag="flight")
    def zzzzz_reset_plane_details(self):
        self.plane_position = screen.WIDTH
        self._clear_band()

    @Animator.KeyFrame.add(1, tag="flight")
    def zzzzz_plane_details(self, count):
        plane_data = self._current_flight()
        if not plane_data:
            return

        plane_name = plane_data.get("plane", "") or ""
        distance = plane_data.get("distance", None)
        direction = plane_data.get("direction", "") or ""
        units = _unit_label()

        plane_name_text = f"{plane_name} " if plane_name else ""

        try:
            distance_text = f"{float(distance):.2f}{units}"
        except Exception:
            distance_text = f"--{units}"

        if direction:
            distance_text = f"{distance_text} {direction}"

        # Redraw each tick (scrolling)
        self._clear_band()

        plane_name_width = self.draw_text(
            PLANE_FONT,
            self.plane_position,
            PLANE_DISTANCE_FROM_TOP,
            PLANE_COLOUR,
            plane_name_text,
        )

        distance_width = self.draw_text(
            PLANE_FONT,
            self.plane_position + plane_name_width,
            PLANE_DISTANCE_FROM_TOP,
            PLANE_DISTANCE_COLOUR,
            distance_text,
        )

        total_text_width = plane_name_width + distance_width

        # Scroll
        self.plane_position -= 1

        # Advance index when fully off screen
        if self.plane_position + total_text_width < 0:
            self.plane_position = screen.WIDTH

            data = getattr(self, "_data", [])
            if len(data) > 1:
                self._data_index = (self._data_index + 1) % len(data)
                self._data_all_looped = (self._data_index == 0) or self._data_all_looped
            return