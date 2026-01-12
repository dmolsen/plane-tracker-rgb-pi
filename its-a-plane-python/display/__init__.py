import sys
import os
import json
import time
from datetime import datetime

from setup import frames
from utilities.animator import Animator
from utilities.overhead import Overhead

from scenes.temperature import TemperatureScene
from scenes.flightdetails import FlightDetailsScene
from scenes.flightlogo import FlightLogoScene
from scenes.journey import JourneyScene
from scenes.loadingpulse import LoadingPulseScene
from scenes.clock import ClockScene
from scenes.planedetails import PlaneDetailsScene
from scenes.daysforecast import DaysForecastScene
from scenes.date import DateScene

from rgbmatrix import graphics
from rgbmatrix import RGBMatrix, RGBMatrixOptions


# =============================
# DEBUG SETTINGS
# =============================
DEBUG = True
DEBUG_EVERY_N_FRAMES = 30
DEBUG_SUMMARY_EVERY_SECONDS = 5.0
DEBUG_SHOW_PANEL_PIXELS = False
DEBUG_LOG_IMAGE_DRAW = True


def _ts() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _dbg(msg: str, flush: bool = True):
    if not DEBUG:
        return
    print(f"{_ts()} PID={os.getpid()} {msg}", flush=flush)


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

        _dbg(
            f"BOOT rgbmatrix mapping={options.hardware_mapping!r} rows={options.rows} cols={options.cols} "
            f"gpio_slowdown={options.gpio_slowdown} brightness={options.brightness} "
            f"drop_privileges={options.drop_privileges}"
        )

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

        # Init animator + scenes
        super().__init__()

        self._mode = None
        self.enabled_tags = {"default", "flight"}

        print("DEBUG pending_reset:", getattr(self, "_pending_reset", None), flush=True)
        self.delay = frames.PERIOD

        # Debug stats
        self._dbg_last_summary_t = time.time()
        self._dbg_swap_count = 0
        self._dbg_clear_count = 0
        self._dbg_reset_count = 0
        self._dbg_last_policy_should_off = None
        self._dbg_last_flights_active = None

        if DEBUG and hasattr(self, "keyframes"):
            try:
                names = [name for name, _ in self.keyframes]
                _dbg("KEYFRAMES order=" + ", ".join(names))
                if names and names[-1] != "zzzzzz_present":
                    _dbg(f"WARNING: present is not last! last={names[-1]}")
            except Exception as e:
                _dbg(f"Could not print keyframe order: {e}")

        self._canvas_has_setimage = hasattr(self.canvas, "SetImage")
        if DEBUG_LOG_IMAGE_DRAW:
            _dbg(f"CAPS canvas.SetImage={self._canvas_has_setimage}")

    # -----------------------------
    # Draw helpers (dirty only)
    # -----------------------------
    def mark_dirty(self):
        self._dirty = True

    def clear_canvas(self, reason: str = ""):
        self.canvas.Clear()
        self._clear_token += 1
        self._dirty = True
        self._redraw_all_this_frame = True
        if DEBUG and reason:
            _dbg(f"CLEAR_CANVAS token={self._clear_token} reason={reason}")

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
    # Debug summary
    # -----------------------------
    def _dbg_summary(self):
        now = time.time()
        if now - self._dbg_last_summary_t < DEBUG_SUMMARY_EVERY_SECONDS:
            return
        self._dbg_last_summary_t = now
        flights_active = len(getattr(self, "_data", [])) > 0
        _dbg(
            f"SUMMARY swaps={self._dbg_swap_count} clears={self._dbg_clear_count} resets={self._dbg_reset_count} "
            f"dirty={self._dirty} paused={self.paused} eff_off={self._effective_off} "
            f"flights_active={flights_active} data_len={len(getattr(self,'_data',[]))} data_idx={getattr(self,'_data_index',None)}"
        )

    # -----------------------------
    # Data polling
    # -----------------------------
    @Animator.KeyFrame.add(1, run_while_paused=True)
    def aaaa_begin_frame(self, count):
        # This must be reset every frame, otherwise scenes treat every tick like a full redraw.
        self._redraw_all_this_frame = False


    @Animator.KeyFrame.add(frames.PER_SECOND * 5)
    def check_for_loaded_data(self, count):
        if self.overhead.new_data:
            there_is_data = len(self._data) > 0 or not self.overhead.data_is_empty
            new_data = self.overhead.data
            data_is_different = not flight_updated(self._data, new_data)

            if DEBUG:
                _dbg(
                    f"DATA new_data=True there_is_data={there_is_data} "
                    f"old_len={len(self._data)} new_len={len(new_data)} different={data_is_different} "
                    f"processing={getattr(self.overhead,'processing',None)} empty={getattr(self.overhead,'data_is_empty',None)}"
                )

            if data_is_different:
                # Force crawler positions to restart on data change
                self.reset_scene()
                self.clear_canvas("data_change")
                self._data_index = 0
                self._data_all_looped = False
                self._data = new_data

            reset_required = there_is_data and data_is_different
            if reset_required:
                self._dbg_reset_count += 1
                _dbg(f"RESET_SCENE triggered resets={self._dbg_reset_count}")
                self.reset_scene()
                self._dirty = True

        flights_active = len(getattr(self, "_data", [])) > 0
        if self._dbg_last_flights_active is None:
            self._dbg_last_flights_active = flights_active
        elif flights_active != self._dbg_last_flights_active:
            self._dbg_last_flights_active = flights_active
            _dbg(f"FLIGHT_STATE change flights_active={flights_active} len(_data)={len(self._data)}")

    # -----------------------------
    # POLICY: tag gating + brightness + pause
    # -----------------------------
    @Animator.KeyFrame.add(1, run_while_paused=True)
    def zzzzzy_policy(self, count):
        screen_state = read_screen_state()
        target_brightness = desired_brightness()
        should_be_off = (screen_state == "off") or (target_brightness <= 0)

        flights_active = len(getattr(self, "_data", [])) > 0
        new_mode = "flight" if flights_active else "default"
        if DEBUG and (self.frame % 10 == 0):
            _dbg(f"MODE_CHECK frame={self.frame} flights_active={flights_active} len(_data)={len(self._data)} mode={self._mode} new_mode={new_mode}")
        if new_mode != self._mode:
            self._mode = new_mode
            self.enabled_tags = {"flight"} if new_mode == "flight" else {"default"}

            _dbg(f"MODE_SWITCH -> {self._mode} (enabled_tags={self.enabled_tags})")

            # Force a clean redraw
            self.reset_scene()
            self.clear_canvas(f"mode_switch->{self._mode}")

        if DEBUG and (self.frame % DEBUG_EVERY_N_FRAMES == 0):
            _dbg(
                f"POLICY frame={self.frame} screen={screen_state} night={is_night_time()} "
                f"target_brightness={target_brightness} should_off={should_be_off} "
                f"paused={self.paused} eff_off={self._effective_off}"
            )

        if should_be_off:
            if not self._effective_off:
                self._effective_off = True
                _dbg("POLICY entering OFF: pause() + brightness=0")
                self.pause()

            self.clear_canvas("policy_off")
            if getattr(self.matrix, "brightness", 0) != 0:
                self._set_matrix_brightness(0)

            self._dbg_summary()
            return

        # ON
        if self._effective_off:
            self._effective_off = False
            _dbg("POLICY leaving OFF: resume() + clear backbuffer")
            self.resume()
            self.clear_canvas("policy_on_resume")

            if hasattr(self, "_redraw_time"):
                self._redraw_time = True
            if hasattr(self, "_redraw_date"):
                self._redraw_date = True

        if getattr(self.matrix, "brightness", target_brightness) != target_brightness:
            self._set_matrix_brightness(target_brightness)

        self._dbg_summary()

    # -----------------------------
    # PRESENT: the only SwapOnVSync
    # -----------------------------
    @Animator.KeyFrame.add(1, run_while_paused=True)
    def zzzzzz_present(self, count):
        if self._effective_off:
            self.canvas = self.matrix.SwapOnVSync(self.canvas)
            self._dbg_swap_count += 1
            self._dirty = False
            self._redraw_all_this_frame = False
            return

        if not self._dirty:
            return

        self.canvas = self.matrix.SwapOnVSync(self.canvas)
        self._dbg_swap_count += 1
        self._dirty = False

        # IMPORTANT: this is a one-frame signal
        self._redraw_all_this_frame = False

    @Animator.KeyFrame.add(frames.PER_SECOND * 30)
    def grab_new_data(self, count):
        if not (self.overhead.processing and self.overhead.new_data) and (
            self._data_all_looped or len(self._data) <= 1
        ):
            if DEBUG:
                _dbg("GRAB_NEW_DATA calling overhead.grab_data()")
            self.overhead.grab_data()

    def run(self):
        try:
            _dbg("RUN starting Animator.play()")
            self.play()
        except KeyboardInterrupt:
            _dbg("Exiting (KeyboardInterrupt)")
            sys.exit(0)