import os
from PIL import Image

from utilities.animator import Animator
from setup import colours

LOGO_SIZE = 16
DEFAULT_IMAGE = "default"

# Clear region (top-left logo square)
LOGO_CLEAR_X0 = 0
LOGO_CLEAR_Y0 = 0
LOGO_CLEAR_X1 = LOGO_SIZE
LOGO_CLEAR_Y1 = LOGO_SIZE

_THIS_DIR = os.path.dirname(__file__)
LOGOS_DIR = os.path.join(_THIS_DIR, "logos")


class FlightLogoScene(object):
    def __init__(self):
        super().__init__()
        self._last_icao_drawn = None
        self._logo_cache = {}  # icao -> PIL RGB image or None

    def _clear_logo_area(self):
        self.draw_square(
            LOGO_CLEAR_X0,
            LOGO_CLEAR_Y0,
            LOGO_CLEAR_X1,
            LOGO_CLEAR_Y1,
            colours.BLACK,
        )

    def _get_logo(self, icao: str):
        if not icao or icao in ("", "N/A"):
            icao = DEFAULT_IMAGE

        if icao in self._logo_cache:
            return self._logo_cache[icao]

        path = os.path.join(LOGOS_DIR, f"{icao}.png")
        fallback = os.path.join(LOGOS_DIR, f"{DEFAULT_IMAGE}.png")

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

        try:
            resample = Image.Resampling.LANCZOS
        except AttributeError:
            resample = Image.ANTIALIAS

        img.thumbnail((LOGO_SIZE, LOGO_SIZE), resample)
        img = img.convert("RGB")

        self._logo_cache[icao] = img
        return img

    def _current_flight(self):
        data = getattr(self, "_data", None)
        idx = getattr(self, "_data_index", 0)
        if not data or idx < 0 or idx >= len(data):
            return None
        return data[idx]

    @Animator.KeyFrame.add(0, tag="flight")
    def reset_logo(self):
        self._last_icao_drawn = None
        self._clear_logo_area()

    @Animator.KeyFrame.add(1, tag="flight")
    def logo_details(self, count):
        f = self._current_flight()
        if not f:
            return

        icao = f.get("owner_icao") or DEFAULT_IMAGE
        if icao in ("", "N/A"):
            icao = DEFAULT_IMAGE

        if icao == self._last_icao_drawn:
            return

        self._clear_logo_area()

        img = self._get_logo(str(icao))
        if img is not None:
            self.set_image(img, 0, 0)

        self._last_icao_drawn = icao