# scenes/planedetails.py
from utilities.animator import Animator
from setup import colours, fonts, screen
from config import DISTANCE_UNITS

# -----------------------------
# CONFIG / LAYOUT (matches original)
# -----------------------------
PLANE_COLOUR = colours.LIGHT_MID_BLUE
PLANE_DISTANCE_COLOUR = colours.LIGHT_PINK

PLANE_DISTANCE_FROM_TOP = 31  # baseline
PLANE_TEXT_HEIGHT = 8
PLANE_FONT = fonts.small

# Clear only the bottom band we own
# NOTE: Display.draw_square uses DrawLine with inclusive y, so keep Y1 as screen.HEIGHT (exclusive-ish by range(x))
PLANE_CLEAR_X0 = 0
PLANE_CLEAR_Y0 = PLANE_DISTANCE_FROM_TOP - (PLANE_TEXT_HEIGHT - 1)  # 31 - 7 = 24
PLANE_CLEAR_X1 = screen.WIDTH
PLANE_CLEAR_Y1 = screen.HEIGHT 


def _unit_label() -> str:
    # Keep original casing: metric -> "KM"
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

    @Animator.KeyFrame.add(0, tag="flight")
    def reset_plane_details(self):
        # Called on reset_scene() (mode switch / clear_screen)
        self.plane_position = screen.WIDTH
        self._clear_band()

    @Animator.KeyFrame.add(1, tag="flight")
    def plane_details(self, count):
        plane_data = self._current_flight()
        if not plane_data:
            return

        # Extract data (be defensive)
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

        # Scrolling widget: redraw every tick
        self._clear_band()

        # Draw plane name then distance/direction directly after it
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

        # Advance index when the text fully exits left
        if self.plane_position + total_text_width < 0:
            self.plane_position = screen.WIDTH

            data = getattr(self, "_data", [])
            if len(data) > 1:
                self._data_index = (self._data_index + 1) % len(data)

                # Track whether we've looped all flights at least once (matches old behavior)
                self._data_all_looped = (self._data_index == 0) or self._data_all_looped

            # IMPORTANT: do NOT call reset_scene() here (avoid nuking other widgets)
            return