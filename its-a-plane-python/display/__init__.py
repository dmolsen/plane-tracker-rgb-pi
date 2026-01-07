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

# print every N frames for high-frequency stuff (policy/present)
DEBUG_EVERY_N_FRAMES = 30  # ~3 seconds if PERIOD=0.1, adjust

# print every N seconds for periodic summaries
DEBUG_SUMMARY_EVERY_SECONDS = 5.0


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
    """
    Returns "on" or "off".
    If file missing/bad, default to "on".
    """
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
    """
    If NIGHT_BRIGHTNESS is True and currently night, use BRIGHTNESS_NIGHT.
    Otherwise use BRIGHTNESS.
    """
    if NIGHT_BRIGHTNESS and is_night_time():
        return int(BRIGHTNESS_NIGHT)
    return int(BRIGHTNESS)


class Display(
    # “Home” widgets:
    TemperatureScene,
    ClockScene,
    DateScene,
    DaysForecastScene,

    # “Flight” widgets:
    FlightLogoScene,
    JourneyScene,
    FlightDetailsScene,
    PlaneDetailsScene,

    # status widget:
    LoadingPulseScene,

    Animator,
):
    def __init__(self):
        # Setup Display
        options = RGBMatrixOptions()
        options.hardware_mapping = "adafruit-hat"  # hard-coded per your test
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

        # Setup canvas (IMPORTANT: keep and swap the returned canvas)
        self.canvas = self.matrix.CreateFrameCanvas()
        self.canvas.Clear()

        # Data to render
        self._data_index = 0
        self._data = []
        self._data_all_looped = False

        # Start Looking for planes
        self.overhead = Overhead()
        self.overhead.grab_data()

        # Initialize animator + scenes
        super().__init__()

        # Animator timing
        self.delay = frames.PERIOD

        # Track current “off” state so we don’t thrash pause/resume
        self._effective_off = False

        # =============================
        # DEBUG STATE
        # =============================
        self._dbg_last_summary_t = time.time()
        self._dbg_swap_count = 0
        self._dbg_clear_count = 0
        self._dbg_reset_count = 0
        self._dbg_last_policy_should_off = None
        self._dbg_last_flights_active = None

        # Print keyframe order once (VERY IMPORTANT)
        if DEBUG and hasattr(self, "keyframes"):
            try:
                names = [name for name, _ in self.keyframes]
                _dbg("KEYFRAMES order=" + ", ".join(names))
                # sanity: ensure present is last
                if names and names[-1] != "zzzzzz_present":
                    _dbg(f"WARNING: present is not last! last={names[-1]}")
            except Exception as e:
                _dbg(f"Could not print keyframe order: {e}")

    def draw_square(self, x0, y0, x1, y1, colour):
        for x in range(x0, x1):
            _ = graphics.DrawLine(self.canvas, x, y0, x, y1, colour)

    # =============================
    # DEBUG HELPERS
    # =============================
    def _dbg_summary(self):
        now = time.time()
        if now - self._dbg_last_summary_t < DEBUG_SUMMARY_EVERY_SECONDS:
            return
        self._dbg_last_summary_t = now

        flights_active = len(getattr(self, "_data", [])) > 0

        _dbg(
            f"SUMMARY swaps={self._dbg_swap_count} clears={self._dbg_clear_count} resets={self._dbg_reset_count} "
            f"paused={self.paused} eff_off={self._effective_off} "
            f"flights_active={flights_active} data_len={len(getattr(self,'_data',[]))} data_idx={getattr(self,'_data_index',None)}"
        )

    @Animator.KeyFrame.add(0)
    def clear_screen(self):
        # First operation after a scene reset
        self._dbg_clear_count += 1
        if DEBUG:
            _dbg(f"CLEAR_SCREEN fired count={self._dbg_clear_count}")
        self.canvas.Clear()

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
                self._data_index = 0
                self._data_all_looped = False
                self._data = new_data

            reset_required = there_is_data and data_is_different
            if reset_required:
                # (3,0) = yellow flash on reset trigger (will persist until cleared)
                self.canvas.SetPixel(3, 0, 255, 255, 0)
                self._dbg_reset_count += 1
                _dbg(f"RESET_SCENE triggered resets={self._dbg_reset_count}")
                self.reset_scene()

        # track flight/home transitions (even if no new_data)
        flights_active = len(getattr(self, "_data", [])) > 0
        if self._dbg_last_flights_active is None:
            self._dbg_last_flights_active = flights_active
        elif flights_active != self._dbg_last_flights_active:
            self._dbg_last_flights_active = flights_active
            _dbg(f"FLIGHT_STATE change flights_active={flights_active} len(_data)={len(self._data)}")

    # -----------------------------
    # POLICY: off/on + night + pause/resume
    # (NO SwapOnVSync here)
    # -----------------------------
    @Animator.KeyFrame.add(1, run_while_paused=True)
    def zzzzzy_policy(self, count):
        screen_state = read_screen_state()
        target_brightness = desired_brightness()
        should_be_off = (screen_state == "off") or (target_brightness <= 0)

        # Debug state pixels (visible on panel)
        # (1,0) = red when policy says OFF
        self.canvas.SetPixel(1, 0, 255 if should_be_off else 0, 0, 0)

        # (2,0) = blue when flights active
        flights_active = len(getattr(self, "_data", [])) > 0
        self.canvas.SetPixel(2, 0, 0, 0, 255 if flights_active else 0)

        # Only print policy occasionally (otherwise it floods)
        if DEBUG and (self.frame % DEBUG_EVERY_N_FRAMES == 0):
            _dbg(
                f"POLICY frame={self.frame} screen={screen_state} night={is_night_time()} "
                f"target_brightness={target_brightness} should_off={should_be_off} "
                f"paused={self.paused} eff_off={self._effective_off} "
                f"matrix.brightness={getattr(self.matrix,'brightness',None)}"
            )

        # detect unexpected toggling
        if self._dbg_last_policy_should_off is None:
            self._dbg_last_policy_should_off = should_be_off
        elif should_be_off != self._dbg_last_policy_should_off:
            self._dbg_last_policy_should_off = should_be_off
            _dbg(f"POLICY TOGGLE should_be_off -> {should_be_off} (screen_state={screen_state}, target={target_brightness})")

        if should_be_off:
            if not self._effective_off:
                self._effective_off = True
                _dbg("POLICY entering OFF: pause() + brightness=0")
                self.pause()

            # Keep backbuffer blank while off
            self.canvas.Clear()

            # Force matrix brightness to 0
            if self.matrix.brightness != 0:
                self.matrix.brightness = 0

            self._dbg_summary()
            return

        # --- ON MODE ---
        if self._effective_off:
            self._effective_off = False
            _dbg("POLICY leaving OFF: resume() + clear backbuffer")
            self.resume()
            self.canvas.Clear()

        if self.matrix.brightness != target_brightness:
            self.matrix.brightness = target_brightness

        self._dbg_summary()

    # -----------------------------
    # PRESENT: the ONLY SwapOnVSync
    # (runs even while paused)
    # -----------------------------
    @Animator.KeyFrame.add(1, run_while_paused=True)
    def zzzzzz_present(self, count):
        self._dbg_swap_count += 1

        # print occasionally
        # proof pixel (0,0) green: present is running
        self.canvas.SetPixel(0, 0, 0, 255, 0)

        # blink-reset indicator pixel at (3,0) every ~1s so you can see it flash
        # (If reset never happens, it stays off)
        if (self.frame % (frames.PER_SECOND * 1)) == 0:
            self.canvas.SetPixel(3, 0, 0, 0, 0)

        # proof pixel (top-left green)
        self.canvas.SetPixel(0, 0, 0, 255, 0)

        # Swap and KEEP the returned backbuffer
        self.canvas = self.matrix.SwapOnVSync(self.canvas)

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