from utilities.animator import Animator

class SmokeScene(object):
    def __init__(self):
        super().__init__()

    @Animator.KeyFrame.add(1, tag="smoke")
    def smoke(self, count):
        # preferred: use your Display helper that marks dirty
        if hasattr(self, "set_pixel"):
            self.set_pixel(22, 22, 255, 255, 255)
        else:
            # fallback: direct draw + mark dirty
            self.canvas.SetPixel(22, 22, 255, 255, 255)
            if hasattr(self, "mark_dirty"):
                self.mark_dirty()
            elif hasattr(self, "_dirty"):
                self._dirty = True
        return False