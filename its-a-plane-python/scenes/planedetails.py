from utilities.animator import Animator
from setup import colours, fonts, screen
from config import DISTANCE_UNITS
from rgbmatrix import graphics

PLANE_COLOUR = colours.LIGHT_MID_BLUE
PLANE_DISTANCE_COLOUR = colours.LIGHT_PINK

PLANE_DISTANCE_FROM_TOP = 31  # baseline
PLANE_TEXT_HEIGHT = 8
PLANE_FONT = fonts.small

# Clear band: baseline - (height-1) .. baseline inclusive
PLANE_CLEAR_X0 = 0
PLANE_CLEAR_X1 = screen.WIDTH
PLANE_CLEAR_Y0 = PLANE_DISTANCE_FROM_TOP - (PLANE_TEXT_HEIGHT - 1)  # 31 - 7 = 24 ✅
PLANE_CLEAR_Y1 = PLANE_DISTANCE_FROM_TOP + 1                        # 32 (exclusive) ✅

BLACK = graphics.Color(0, 0, 0)

def _unit_label() -> str:
    return "mi" if str(DISTANCE_UNITS).lower() == "imperial" else "KM"


class PlaneDetailsScene(object):
    def __init__(self):
        super().__init__()
        self.plane_position = screen.WIDTH
        self._data_all_looped = False

    def _clear_band(self):
        self.draw_square(PLANE_CLEAR_X0, PLANE_CLEAR_Y0, PLANE_CLEAR_X1, PLANE_CLEAR_Y1, BLACK)

    def _current_flight(self):
        data = getattr(self, "_data", None)
        idx = getattr(self, "_data_index", 0)
        if not data or idx < 0 or idx >= len(data):
            return None
        return data[idx]

    @Animator.KeyFrame.add(0, tag="plane_details")
    def reset_plane_details(self):
        self.plane_position = screen.WIDTH
        self._clear_band()

    @Animator.KeyFrame.add(1, tag="plane_details")
    def plane_details(self, count):
        f = self._current_flight()
        if not f:
            return

        plane_name = f.get("plane", "") or ""
        distance = f.get("distance", None)
        direction = f.get("direction", "") or ""

        units = _unit_label()
        plane_name_text = f"{plane_name} " if plane_name else ""

        try:
            distance_text = f"{float(distance):.2f}{units}"
        except Exception:
            distance_text = f"--{units}"

        if direction:
            distance_text = f"{distance_text} {direction}"

        self._clear_band()

        w1 = self.draw_text(
            PLANE_FONT,
            self.plane_position,
            PLANE_DISTANCE_FROM_TOP,
            PLANE_COLOUR,
            plane_name_text,
        )
        w2 = self.draw_text(
            PLANE_FONT,
            self.plane_position + w1,
            PLANE_DISTANCE_FROM_TOP,
            PLANE_DISTANCE_COLOUR,
            distance_text,
        )
        total = w1 + w2

        self.plane_position -= 1

        # When PlaneDetails wraps, it advances _data_index (single “source of truth”)
        if self.plane_position + max(total, 1) < 0:
            self.plane_position = screen.WIDTH
            data = getattr(self, "_data", [])
            if len(data) > 1:
                self._data_index = (self._data_index + 1) % len(data)
                self._data_all_looped = (self._data_index == 0) or self._data_all_looped
                self._pending_reset = True
            return
