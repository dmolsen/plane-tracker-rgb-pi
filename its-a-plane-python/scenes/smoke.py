from utilities.animator import Animator

class SmokeScene(object):
    def __init__(self):
        super().__init__()
        self._last = None

    @Animator.KeyFrame.add(1,tag="smoke")
    def smoke(self, count):
        self.canvas.SetPixel(22, 22, 255, 255, 255)
        return False