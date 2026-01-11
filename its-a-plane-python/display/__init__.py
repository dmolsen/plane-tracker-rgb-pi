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
DEBUG_EVERY_N_FRAMES = 30           # policy prints
DEBUG_SUMMARY_EVERY_SECONDS = 5.0   # periodic summary
DEBUG_SHOW_PANEL_PIXELS = False      # tiny pixels at top-left for state visibility

# If your icons/logos still don't show, set True to log missing SetImage support:
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
    """If NIGHT_BRIGHTNESS is True and it's night, use BRIGHTNESS_NIGHT else BRIGHTNESS."""
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

        # You discovered adafruit-hat works; keep hard-coded for now.
        # If you later want pwm again, switch carefully.
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

        # NOTE: You were testing drop_privileges=False; keep as-is.
        # If you run as root, you can set True.
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
        self._clear_token = 0

        # Data to render
        self._data_index = 0
        self._data = []
        self._data_all_looped = False

        # Start Looking for planes
        self.overhead = Overhead()
        self.overhead.grab_data()

        # -----------------------------
        # Dirty-buffer presentation
        # -----------------------------
        # If we SwapOnVSync every frame but only partially redraw, you will flicker.
        # We fix that by swapping ONLY when the frame is "dirty".
        self._dirty = True
        self._off_mode_force_swap_counter = 0

        # Track current “off” state so we don’t thrash pause/resume
        self._effective_off = False

        # Initialize animator + scenes
        super().__init__()

        self._redraw_all_this_frame = False
        self._mode = None  # "default" or "flight"
        self.enabled_tags = {"default","flight"}  # start with just clock

        print("DEBUG pending_reset:", getattr(self, "_pending_reset", None), flush=True)

        # Animator timing
        self.delay = frames.PERIOD

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
                if names and names[-1] != "zzzzzz_present":
                    _dbg(f"WARNING: present is not last! last={names[-1]}")
            except Exception as e:
                _dbg(f"Could not print keyframe order: {e}")

        # Detect whether canvas supports SetImage (for icons/logos)
        self._canvas_has_setimage = hasattr(self.canvas, "SetImage")
        if DEBUG_LOG_IMAGE_DRAW:
            _dbg(f"CAPS canvas.SetImage={self._canvas_has_setimage}")

    # -----------------------------
    # Draw helpers (mark dirty!)
    # -----------------------------
    def mark_dirty(self):
        self._dirty = True

    def clear_canvas(self, reason: str = ""):
        # full backbuffer clear that scenes can detect
        self.canvas.Clear()
        self._clear_token += 1
        self._dirty = True
        self._redraw_all_this_frame = True
        if DEBUG and reason:
            _dbg(f"CLEAR_CANVAS token={self._clear_token} reason={reason}")

    def draw_square(self, x0, y0, x1, y1, colour):
        self._dirty = True
        self._redraw_all_this_frame = True

        # Treat x1/y1 as EXCLUSIVE bounds.
        # rgbmatrix DrawLine is inclusive, so we use y1-1.
        y_end = y1 - 1
        if y_end < y0:
            return

        for x in range(x0, x1):
            _ = graphics.DrawLine(self.canvas, x, y0, x, y_end, colour)

    def draw_text(self, font, x, y, colour, text) -> int:
        self._dirty = True
        self._redraw_all_this_frame = True
        return graphics.DrawText(self.canvas, font, x, y, colour, text)

    def set_pixel(self, x, y, r, g, b):
        self._dirty = True
        self._redraw_all_this_frame = True
        self.canvas.SetPixel(x, y, int(r), int(g), int(b))

    def set_image(self, pil_img, x=0, y=0):
        """
        Draw a PIL image onto the current *canvas* (backbuffer).
        This is critical: drawing to matrix directly bypasses the buffer flow and
        often results in 'no icon' or tearing/flicker.
        """
        if pil_img is None:
            return

        if self._canvas_has_setimage:
            self._dirty = True
            self._redraw_all_this_frame = True
            self.canvas.SetImage(pil_img, x, y)
            return

        # Fallback: very slow pixel blit (but guarantees something shows)
        if DEBUG_LOG_IMAGE_DRAW:
            _dbg("WARN canvas has no SetImage; using slow pixel blit fallback")
        self._dirty = True
        self._redraw_all_this_frame = True
        img = pil_img.convert("RGB")
        w, h = img.size
        pix = img.load()
        for iy in range(h):
            for ix in range(w):
                r, g, b = pix[ix, iy]
                self.canvas.SetPixel(x + ix, y + iy, int(r), int(g), int(b))
    
    def _set_matrix_brightness(self, value: int):
        v = int(max(0, min(100, value)))
        # Prefer the real API if present
        if hasattr(self.matrix, "SetBrightness"):
            self.matrix.SetBrightness(v)
        else:
            # fallback (some bindings expose brightness as a property)
            try:
                self.matrix.brightness = v
            except Exception:
                pass

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
            f"dirty={self._dirty} paused={self.paused} eff_off={self._effective_off} "
            f"flights_active={flights_active} data_len={len(getattr(self,'_data',[]))} data_idx={getattr(self,'_data_index',None)}"
        )

    #@Animator.KeyFrame.add(0)
    #def clear_screen(self):
    #    self._dbg_clear_count += 1
    #    if DEBUG:
    #        _dbg(f"CLEAR_SCREEN fired count={self._dbg_clear_count}")
    #    self.clear_canvas("clear_screen")

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
                self._dbg_reset_count += 1
                _dbg(f"RESET_SCENE triggered resets={self._dbg_reset_count}")
                self.reset_scene()
                self._dirty = True

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

        flights_active = len(getattr(self, "_data", [])) > 0
        new_mode = "flight" if flights_active else "default"
        if new_mode != self._mode:
            self._mode = new_mode
            self.enabled_tags = {"flight"} if new_mode == "flight" else {"default"}

            _dbg(f"MODE_SWITCH -> {self._mode} (enabled_tags={self.enabled_tags})")

            # Force a clean redraw:
            self.reset_scene()
            self.clear_canvas(f"mode_switch->{self._mode}")

        if DEBUG_SHOW_PANEL_PIXELS:
            # (0,0) set in present (green heartbeat)
            # (1,0) red when policy says OFF
            self.canvas.SetPixel(1, 0, 255 if should_be_off else 0, 0, 0)
            # (2,0) blue when flights active
            self.canvas.SetPixel(2, 0, 0, 0, 255 if flights_active else 0)
            self._dirty = True

        if DEBUG and (self.frame % DEBUG_EVERY_N_FRAMES == 0):
            _dbg(
                f"POLICY frame={self.frame} screen={screen_state} night={is_night_time()} "
                f"target_brightness={target_brightness} should_off={should_be_off} "
                f"paused={self.paused} eff_off={self._effective_off} "
                f"matrix.brightness={getattr(self.matrix,'brightness',None)}"
                f"has_SetBrightness={hasattr(self.matrix,'SetBrightness')} "
                f"matrix_brightness_attr={getattr(self.matrix,'brightness',None)}"
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

            # keep backbuffer blank while off
            self.clear_canvas("policy_off")

            # force matrix brightness to 0
            if self.matrix.brightness != 0:
                self._set_matrix_brightness(0)

            self._dbg_summary()
            return

        # --- ON MODE ---
        if self._effective_off:
            self._effective_off = False
            _dbg("POLICY leaving OFF: resume() + clear backbuffer")
            self.resume()

            self.clear_canvas("policy_on_resume")

            # Force scenes to redraw next time they run
            if hasattr(self, "_redraw_time"):
                self._redraw_time = True
            if hasattr(self, "_redraw_date"):
                self._redraw_date = True

        if self.matrix.brightness != target_brightness:
            self._set_matrix_brightness(target_brightness)

        self._dbg_summary()

    # -----------------------------
    # PRESENT: the ONLY SwapOnVSync
    # (runs even while paused)
    # -----------------------------
    @Animator.KeyFrame.add(1, run_while_paused=True)
    def zzzzzz_present(self, count):
        # heartbeat pixel so you always know present is running
        if DEBUG_SHOW_PANEL_PIXELS:
            self.canvas.SetPixel(0, 0, 0, 255, 0)
            self._dirty = True

        # If OFF: we *must* keep swapping occasionally to enforce blankness.
        # If ON: swap ONLY when dirty -> eliminates flicker.
        if self._effective_off:
            # swap every frame while off (safe) OR rate-limit if you prefer
            self.canvas = self.matrix.SwapOnVSync(self.canvas)
            self._dbg_swap_count += 1
            self._dirty = False
            return

        # ON mode: dirty-driven swap
        if not self._dirty:
            return

        self.canvas = self.matrix.SwapOnVSync(self.canvas)
        self._dbg_swap_count += 1
        self._dirty = False

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