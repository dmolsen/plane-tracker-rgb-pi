from utilities.animator import Animator
from setup import colours, fonts, screen
from config import DISTANCE_UNITS

# -----------------------------
# CONFIG / LAYOUT
# -----------------------------
PLANE_COLOUR = colours.LIGHT_MID_BLUE
PLANE_DISTANCE_COLOUR = colours.LIGHT_PINK

PLANE_DISTANCE_FROM_TOP = 31      # baseline Y
PLANE_TEXT_HEIGHT = 6             # approx font height
PLANE_FONT = fonts.small

# Only clear the bottom band we own (avoid nuking everything)
PLANE_CLEAR_X0 = 0
PLANE_CLEAR_Y0 = PLANE_DISTANCE_FROM_TOP - PLANE_TEXT_HEIGHT
PLANE_CLEAR_X1 = screen.WIDTH
PLANE_CLEAR_Y1 = screen.HEIGHT


def _unit_label() -> str:
    return "mi" if str(DISTANCE_UNITS).lower() == "imperial" else "km"


class PlaneDetailsScene(object):
    def __init__(self):
        super().__init__()
        self.plane_position = screen.WIDTH
        self._data_all_looped = False

        # Track flight transitions so we can clear once when flights stop
        self._was_showing_flights = False

    def _flights_active(self) -> bool:
        return len(getattr(self, "_data", [])) > 0

    def _clear_band(self):
        self.draw_square(
            PLANE_CLEAR_X0,
            PLANE_CLEAR_Y0,
            PLANE_CLEAR_X1,
            PLANE_CLEAR_Y1,
            colours.BLACK,
        )

    def _current_flight(self):
        if not getattr(self, "_data", None):
            return None
        if getattr(self, "_data_index", 0) < 0 or self._data_index >= len(self._data):
            return None
        return self._data[self._data_index]

    @Animator.KeyFrame.add(1, tag="flightPlaneDetails")
    def plane_details(self, count):
        flights_active = self._flights_active()

        # If flights ended: clear once and stop drawing
        if not flights_active:
            if self._was_showing_flights:
                self._was_showing_flights = False
                self._clear_band()
                self.plane_position = screen.WIDTH
            return

        # Flights just started: clear + reset scroll once
        if not self._was_showing_flights:
            self._was_showing_flights = True
            self._clear_band()
            self.plane_position = screen.WIDTH

        plane_data = self._current_flight()
        if not plane_data:
            return

        plane_name = plane_data.get("plane", "") or ""
        distance = plane_data.get("distance", 0) or 0
        direction = plane_data.get("direction", "") or ""

        units = _unit_label()

        # Construct strings
        plane_name_text = f"{plane_name} " if plane_name else ""
        try:
            distance_text = f"{float(distance):.2f}{units}"
        except Exception:
            distance_text = f"--{units}"

        if direction:
            distance_text = f"{distance_text} {direction}"

        # Clear band every frame for clean scroll
        self._clear_band()

        # IMPORTANT: use self.draw_text (not graphics.DrawText)
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

        # When fully off-screen, advance to next plane (if any)
        if self.plane_position + total_text_width < 0:
            self.plane_position = screen.WIDTH

            if len(self._data) > 1:
                self._data_index = (self._data_index + 1) % len(self._data)
                self._data_all_looped = (self._data_index == 0) or self._data_all_looped

                if hasattr(self, "reset_scene"):
                    self.reset_scene()

    @Animator.KeyFrame.add(0)
    def reset_scrolling(self):
        self.plane_position = screen.WIDTH