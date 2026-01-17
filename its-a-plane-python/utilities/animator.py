from time import sleep

DELAY_DEFAULT = 0.01


class Animator(object):
    """
    Deterministic keyframe scheduling + pause mechanism + optional tag gating.

    - Keyframes are registered in sorted name order (stable/deterministic).
    - When paused, only keyframes marked run_while_paused=True run.
    - On resume, we force a reset_scene() once.
    - Optional: tag-based enable/disable of groups of keyframes for debugging.
      * If enabled_tags is None: run everything (default).
      * If enabled_tags is a set: only keyframes whose tag is in enabled_tags run.
      * tag=None means "core" and always runs (policy/present/etc).
    """

    class KeyFrame(object):
        @staticmethod
        def add(divisor, offset=0, run_while_paused=False, tag=None, order=1):
            def wrapper(func):
                func.properties = {
                    "divisor": divisor,
                    "offset": offset,
                    "count": 0,
                    "run_while_paused": run_while_paused,
                    "tag": tag,
                    "order": order,
                }
                return func
            return wrapper

    def __init__(self):
        self.keyframes = []
        self.frame = 0
        self._delay = DELAY_DEFAULT

        self._paused = False
        self._pending_reset = True

        self.enabled_tags = None
        self._last_enabled_tags_snapshot = None

        self._register_keyframes()
        super().__init__()

    def _register_keyframes(self):
        items = []
        for methodname in dir(self):
            method = getattr(self, methodname)
            if hasattr(method, "properties"):
                items.append((methodname, method))
        items.sort(key=lambda x: (x[1].properties.get("order", 1), x[0]))
        self.keyframes = items

    def _tag_allowed(self, props) -> bool:
        """
        Returns True if this keyframe should run under current enabled_tags.
        tag=None => always allowed (core).
        """
        if self.enabled_tags is None:
            return True
        tag = props.get("tag", None)
        if tag is None:
            return True
        return tag in self.enabled_tags

    def reset_scene(self):
        # ✅ FIX: respect tag gating for divisor==0 keyframes too
        for _, keyframe in self.keyframes:
            props = keyframe.properties
            if props["divisor"] == 0 and self._tag_allowed(props):
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

    def reset_on_enable_tags_change(self):
        self._pending_reset = True

    def play(self):
        while True:
            snapshot = None if self.enabled_tags is None else tuple(sorted(self.enabled_tags))
            if snapshot != self._last_enabled_tags_snapshot:
                self._last_enabled_tags_snapshot = snapshot
                self._pending_reset = True

            if self._pending_reset:
                self.reset_scene()
                self._pending_reset = False
                for _, kf in self.keyframes:
                    kf.properties["count"] = 0

            for _, keyframe in self.keyframes:
                props = keyframe.properties

                if not self._tag_allowed(props):
                    continue

                if self._paused and not props.get("run_while_paused", False):
                    continue

                if props["divisor"] == 0:
                    continue

                d = props["divisor"]
                o = props["offset"]
                force_run = bool(getattr(self, "_force_run_keyframes", False))

                should_run = d and ((self.frame - o) % d == 0)
                if should_run or force_run:
                    if keyframe(props["count"]):
                        props["count"] = 0
                    else:
                        if should_run:
                            props["count"] += 1

            self.frame += 1
            if getattr(self, "_force_run_keyframes", False):
                self._force_run_keyframes = False
            sleep(self._delay)

    @property
    def delay(self):
        return self._delay

    @delay.setter
    def delay(self, value):
        self._delay = value
