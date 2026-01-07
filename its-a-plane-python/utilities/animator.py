from time import sleep

DELAY_DEFAULT = 0.01


class Animator(object):
    """
    Deterministic keyframe scheduling + pause mechanism.

    - Keyframes are registered in sorted name order (stable/deterministic).
    - When paused, only keyframes marked run_while_paused=True run.
    - On resume, we force a reset_scene() once.
    """

    class KeyFrame(object):
        @staticmethod
        def add(divisor, offset=0, run_while_paused=False):
            def wrapper(func):
                func.properties = {
                    "divisor": divisor,
                    "offset": offset,
                    "count": 0,
                    "run_while_paused": run_while_paused,
                }
                return func
            return wrapper

    def __init__(self):
        self.keyframes = []  # list of (name, bound_method)
        self.frame = 0
        self._delay = DELAY_DEFAULT

        self._paused = False
        self._pending_reset = True  # do divisor==0 once on first loop and on resume

        self._register_keyframes()
        super().__init__()

    def _register_keyframes(self):
        # Register in deterministic order so "present" can be reliably last.
        items = []
        for methodname in dir(self):
            method = getattr(self, methodname)
            if hasattr(method, "properties"):
                items.append((methodname, method))
        items.sort(key=lambda x: x[0])
        self.keyframes = items

    def reset_scene(self):
        for _, keyframe in self.keyframes:
            if keyframe.properties["divisor"] == 0:
                keyframe()

    def pause(self):
        self._paused = True

    def resume(self):
        if self._paused:
            self._paused = False
            self._pending_reset = True

    def set_paused(self, value: bool):
        self.pause() if value else self.resume()

    @property
    def paused(self) -> bool:
        return self._paused

    def play(self):
        while True:
            if self._pending_reset:
                self.reset_scene()
                self._pending_reset = False
                # reset counts so animations don't jump
                for _, kf in self.keyframes:
                    kf.properties["count"] = 0

            for _, keyframe in self.keyframes:
                props = keyframe.properties

                if self._paused and not props.get("run_while_paused", False):
                    continue

                # divisor==0 are only run via reset_scene()
                if props["divisor"] == 0:
                    continue

                d = props["divisor"]
                o = props["offset"]

                if d and ((self.frame - o) % d == 0):
                    if keyframe(props["count"]):
                        props["count"] = 0
                    else:
                        props["count"] += 1

            self.frame += 1
            sleep(self._delay)

    @property
    def delay(self):
        return self._delay

    @delay.setter
    def delay(self, value):
        self._delay = value