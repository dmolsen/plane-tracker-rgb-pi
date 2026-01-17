# scenes/flightbackground.py
from utilities.animator import Animator
from setup import colours, screen


class FlightBackgroundScene(object):
    def __init__(self):
        super().__init__()

    @Animator.KeyFrame.add(1, tag="flight_bg")
    def flight_background(self, count):
        # Full-screen black background for flight mode.
        self.draw_square(0, 0, screen.WIDTH, screen.HEIGHT, colours.BLACK)
