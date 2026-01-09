from utilities.animator import Animator
from setup import colours, fonts, screen

# Setup
FLIGHT_NO_DISTANCE_FROM_TOP = 24
FLIGHT_NO_TEXT_HEIGHT = 8  # based on font size
FLIGHT_NO_FONT = fonts.small

FLIGHT_NUMBER_ALPHA_COLOUR = colours.LIGHT_PURPLE
FLIGHT_NUMBER_NUMERIC_COLOUR = colours.LIGHT_ORANGE

DATA_INDEX_POSITION = (52, 24)
DATA_INDEX_TEXT_HEIGHT = 7
DATA_INDEX_FONT = fonts.extrasmall
DATA_INDEX_COLOUR = colours.GREY


class FlightDetailsScene(object):
    def __init__(self):
        super().__init__()
        self.flight_position = screen.WIDTH
        self._data_all_looped = False

    def _get_current(self, key, default=""):
        """Safe access to current flight dict fields."""
        try:
            data = getattr(self, "_data", None)
            idx = getattr(self, "_data_index", 0)
            if not data or idx < 0 or idx >= len(data):
                return default
            val = data[idx].get(key, default)
            return default if val is None else val
        except Exception:
            return default

    @Animator.KeyFrame.add(1, tag="flight")
    def flight_details(self, count):
        # Guard against no data
        if not getattr(self, "_data", None) or len(self._data) == 0:
            return

        # Clear the whole band each tick (keeps scroll clean)
        self.draw_square(
            0,
            FLIGHT_NO_DISTANCE_FROM_TOP - FLIGHT_NO_TEXT_HEIGHT,
            screen.WIDTH,
            FLIGHT_NO_DISTANCE_FROM_TOP,
            colours.BLACK,
        )

        flight_no_text_length = 0

        callsign = self._get_current("callsign", "")
        owner_icao = self._get_current("owner_icao", "")

        if callsign and callsign != "N/A":
            # Remove ICAO prefix from callsign if present
            if owner_icao and callsign.startswith(owner_icao):
                flight_no = callsign[len(owner_icao):]
            else:
                flight_no = callsign

            # Add airline name if available
            airline = self._get_current("airline", "")
            if airline:
                flight_no = f"{airline} {flight_no}"

            # IMPORTANT: draw via Display helper so present() sees it
            for ch in flight_no:
                ch_length = self.draw_text(
                    FLIGHT_NO_FONT,
                    self.flight_position + flight_no_text_length,
                    FLIGHT_NO_DISTANCE_FROM_TOP,
                    FLIGHT_NUMBER_NUMERIC_COLOUR if ch.isnumeric() else FLIGHT_NUMBER_ALPHA_COLOUR,
                    ch,
                )
                flight_no_text_length += ch_length

        # Draw "N/M" pager if multiple flights
        if len(self._data) > 1:
            pager_len = self.draw_text(
                DATA_INDEX_FONT,
                DATA_INDEX_POSITION[0],
                DATA_INDEX_POSITION[1],
                DATA_INDEX_COLOUR,
                f"{self._data_index + 1}/{len(self._data)}",
            )

            # Include pager in scroll-off calculation
            flight_no_text_length += pager_len

        # Handle scrolling
        self.flight_position -= 1

        # When scrolled fully off-screen, advance to next flight (if any)
        if self.flight_position + flight_no_text_length < 0:
            self.flight_position = screen.WIDTH

            if len(self._data) > 1:
                self._data_index = (self._data_index + 1) % len(self._data)
                self._data_all_looped = (self._data_index == 0) or self._data_all_looped

                # Reset scene so other regions can redraw cleanly for the new flight
                if hasattr(self, "reset_scene"):
                    self.reset_scene()

    @Animator.KeyFrame.add(0, tag="flight")
    def reset_scrolling(self):
        self.flight_position = screen.WIDTH