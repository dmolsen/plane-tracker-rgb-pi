# scenes/networkstatus.py
from utilities.animator import Animator
from utilities.network_status import NetStatus
from setup import colours, fonts, screen


STATUS_MESSAGES = {
    NetStatus.NO_SSID: "NO SSID",
    NetStatus.NO_WIFI: "NO WIFI",
    NetStatus.NO_NET: "NO NET",
    NetStatus.API_DOWN: "API DOWN",
}


class NetworkStatusScene(object):
    def __init__(self):
        super().__init__()

    def _draw_icon(self, x, y, colour):
        # 9x9 Wi-Fi icon with a diagonal slash.
        pixels = [
            # outer arc
            (1, 0), (2, 0), (3, 0), (4, 0), (5, 0), (6, 0), (7, 0),
            (0, 1), (8, 1),
            (0, 2), (8, 2),
            # middle arc
            (2, 3), (3, 3), (4, 3), (5, 3), (6, 3),
            (2, 4), (6, 4),
            # inner arc
            (3, 5), (4, 5), (5, 5),
            # dot
            (4, 7),
            # slash
            (1, 8), (2, 7), (3, 6), (4, 5), (5, 4), (6, 3), (7, 2), (8, 1),
        ]
        for dx, dy in pixels:
            self.set_pixel(x + dx, y + dy, colour.red, colour.green, colour.blue)

    @Animator.KeyFrame.add(1, tag="net_status")
    def network_status(self, count):
        status = getattr(self, "_net_status", NetStatus.OK)
        if status == NetStatus.OK:
            return

        self.draw_square(0, 0, screen.WIDTH, screen.HEIGHT, colours.BLACK)

        msg = STATUS_MESSAGES.get(status, "NET ERROR")
        colour = colours.RED

        # Center text roughly (extrasmall font width ~4).
        text_width = len(msg) * 4
        text_x = max(0, (screen.WIDTH - text_width) // 2)
        text_y = 20

        icon_x = max(0, (screen.WIDTH - 9) // 2)
        icon_y = 6
        self._draw_icon(icon_x, icon_y, colour)

        self.draw_text(fonts.extrasmall, text_x, text_y, colour, msg)
