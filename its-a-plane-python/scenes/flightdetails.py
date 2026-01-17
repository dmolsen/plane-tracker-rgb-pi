from utilities.animator import Animator
from setup import colours, fonts, screen
from rgbmatrix import graphics

FLIGHT_NO_DISTANCE_FROM_TOP = 23   # baseline
FLIGHT_NO_TEXT_HEIGHT = 8
FLIGHT_NO_FONT = fonts.small

FLIGHT_NUMBER_ALPHA_COLOUR = colours.LIGHT_PURPLE
FLIGHT_NUMBER_NUMERIC_COLOUR = colours.LIGHT_ORANGE

DATA_INDEX_POSITION = (52, 23)
DATA_INDEX_FONT = fonts.extrasmall
DATA_INDEX_COLOUR = colours.GREY

# Clear band: baseline - (height-1) .. baseline inclusive
BAND_X0 = 0
BAND_X1 = screen.WIDTH
BAND_Y0 = FLIGHT_NO_DISTANCE_FROM_TOP - (FLIGHT_NO_TEXT_HEIGHT - 1)  # 23 - 7 = 16 ✅
BAND_Y1 = FLIGHT_NO_DISTANCE_FROM_TOP + 1                             # 24 (exclusive) ✅

# Use a known-good black for draw_square -> DrawLine
BLACK = graphics.Color(0, 0, 0)


class FlightDetailsScene(object):
    def __init__(self):
        super().__init__()
        self.flight_position = screen.WIDTH

    def _clear_band(self):
        self.draw_square(BAND_X0, BAND_Y0, BAND_X1, BAND_Y1, BLACK)

    def _current_flight(self):
        data = getattr(self, "_data", None)
        idx = getattr(self, "_data_index", 0)
        if not data or idx < 0 or idx >= len(data):
            return None
        return data[idx]

    @Animator.KeyFrame.add(0, tag="flight_details", order=2)
    def reset_flight_details(self):
        self.flight_position = screen.WIDTH
        self._clear_band()

    @Animator.KeyFrame.add(1, tag="flight_details", order=2)
    def flight_details(self, count):
        f = self._current_flight()
        if not f:
            return

        self._clear_band()

        callsign = f.get("callsign") or ""
        owner_icao = f.get("owner_icao") or ""
        airline = f.get("airline") or ""

        flight_no = ""
        if callsign and callsign != "N/A":
            if owner_icao and callsign.startswith(owner_icao):
                flight_no = callsign[len(owner_icao):]
            else:
                flight_no = callsign
            if airline:
                flight_no = f"{airline} {flight_no}"

        data = getattr(self, "_data", [])
        if hasattr(self, "_trace"):
            self._trace(
                f"FLIGHT_DETAILS frame={getattr(self, 'frame', None)} "
                f"callsign={callsign!r} owner_icao={owner_icao!r} airline={airline!r} "
                f"flight_no={flight_no!r} data_len={len(data)}"
            )
        if not flight_no and len(data) <= 1:
            return

        total_len = 0

        if flight_no:
            for ch in flight_no:
                total_len += self.draw_text(
                    FLIGHT_NO_FONT,
                    self.flight_position + total_len,
                    FLIGHT_NO_DISTANCE_FROM_TOP,
                    FLIGHT_NUMBER_NUMERIC_COLOUR if ch.isnumeric() else FLIGHT_NUMBER_ALPHA_COLOUR,
                    ch,
                )

        # Pager is OK to show, but DO NOT use it to extend total_len unless you want it to affect wrap timing
        if len(data) > 1:
            self.draw_text(
                DATA_INDEX_FONT,
                DATA_INDEX_POSITION[0],
                DATA_INDEX_POSITION[1],
                DATA_INDEX_COLOUR,
                f"{getattr(self,'_data_index',0) + 1}/{len(data)}",
            )

        self.flight_position -= 1

        # Wrap without advancing _data_index (PlaneDetails will drive index)
        if self.flight_position + max(total_len, 1) < 0:
            self.flight_position = screen.WIDTH
            return
