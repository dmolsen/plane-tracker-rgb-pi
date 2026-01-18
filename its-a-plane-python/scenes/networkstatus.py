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
        # Fallback: 9x9 Wi-Fi icon with a diagonal slash.
        pixels = [
            (1, 0), (2, 0), (3, 0), (4, 0), (5, 0), (6, 0), (7, 0),
            (0, 1), (8, 1),
            (0, 2), (8, 2),
            (2, 3), (3, 3), (4, 3), (5, 3), (6, 3),
            (2, 4), (6, 4),
            (3, 5), (4, 5), (5, 5),
            (4, 7),
            (1, 5), (2, 4), (3, 3), (4, 2), (5, 1), (6, 0), (7, -1), (8, -2),
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

        # Centered icon + text layout.
        icon_x = max(0, (screen.WIDTH - 9) // 2)
        icon_y = 6
        self._draw_icon(icon_x, icon_y, colour)

        text_width = len(msg) * 4
        text_x = max(0, (screen.WIDTH - text_width) // 2)
        text_y = 18
        self.draw_text(fonts.extrasmall, text_x, text_y, colour, msg)
