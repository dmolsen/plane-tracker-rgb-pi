# scenes/planedetails.py
from utilities.animator import Animator
from setup import colours, fonts, screen
from config import DISTANCE_UNITS
from rgbmatrix import graphics

# ============================================================
# DEBUG TOGGLES (set these True/False while testing)
# ============================================================

# If True, PlaneDetails clears the ENTIRE screen every tick.
# Use this to prove whether "red/blue blob" is coming from some other scene.
DEBUG_CLEAR_WHOLE_SCREEN = False

# If True, draw marker lines showing exactly what region is being cleared.
DEBUG_DRAW_BAND_MARKERS = True

# If True, draw a tiny "PD" label and some numbers so you can confirm the scene is running.
DEBUG_DRAW_TEXT_OVERLAY = True

# If True, use slow pixelwise clear for the band (definitive test if DrawLine+Color is suspicious).
# This is slow, but on 64x32 should still be OK for debugging.
DEBUG_PIXELWISE_CLEAR = False

# ============================================================
# CONFIG / LAYOUT
# ============================================================

PLANE_COLOUR = colours.LIGHT_MID_BLUE
PLANE_DISTANCE_COLOUR = colours.LIGHT_PINK

# 64x32 display: bottom baseline is y=31
PLANE_DISTANCE_FROM_TOP = 31      # baseline Y for 5x8 font
PLANE_TEXT_HEIGHT = 8             # 5x8 font height
PLANE_FONT = fonts.small          # 5x8.bdf

# ---- Clear band we "own"
# With baseline=31 and height=8, safe band is y=23..31 inclusive.
# Display.draw_square treats y1 as EXCLUSIVE, so use y1=32 to include row 31.
PLANE_CLEAR_X0 = 0
PLANE_CLEAR_X1 = screen.WIDTH     # 64
PLANE_CLEAR_Y0 = PLANE_DISTANCE_FROM_TOP - PLANE_TEXT_HEIGHT  # 31 - 8 = 23
PLANE_CLEAR_Y1 = screen.HEIGHT    # 32

# ============================================================
# Known-good colors (avoid any mismatch with your colours.BLACK object)
# ============================================================
BLACK = graphics.Color(0, 0, 0)
GREEN = graphics.Color(0, 255, 0)
YELLOW = graphics.Color(255, 255, 0)
WHITE = graphics.Color(255, 255, 255)


def _unit_label() -> str:
    return "mi" if str(DISTANCE_UNITS).lower() == "imperial" else "KM"


class PlaneDetailsScene(object):
    def __init__(self):
        super().__init__()
        self.plane_position = screen.WIDTH
        self._data_all_looped = False
        self._dbg_tick = 0

    def _current_flight(self):
        data = getattr(self, "_data", None)
        idx = getattr(self, "_data_index", 0)
        if not data or idx < 0 or idx >= len(data):
            return None
        return data[idx]

    def _clear_rect_pixelwise(self, x0, y0, x1, y1):
        # y1 is EXCLUSIVE
        for y in range(max(0, y0), min(screen.HEIGHT, y1)):
            for x in range(max(0, x0), min(screen.WIDTH, x1)):
                self.canvas.SetPixel(x, y, 0, 0, 0)
        self.mark_dirty()

    def _clear_band(self):
        if DEBUG_CLEAR_WHOLE_SCREEN:
            # Clear full screen (definitive test)
            if DEBUG_PIXELWISE_CLEAR:
                self._clear_rect_pixelwise(0, 0, screen.WIDTH, screen.HEIGHT)
            else:
                self.draw_square(0, 0, screen.WIDTH, screen.HEIGHT, BLACK)

            if DEBUG_DRAW_BAND_MARKERS:
                # Mark the *intended* band even when clearing whole screen
                graphics.DrawLine(self.canvas, 0, PLANE_CLEAR_Y0, 63, PLANE_CLEAR_Y0, GREEN)
                graphics.DrawLine(self.canvas, 0, PLANE_CLEAR_Y1 - 1, 63, PLANE_CLEAR_Y1 - 1, YELLOW)
                self.mark_dirty()
            return

        # Normal: clear only bottom band
        if DEBUG_PIXELWISE_CLEAR:
            self._clear_rect_pixelwise(PLANE_CLEAR_X0, PLANE_CLEAR_Y0, PLANE_CLEAR_X1, PLANE_CLEAR_Y1)
        else:
            self.draw_square(PLANE_CLEAR_X0, PLANE_CLEAR_Y0, PLANE_CLEAR_X1, PLANE_CLEAR_Y1, BLACK)

        if DEBUG_DRAW_BAND_MARKERS:
            graphics.DrawLine(self.canvas, 0, PLANE_CLEAR_Y0, 63, PLANE_CLEAR_Y0, GREEN)
            graphics.DrawLine(self.canvas, 0, PLANE_CLEAR_Y1 - 1, 63, PLANE_CLEAR_Y1 - 1, YELLOW)
            self.mark_dirty()

    # ------------------------------------------------------------
    # NOTE: zzzzz_* prefix is intentional so this runs late.
    # ------------------------------------------------------------

    @Animator.KeyFrame.add(0, tag="flight")
    def zzzzz_reset_plane_details(self):
        self.plane_position = screen.WIDTH
        self._dbg_tick = 0
        self._clear_band()

    @Animator.KeyFrame.add(1, tag="flight")
    def zzzzz_plane_details(self, count):
        f = self._current_flight()
        if not f:
            # Still show something so you know the scene is running.
            self._clear_band()
            if DEBUG_DRAW_TEXT_OVERLAY:
                graphics.DrawText(self.canvas, fonts.extrasmall, 0, 6, WHITE, "PD(no data)")
                self.mark_dirty()
            return

        self._dbg_tick += 1

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

        # Clear region first
        self._clear_band()

        # Optional overlay confirms execution + shows band coords and scroll
        if DEBUG_DRAW_TEXT_OVERLAY:
            # Top-left small overlay (outside the bottom band, so it won't be cleared by band clear)
            # If you are clearing whole screen, this still renders after clear so you can see it.
            overlay = f"PD y{PLANE_CLEAR_Y0}-{PLANE_CLEAR_Y1-1} x={self.plane_position}"
            graphics.DrawText(self.canvas, fonts.extrasmall, 0, 6, WHITE, overlay[:21])  # keep short
            self.mark_dirty()

        # Draw plane name then distance/direction right after it
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

        # Scroll
        self.plane_position -= 1

        # Wrap/advance when fully off screen
        if self.plane_position + total < 0:
            self.plane_position = screen.WIDTH
            data = getattr(self, "_data", [])
            if len(data) > 1:
                self._data_index = (self._data_index + 1) % len(data)
                self._data_all_looped = (self._data_index == 0) or self._data_all_looped
            return