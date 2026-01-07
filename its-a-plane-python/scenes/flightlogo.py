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

# Resolve logos directory relative to this file so CWD doesn't matter
_THIS_DIR = os.path.dirname(__file__)
# If your logos folder is at project-root/logos, use the second line instead.
LOGOS_DIR = os.path.join(_THIS_DIR, "logos")
# LOGOS_DIR = os.path.join(os.path.dirname(_THIS_DIR), "logos")


class FlightLogoScene(object):
    def __init__(self):
        super().__init__()
        self._was_showing_flights = False
        self._last_icao_drawn = None

        # icao -> PIL RGB image (already resized) or None
        self._logo_cache = {}

    def _flights_active(self) -> bool:
        return len(getattr(self, "_data", [])) > 0

    def _clear_logo_area(self):
        self.draw_square(
            LOGO_CLEAR_X0,
            LOGO_CLEAR_Y0,
            LOGO_CLEAR_X1,
            LOGO_CLEAR_Y1,
            colours.BLACK,
        )

    def _get_logo(self, icao: str):
        """Load+resize once; return cached PIL RGB image or None."""
        if not icao:
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

        # Resize once
        try:
            resample = Image.Resampling.LANCZOS  # Pillow 10+
        except AttributeError:
            resample = Image.ANTIALIAS          # Pillow <10

        img.thumbnail((LOGO_SIZE, LOGO_SIZE), resample)
        img = img.convert("RGB")

        self._logo_cache[icao] = img
        return img

    @Animator.KeyFrame.add(1, tag="flightLogo")
    def logo_details(self, count):
        flights_active = self._flights_active()

        # If flights are not active, ensure logo area is cleared once and stop.
        if not flights_active:
            if self._was_showing_flights:
                self._was_showing_flights = False
                self._last_icao_drawn = None
                self._clear_logo_area()
            return

        # Flights are active
        if not self._was_showing_flights:
            self._was_showing_flights = True
            self._clear_logo_area()

        # Guard against bad indexes / empty data
        if not getattr(self, "_data", None) or len(self._data) == 0:
            return
        if getattr(self, "_data_index", 0) < 0 or self._data_index >= len(self._data):
            return

        icao = self._data[self._data_index].get("owner_icao") or DEFAULT_IMAGE
        if icao in ("", "N/A"):
            icao = DEFAULT_IMAGE

        # Only redraw if ICAO changed (plane changed)
        if icao == self._last_icao_drawn:
            return

        self._clear_logo_area()

        img = self._get_logo(str(icao))
        if img is not None:
            # IMPORTANT: draw via Display helper (marks dirty + correct target)
            self.set_image(img, 0, 0)

        self._last_icao_drawn = icao