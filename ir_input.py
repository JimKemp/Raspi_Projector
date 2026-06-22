"""
IR remote input for a VS838 receiver on a GPIO pin.

Runs a background thread that waits efficiently for IR activity (via edge
detection, so it isn't busy-spinning a CPU core when idle), decodes NEC
frames, maps the code to a semantic action via config.IR_KEYMAP, and pushes
the action onto a thread-safe queue. The UI drains that queue each frame.

If RPi.GPIO isn't available (e.g. testing on a laptop), start() returns False
and the queue simply stays empty -- main.py's keyboard fallback covers that.
"""

import queue
import threading
import time

try:
    import RPi.GPIO as GPIO
    _HAS_GPIO = True
except (ImportError, RuntimeError):
    _HAS_GPIO = False

# NEC protocol timing in microseconds, with generous tolerance for cheap
# remotes and non-realtime Python timing.
_LEADER_PULSE = 9000
_LEADER_SPACE = 4500
_BIT_PULSE = 562
_ZERO_SPACE = 562
_ONE_SPACE = 1687
_TOL = 0.35
_FRAME_TIMEOUT_US = 120_000   # give up on a frame after this long
_IDLE_GAP_US = 10_000         # line idle this long = end of frame


def _within(value, target, tol=_TOL):
    return abs(value - target) <= target * tol


def _decode_nec(edges):
    """Decode a list of (level, duration_us) edges as NEC -> 32-bit int, or None."""
    if len(edges) < 4:
        return None
    if not (edges[0][0] == 0 and _within(edges[0][1], _LEADER_PULSE)):
        return None
    if not (edges[1][0] == 1 and _within(edges[1][1], _LEADER_SPACE)):
        return None

    bits = []
    i = 2
    while i + 1 < len(edges) and len(bits) < 32:
        p_level, p_dur = edges[i]
        s_level, s_dur = edges[i + 1]
        if p_level != 0 or s_level != 1 or not _within(p_dur, _BIT_PULSE):
            break
        if _within(s_dur, _ONE_SPACE):
            bits.append(1)
        elif _within(s_dur, _ZERO_SPACE):
            bits.append(0)
        else:
            break
        i += 2

    if len(bits) < 32:
        return None
    value = 0
    for b in bits[:32]:
        value = (value << 1) | b
    return value


class IRRemote:
    def __init__(self, pin, keymap, repeat_suppress_s):
        self.pin = pin
        self.keymap = keymap
        self.repeat_suppress_s = repeat_suppress_s
        self.events = queue.Queue()
        self._stop = threading.Event()
        self._thread = None
        self._last_action = None
        self._last_time = 0.0

    def start(self):
        if not _HAS_GPIO:
            return False
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.pin, GPIO.IN)
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return True

    def _capture_frame(self):
        """
        Called just after a falling edge: the line is LOW (start of the NEC
        leader). Record level-change durations until the line goes idle.
        Returns a list of (level, duration_us).
        """
        edges = []
        last_change = time.monotonic()
        frame_start = last_change
        last_level = 0
        while True:
            now = time.monotonic()
            level = GPIO.input(self.pin)
            if level != last_level:
                dur_us = (now - last_change) * 1_000_000
                edges.append((last_level, dur_us))
                last_change = now
                last_level = level
            elif level == 1 and (now - last_change) * 1_000_000 > _IDLE_GAP_US:
                break
            if (now - frame_start) * 1_000_000 > _FRAME_TIMEOUT_US:
                break
        return edges

    def _run(self):
        while not self._stop.is_set():
            # Block (efficiently) until the line drops, i.e. a frame begins.
            channel = GPIO.wait_for_edge(self.pin, GPIO.FALLING, timeout=200)
            if channel is None:
                continue
            edges = self._capture_frame()
            code = _decode_nec(edges)
            if code is None:
                # NEC repeat frame or noise -- ignore (holding a button won't spam).
                continue
            action = self.keymap.get(code)
            if action is None:
                continue
            now = time.monotonic()
            if action == self._last_action and (now - self._last_time) < self.repeat_suppress_s:
                self._last_time = now
                continue
            self._last_action = action
            self._last_time = now
            self.events.put(action)

    def drain(self):
        """Return all actions queued since the last call (oldest first)."""
        actions = []
        while True:
            try:
                actions.append(self.events.get_nowait())
            except queue.Empty:
                break
        return actions

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=1)
        if _HAS_GPIO:
            try:
                GPIO.cleanup(self.pin)
            except Exception:
                pass
