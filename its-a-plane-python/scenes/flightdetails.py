from utilities.animator import Animator
from setup import colours, fonts, screen

FLIGHT_NO_DISTANCE_FROM_TOP = 24
FLIGHT_NO_TEXT_HEIGHT = 8
FLIGHT_NO_FONT = fonts.small

FLIGHT_NUMBER_ALPHA_COLOUR = colours.LIGHT_PURPLE
FLIGHT_NUMBER_NUMERIC_COLOUR = colours.LIGHT_ORANGE

DATA_INDEX_POSITION = (52, 24)
DATA_INDEX_FONT = fonts.extrasmall
DATA_INDEX_COLOUR = colours.GREY

# Band we own (full width, y-range covering the crawl + pager)
# NOTE: Display.draw_square uses DrawLine(..., y0, y1, ...) which is inclusive in y,
# and range(x0, x1) which is exclusive in x.
BAND_X0 = 0
BAND_X1 = screen.WIDTH
BAND_Y0 = FLIGHT_NO_DISTANCE_FROM_TOP - FLIGHT_NO_TEXT_HEIGHT
BAND_Y1 = FLIGHT_NO_DISTANCE_FROM_TOP + 1  # +1 for safety (still tiny)


class FlightDetailsScene(object):
    def __init__(self):
        super().__init__()
        self.flight_position = screen.WIDTH

    def _clear_band(self):
        self.draw_square(BAND_X0, BAND_Y0, BAND_X1, BAND_Y1, colours.BLACK)

    def _get_current(self, key, default=""):
        try:
            data = getattr(self, "_data", None)
            idx = getattr(self, "_data_index", 0)
            if not data or idx < 0 or idx >= len(data):
                return default
            val = data[idx].get(key, default)
            return default if val is None else val
        except Exception:
            return default

    @Animator.KeyFrame.add(0, tag="flight")
    def reset_scrolling(self):
        # Called on reset_scene() (mode switch / clear_screen)
        self.flight_position = screen.WIDTH
        self._clear_band()

    @Animator.KeyFrame.add(1, tag="flight")
    def flight_details(self, count):
        data = getattr(self, "_data", None)
        if not data:
            return

        # Clear our band each tick for clean scroll
        self._clear_band()

        callsign = self._get_current("callsign", "")
        owner_icao = self._get_current("owner_icao", "")
        airline = self._get_current("airline", "")

        # Build display string
        flight_no = ""
        if callsign and callsign != "N/A":
            if owner_icao and callsign.startswith(owner_icao):
                flight_no = callsign[len(owner_icao):]
            else:
                flight_no = callsign

            if airline:
                flight_no = f"{airline} {flight_no}"

        # If we have nothing to show, don't scroll a zero-length string forever.
        # (Optional: you can show a placeholder like "--")
        if not flight_no and len(data) <= 1:
            return

        flight_no_text_length = 0

        # Draw crawl text
        if flight_no:
            for ch in flight_no:
                flight_no_text_length += self.draw_text(
                    FLIGHT_NO_FONT,
                    self.flight_position + flight_no_text_length,
                    FLIGHT_NO_DISTANCE_FROM_TOP,
                    FLIGHT_NUMBER_NUMERIC_COLOUR if ch.isnumeric() else FLIGHT_NUMBER_ALPHA_COLOUR,
                    ch,
                )

        # Pager (fixed position)
        if len(data) > 1:
            pager_len = self.draw_text(
                DATA_INDEX_FONT,
                DATA_INDEX_POSITION[0],
                DATA_INDEX_POSITION[1],
                DATA_INDEX_COLOUR,
                f"{self._data_index + 1}/{len(data)}",
            )
            # Include pager width so "fully off-screen" accounts for it
            flight_no_text_length += pager_len

        # Scroll left
        self.flight_position -= 1

        # Wrap / advance flight when fully off-screen
        # If flight_no_text_length is 0 (e.g., blank crawl but pager exists),
        # this still works because pager_len was added above when len(data)>1.
        if self.flight_position + flight_no_text_length < 0:
            self.flight_position = screen.WIDTH
            if len(data) > 1:
                self._data_index = (self._data_index + 1) % len(data)
            # IMPORTANT: do NOT call reset_scrolling() here (avoid extra clear/blink).
            return