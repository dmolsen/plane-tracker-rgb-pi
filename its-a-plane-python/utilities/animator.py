from time import sleep

DELAY_DEFAULT = 0.01


class Animator(object):
    """
    Animator with a real pause mechanism.

    - When paused, ONLY keyframes declared with run_while_paused=True will run.
    - When resuming, we force a scene reset (divisor==0 keyframes) exactly once,
      and we reset per-keyframe counters so animations don’t jump.

    This is the clean foundation for "screen off" without every scene needing
    to do brightness checks.
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
        self.keyframes = []
        self.frame = 0
        self._delay = DELAY_DEFAULT

        self._paused = False
        self._pending_reset = True  # run divisor==0 keyframes on first loop (and after resume)

        self._register_keyframes()
        super().__init__()

    def _register_keyframes(self):
        # Some introspection to setup keyframes
        for methodname in dir(self):
            method = getattr(self, methodname)
            if hasattr(method, "properties"):
                self.keyframes.append(method)

    def reset_scene(self):
        # Run only divisor==0 frames (scene reset hooks)
        for keyframe in self.keyframes:
            if keyframe.properties["divisor"] == 0:
                keyframe()

    def pause(self):
        self._paused = True

    def resume(self):
        # Resume should force a clean redraw on next loop.
        if self._paused:
            self._paused = False
            self._pending_reset = True

    def set_paused(self, value: bool):
        if value:
            self.pause()
        else:
            self.resume()

    @property
    def paused(self) -> bool:
        return self._paused

    def play(self):
        while True:
            # If we need to reset (first loop or resume), do it once.
            if self._pending_reset:
                self.reset_scene()
                self._pending_reset = False

                # Reset per-keyframe counters so animations don’t jump on resume.
                for kf in self.keyframes:
                    kf.properties["count"] = 0

            for keyframe in self.keyframes:
                props = keyframe.properties

                # If paused, only run keyframes explicitly allowed.
                if self._paused and not props.get("run_while_paused", False):
                    continue

                # divisor==0 keyframes are handled by reset_scene()
                if props["divisor"] == 0:
                    continue

                # Normal schedule
                if (
                    props["divisor"]
                    and not ((self.frame - props["offset"]) % props["divisor"])
                ):
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