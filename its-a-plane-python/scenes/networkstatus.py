# scenes/networkstatus.py
import os

from PIL import Image

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
        # Match logo/icon behavior: load from ./icons relative to CWD, with fallbacks.
        self._qr_paths = [
            os.path.join("icons", "network_qr.png"),
            os.path.expanduser(os.path.join("~", "icons", "network_qr.png")),
            os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "icons", "network_qr.png")),
            os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "icons", "network_qr.png")),
        ]
        self._qr_img = None
        self._load_qr()

    def _load_qr(self):
        for path in self._qr_paths:
            try:
                img = Image.open(path).convert("RGBA")
                if img.size != (32, 32):
                    img = img.resize((32, 32), Image.NEAREST)
                # Composite on white to avoid black-on-black with transparency.
                bg = Image.new("RGB", img.size, (255, 255, 255))
                bg.paste(img, mask=img.split()[3])
                self._qr_img = bg
                return
            except Exception:
                continue
        self._qr_img = None

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

        if self._qr_img is not None:
            self.set_image(self._qr_img, 0, 0)
        else:
            # If no QR, draw the icon on the left as a fallback.
            self._draw_icon(11, 11, colour)

        # Right half layout (x=32..63).
        text_width = len(msg) * 4
        text_x = 32 + max(0, (32 - text_width) // 2)
        text_y = 18

        icon_x = 32 + (32 - 9) // 2
        icon_y = 6
        self._draw_icon(icon_x, icon_y, colour)

        self.draw_text(fonts.extrasmall, text_x, text_y, colour, msg)
