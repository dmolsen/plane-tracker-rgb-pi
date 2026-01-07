from utilities.animator import Animator

class SmokeScene(object):
    def __init__(self):
        super().__init__()
        self._last = None

    @Animator.KeyFrame.add(1,tag="smoke")
    def smoke(self, count):
        # erase previous pixel
        if self._last is not None:
            lx, ly = self._last
            self.canvas.SetPixel(lx, ly, 0, 0, 0)

        # draw new pixel
        x = count % 64
        y = count % 32
        self.canvas.SetPixel(x, y, 255, 255, 255)

        self._last = (x, y)
        return False