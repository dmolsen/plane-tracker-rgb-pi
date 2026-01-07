from utilities.animator import Animator
from setup import colours

# Setup
BLINKER_POSITION = (63, 0)
BLINKER_STEPS = 10
BLINKER_COLOUR = colours.GREY


class LoadingPulseScene(object):
    def __init__(self):
        super().__init__()

    def _clear_pixel(self):
        self.canvas.SetPixel(BLINKER_POSITION[0], BLINKER_POSITION[1], 0, 0, 0)

    @Animator.KeyFrame.add(0, "defaultPulse")
    def reset_loading_pulse(self):
        """
        Called on reset_scene() (startup, resume-from-off, flight index change).
        Ensures the pulse pixel isn't left in a half-lit state.
        """
        self._clear_pixel()

    @Animator.KeyFrame.add(2, "defaultPulse")  # run_while_paused stays False by default (important)
    def loading_pulse(self, count):
        # If overhead is missing for any reason, just keep it cleared.
        if not hasattr(self, "overhead"):
            self._clear_pixel()
            return True

        # If not processing, keep cleared
        if not self.overhead.processing:
            self._clear_pixel()
            return True

        # Calculate brightness scaler
        brightness = (1 - (count / BLINKER_STEPS)) / 2
        if brightness < 0 or brightness > 1:
            brightness = 0

        self.canvas.SetPixel(
            BLINKER_POSITION[0],
            BLINKER_POSITION[1],
            int(brightness * BLINKER_COLOUR.red),
            int(brightness * BLINKER_COLOUR.green),
            int(brightness * BLINKER_COLOUR.blue),
        )

        # Only count 0 -> (BLINKER_STEPS - 1)
        return count == (BLINKER_STEPS - 1)