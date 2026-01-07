import sys
import os
import json
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

    If you want "night = fully off", set BRIGHTNESS_NIGHT = 0 in config.
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
        options.drop_privileges = True

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

    def draw_square(self, x0, y0, x1, y1, colour):
        for x in range(x0, x1):
            _ = graphics.DrawLine(self.canvas, x, y0, x, y1, colour)

    @Animator.KeyFrame.add(0)
    def clear_screen(self):
        # First operation after a scene reset
        self.canvas.Clear()

    @Animator.KeyFrame.add(frames.PER_SECOND * 5)
    def check_for_loaded_data(self, count):
        if self.overhead.new_data:
            there_is_data = len(self._data) > 0 or not self.overhead.data_is_empty
            new_data = self.overhead.data
            data_is_different = not flight_updated(self._data, new_data)

            if data_is_different:
                self._data_index = 0
                self._data_all_looped = False
                self._data = new_data

            reset_required = there_is_data and data_is_different
            if reset_required:
                self.reset_scene()

    # -----------------------------
    # POLICY: off/on + night + pause/resume
    # (NO SwapOnVSync here)
    # -----------------------------
    @Animator.KeyFrame.add(1, run_while_paused=True)
    def zz_sync_policy(self, count):
        screen_state = read_screen_state()
        target_brightness = desired_brightness()
        should_be_off = (screen_state == "off") or (target_brightness <= 0)

        # Debug prints (keep while you test)
        print(
            f"{datetime.now().isoformat()} screen={screen_state} "
            f"night={is_night_time()} target_brightness={target_brightness} "
            f"should_be_off={should_be_off} paused={self.paused} "
            f"matrix.brightness={getattr(self.matrix, 'brightness', None)}",
            flush=True,
        )

        if should_be_off:
            if not self._effective_off:
                self._effective_off = True
                self.pause()

            # Keep backbuffer blank while off
            self.canvas.Clear()

            # Force matrix brightness to 0
            if self.matrix.brightness != 0:
                self.matrix.brightness = 0

            return

        # --- ON MODE ---
        if self._effective_off:
            self._effective_off = False
            # Resume triggers reset_scene once on the next loop
            self.resume()
            # Clear backbuffer so the first "on" frame is clean
            self.canvas.Clear()

        if self.matrix.brightness != target_brightness:
            self.matrix.brightness = target_brightness

    # -----------------------------
    # PRESENT: the ONLY SwapOnVSync
    # (runs even while paused)
    # -----------------------------
    @Animator.KeyFrame.add(1, run_while_paused=True)
    def zzz_present(self, count):
        # Optional proof pixel (uncomment while debugging)
        # self.canvas.SetPixel(0, 0, 0, 255, 0)

        self.canvas = self.matrix.SwapOnVSync(self.canvas)

    @Animator.KeyFrame.add(frames.PER_SECOND * 30)
    def grab_new_data(self, count):
        if not (self.overhead.processing and self.overhead.new_data) and (
            self._data_all_looped or len(self._data) <= 1
        ):
            self.overhead.grab_data()

    def run(self):
        try:
            print("Press CTRL-C to stop")
            self.play()
        except KeyboardInterrupt:
            print("Exiting\n")
            sys.exit(0)