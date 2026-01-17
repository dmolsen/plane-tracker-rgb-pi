import sys
import os
import json
from datetime import datetime

from setup import frames
from utilities.animator import Animator
from utilities.overhead import Overhead

from scenes.temperature import TemperatureScene
from scenes.flightdetails import FlightDetailsScene
from scenes.flightbackground import FlightBackgroundScene
from scenes.flightlogo import FlightLogoScene
from scenes.journey import JourneyScene
from scenes.loadingpulse import LoadingPulseScene
from scenes.clock import ClockScene
from scenes.planedetails import PlaneDetailsScene
from scenes.daysforecast import DaysForecastScene
from scenes.date import DateScene

from rgbmatrix import graphics
from rgbmatrix import RGBMatrix, RGBMatrixOptions




# -----------------------------
# Screen State IPC (file)
# -----------------------------
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCREEN_STATE_FILE = os.path.join(BASE_DIR, "screen_state.json")


def read_screen_state():
    """Returns 'on' or 'off'. Defaults to 'on' on error."""
    try:
        with open(SCREEN_STATE_FILE, "r", encoding="utf-8") as f:
            v = json.load(f).get("screen", "on")
            return v if v in ("on", "off") else "on"
    except Exception:
        return "on"


def read_mode_override():
    """Returns 'auto', 'default', or 'flight'. Defaults to 'auto' on error."""
    try:
        with open(SCREEN_STATE_FILE, "r", encoding="utf-8") as f:
            v = json.load(f).get("mode", "auto")
            return v if v in ("auto", "default", "flight") else "auto"
    except Exception:
        return "auto"


def flight_updated(flights_a, flights_b):
    get_callsigns = lambda flights: [(f.get("callsign"), f.get("direction")) for f in flights]
    return set(get_callsigns(flights_a)) == set(get_callsigns(flights_b))


# -----------------------------
# Config
# -----------------------------
try:
    from config import (
        BRIGHTNESS,
        BRIGHTNESS_NIGHT,
        GPIO_SLOWDOWN,
        HAT_PWM_ENABLED,
        NIGHT_START,
        NIGHT_END,
        NIGHT_BRIGHTNESS,
    )
    NIGHT_START_DT = datetime.strptime(NIGHT_START, "%H:%M")
    NIGHT_END_DT = datetime.strptime(NIGHT_END, "%H:%M")
except Exception:
    BRIGHTNESS = 100
    BRIGHTNESS_NIGHT = 50
    GPIO_SLOWDOWN = 1
    HAT_PWM_ENABLED = True
    NIGHT_BRIGHTNESS = False
    NIGHT_START_DT = datetime.strptime("22:00", "%H:%M")
    NIGHT_END_DT = datetime.strptime("06:00", "%H:%M")


def is_night_time():
    if not NIGHT_BRIGHTNESS:
        return False

    now = datetime.now().time().replace(second=0, microsecond=0)
    night_start = NIGHT_START_DT.time().replace(second=0, microsecond=0)
    night_end = NIGHT_END_DT.time().replace(second=0, microsecond=0)

    if night_start < night_end:
        return night_start <= now < night_end

    # crosses midnight
    return now >= night_start or now < night_end


def desired_brightness():
    if NIGHT_BRIGHTNESS and is_night_time():
        return int(BRIGHTNESS_NIGHT)
    return int(BRIGHTNESS)


class Display(
    # Home widgets
    TemperatureScene,
    ClockScene,
    DateScene,
    DaysForecastScene,

    # Flight widgets
    FlightBackgroundScene,
    FlightLogoScene,
    JourneyScene,
    FlightDetailsScene,
    PlaneDetailsScene,

    # Status widget (optional)
    # LoadingPulseScene,

    Animator,
):
    def __init__(self):
        options = RGBMatrixOptions()
        options.hardware_mapping = "adafruit-hat-pwm" if HAT_PWM_ENABLED else "adafruit-hat"
        options.rows = 32
        options.cols = 64
        options.chain_length = 1
        options.parallel = 1
        options.row_address_type = 0
        options.multiplexing = 0
        options.pwm_bits = 11
        options.brightness = int(BRIGHTNESS)
        options.pwm_lsb_nanoseconds = 130
        options.led_rgb_sequence = "RGB"
        options.pixel_mapper_config = ""
        options.show_refresh_rate = 0
        options.gpio_slowdown = int(GPIO_SLOWDOWN)
        options.disable_hardware_pulsing = True
        options.drop_privileges = False

        self.matrix = RGBMatrix(options=options)

        self.canvas = self.matrix.CreateFrameCanvas()
        self.canvas.Clear()

        # Token increments only when we do a full backbuffer clear
        self._clear_token = 0

        # Data shared across scenes
        self._data_index = 0
        self._data = []
        self._data_all_looped = False

        self.overhead = Overhead()
        self.overhead.grab_data()

        # Presentation bookkeeping
        self._dirty = True
        self._effective_off = False

        # IMPORTANT: This should mean "a full-canvas clear happened this frame"
        self._redraw_all_this_frame = True
        self._force_redraw_next_frame = False
        self._did_forced_redraw_this_frame = False

        # Init animator + scenes
        super().__init__()

        self._mode = None
        self.enabled_tags = {"clock", "date", "temperature", "days_forecast"}
        self._requires_post_swap_redraw = True
        self._update_post_swap_requirement()

        self.delay = frames.PERIOD

        self._canvas_has_setimage = hasattr(self.canvas, "SetImage")

    # -----------------------------
    # Draw helpers (dirty only)
    # -----------------------------
    def _update_post_swap_requirement(self):
        enabled = self.enabled_tags
        requires = False
        for _, keyframe in getattr(self, "keyframes", []):
            props = keyframe.properties
            tag = props.get("tag", None)
            if tag is None:
                continue
            if enabled is not None and tag not in enabled:
                continue
            if props.get("divisor", 0) > 1:
                requires = True
                break
        self._requires_post_swap_redraw = requires

    def mark_dirty(self):
        self._dirty = True

    def clear_canvas(self, reason: str = ""):
        self.canvas.Clear()
        self._clear_token += 1
        self._dirty = True
        self._redraw_all_this_frame = True

    def draw_square(self, x0, y0, x1, y1, colour):
        self._dirty = True
        # DO NOT set _redraw_all_this_frame here.

        y_end = y1 - 1
        if y_end < y0:
            return
        for x in range(x0, x1):
            graphics.DrawLine(self.canvas, x, y0, x, y_end, colour)

    def draw_text(self, font, x, y, colour, text) -> int:
        self._dirty = True
        # DO NOT set _redraw_all_this_frame here.
        return graphics.DrawText(self.canvas, font, x, y, colour, text)

    def set_pixel(self, x, y, r, g, b):
        self._dirty = True
        # DO NOT set _redraw_all_this_frame here.
        self.canvas.SetPixel(x, y, int(r), int(g), int(b))

    def set_image(self, pil_img, x=0, y=0):
        if pil_img is None:
            return
        self._dirty = True
        # DO NOT set _redraw_all_this_frame here.

        if self._canvas_has_setimage:
            self.canvas.SetImage(pil_img, x, y)
            return

        img = pil_img.convert("RGB")
        w, h = img.size
        pix = img.load()
        for iy in range(h):
            for ix in range(w):
                r, g, b = pix[ix, iy]
                self.canvas.SetPixel(x + ix, y + iy, int(r), int(g), int(b))

    def _set_matrix_brightness(self, value: int):
        v = int(max(0, min(100, value)))
        if hasattr(self.matrix, "SetBrightness"):
            self.matrix.SetBrightness(v)
        else:
            try:
                self.matrix.brightness = v
            except Exception:
                pass

    # -----------------------------
    # Data polling
    # -----------------------------
    @Animator.KeyFrame.add(1, run_while_paused=True, order=0)
    def begin_frame(self, count):
        # Restore any pending full redraw after a swap, then clear the flag.
        self._redraw_all_this_frame = self._force_redraw_next_frame
        self._force_redraw_next_frame = False
        self._did_forced_redraw_this_frame = False
        if self._redraw_all_this_frame:
            self.canvas.Clear()
            self._clear_token += 1
            self._dirty = True
            self._force_run_keyframes = True
            self._did_forced_redraw_this_frame = True


    @Animator.KeyFrame.add(frames.PER_SECOND * 5, order=0)
    def check_for_loaded_data(self, count):
        if self.overhead.new_data:
            there_is_data = len(self._data) > 0 or not self.overhead.data_is_empty
            new_data = self.overhead.data
            data_is_different = not flight_updated(self._data, new_data)

            if data_is_different:
                self._data = new_data
                self._data_index = 0
                self._data_all_looped = False

                self.reset_scene()

            reset_required = there_is_data and data_is_different
            if reset_required:
                self.reset_scene()
                self._dirty = True

    # -----------------------------
    # POLICY: tag gating + brightness + pause
    # -----------------------------
    @Animator.KeyFrame.add(1, run_while_paused=True, order=0)
    def policy(self, count):
        screen_state = read_screen_state()
        target_brightness = desired_brightness()
        should_be_off = (screen_state == "off") or (target_brightness <= 0)

        flights_active = len(getattr(self, "_data", [])) > 0
        mode_override = read_mode_override()
        if mode_override == "auto":
            new_mode = "flight" if flights_active else "default"
        else:
            new_mode = mode_override
        if new_mode != self._mode:
            self._mode = new_mode
            if self._mode == "flight":
                self.enabled_tags = {
                    "flight_bg",
                    "flight_logo",
                    "journey",
                    "plane_details",
                    "flight_details",
                }
            else:
                self.enabled_tags = {"clock", "date", "temperature", "days_forecast"}
            self._update_post_swap_requirement()


            # Force a clean redraw
            self.reset_scene()
            self.clear_canvas(f"mode_switch->{self._mode}")
            self._data_index = 0

        if should_be_off:
            if not self._effective_off:
                self._effective_off = True
                self.pause()

            self.clear_canvas("policy_off")
            if getattr(self.matrix, "brightness", 0) != 0:
                self._set_matrix_brightness(0)

            return

        # ON
        if self._effective_off:
            self._effective_off = False
            self.resume()
            self.clear_canvas("policy_on_resume")

            if hasattr(self, "_redraw_time"):
                self._redraw_time = True
            if hasattr(self, "_redraw_date"):
                self._redraw_date = True

        if getattr(self.matrix, "brightness", target_brightness) != target_brightness:
            self._set_matrix_brightness(target_brightness)


    # -----------------------------
    # PRESENT: the only SwapOnVSync
    # -----------------------------
    @Animator.KeyFrame.add(1, run_while_paused=True, order=2)
    def present(self, count):
        if self._effective_off:
            self.canvas = self.matrix.SwapOnVSync(self.canvas)
            self._dirty = False
            if self._requires_post_swap_redraw and not self._did_forced_redraw_this_frame:
                self._force_redraw_next_frame = True
            return

        if not self._dirty:
            return

        # If we need a full redraw after swaps, avoid swapping a partial frame.
        if self._requires_post_swap_redraw and not self._did_forced_redraw_this_frame:
            self._force_redraw_next_frame = True
            self._dirty = False
            return

        self.canvas = self.matrix.SwapOnVSync(self.canvas)
        self._dirty = False

        # Force a full redraw on the next frame after a swap.
        if self._requires_post_swap_redraw and not self._did_forced_redraw_this_frame:
            self._force_redraw_next_frame = True

    @Animator.KeyFrame.add(frames.PER_SECOND * 30)
    def grab_new_data(self, count):
        if not (self.overhead.processing and self.overhead.new_data) and (
            self._data_all_looped or len(self._data) <= 1
        ):
            self.overhead.grab_data()

    def run(self):
        try:
            self.play()
        except KeyboardInterrupt:
            sys.exit(0)
