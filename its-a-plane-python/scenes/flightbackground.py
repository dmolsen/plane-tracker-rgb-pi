# scenes/flightbackground.py
from utilities.animator import Animator
from setup import colours, screen


class FlightBackgroundScene(object):
    def __init__(self):
        super().__init__()

    @Animator.KeyFrame.add(1, tag="flight_bg", order=0)
    def flight_background(self, count):
        # Full-screen black background for flight mode.
        self.draw_square(0, 0, screen.WIDTH, screen.HEIGHT, colours.BLACK)
        # Signal other flight scenes to redraw this frame.
        self._redraw_all_this_frame = True
