# scenes/flightlogo.py
from PIL import Image
import os

from utilities.animator import Animator
from setup import colours

LOGO_SIZE = 16
DEFAULT_IMAGE = "default"

# Region we own: top-left 16x16
LOGO_CLEAR_X0 = 0
LOGO_CLEAR_Y0 = 0
LOGO_CLEAR_X1 = LOGO_SIZE
LOGO_CLEAR_Y1 = LOGO_SIZE

# OLD behavior: load from ./logos/<icao>.png relative to process CWD
# (matches your original version)
def _logo_path(icao: str) -> str:
    return f"logos/{icao}.png"


class FlightLogoScene(object):
    def __init__(self):
        super().__init__()
        self._last_icao_drawn = None

        # icao -> PIL.Image(RGB) or None
        self._logo_cache = {}

        # Track Display-level full clears (clear_canvas/clear_screen) so we redraw after canvas.Clear()
        self._last_clear_token_seen = None

    def _clear_logo_area(self):
        self.draw_square(
            LOGO_CLEAR_X0,
            LOGO_CLEAR_Y0,
            LOGO_CLEAR_X1,
            LOGO_CLEAR_Y1,
            colours.BLACK,
        )

    def _current_flight(self):
        data = getattr(self, "_data", None)
        idx = getattr(self, "_data_index", 0)
        if not data or idx < 0 or idx >= len(data):
            return None
        return data[idx]

    def _sync_with_canvas_clear(self):
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

    def _get_logo(self, icao: str):
        """Load+resize once; return cached PIL RGB image or None."""
        if not icao or icao in ("", "N/A"):
            icao = DEFAULT_IMAGE

        icao = str(icao).strip()

        if icao in self._logo_cache:
            return self._logo_cache[icao]

        path = _logo_path(icao)
        fallback = _logo_path(DEFAULT_IMAGE)

        try:
            img = Image.open(path)
        except FileNotFoundError:
            try:
                img = Image.open(fallback)
            except Exception:
                self._logo_cache[icao] = None
                return None
        except Exception:
            self._logo_cache[icao] = None
            return None

        # Resize
        try:
            resample = Image.Resampling.LANCZOS  # Pillow 10+
        except AttributeError:
            resample = Image.ANTIALIAS          # Pillow <10

        img.thumbnail((LOGO_SIZE, LOGO_SIZE), resample)
        img = img.convert("RGB")

        self._logo_cache[icao] = img
        return img

    @Animator.KeyFrame.add(0, tag="flight_logo")
    def reset_logo(self):
        # Called on reset_scene() (mode switch / clear_screen)
        self._last_icao_drawn = None
        self._last_clear_token_seen = getattr(self, "_clear_token", None)
        self._clear_logo_area()

    @Animator.KeyFrame.add(1, tag="flight_logo")
    def logo_details(self, count):
        ## Redraw if the display did a full clear this frame
        cleared = self._sync_with_canvas_clear()

        f = self._current_flight()
        if not f:
            return

        icao = f.get("owner_icao") or DEFAULT_IMAGE
        if icao in ("", "N/A"):
            icao = DEFAULT_IMAGE
        icao = str(icao).strip()

        force = bool(getattr(self, "_redraw_all_this_frame", False))

        ## Only redraw when needed:
        if (icao == self._last_icao_drawn) and (not force) and (not cleared):
            return

        ## Clear our region and draw
        self._clear_logo_area()

        img = self._get_logo(icao)
        if img is not None:
            # Bottom-align inside the 16x16 logo box ("logo should be at the base")
            y = LOGO_SIZE - img.size[1]
            if y < 0:
                y = 0

            # (Optional) left align; you can center if you want:
            x = 0
            x = max(0, (LOGO_SIZE - img.size[0]) // 2)

            # IMPORTANT: draw to backbuffer via Display helper
            self.set_image(img, x, y)

        self._last_icao_drawn = icao
