import sys
import json
import os
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

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCREEN_STATE_FILE = os.path.join(BASE_DIR, "screen_state.json")


def read_screen_state():
    try:
        with open(SCREEN_STATE_FILE, "r") as f:
            return json.load(f).get("screen", "on")
    except Exception:
        return "on"


def flight_updated(flights_a, flights_b):
    get_callsigns = lambda flights: [(f["callsign"], f["direction"]) for f in flights]
    return set(get_callsigns(flights_a)) == set(get_callsigns(flights_b))


try:
    # Load config data
    from config import (
        BRIGHTNESS,
        GPIO_SLOWDOWN,
        HAT_PWM_ENABLED,
        NIGHT_START,
        NIGHT_END,
        NIGHT_BRIGHTNESS,
    )
    NIGHT_START = datetime.strptime(NIGHT_START, "%H:%M")
    NIGHT_END = datetime.strptime(NIGHT_END, "%H:%M")

except (ModuleNotFoundError, NameError):
    BRIGHTNESS = 100
    GPIO_SLOWDOWN = 1
    HAT_PWM_ENABLED = True
    NIGHT_BRIGHTNESS = False


def is_night_time():
    if not NIGHT_BRIGHTNESS:
        return False
    now = datetime.now().time().replace(second=0, microsecond=0)
    night_start = NIGHT_START.time()
    night_end = NIGHT_END.time()
    if night_start < night_end:
        return night_start <= now < night_end
    else:
        return now >= night_start or now < night_end


class Display(
    TemperatureScene,
    FlightDetailsScene,
    FlightLogoScene,
    JourneyScene,
    LoadingPulseScene,
    PlaneDetailsScene,
    ClockScene,
    DaysForecastScene,
    DateScene,
    Animator,
):
    def __init__(self):
        # --- Setup LED Matrix ---
        options = RGBMatrixOptions()
        options.hardware_mapping = "adafruit-hat-pwm" if HAT_PWM_ENABLED else "adafruit-hat"
        options.rows = 32
        options.cols = 64
        options.chain_length = 1
        options.parallel = 1
        options.row_address_type = 0
        options.multiplexing = 0
        options.pwm_bits = 11
        options.brightness = BRIGHTNESS
        options.pwm_lsb_nanoseconds = 130
        options.led_rgb_sequence = "RGB"
        options.pixel_mapper_config = ""
        options.show_refresh_rate = 0
        options.gpio_slowdown = GPIO_SLOWDOWN
        options.disable_hardware_pulsing = True
        options.drop_privileges = True

        self.matrix = RGBMatrix(options=options)
        self.canvas = self.matrix.CreateFrameCanvas()

        # Flight data
        self._data_index = 0
        self._data = []
        self._data_all_looped = True

        # Plane lookup
        self.overhead = Overhead()
        self.overhead.grab_data()

        # Animator/scenes
        super().__init__()
        self.delay = frames.PERIOD

    def draw_square(self, x0, y0, x1, y1, colour):
        for x in range(x0, x1):
            _ = graphics.DrawLine(self.canvas, x, y0, x, y1, colour)

    @Animator.KeyFrame.add(0)
    def clear_screen(self):
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

            if there_is_data and data_is_different:
                self.reset_scene()

    @Animator.KeyFrame.add(1)
    def sync(self, count):
        screen_state = read_screen_state()
        night = is_night_time()

        # Track previous state
        if not hasattr(self, "_screen_was_off"):
            self._screen_was_off = False

        # -------------------------
        # SCREEN OFF
        # -------------------------
        if screen_state == "off" or night:
            self.canvas.Clear()
            if self.matrix.brightness != 0:
                self.matrix.brightness = 0
            self._screen_was_off = True
            _ = self.matrix.SwapOnVSync(self.canvas)
            return

        # -------------------------
        # SCREEN TURNING BACK ON
        # -------------------------
        if self._screen_was_off:
            self._screen_was_off = False

            # Restore brightness
            if self.matrix.brightness != BRIGHTNESS:
                self.matrix.brightness = BRIGHTNESS

            # 🔥 THIS IS THE CRITICAL LINE
            self.reset_scene()

        # Normal draw
        _ = self.matrix.SwapOnVSync(self.canvas)


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
