from utilities.animator import Animator

class SmokeScene(object):
    @Animator.KeyFrame.add(1, tag="smoke")
    def smoke(self, count):
        # diagonal moving white pixel
        x = count % 64
        y = count % 32
        self.canvas.SetPixel(x, y, 255, 255, 255)
        return False